#!/bin/sh

set -eu

PROGRAM=${0##*/}
ROLE=
MODEL=
EFFORT=
WORKDIR=
PROMPT_FILE=
OUTPUT_FILE=
MAX_TURNS=24
TEMP_OUTPUT=

usage() {
  cat <<EOF
Usage:
  $PROGRAM --check
  $PROGRAM --role plan|implement|review --model MODEL --effort EFFORT \\
    --workdir ABS_PATH --prompt-file ABS_PATH --output-file ABS_PATH \\
    [--max-turns 1-100]
EOF
}

die() {
  printf '%s: %s\n' "$PROGRAM" "$*" >&2
  exit 2
}

cleanup() {
  if [ -n "$TEMP_OUTPUT" ] && [ -f "$TEMP_OUTPUT" ]; then
    rm -f -- "$TEMP_OUTPUT"
  fi
}

trap cleanup EXIT
trap 'cleanup; exit 130' HUP INT TERM

preflight() {
  if ! command -v claude >/dev/null 2>&1; then
    die "Claude Code CLI was not found in PATH"
  fi

  auth_status=$(claude auth status 2>&1) || die "Claude Code authentication check failed: $auth_status"
  if ! printf '%s\n' "$auth_status" | grep -E '"loggedIn"[[:space:]]*:[[:space:]]*true' >/dev/null 2>&1; then
    die "Claude Code CLI is not authenticated; run 'claude auth login' in this environment"
  fi
}

if [ "${1:-}" = "--check" ]; then
  [ "$#" -eq 1 ] || die "--check does not accept additional arguments"
  preflight
  printf '%s\n' "Claude Code CLI is available and authenticated"
  exit 0
fi

while [ "$#" -gt 0 ]; do
  case $1 in
    --role)
      [ "$#" -ge 2 ] || die "--role requires a value"
      ROLE=$2
      shift 2
      ;;
    --model)
      [ "$#" -ge 2 ] || die "--model requires a value"
      MODEL=$2
      shift 2
      ;;
    --effort)
      [ "$#" -ge 2 ] || die "--effort requires a value"
      EFFORT=$2
      shift 2
      ;;
    --workdir)
      [ "$#" -ge 2 ] || die "--workdir requires a value"
      WORKDIR=$2
      shift 2
      ;;
    --prompt-file)
      [ "$#" -ge 2 ] || die "--prompt-file requires a value"
      PROMPT_FILE=$2
      shift 2
      ;;
    --output-file)
      [ "$#" -ge 2 ] || die "--output-file requires a value"
      OUTPUT_FILE=$2
      shift 2
      ;;
    --max-turns)
      [ "$#" -ge 2 ] || die "--max-turns requires a value"
      MAX_TURNS=$2
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "unknown argument: $1"
      ;;
  esac
done

case $ROLE in
  plan|implement|review) ;;
  *) die "--role must be plan, implement, or review" ;;
esac

case $EFFORT in
  low|medium|high|xhigh|max) ;;
  *) die "--effort must be low, medium, high, xhigh, or max" ;;
esac

case $MODEL in
  ''|-*|*[!A-Za-z0-9._:/@-]*) die "--model contains unsupported characters" ;;
esac

case $MAX_TURNS in
  ''|*[!0-9]*) die "--max-turns must be an integer from 1 to 100" ;;
esac
if [ "$MAX_TURNS" -lt 1 ] || [ "$MAX_TURNS" -gt 100 ]; then
  die "--max-turns must be an integer from 1 to 100"
fi

