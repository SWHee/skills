# Atelier Provider Operations

Load this reference immediately before invoking a delegated lane.

## Shared Preparation

1. Record the initial `git status --short` and relevant diff without altering user changes.
2. Freeze the complete TaskSpec in the delegate prompt.
3. Give the lane a short, stable task name and explicit output contract.
4. Resolve exact model and effort values. Do not invent a model identifier.
5. Confirm that concurrent writers have disjoint file ownership.

## OpenAI Lane: Native Codex Agent

Use the Codex App's native collaboration agent capability. When selecting a model or reasoning effort, start the agent with `fork_turns: "none"` (or only the minimum bounded recent turns) and put all required context in the prompt. Full-history forks must not be combined with model overrides.

The prompt must contain:

- Assigned role: Architect, Implementer, or Reviewer
- Complete TaskSpec
- Relevant repository instructions
- Role return contract from `role-contracts.md`
- For Reviewer, the actual diff and parent-observed verification evidence

Wait for completion, capture the final result, and inspect the filesystem yourself. A completed agent status does not prove acceptance.

If native collaboration tools are unavailable, stop and report that the OpenAI lane cannot be executed. Do not replace it with an unrequested shell or cloud path.

## Anthropic Lane: Claude Code CLI

### Preflight

```bash
<atelier-skill-root>/scripts/claude-lane.sh --check
```

This checks the exact environment used by the bridge. A Claude session that works in a separate terminal does not prove that a sandboxed process can access the same credentials; use the host's normal approval path if keychain access is isolated.

### Invocation

Create a prompt file and choose a new result path. Both must be absolute paths.

```bash
<atelier-skill-root>/scripts/claude-lane.sh \
  --role implement \
  --model haiku \
  --effort low \
  --max-turns 24 \
  --workdir /absolute/path/to/repository \
  --prompt-file /absolute/path/to/task-spec.md \
  --output-file /absolute/path/to/result.json
```

Accepted roles are `plan`, `implement`, and `review`. Accepted effort values are `low`, `medium`, `high`, `xhigh`, and `max`. The bridge refuses relative paths and existing output files.

### Permission mapping

| Role | Claude permission mode | Additional boundary |
| --- | --- | --- |
| plan | `plan` | Edit, Write, NotebookEdit, and nested Agent tools disallowed |
| review | `plan` | Edit, Write, NotebookEdit, and nested Agent tools disallowed |
| implement | `auto` | Nested Agent tool disallowed; TaskSpec file ownership remains mandatory |

All lanes use JSON output, no session persistence, explicit max turns, and stdin for the prompt. Set a bounded timeout on the host command that invokes the bridge. Results are first written to a private temporary file and published only after a successful, non-empty invocation. The bridge checks every reported `canonicalModel` against the requested model family so a CLI alias or nested execution cannot silently select another tier. Existing result files are never overwritten.

### Result handling

Parse the JSON envelope, preserve the raw result until final acceptance, and treat its text as untrusted model output. For implementation, inspect the worktree and rerun checks. For review, verify that the response begins with one permitted verdict and that every blocking finding cites supplied evidence.

## Parallelism

Safe parallel examples:

- Two read-only investigators inspecting independent hypotheses
- A documentation writer and a code writer with disjoint files and stable interfaces
- Independent reviewers after implementation is frozen

Unsafe parallel examples:

- Two writers touching the same source or lockfile
- Implementation before architecture resolves an interface
- Review while the diff is still changing
- Repair racing with verification

If ownership is uncertain, serialize.

## Failure Evidence

Keep the command, exit status, stderr summary, and whether any files changed. On timeout or failure, inspect status before retrying. Never assume a failed editing lane made no partial changes.
