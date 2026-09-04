# Atelier Role Contracts

Load this reference when constructing prompts or deciding whether a result is complete.

## Shared TaskSpec

Every delegate receives the same six fields. Do not send a link or a conversational summary in place of their contents.

```text
Objective
- Observable end state:

Scope & ownership
- Working directory:
- Allowed files:
- Forbidden or pre-existing user changes:
- Other active writers:

Interfaces
- Inputs and outputs:
- Public APIs or schemas:
- Compatibility requirements:

Constraints & non-goals
- Required constraints:
- Explicit non-goals:

Acceptance & verification
- Commands:
- Observable pass conditions:
- Expected diff or artifact:

Route
- Role:
- Provider and model:
- Reasoning effort:
- Permission: read-only | write
- Selection rationale:
```

## Architect / Orchestrator

### Input

- User request and repository instructions
- Current worktree status and relevant implementation context
- Model availability, provider authentication, and budget or latency constraints

### Required output

- One bounded TaskSpec per independent unit of work
- Dependency order and exclusive file ownership
- Risk classification: `low`, `medium`, or `high`
- Route with an explicit reason for each model and effort choice
- Decisions that remain with the user

### Must not

- Edit implementation files while delegated architecture is still unresolved
- Hide an authentication or availability failure by rewriting the route
- Delegate product ambiguity that could materially change the requested outcome

## Implementer

### Input

- The complete TaskSpec
- Repository instructions relevant to owned files
- Prior verifier/reviewer findings when this is a repair cycle

### Required output

```text
Status: complete | blocked
Changed files:
- <path>: <purpose>
Commands run:
- <command>: <exit/result>
Acceptance mapping:
- <condition>: <evidence>
Residual risks:
- <risk or none>
```

### Must not

- Modify files outside ownership
- Expand scope, replace dependencies, or redesign public interfaces without returning `blocked`
- Claim success from a test it did not run
- Commit, push, deploy, or message external systems unless the TaskSpec explicitly authorizes it

## Verifier

The current Codex task owns mechanical verification even if a delegate also ran tests.

### Required checks

- Compare pre- and post-work status so existing user changes are not attributed to Atelier
- Inspect the actual diff and untracked files
- Re-run decisive commands in the repository, not in a delegate's narrative
- Map evidence to every acceptance condition
- Identify unexpected empty, partial, generated, or broad changes

### Required output

```text
Verification: pass | fail | blocked
Observed diff:
- <paths and scope>
Checks:
- <command>: <observed result>
Unmet conditions:
- <condition or none>
```

## Reviewer

Use a fresh context. Supply the TaskSpec, actual diff, and verifier evidence. Omit brainstorming history, implementer confidence, and social pressure.

### Required output

```text
Verdict: ship | fix-first | rethink
Blocking findings:
1. <location, failure, evidence, required correction>
Residual risks:
- <non-blocking risk or none>
```

### Verdict rules

- Choose `ship` only when every acceptance condition is supported by observed evidence.
- Choose `fix-first` when the design is adequate and bounded code changes can correct the defect.
- Choose `rethink` when the specification, ownership, architecture, or requested outcome must change.
- Do not invent findings to justify the review lane. A clean change may receive `ship`.

## Repair Cycle

There is no separate repairer persona. Preserve the original Implementer's provider, model, and effort unless the Reviewer explicitly establishes that model capability—not just implementation error—is the blocker. Route changes require the parent to disclose the change.

Send only numbered findings, failing evidence, and the unchanged TaskSpec. After repair, discard the prior Reviewer context and repeat verification before a new review.
