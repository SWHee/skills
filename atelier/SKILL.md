---
name: atelier
description: Use when the user asks Codex to coordinate a software change across OpenAI and Anthropic models, invokes $atelier, assigns models to architecture, implementation, or review roles, or wants cost-aware cross-vendor implementation with independent verification.
---

# Atelier

## Purpose

Run one software task as a small model workshop. Assign each responsibility to the lowest-cost model that can safely carry it, preserve independent review, and keep the current Codex task responsible for final acceptance.

Atelier coordinates models; it does not merely recommend them. For a substantive change, execute the chosen lanes unless the user asked only for a plan. A user-specified provider, model, or effort takes precedence when it is available and safe.

## Non-Negotiable Rules

- Keep the current Codex task as orchestrator and final acceptor.
- Declare the route before delegating. Never let a delegate choose its own replacement model.
- Give every writer a complete TaskSpec and exclusive file ownership.
- Never run writers with overlapping files concurrently.
- Prefer a reviewer from the other provider than the implementer.
- Treat delegate reports as claims. Re-read the actual diff and re-run decisive checks locally.
- Fail closed on missing CLI, authentication, unavailable models, timeouts, empty results, or an unexpected empty diff. Do not silently substitute another provider or model.
- Keep planning and review read-only. Grant write access only to an implementer.
- Return `fix-first` work to the original implementer. Use a fresh reviewer after each repair.

## Workflow

### 1. Inspect Before Routing

Read repository instructions, current status, relevant files, and existing tests. Separate user changes from Atelier's prospective changes. Identify ambiguity, security or concurrency risk, blast radius, and whether the task is fully specified.

For any Anthropic lane, run the bridge preflight before promising the route:

```bash
<atelier-skill-root>/scripts/claude-lane.sh --check
```

If the host sandbox hides the user's Claude credentials, repeat this read-only check through the host's normal approval path. Stop if it still fails.

### 2. Publish the Route

State a compact route in the user's language:

```text
ATELIER ROUTE
Architect:    <parent | provider:model/effort> — <reason>
Implementer: <provider:model/effort> — <reason>
Verifier:    parent — actual diff and commands
Reviewer:    <provider:model/effort> — <reason>
Write scope: <exclusive files or serial phases>
```

Use `parent/current` when the current Codex task owns a responsibility. Verify names against the models available in the current Codex host or Claude CLI; do not assume that an example model is available.

Use the detailed decision table in [routing.md](references/routing.md) when the route is not obvious. An explicit Atelier request normally uses both providers for a substantive implementation. Compress trivial work to fewer calls when delegation would cost more than the work, and disclose that choice before acting.

### 3. Freeze a Six-Field TaskSpec

Before any writer starts, produce:

1. **Objective** — one observable completion state.
2. **Scope & ownership** — allowed files and exclusive ownership boundaries.
3. **Interfaces** — inputs, outputs, APIs, schemas, and compatibility to preserve.
4. **Constraints & non-goals** — forbidden changes and intentionally excluded work.
5. **Acceptance & verification** — exact checks and observable pass conditions.
6. **Route** — role, provider, model, effort, permission, and rationale.

Resolve consequential ambiguity in the parent task. Delegates may report a missing decision but must not broaden scope to invent one. See [role-contracts.md](references/role-contracts.md) for exact inputs and return contracts.

### 4. Execute the Lanes

- Use native Codex agents for OpenAI lanes. Start them without inherited conversation history and include the complete TaskSpec and role contract.
- Use `scripts/claude-lane.sh` for Anthropic lanes. Pass an absolute workdir, prompt file, new output file, explicit model, and effort.
- Parallelize only independent read-only analysis or writers with disjoint ownership. Serialize everything else.
- Do not continue past a provider failure as though the assigned lane succeeded.

Follow [provider-operations.md](references/provider-operations.md) for invocation and evidence handling.

### 5. Verify Independently

After implementation, the parent task must:

1. Inspect repository status and the exact diff, including unexpected files.
2. Check that changes stay inside the TaskSpec and preserve pre-existing user work.
3. Re-run the smallest decisive tests, linters, type checks, or build steps.
4. Compare observable results with every acceptance condition.
5. Reject an unexpected empty diff, unverifiable claim, or truncated result.

Only then provide the spec, diff, and verification evidence—not the implementer's persuasive narrative—to an independent Reviewer.

### 6. Apply the Verdict

The Reviewer returns exactly one leading verdict:

- `ship` — acceptance conditions hold and no blocking defect remains.
- `fix-first` — the design remains valid, but specified implementation defects block acceptance.
- `rethink` — the TaskSpec or architecture cannot safely determine the result.

For `fix-first`, send numbered findings and failing evidence to the original Implementer, then independently verify and start a fresh review. Allow at most two repair cycles. If the same defect recurs or the fix requires a material scope change, move to `rethink`.

For `rethink`, return to architecture. Ask the user only when a new product decision, authority, or material scope expansion is required.

## Completion Contract

Lead the final response with the outcome. Include the actual route used, changed files, checks with pass/fail status, the final verdict, and any residual risk. Distinguish a provider's claim from evidence the parent task observed. Do not claim multi-model execution if a lane was only proposed or its invocation failed.

## Quick Example

```text
Request: Add a bounded retry helper. Use Haiku for implementation and Sol for review.

Route: parent architect → Claude Haiku/low implementer → parent verifier → Codex Sol/high reviewer
TaskSpec: retry only declared transient errors, preserve the public API, add deterministic tests, no new dependency
Result: parent inspects diff and reruns tests → reviewer says fix-first → same Haiku lane fixes off-by-one → parent reverifies → fresh Sol review says ship
```

## Common Failures

| Failure | Correction |
| --- | --- |
| Model list without execution | Invoke each approved lane and retain its result evidence. |
| Vague delegation | Freeze all six TaskSpec fields first. |
| Two agents edit the same file | Serialize them or split exclusive ownership. |
| Implementer self-approves | Re-run checks in the parent and use an independent reviewer. |
| New repair persona | Return precise findings to the original implementer. |
| Provider failure followed by fallback | Stop, report the failed route, and ask before changing it. |
| Endless review loop | Cap repair at two cycles, then rethink. |
