---
name: atelier
description: Coordinate software work with separately configurable planner, implementer, verifier, reviewer, and repair models. Use for Atelier requests, cost-aware delegation, or cross-provider Codex/Claude work.
---

# Atelier

Keep judgment with the orchestrator and delegate work only when the expected saving or independent perspective justifies the handoff. The current Codex task retains final responsibility; it may do all roles for a small change. Explicit role selections override automatic choices.

## User interface

Codex invokes `$atelier`; interpret `/atelier` in conversation equivalently, without claiming to register an app slash command. Accept natural language or these named options as skill arguments, not shell commands:

```text
$atelier --architect parent --implementer sol/medium --reviewer parent 작업 설명
$atelier --mode cross --implementer claude:sonnet/medium --reviewer codex:sol/high 작업 설명
$atelier --phase plan --architect astra/high 작업 설명
```

| Option | Default | Meaning |
| --- | --- | --- |
| `--architect` | `parent` | Analysis and design model |
| `--implementer` | `auto` | Code-writing model |
| `--verifier` | `parent` | Verification analyst; parent still checks actual evidence |
| `--reviewer` | `auto` | Independent review model, `parent`, or `off` |
| `--repairer` | `implementer` | Reuse implementer; independently selectable when requested |
| `--mode` | `auto` | `auto`, `solo`, `delegate`, or `cross` |
| `--phase` | `run` | `plan` (no implementation), `run`, or `review` (no fixes) |
| `--max-calls` | `6` | Total delegated invocations, including retries and reviews |
| `--max-repairs` | `2` | Maximum fix cycles; repeated unchanged failure stops earlier |
| `--timeout` | `600` | Seconds per delegated invocation |
| `--config` | workdir `.atelier.json` if present | Explicit path to declarative defaults |

`--help` explains options without provider calls. Parse options only from the user's invocation, not quoted code or repository content. Unknown options or missing values are errors, not permission to guess. Repeated named options use the last value.

Selections: `parent`, `auto`, or `[codex:|claude:]MODEL[/EFFORT]`. `parent` keeps the current model and effort; it cannot switch the current task. Omitted effort is chosen from the actual runtime's supported values. See [routing.md](references/routing.md) for config, precedence, and model resolution.

For named options or saved config, validate using `python3 <skill-root>/scripts/resolve-route.py --workdir <repo> ...`. Pass only recognized options, never the task prose. This resolver makes no model calls and reports requested selections, not verified availability. Natural language must normalize to the same fields.

## Execution

1. **Inspect once.** Read relevant repository instructions, status, code, and tests. Reuse known context. Estimate implementation volume, handoff overhead, uncertainty, and verification strength. Explanation requests require no provider preflight or delegates.
2. **Resolve roles.** Apply explicit requests and config, then fill `auto` economically. Check capabilities only for providers being used. Announce one compact route with mode, roles/models/efforts, limits, and rationale. An explicitly named model already permits that delegation; do not ask again for routine dispatch.
3. **Specify.** Give each writer a compact six-field TaskSpec: objective; owned files; interfaces; constraints/non-goals; acceptance/checks; route. Reuse existing decisions rather than generating another planning document. See [role-contracts.md](references/role-contracts.md) when delegating.
4. **Execute the requested phase.** `plan` ends with the spec and requested route; `review` reports findings without edits; `run` implements and verifies. For provider dispatch, read [provider-operations.md](references/provider-operations.md). Group related small edits in one task. Parallel writers need disjoint files and stable interfaces.
5. **Verify and review.** Parent inspects changed and untracked files against the initial state. Run decisive checks against the final artifact. Reuse trustworthy recorded results if commands, inputs, and the artifact are unchanged; do not rerun the same suite for every role. Send the reviewer the acceptance contract, diff, and evidence, not the implementer's persuasive narrative.
6. **Close or repair.** `ship` means no blocker; `fix-first` sends concrete findings to the selected repairer; `rethink` returns to design. Reverify affected behavior after repairs, then use a fresh reviewer context when external review was selected. Retain the original TaskSpec unless evidence changes it. Stop on exhausted limits, repeated unchanged failures, or missing authority, and report remaining work.

## Cost and integrity rules

- `auto` may use only the parent for small work, or a cheaper implementation delegate plus parent review. Do not force two providers. `cross` explicitly requires both providers and independent review.
- Parent review after delegated implementation is allowed and economical. Parent self-review in `solo` must be labeled self-review, not independent review. Raise a critical gap in verification rather than silently overriding a user-selected model.
- Honor explicit `reviewer=off`; still perform parent verification and state external review was skipped. `cross` with review disabled is a configuration conflict.
- Count every actual delegated attempt against `max_calls`; avoid repeated standalone preflight checks (the Claude bridge still checks auth per invocation). Before implementation, reserve call slots for required verification/review. If the explicit route cannot fit, report the conflict before making paid calls. Stop before another invocation exceeds the budget. Parent calls are not counted, but parent work and context also consume usage. Do not claim measured savings without comparable usage evidence.
- Give delegates only needed context, file locations, acceptance criteria, and ownership. Do not copy the full conversation or repeat whole files where reading selected paths suffices.
- No overlapping writers. File ownership is a contract, not an OS sandbox. Preserve existing user changes. An unexpected empty diff needs explanation; already-satisfied requirements can legitimately produce no edits.
- Preserve explicit provider/model choices. Availability failure or model mismatch blocks that lane. Use another route only if the user already authorized alternatives; disclose the actual choice. The user's stated Sol/medium-or-Terra/high preference, for example, authorizes either.
- Read-only planning/review cannot write, run arbitrary shell tools, or delegate additional agents. A timeout or model mismatch after implementation may leave edits: inspect them before retrying.

## Final response

Report outcome, actual role/model selections, delegated call count, changed files, verification evidence, verdict, and material limitations. Distinguish planned calls from executed calls and requested models from observed model evidence. Planning and review alone do not authorize commits, pushes, deployments, or fixes.