for absolute_path in "$WORKDIR" "$PROMPT_FILE" "$OUTPUT_FILE"; do
  case $absolute_path in
    /*) ;;
    *) die "workdir, prompt file, and output file must use absolute paths" ;;
  esac
done

[ -d "$WORKDIR" ] || die "workdir does not exist: $WORKDIR"
[ -f "$PROMPT_FILE" ] || die "prompt file does not exist: $PROMPT_FILE"
[ ! -e "$OUTPUT_FILE" ] || die "output file already exists: $OUTPUT_FILE"

OUTPUT_DIR=$(dirname -- "$OUTPUT_FILE")
[ -d "$OUTPUT_DIR" ] || die "output directory does not exist: $OUTPUT_DIR"

preflight

case $ROLE in
  plan)
    PERMISSION_MODE=plan
    ROLE_PROMPT="Act as Atelier's architect. Stay read-only. Return a bounded TaskSpec and call out unresolved decisions."
    ;;
  review)
    PERMISSION_MODE=plan
    ROLE_PROMPT="Act as Atelier's independent reviewer. Stay read-only. Inspect evidence and return exactly one verdict: ship, fix-first, or rethink."
    ;;
  implement)
    PERMISSION_MODE=auto
    ROLE_PROMPT="Act as Atelier's implementer. Modify only the files owned by the supplied TaskSpec, run its verification, and report changed files, commands, results, and residual risks."
    ;;
esac

umask 077
TEMP_OUTPUT=$(mktemp "$OUTPUT_FILE.tmp.XXXXXX") || die "could not allocate a temporary result file"

if [ "$ROLE" = "implement" ]; then
  if ! (
    cd -- "$WORKDIR"
    claude -p \
      --model "$MODEL" \
      --effort "$EFFORT" \
      --permission-mode "$PERMISSION_MODE" \
      --disallowedTools "Agent" \
      --append-system-prompt "$ROLE_PROMPT" \
      --output-format json \
      --no-session-persistence \
      --max-turns "$MAX_TURNS" <"$PROMPT_FILE"
  ) >"$TEMP_OUTPUT"; then
    die "Claude implement lane failed"
  fi
else
  if ! (
    cd -- "$WORKDIR"
    claude -p \
      --model "$MODEL" \
      --effort "$EFFORT" \
      --permission-mode "$PERMISSION_MODE" \
      --disallowedTools "Edit,Write,NotebookEdit,Agent" \
      --append-system-prompt "$ROLE_PROMPT" \
      --output-format json \
      --no-session-persistence \
      --max-turns "$MAX_TURNS" <"$PROMPT_FILE"
  ) >"$TEMP_OUTPUT"; then
    die "Claude $ROLE lane failed"
  fi
fi

[ -s "$TEMP_OUTPUT" ] || die "Claude returned an empty result"

if ! grep -E '"is_error"[[:space:]]*:[[:space:]]*false' "$TEMP_OUTPUT" >/dev/null 2>&1; then
  die "Claude result did not report a successful invocation"
fi

CANONICAL_MODELS=$(grep -Eo '"canonicalModel"[[:space:]]*:[[:space:]]*"[^"]+"' "$TEMP_OUTPUT" || true)
[ -n "$CANONICAL_MODELS" ] || die "Claude result did not identify the canonical model used"

MODEL_FAMILY=$(printf '%s\n' "$MODEL" | tr '[:upper:]' '[:lower:]')
case $MODEL_FAMILY in
  *haiku*) EXPECTED_MODEL=haiku ;;
  *sonnet*) EXPECTED_MODEL=sonnet ;;
  *opus*) EXPECTED_MODEL=opus ;;
  *fable*) EXPECTED_MODEL=fable ;;
  *) EXPECTED_MODEL=$MODEL_FAMILY ;;
esac

if printf '%s\n' "$CANONICAL_MODELS" | grep -Fvi -- "$EXPECTED_MODEL" >/dev/null 2>&1; then
  die "requested model '$MODEL' was not used; result reported $CANONICAL_MODELS"
fi

if ! ln -- "$TEMP_OUTPUT" "$OUTPUT_FILE"; then
  die "could not publish result without overwriting: $OUTPUT_FILE"
fi
rm -f -- "$TEMP_OUTPUT"
TEMP_OUTPUT=

printf '%s\n' "$OUTPUT_FILE"
