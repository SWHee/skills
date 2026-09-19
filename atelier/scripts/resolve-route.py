#!/usr/bin/env python3
"""Validate Atelier options without invoking a model or changing files."""
import argparse
import json
import re
from pathlib import Path

ROLES = ("architect", "implementer", "verifier", "reviewer", "repairer")
DEFAULTS = dict(mode="auto", phase="run", architect="parent", implementer="auto",
                verifier="parent", reviewer="auto", repairer="implementer",
                max_calls=6, max_repairs=2, timeout=600)
CODEX = {"astra", "sol", "terra", "luna"}
CLAUDE = {"haiku", "sonnet", "opus", "fable"}
EFFORTS = {"low", "medium", "high", "xhigh", "max", "ultra", "minimal", "none"}


def selection(value, role):
    if not isinstance(value, str) or not value:
        raise ValueError(f"{role}: expected a nonempty model selection")
    if value in {"auto", "parent"}:
        return {"source": value}
    if value == "implementer" and role == "repairer":
        return {"source": "implementer"}
    if value == "off" and role == "reviewer":
        return {"source": "off"}
    model, sep, effort = value.rpartition("/")
    if not sep:
        model, effort = value, None
    elif effort not in EFFORTS:
        raise ValueError(f"{role}: unknown effort {effort!r}")
    provider, colon, name = model.partition(":")
    if not colon:
        name = model
        if name in CODEX or name.startswith("gpt-"):
            provider = "codex"
        elif name in CLAUDE or name.startswith("claude-"):
            provider = "claude"
        else:
            raise ValueError(f"{role}: use codex:MODEL or claude:MODEL for unknown aliases")
    if provider not in {"codex", "claude"} or not name or name.startswith("-"):
        raise ValueError(f"{role}: invalid provider/model")
    if not re.fullmatch(r"[A-Za-z0-9._@-]+", name):
        raise ValueError(f"{role}: invalid model name")
    if provider == "claude" and effort in {"minimal", "none", "ultra"}:
        raise ValueError(f"{role}: effort {effort!r} is not supported by the Claude adapter")
    return {"source": "model", "provider": provider, "model": name, "effort": effort}


def resolve(config, overrides):
    if not isinstance(config, dict):
        raise ValueError("config must be a JSON object")
    unknown = config.keys() - DEFAULTS.keys()
    if unknown:
        raise ValueError(f"unknown config keys: {', '.join(sorted(unknown))}")
    values = DEFAULTS | config | {k: v for k, v in overrides.items() if v is not None}
    for key, choices in {"mode": {"auto", "solo", "delegate", "cross"},
                         "phase": {"plan", "run", "review"}}.items():
        if not isinstance(values[key], str) or values[key] not in choices:
            raise ValueError(f"invalid {key}: {values[key]!r}")
    for key, upper in {"max_calls": 50, "max_repairs": 10, "timeout": 86400}.items():
        low = 0 if key == "max_repairs" else 1
        if type(values[key]) is not int or not low <= values[key] <= upper:
            raise ValueError(f"{key} must be an integer from {low} to {upper}")
    roles = {role: selection(values[role], role) for role in ROLES}
    active = {"plan": ("architect",), "review": ("verifier", "reviewer"),
              "run": ROLES}[values["phase"]]
    if values["mode"] == "solo" and any(roles[r]["source"] == "model" for r in active):
        raise ValueError("solo conflicts with explicit delegated model selections; use parent or auto")
    if values["mode"] == "cross" and roles["reviewer"]["source"] == "off":
        raise ValueError("cross requires independent review; reviewer cannot be off")
    return {"mode": values["mode"], "phase": values["phase"], "roles": roles,
            "active_roles": list(active),
            "limits": {k: values[k] for k in ("max_calls", "max_repairs", "timeout")},
            "status": "requested", "availability_checked": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--config", type=Path, help="Explicit JSON config; otherwise use workdir/.atelier.json if present")
    parser.add_argument("--workdir", type=Path, default=Path.cwd())
    parser.add_argument("--dry-run", action="store_true", help="Preview only; this resolver never invokes models")
    for key in DEFAULTS:
        flags = ["--" + key.replace("_", "-")]
        if key == "architect":
            flags.append("--planner")
        parser.add_argument(*flags, type=int if isinstance(DEFAULTS[key], int) else str)
    args = vars(parser.parse_args())
    explicit = args.pop("config")
    workdir = args.pop("workdir")
    dry_run = args.pop("dry_run")
    if not workdir.is_dir():
        parser.error(f"workdir is not a directory: {workdir}")
    path = explicit if explicit is not None else workdir / ".atelier.json"
    try:
        config = json.loads(path.read_text()) if explicit is not None or path.exists() else {}
        result = resolve(config, args)
        result["dry_run"] = dry_run
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
