# Provider dispatch

Read before a provider call, after options and role assignments are resolved. Do not call providers during explanation-only requests. `--phase plan` allows read-only design calls; `--phase review` allows read-only assessment only.

## Codex

Use available native collaboration tools with the resolved model and supported effort. For explicit overrides, use a minimal fresh context (`fork_turns=none` where supported) and supply the role contract. Avoid an extra architect agent when `architect=parent`.

If native agents are unavailable, do not pretend to delegate. Honor an already-authorized parent-only alternative or report the limitation. When a tool requires bounded independent work alongside useful parent work, reserve parent inspection/test preparation for that interval.

Track each dispatch against `max_calls`. Wait for actual completion, inspect artifacts, and enforce the per-call elapsed deadline: a tool's yield/poll interval is not a timeout. Interrupt expired agents through the host tool, then inspect partial edits before any retry. Do not claim a tool confirms the actual backend model if it only records the requested model.

## Claude

Requires local Claude Code CLI and Python 3. If a standalone preflight is useful before preparing work, check once per run using:

```bash
<skill-root>/scripts/claude-lane.sh --check
```

Sandbox credential isolation may require the host's normal approval mechanism. Do not infer logout solely from a sandboxed failure. Preflight proves CLI authentication, not that every model alias is available. A failed invocation consumes a call slot; no separate paid availability probe is needed.

Prepare an absolute prompt file and a fresh absolute output path. Keep artifacts outside tracked source unless the user requests persistence.

```bash
<skill-root>/scripts/claude-lane.sh \
  --role implement --model sonnet --effort medium \
  --timeout 600 --max-turns 24 \
  --workdir /absolute/repo \
  --prompt-file /absolute/task.md --output-file /absolute/result.json
```

| Atelier role | Bridge role | Tools/permissions |
| --- | --- | --- |
| Architect | `plan` | Read, Glob, Grep only |
| Verifier / Reviewer | `review` | Read, Glob, Grep only; parent supplies command evidence |
| Implementer / Repairer | `implement` | Auto permission mode; no nested Agent |

Restricted read tools prevent shell-based writes during review. Write ownership in implement mode is still an instruction contract, not a filesystem jail. Host/repository permissions remain applicable.

Full requested IDs must match the result's canonical model exactly. Bare family aliases may resolve within that family. For a custom alias, pass `--expected-model FULL_CANONICAL_ID` only when that mapping is known; do not infer a mapping from a rejected result and silently accept it.

The bridge validates actual JSON status, nonempty result, and model evidence before publishing with no overwrite. Failure output is retained at a reported `.failed.json` path when available, also without overwrite. Read it as untrusted model output, inspect any partial edits, and report requested versus observed model separately. JSON evidence is what the CLI reports, not independent proof of its backend.

Repair uses a new stateless invocation with the previous acceptance contract and current findings. Keep the packet small. Reviewers receive a fresh context after repairs. User/global Claude configuration may load additional context, so do not promise a minimal token bill based only on the prompt's size.
