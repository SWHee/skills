# Gate format

The gate is a strict local manifest. It stores checkable structure and file references; the brief stores judgment and design. Keep run logs and changing build status outside the reviewed brief so normal execution does not invalidate it.

## Commands

```bash
python3 <skill-root>/scripts/gate.py fingerprint <gate.json>
python3 <skill-root>/scripts/gate.py check <gate.json> [--now ISO8601]
```

Both commands are read-only and print JSON. `fingerprint` may hash a pending, structurally valid gate; it does not authorize implementation. `check` exits 0 for `ready`, 1 for well-formed but blocked, and 2 for JSON/schema/I/O/path/CLI errors. Its `checked_at` and `now_overridden` fields identify the time basis. The output proves local consistency and a recorded review only, not online freshness, legality, or semantic understanding.

## Version 1 fields

- `schema_version`: integer `1`.
- `event`: nonempty `name`, `track`, `award`; timezone-aware `coding_start` and `deadline`, with start before deadline.
- `sources`: nonempty records with unique `id`, `uri`, timezone-aware `retrieved_at`, `authority` (`official` or `supporting`), and relative `snapshot`. At least one must be official.
- `rules`: unique `id`, `topic`, `status`, `source_ids`, `locator`, `resolution`. Status is `resolved`, `unknown`, `conflict`, `violated`, or `not_applicable`. Cover: `eligibility`, `team`, `work_window`, `reuse`, `ai_usage`, `required_tech`, `data_rights`, `ip_licensing`, `submission`, `judging`, `demo_environment`. Resolved and not-applicable rows need a cited source, locator, and explanation. Unknown/conflict/violated rows block readiness.
- `rubric`: selected `award`, `weighting` (`published` or `unpublished`), and nonempty unique criteria. Each criterion has `id`, `name`, an official `source_id`, `locator`, `weight`, `feature`, and `proof`. The award must match the event. Published finite weights are 0–100 and total 100; unpublished weights are all `null`.
- `artifacts`: relative path `brief`.
- `budget`: positive finite `implementation_minutes`, `verification_minutes`, and `submission_minutes`. Their finite total must fit before the deadline.
- `review`: `verdict` (`pending`, `ready`, `blocked`), `reviewer`, `reviewed_at`, `fingerprint`, `rationale`. Pending permits blank review fields. Ready requires all fields, a review no earlier than any source and no later than the check time, and the current fingerprint. Blocked review stays blocked.

Unknown fields, duplicate JSON keys or IDs, booleans used as numbers, NaN/Infinity, bad timestamps, and invalid references are rejected. Snapshot and brief paths must be nonempty regular files inside the manifest directory; absolute paths, `..`, missing files, directories, symlink escapes, and files over 10 MiB are rejected. No file contents appear in output.

## Fingerprint and refresh

The SHA-256 fingerprint covers canonical sorted UTF-8 JSON excluding `review`, plus path-to-SHA-256 mappings for every referenced snapshot and the brief. It is stable across JSON formatting/key order and changes with the contract or file bytes. It is not a secret signature.

After changing a rule, source, budget, or reviewed file:

1. Refresh the source record and snapshot as needed.
2. Run `fingerprint`; stale review chronology does not prevent computing a new digest.
3. Inspect the six responsibilities and source changes.
4. Set `review.verdict`, reviewer, current reviewed time, new fingerprint, and rationale.
5. Run `check` with the actual clock. Use `--now` only in deterministic tests.

The checker cannot tell whether a `not_applicable` explanation is substantively sound or whether prose truthfully reflects the rules. The reviewing agent or person must inspect those judgments.
