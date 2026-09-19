#!/usr/bin/env python3
"""Read-only structural and fingerprint checks for an Agon readiness gate."""

import hashlib
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


CORE_TOPICS = {
    "eligibility", "team", "work_window", "reuse", "ai_usage",
    "required_tech", "data_rights", "ip_licensing", "submission",
    "judging", "demo_environment",
}
MAX_FILE_BYTES = 10 * 1024 * 1024
SCOPE = "Local consistency and recorded-review check only; it does not verify online rule freshness or semantic understanding."
HEX256 = re.compile(r"^[0-9a-f]{64}$")
TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T.+(?:Z|[+-]\d{2}:\d{2})$")


class GateError(Exception):
    pass


def fail(message):
    raise GateError(message)


def reject_constant(value):
    fail("JSON numbers must be finite")


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            fail("duplicate JSON key: " + key)
        result[key] = value
    return result


def load_json(path):
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        fail("cannot read gate: " + str(exc))
    try:
        return json.loads(text, object_pairs_hook=unique_object, parse_constant=reject_constant)
    except GateError:
        raise
    except (json.JSONDecodeError, UnicodeError) as exc:
        fail("invalid JSON: " + str(exc))


def exact_object(value, name, fields):
    if not isinstance(value, dict):
        fail(name + " must be an object")
    missing = set(fields) - set(value)
    extra = set(value) - set(fields)
    if missing:
        fail(name + " missing field(s): " + ", ".join(sorted(missing)))
    if extra:
        fail(name + " has unknown field(s): " + ", ".join(sorted(extra)))


def nonempty(value, name):
    if not isinstance(value, str) or not value.strip():
        fail(name + " must be a nonempty string")
    return value


def text(value, name):
    if not isinstance(value, str):
        fail(name + " must be a string")
    return value


def timestamp(value, name, allow_blank=False):
    if allow_blank and value == "":
        return None
    nonempty(value, name)
    if not TIMESTAMP.match(value):
        fail(name + " must be ISO 8601 with an explicit timezone")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        fail(name + " is not a valid timestamp")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        fail(name + " must include a timezone")
    return parsed


