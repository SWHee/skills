#!/usr/bin/env python3
"""Run and validate the small JSON boundary used by claude-lane.sh."""

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path


def command_tail(values):
    if values and values[0] == "--":
        values = values[1:]
    if not values:
        raise ValueError("missing subprocess command")
    return values


def terminate_process_group(process):
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=0.1)
    except subprocess.TimeoutExpired:
        pass
    deadline = time.monotonic() + 1
    while time.monotonic() < deadline:
        try:
            os.killpg(process.pid, 0)
        except (ProcessLookupError, PermissionError):
            break
        time.sleep(0.05)
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
    try:
        process.wait(timeout=1)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def run_process(command, timeout, *, cwd=None, stdin_bytes=None, stdout=None):
    process = subprocess.Popen(
        command,
        cwd=cwd,
        stdin=subprocess.PIPE if stdin_bytes is not None else subprocess.DEVNULL,
        stdout=stdout or subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    previous_handlers = {}

    def interrupted(signum, _frame):
        terminate_process_group(process)
        raise SystemExit(128 + signum)

    for signum in (signal.SIGHUP, signal.SIGINT, signal.SIGTERM):
        previous_handlers[signum] = signal.signal(signum, interrupted)
    try:
        try:
            output, errors = process.communicate(input=stdin_bytes, timeout=timeout)
        except subprocess.TimeoutExpired:
            terminate_process_group(process)
            print(f"Claude subprocess timed out after {timeout} seconds", file=sys.stderr)
            return 124, b"", b""
    finally:
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)
    return process.returncode, output or b"", errors or b""


def load_object(path):
    try:
        with Path(path).open(encoding="utf-8") as stream:
            value = json.load(stream)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("JSON value must be an object")
    return value


def canonical_models(result):
    usage = result.get("modelUsage")
    if not isinstance(usage, dict) or not usage:
        raise ValueError("result did not identify model usage")
    models = []
    for key, details in usage.items():
        if not isinstance(key, str) or not key:
            raise ValueError("modelUsage contains an invalid model key")
        if not isinstance(details, dict):
            raise ValueError(f"modelUsage entry for {key!r} is not an object")
        if "canonicalModel" in details:
            model = details["canonicalModel"]
            if not isinstance(model, str) or not model:
                raise ValueError(f"modelUsage entry for {key!r} has an invalid canonicalModel")
        else:
            model = key
        models.append(model)
    return models


def model_matches(requested, expected, actual):
    if expected is not None:
        return actual == expected
    if requested in {"haiku", "sonnet", "opus", "fable"}:
        pattern = rf"(^|[^a-z0-9]){re.escape(requested)}([^a-z0-9]|$)"
        return re.search(pattern, actual.lower()) is not None
    return actual == requested


def validate_result(path, requested, expected):
    result = load_object(path)
    if result.get("type") != "result":
        raise ValueError("top-level type is not result")
    if result.get("is_error") is not False:
        raise ValueError("result did not report a successful invocation")
    if "subtype" in result and result["subtype"] != "success":
        raise ValueError(f"result subtype is not success: {result['subtype']!r}")
    text = result.get("result")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("result text is empty")

    models = canonical_models(result)
    mismatches = [model for model in models if not model_matches(requested, expected, model)]
    if mismatches:
        wanted = expected if expected is not None else requested
        raise ValueError(f"requested model {wanted!r} was not used; result reported {models!r}")


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="action", required=True)
    auth = subparsers.add_parser("auth")
    auth.add_argument("--timeout", type=int, required=True)
    auth.add_argument("command", nargs=argparse.REMAINDER)
    invoke = subparsers.add_parser("invoke")
    invoke.add_argument("--timeout", type=int, required=True)
    invoke.add_argument("--cwd", required=True)
    invoke.add_argument("--input", required=True)
    invoke.add_argument("--output", required=True)
    invoke.add_argument("command", nargs=argparse.REMAINDER)
    validate = subparsers.add_parser("validate")
    validate.add_argument("--model", required=True)
    validate.add_argument("--expected-model")
    validate.add_argument("path")
    args = parser.parse_args()

    try:
        if args.action == "auth":
            status, output, _errors = run_process(command_tail(args.command), args.timeout)
            if status != 0:
                raise ValueError(f"authentication check failed (exit status {status})")
            try:
                auth_result = json.loads(output)
            except (UnicodeError, json.JSONDecodeError) as exc:
                raise ValueError(f"authentication check returned invalid JSON: {exc}") from exc
            if not isinstance(auth_result, dict) or auth_result.get("loggedIn") is not True:
                raise ValueError("Claude Code CLI is not authenticated; run 'claude auth login' in this environment")
        elif args.action == "invoke":
            prompt = Path(args.input).read_bytes()
            with Path(args.output).open("wb") as output:
                status, _unused, errors = run_process(
                    command_tail(args.command), args.timeout, cwd=args.cwd,
                    stdin_bytes=prompt, stdout=output
                )
            if errors:
                sys.stderr.buffer.write(errors)
            if status != 0:
                return status
        else:
            validate_result(args.path, args.model, args.expected_model)
    except (OSError, ValueError) as exc:
        print(f"claude-result.py: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
