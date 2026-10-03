---
name: prism
description: Run an independent read-only Claude Code review from Codex when the user requests Claude review or cross-model adversarial review. Return findings without automatic fixes or review loops.
---

# Prism

Use the bundled `scripts/review.py`, resolved relative to this SKILL.md's real path.
The host is Codex; Claude is the reviewer. Do not substitute a Codex review if Claude fails.

## Run

- Setup request: `python3 <skill>/scripts/review.py --check`.
- Default: `python3 <skill>/scripts/review.py --cwd <repo> --mode review`.
- Adversarial request: add `--mode adversarial` instead of `--mode review`.
- Branch review: add `--base <user-specified-ref>`. Default scope is tracked staged/unstaged changes plus untracked files. A clean working tree does not implicitly select another branch.
- Forward a requested focus with `--focus <text>` and the user's language with `--language Korean` (or the appropriate language).
- Model is pinned to `claude-opus-5-5`. Never substitute Sonnet or another model, including on failure. Changing the model requires a new user request and implementation change.
- Choose `--effort high|xhigh` in the current Codex turn, using the task context and a brief inspection of the scoped diff. No classifier, subagent, or extra model call is needed. Default to high for localized changes with clear contracts. Choose xhigh for nontrivial concurrency, authorization/trust boundaries, irreversible data/migration behavior, or cross-component design interactions that require tracing multiple failure paths. File count alone is not sufficient. Honor an explicit high/xhigh request. If uncertain, use high; never escalate after seeing findings automatically.
- Before execution, state the selected effort and one short task-specific reason. Direct CLI usage defaults to high. Do not conduct a full Codex review just to choose effort.
- Optional `--path <repo-relative-path>` is repeatable; use only when the user selected a narrower scope. Never silently narrow scope to fit the context limit.
- Optional `--output <new-absolute-path>` stores the complete JSON report without overwriting an existing file. Default output is stdout, without a job database.
- `--dry-run` prints the review input and scope without invoking Claude. It may contain source code.

Use argument-safe shell quoting; never interpolate raw user text as shell code. This sends review context to the user's configured Claude provider. Follow the host's normal execution/network permissions. Never bypass sandbox or permission checks.

### Authentication and execution permissions

- A sandboxed `loggedIn: false` or authentication error does not prove logout. Credentials available in the user's terminal may be inaccessible to the host sandbox.
- If authentication fails and the terminal is already logged in, request the host's approved execution permissions for `python3 <skill>/scripts/review.py --check` once (in Codex exec_command: `sandbox_permissions="require_escalated"` with a task-specific justification). This is a prerequisite check, not a model call. If host policy disallows escalation or approval is denied, stop and report that execution permissions block the review; do not use an alternative bypass.
- If that check succeeds, run the requested review with the same approved execution permissions, unchanged model and read-only flags. Approval of the check alone does not authorize the review command: use the host's approval mechanism for each command as required. Do not return to the sandbox that could not access authentication.
- If the same environment mismatch was already established in this task, request approved execution directly instead of repeating a known-failing sandbox attempt. Do not run an authentication check before every otherwise working review.
- Suggest login only when the user's normal terminal also lacks authentication. Never extract, copy, print, or relocate credentials, disable the host sandbox globally, or relax Claude's read-only flags. Do not automatically rerun a model request that timed out or may already have started; resolve prerequisites first and avoid duplicate paid calls.

The helper uses Python 3.10+, Git, and a Claude CLI with `--safe-mode`, `--restricted`, and `--json-schema`. It disables customizations/MCP and exposes only Read, Glob, and Grep. It cannot run tests or edits. Normal authentication is retained; it deliberately does not use `--bare`, which excludes subscription credentials.

Use the host's existing execution session and wait mechanism for long runs, with concise updates explaining that Claude is still working and elapsed time when available; JSON output arrives only at completion. No custom detached jobs, polling daemon, or status/cancel commands are required. Default timeout is 10 minutes; no automatic retries. If interrupted, cancel the running execution rather than starting another review. The child remains in the host process group; SIGTERM/SIGHUP/SIGINT and timeouts trigger cleanup. SIGKILL directed only at the Python parent cannot run cleanup: the host must terminate the whole execution group.

## Present and stop

Report mode, scope, and Claude's verdict, followed by findings ordered by severity. Preserve each finding's substance, file/lines, confidence, recommendation, and uncertainty. Include limitations and any stale-result warning prominently. Do not treat `approve` as proof of correctness or claim tests were run.

Do not silently omit findings, adjudicate them, modify code, or start another review. Stop after presenting the report. A later user request to assess or fix findings is a separate ordinary Codex task; this skill does not impose an automatic repair workflow.

If input is too large, request a smaller explicit scope. For authentication failures, follow the permission procedure above before concluding that execution is blocked. For timeout, JSON validation, or other CLI failures, report the error and stop; do not invent findings. `--check` validates local prerequisites/authentication state, not a successful model round trip.
