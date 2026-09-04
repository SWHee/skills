# Atelier Routing Guide

Load this reference when the user has not supplied a complete route or when risk changes during the task.

## Decide in This Order

1. Respect an explicit provider, model, or effort request if it is available and safe.
2. Choose the role and permission boundary before choosing a model.
3. Classify ambiguity, algorithmic difficulty, blast radius, security impact, and verification strength.
4. Select the lowest-cost model that is adequate for that role.
5. Put the Reviewer on the other provider when practical.
6. Preflight the selected paths before implementation begins.

## Work Classification

| Class | Typical work | Suggested capability | Effort |
| --- | --- | --- | --- |
| Mechanical | Renames, generated edits, formatting, narrow docs, fully specified tests | Fast/low-cost model such as Luna or Haiku | low |
| Routine | Local feature, familiar bug, bounded refactor, conventional integration | Balanced model such as Terra or Sonnet | medium |
| Complex | Cross-cutting refactor, unfamiliar subsystem, difficult debugging, performance tradeoff | Strong model such as Sol or Opus | high or xhigh |
| Critical | Auth, cryptography, concurrency, data loss, irreversible migration, broad public API | Strongest available model plus independent strong review | xhigh or max |

These names are examples, not guaranteed inventory. Use model aliases or full identifiers accepted by the current Codex host and Claude CLI.

## Default Role Shapes

### Spec-determined implementation

```text
Architect:    parent/current balanced model, medium
Implementer: fast model from either provider, low
Verifier:    parent/current
Reviewer:    strong model from the other provider, medium or high
```

### Ambiguous or high-risk implementation

```text
Architect:    strong model, high
Implementer: balanced or strong model, medium/high
Verifier:    parent/current plus targeted tools
Reviewer:    strongest practical model from the other provider, high/xhigh
```

### Investigation before writing

Run one or more read-only architecture/investigation lanes. Consolidate their evidence in the parent, resolve contradictions, then freeze one TaskSpec. Do not let competing analyses write simultaneously.

## When to Compress

Atelier may keep architecture and verification in the parent and use only one delegated lane when the edit is trivial, easily reversible, and strongly testable. It may avoid all delegation for a no-write explanation or when the user asked only whether Atelier is appropriate.

When `$atelier` is explicitly invoked for a substantive implementation, use both providers by default: one as Implementer or Architect and the other as Reviewer. If this would be wasteful or a provider is unavailable, disclose the proposed compression or blockage before acting.

## Escalation Signals

Increase model capability or reasoning effort when any of these appears:

- The TaskSpec cannot fully determine a correct implementation.
- Failures are nondeterministic or span process/thread boundaries.
- A defect could expose credentials, corrupt data, or break rollback.
- The change alters several modules' contracts.
- The first repair repeats the same failure.
- Verification cannot cheaply distinguish a correct result.

Do not increase effort merely because the diff is long. Large mechanical output can remain a low-effort implementation if the specification and checks fully determine it.

## Route Changes

A provider/model failure is a failed route, not permission to improvise. Report:

```text
Assigned lane:
Observed failure:
Work completed before failure:
Proposed replacement route:
Cost/risk difference:
```

Continue with the replacement only after the user has already authorized flexible routing or approves the change. Never report the originally requested multi-provider route as completed after substitution.
