# Delegation contracts

The parent owns scope, dispatch, and acceptance even when a separate architect is selected. Roles describe responsibilities, not mandatory extra agents.

## TaskSpec

Include these six fields in a compact prompt, using repository-relative paths under an explicit workdir:

1. Objective: observable end state.
2. Scope: owned files, existing user changes, other writers.
3. Interfaces: API/schema/compatibility constraints.
4. Constraints: non-goals and prohibited side effects.
5. Acceptance: exact checks and pass conditions.
6. Route: role, resolved provider/model/effort, permission, timeout.

Reference specific files for further context. Do not hand off unexplained conversation history or create permanent planning artifacts for routine work.

## Returns

| Role | Return |
| --- | --- |
| Architect | Bounded TaskSpec, dependency/ownership boundaries, unresolved decisions |
| Implementer | Changed paths, executed commands/results, unmet conditions, residual risks |
| Verifier | Observed checks against current artifact, failures, missing evidence |
| Reviewer | `ship`, `fix-first`, or `rethink`; findings with location, consequence and required correction |
| Repairer | Implementer return plus disposition of each supplied finding |

`blocked` is a valid execution status and must explain the missing decision/evidence. A delegate cannot broaden scope or independently change its model. Delegate success does not establish acceptance.

## Verification and review

Parent checks status and diff against the pre-task baseline, including untracked files. Prefer a focused test that discriminates the defect from the intended behavior. Repeat a check only after relevant changes, stale evidence, or unresolved doubt; do not run identical suites once per persona.

External reviewer context must be fresh and contain the spec, current diff, and verification evidence. It can read relevant surrounding code, but should not inherit the implementer's narrative. `ship` is not permission to deploy; it means the supplied acceptance conditions have no known blocker.

Review the accumulated task changes against the pre-task baseline, not merely the last writer's diff. Include new files and distinguish pre-existing user edits. After repair, supply the cumulative result and the previous findings with their disposition so fixed defects and regressions can both be assessed. A parent who planned the change offers separate judgment from the writer, but not fresh-context review; describe that distinction accurately.

An explicitly selected verifier may analyze tests and evidence. Mechanical commands remain under parent control for read-only Claude roles; give them outputs rather than unrestricted shell access.

## Repairs

Default to the original implementer; honor an explicit repairer override. Keep context when available and useful. Claude's default bridge is stateless, so resend a small repair packet instead of claiming session continuity.

Provide original acceptance criteria, current diff, numbered findings, and failing evidence. Reverify affected behavior and refresh external review afterward. The repair limit is a ceiling, not a requirement to retry an unchanged failure. Report `rethink` when bounded implementation fixes no longer address the cause.
