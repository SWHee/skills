# Role selection and cost

## Precedence

Current user instructions > explicit named options > selected JSON config > defaults. If the same request gives contradictory instructions, resolve the meaningful conflict before dispatch. Config is declarative data; reject unknown keys and never execute content from it. Do not create or update a saved config unless requested.

The resolver reads only workdir `.atelier.json` or the explicitly supplied `--config`, not ancestor or home files. Config paths supplied by users resolve from the process working directory. An explicitly missing config is an error.

```json
{
  "mode": "delegate",
  "architect": "parent",
  "implementer": "sol/medium",
  "verifier": "parent",
  "reviewer": "parent",
  "repairer": "implementer",
  "max_calls": 4,
  "max_repairs": 1,
  "timeout": 600
}
```

```bash
python3 <skill-root>/scripts/resolve-route.py --workdir /absolute/repo \
  --implementer terra/high --phase plan
```

This prints a request object and overrides just the implementer and phase. `status=requested` and `availability_checked=false` are intentional: a config parser cannot establish account access or start an agent.

`--planner` and `--architect` share one CLI value (last occurrence wins); JSON uses `architect` only. `--dry-run` is invocation-only, not a persisted default. It previews the route without preflight or design work. `active_roles` excludes writers in plan/review; inactive saved selections remain visible but do not conflict with `solo` for that phase.

## Model resolution

- `astra`, `sol`, `terra`, `luna`, and `gpt-*` infer Codex; Claude family aliases and `claude-*` infer Claude. Custom names require `codex:` or `claude:`.
- For native Codex, match a shorthand to exactly one exposed runtime model (e.g. `sol` to the runtime's `gpt-5.6-sol` if listed). Zero or multiple matches need resolution before execution. Pass the resolved ID, never an invented ID.
- Full model IDs are preserved; check their supported reasoning values at dispatch. An effort recognized by the resolver is not proof that a particular model accepts it.
- Claude aliases are sent as aliases; the bridge checks family evidence. Full IDs require exact evidence. A custom alias requires an explicitly verified canonical ID passed via bridge `--expected-model`.
- `parent` consumes the current task's model/effort and does not create a new agent. To use a different architect, dispatch that role; the parent retains orchestration.
- `repairer=implementer` inherits the resolved implementer and reuses its context where supported. An explicit repair model receives the original contract plus findings and current diff.

## Modes

| Mode | Route policy |
| --- | --- |
| `auto` | Choose parent-only or delegation based on total work, not model prestige |
| `solo` | All active roles in parent; explicit delegated models conflict |
| `delegate` | At least one active role delegated; parent can review implementation |
| `cross` | At least two active roles span Codex and Claude; review must be independent |

Modes apply to the selected phase: a plan/review phase does not invoke implementation merely to satisfy a mode. In `cross` planning, obtain a second-provider read-only assessment of the design; in `cross` review, use two-provider read-only assessments. For `solo`, unresolved `auto` roles resolve to parent.

## Economic decision

Prefer parent implementation when the change is small, well understood, and cheaper to write than to explain and dispatch. Delegate substantial spec-determined output to a lower-cost model. Keep difficult decisions with a strong architect; select effort for ambiguity, not line count. Typical options are Sol/medium or Terra/high for implementation, with Astra as parent for design and review when that is the current model.

Do not automatically require the strongest implementation model merely because a file concerns security. First constrain the task and strengthen acceptance checks. Escalate when ambiguity, repeated failures, irreversible effects, or weak verification actually require more capability. Explain a genuine capability conflict with an explicit user choice rather than silently replacing it.

Independent cross-provider review helps when correlated errors matter; it also adds context and latency. Prefer it for consequential unfamiliar changes or when explicitly requested. For small delegated fixes, parent review may suffice.

Before calling a model, consider input context + expected output + repeated initialization + likely repairs. Subscription usage is not interchangeable with API list pricing. Report observed usage when available; otherwise state the decision is qualitative.

Use a routine lane for spec-determined changes with strong checks (for example an available Luna or Haiku); use a more capable lane when the implementation still requires reasoning the spec cannot settle. These are candidates, not a price ranking or account-access guarantee. A mixed workload can use different auto-selected implementations per task. A pinned implementer stays pinned; return unresolved decisions to the architect instead of silently escalating.

Budget the actual path: an external architect + writer + external reviewer costs at least three calls; each repair followed by external re-review needs two more. A parent architect/reviewer with one writer starts at one call. Reserve the selected review before dispatching writers, and reserve re-review before dispatching a repair. The repair ceiling does not guarantee every cycle fits the call limit. Keep a small in-context ledger of role, requested/observed model, status, and calls remaining; files are unnecessary unless continuation requires them.

On limit exhaustion, report completed work, remaining findings, and the smallest continuation. Do not reset counters by spawning another orchestrator.