def number(value, name, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        fail(name + " must be a finite number")
    if (positive and value <= 0) or (not positive and value < 0):
        fail(name + (" must be greater than zero" if positive else " must be nonnegative"))
    return value


def safe_file(base, value, name):
    relative = Path(nonempty(value, name))
    if relative.is_absolute() or ".." in relative.parts:
        fail(name + " must stay inside the gate directory")
    try:
        base_resolved = base.resolve(strict=True)
        resolved = (base / relative).resolve(strict=True)
        resolved.relative_to(base_resolved)
    except (OSError, RuntimeError, ValueError):
        fail(name + " is missing or escapes the gate directory")
    if not resolved.is_file():
        fail(name + " must reference a regular file")
    try:
        size = resolved.stat().st_size
        if size == 0:
            fail(name + " must reference a nonempty file")
        if size > MAX_FILE_BYTES:
            fail(name + " exceeds the 10 MiB local validation limit")
    except OSError as exc:
        fail(name + " cannot be inspected: " + str(exc))
    return relative.as_posix(), resolved


def validate(data, gate_path):
    top = {"schema_version", "event", "sources", "rules", "rubric", "artifacts", "budget", "review"}
    exact_object(data, "gate", top)
    if isinstance(data["schema_version"], bool) or data["schema_version"] != 1:
        fail("schema_version must be 1")

    event = data["event"]
    exact_object(event, "event", {"name", "track", "award", "coding_start", "deadline"})
    for key in ("name", "track", "award"):
        nonempty(event[key], "event." + key)
    coding_start = timestamp(event["coding_start"], "event.coding_start")
    deadline = timestamp(event["deadline"], "event.deadline")
    if coding_start >= deadline:
        fail("event.coding_start must be before event.deadline")

    sources = data["sources"]
    if not isinstance(sources, list) or not sources:
        fail("sources must be a nonempty list")
    source_ids = set()
    official_source_ids = set()
    source_times = []
    files = {}
    official = False
    for index, source in enumerate(sources):
        label = "sources[{}]".format(index)
        exact_object(source, label, {"id", "uri", "retrieved_at", "authority", "snapshot"})
        source_id = nonempty(source["id"], label + ".id")
        if source_id in source_ids:
            fail("duplicate source id: " + source_id)
        source_ids.add(source_id)
        nonempty(source["uri"], label + ".uri")
        source_times.append(timestamp(source["retrieved_at"], label + ".retrieved_at"))
        if source["authority"] not in ("official", "supporting"):
            fail(label + ".authority must be official or supporting")
        official = official or source["authority"] == "official"
        if source["authority"] == "official":
            official_source_ids.add(source_id)
        relative, resolved = safe_file(gate_path.parent, source["snapshot"], label + ".snapshot")
        files[relative] = resolved
    if not official:
        fail("at least one official source is required")

    rules = data["rules"]
    if not isinstance(rules, list):
        fail("rules must be a list")
    rule_ids, covered = set(), set()
    for index, rule in enumerate(rules):
        label = "rules[{}]".format(index)
        exact_object(rule, label, {"id", "topic", "status", "source_ids", "locator", "resolution"})
        rule_id = nonempty(rule["id"], label + ".id")
        if rule_id in rule_ids:
            fail("duplicate rule id: " + rule_id)
        rule_ids.add(rule_id)
        topic = nonempty(rule["topic"], label + ".topic")
        covered.add(topic)
        if rule["status"] not in ("resolved", "unknown", "conflict", "violated", "not_applicable"):
            fail(label + ".status is invalid")
        refs = rule["source_ids"]
        if not isinstance(refs, list) or any(not isinstance(item, str) or not item for item in refs):
            fail(label + ".source_ids must be a list of nonempty strings")
        if len(refs) != len(set(refs)):
            fail(label + ".source_ids contains duplicates")
        missing_refs = set(refs) - source_ids
        if missing_refs:
            fail(label + " references unknown source(s): " + ", ".join(sorted(missing_refs)))
        text(rule["locator"], label + ".locator")
        text(rule["resolution"], label + ".resolution")
        if rule["status"] in ("resolved", "not_applicable"):
            if not refs:
                fail(label + " requires a source reference")
            nonempty(rule["locator"], label + ".locator")
            nonempty(rule["resolution"], label + ".resolution")
    missing_topics = CORE_TOPICS - covered
    if missing_topics:
        fail("rules missing core topic(s): " + ", ".join(sorted(missing_topics)))

    rubric = data["rubric"]
    exact_object(rubric, "rubric", {"award", "weighting", "criteria"})
    if nonempty(rubric["award"], "rubric.award") != event["award"]:
        fail("rubric.award must match event.award")
    if rubric["weighting"] not in ("published", "unpublished"):
        fail("rubric.weighting must be published or unpublished")
    criteria = rubric["criteria"]
    if not isinstance(criteria, list) or not criteria:
        fail("rubric.criteria must be a nonempty list")
    criterion_ids, weights = set(), []
    for index, criterion in enumerate(criteria):
        label = "rubric.criteria[{}]".format(index)
        exact_object(criterion, label, {"id", "name", "source_id", "locator", "weight", "feature", "proof"})
        criterion_id = nonempty(criterion["id"], label + ".id")
        if criterion_id in criterion_ids:
            fail("duplicate criterion id: " + criterion_id)
        criterion_ids.add(criterion_id)
        for key in ("name", "source_id", "locator", "feature", "proof"):
            nonempty(criterion[key], label + "." + key)
        if criterion["source_id"] not in source_ids:
            fail(label + ".source_id references an unknown source")
        if criterion["source_id"] not in official_source_ids:
            fail(label + ".source_id must reference an official source")
        weight = criterion["weight"]
        if rubric["weighting"] == "unpublished":
            if weight is not None:
                fail("unpublished rubric weights must be null")
        else:
            weight = number(weight, label + ".weight")
            if weight > 100:
                fail(label + ".weight must be at most 100")
            weights.append(weight)
    if weights and (sum(weights) <= 0 or not math.isclose(sum(weights), 100.0, abs_tol=1e-6)):
        fail("published rubric weights must sum to 100")

    artifacts = data["artifacts"]
    exact_object(artifacts, "artifacts", {"brief"})
    relative, resolved = safe_file(gate_path.parent, artifacts["brief"], "artifacts.brief")
    files[relative] = resolved

    budget = data["budget"]
    exact_object(budget, "budget", {"implementation_minutes", "verification_minutes", "submission_minutes"})
    for key in ("implementation_minutes", "verification_minutes", "submission_minutes"):
        number(budget[key], "budget." + key, positive=True)
    if not math.isfinite(sum(budget.values())):
        fail("budget total must be finite")

    review = data["review"]
    exact_object(review, "review", {"verdict", "reviewer", "reviewed_at", "fingerprint", "rationale"})
    if review["verdict"] not in ("pending", "ready", "blocked"):
        fail("review.verdict is invalid")
    for key in ("reviewer", "reviewed_at", "fingerprint", "rationale"):
        text(review[key], "review." + key)
    reviewed_at = timestamp(review["reviewed_at"], "review.reviewed_at", allow_blank=True)
    if review["fingerprint"] and not HEX256.match(review["fingerprint"]):
        fail("review.fingerprint must be a lowercase SHA-256 digest")
    if review["verdict"] == "ready":
        for key in ("reviewer", "reviewed_at", "rationale"):
            nonempty(review[key], "review." + key)
        nonempty(review["fingerprint"], "review.fingerprint")
    return {
        "coding_start": coding_start,
        "deadline": deadline,
        "source_times": source_times,
        "reviewed_at": reviewed_at,
        "files": files,
    }


def fingerprint(data, files):
    manifest = {key: value for key, value in data.items() if key != "review"}
    file_hashes = {}
    for relative, path in sorted(files.items()):
        try:
            file_hashes[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as exc:
            fail("cannot hash referenced file: " + str(exc))
    payload = {"manifest": manifest, "files": file_hashes}
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def emit(payload, code):
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return code


def parse_now(value):
    return timestamp(value, "--now") if value is not None else datetime.now(timezone.utc)


def main(argv):
    try:
        if len(argv) < 2 or argv[0] not in ("fingerprint", "check"):
            fail("usage: gate.py fingerprint <gate.json> | gate.py check <gate.json> [--now ISO8601]")
        command, gate_arg = argv[0], argv[1]
        now_arg = None
        rest = argv[2:]
        if command == "fingerprint":
            if rest:
                fail("fingerprint accepts only <gate.json>")
        elif rest:
            if len(rest) != 2 or rest[0] != "--now":
                fail("check accepts only optional --now ISO8601")
            now_arg = rest[1]
        gate_path = Path(gate_arg)
        data = load_json(gate_path)
        state = validate(data, gate_path)
        digest = fingerprint(data, state["files"])
        if command == "fingerprint":
            return emit({"status": "fingerprinted", "fingerprint": digest, "scope": SCOPE}, 0)

        now = parse_now(now_arg)
        blockers = []
        for rule in data["rules"]:
            if rule["status"] in ("unknown", "conflict", "violated"):
                blockers.append("rule {} is {}".format(rule["id"], rule["status"]))
        if now < state["coding_start"]:
            blockers.append("coding window has not started")
        if now >= state["deadline"]:
            blockers.append("event deadline has passed")
        remaining = (state["deadline"] - now).total_seconds() / 60
        required = sum(data["budget"].values())
        if now < state["deadline"] and required > remaining:
            blockers.append("recorded budget exceeds time remaining")
        if any(item > now for item in state["source_times"]):
            blockers.append("source retrieval time is in the future")
        review = data["review"]
        if review["verdict"] != "ready":
            blockers.append("review verdict is " + review["verdict"])
        if state["reviewed_at"] is not None and state["reviewed_at"] > now:
            blockers.append("review time is in the future")
        if state["reviewed_at"] is not None and state["reviewed_at"] < max(state["source_times"]):
            blockers.append("review predates a source retrieval")
        if review["verdict"] == "ready" and review["fingerprint"] != digest:
            blockers.append("review fingerprint does not match current contract and files")
        status = "blocked" if blockers else "ready"
        return emit({
            "status": status,
            "blockers": blockers,
            "fingerprint": digest,
            "checked_at": now_arg if now_arg is not None else now.isoformat(),
            "now_overridden": now_arg is not None,
            "scope": SCOPE,
        }, 1 if blockers else 0)
    except GateError as exc:
        return emit({"status": "invalid", "error": str(exc), "scope": SCOPE}, 2)
    except Exception as exc:
        return emit({"status": "invalid", "error": "unexpected local validation error: " + type(exc).__name__, "scope": SCOPE}, 2)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
