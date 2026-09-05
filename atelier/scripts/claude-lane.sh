#!/bin/sh

set -eu

PROGRAM=${0##*/}
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
RESULT_HELPER=$SCRIPT_DIR/claude-result.py
ROLE=
MODEL=
EXPECTED_MODEL=
EFFORT=
WORKDIR=
PROMPT_FILE=
OUTPUT_FILE=
MAX_TURNS=24
TIMEOUT=600
TEMP_OUTPUT=
RUNNER_PID=

usage() {
  cat <<EOF
Usage:
  $PROGRAM --check
  $PROGRAM --role plan|implement|review --model MODEL --effort EFFORT \
    --workdir ABS_PATH --prompt-file ABS_PATH --output-file ABS_PATH \
    [--max-turns 1-100] [--timeout SECONDS] [--expected-model CANONICAL_ID]
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

interrupt() {
  trap - HUP INT TERM
  if [ -n "$RUNNER_PID" ]; then
    kill -TERM "$RUNNER_PID" 2>/dev/null || true
    wait "$RUNNER_PID" 2>/dev/null || true
  fi
  cleanup
  exit 130
}

run_helper() {
  python3 "$RESULT_HELPER" "$@" &
  RUNNER_PID=$!
  if wait "$RUNNER_PID"; then
    HELPER_STATUS=0
  else
    HELPER_STATUS=$?
  fi
  RUNNER_PID=
  return "$HELPER_STATUS"
}

trap cleanup EXIT
trap interrupt HUP INT TERM

preflight() {
  command -v claude >/dev/null 2>&1 || die "Claude Code CLI was not found in PATH"
  command -v python3 >/dev/null 2>&1 || die "Python 3 was not found in PATH"
  [ -f "$RESULT_HELPER" ] || die "JSON result helper was not found: $RESULT_HELPER"
  run_helper auth --timeout 30 -- claude auth status || exit $?
}

preserve_failed_result() {
  [ -s "$TEMP_OUTPUT" ] || return 0
  case $OUTPUT_FILE in
    *.json) FAILED_OUTPUT=${OUTPUT_FILE%.json}.failed.json ;;
    *) FAILED_OUTPUT=$OUTPUT_FILE.failed.json ;;
  esac
  if ln -- "$TEMP_OUTPUT" "$FAILED_OUTPUT" 2>/dev/null; then
    printf '%s: Claude result failed; preserved at %s\n' "$PROGRAM" "$FAILED_OUTPUT" >&2
  else
    printf '%s: Claude result failed; could not preserve without overwriting %s\n' "$PROGRAM" "$FAILED_OUTPUT" >&2
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
    --role) [ "$#" -ge 2 ] || die "--role requires a value"; ROLE=$2; shift 2 ;;
    --model) [ "$#" -ge 2 ] || die "--model requires a value"; MODEL=$2; shift 2 ;;
    --expected-model) [ "$#" -ge 2 ] || die "--expected-model requires a value"; EXPECTED_MODEL=$2; shift 2 ;;
    --effort) [ "$#" -ge 2 ] || die "--effort requires a value"; EFFORT=$2; shift 2 ;;
    --workdir) [ "$#" -ge 2 ] || die "--workdir requires a value"; WORKDIR=$2; shift 2 ;;
    --prompt-file) [ "$#" -ge 2 ] || die "--prompt-file requires a value"; PROMPT_FILE=$2; shift 2 ;;
    --output-file) [ "$#" -ge 2 ] || die "--output-file requires a value"; OUTPUT_FILE=$2; shift 2 ;;
    --max-turns) [ "$#" -ge 2 ] || die "--max-turns requires a value"; MAX_TURNS=$2; shift 2 ;;
    --timeout) [ "$#" -ge 2 ] || die "--timeout requires a value"; TIMEOUT=$2; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown argument: $1" ;;
  esac
done

case $ROLE in plan|implement|review) ;; *) die "--role must be plan, implement, or review" ;; esac
case $EFFORT in low|medium|high|xhigh|max) ;; *) die "--effort must be low, medium, high, xhigh, or max" ;; esac
case $MODEL in ''|-*|*[!A-Za-z0-9._:/@-]*) die "--model contains unsupported characters" ;; esac
case $EXPECTED_MODEL in -*) die "--expected-model contains unsupported characters" ;; *[!A-Za-z0-9._:/@-]*) die "--expected-model contains unsupported characters" ;; esac
case $MAX_TURNS in ''|*[!0-9]*) die "--max-turns must be an integer from 1 to 100" ;; esac
[ "$MAX_TURNS" -ge 1 ] && [ "$MAX_TURNS" -le 100 ] || die "--max-turns must be an integer from 1 to 100"
case $TIMEOUT in ''|*[!0-9]*) die "--timeout must be a positive integer" ;; esac
[ "$TIMEOUT" -ge 1 ] || die "--timeout must be a positive integer"

for absolute_path in "$WORKDIR" "$PROMPT_FILE" "$OUTPUT_FILE"; do
  case $absolute_path in /*) ;; *) die "workdir, prompt file, and output file must use absolute paths" ;; esac
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
    ALLOWED_TOOLS=Read,Glob,Grep
    ROLE_PROMPT="Act as Atelier's architect. Stay read-only. Use only supplied repository context and return a bounded TaskSpec with unresolved decisions."
    ;;
  review)
    PERMISSION_MODE=plan
    ALLOWED_TOOLS=Read,Glob,Grep
    ROLE_PROMPT="Act as Atelier's independent reviewer. Stay read-only. The supplied context must provide the diff and test evidence. Return exactly one verdict: ship, fix-first, or rethink."
    ;;
  implement)
    PERMISSION_MODE=auto
    ALLOWED_TOOLS=
    ROLE_PROMPT="Act as Atelier's implementer. Modify only the files owned by the supplied TaskSpec, run its verification, and report changed files, commands, results, and residual risks."
    ;;
esac

umask 077
TEMP_OUTPUT=$(mktemp "$OUTPUT_FILE.tmp.XXXXXX") || die "could not allocate a temporary result file"
set -- claude -p --model "$MODEL" --effort "$EFFORT" \
  --permission-mode "$PERMISSION_MODE" --disallowedTools Agent \
  --append-system-prompt "$ROLE_PROMPT" --output-format json \
  --no-session-persistence --max-turns "$MAX_TURNS"
[ -z "$ALLOWED_TOOLS" ] || set -- "$@" --tools "$ALLOWED_TOOLS"

if ! run_helper invoke --timeout "$TIMEOUT" --cwd "$WORKDIR" \
  --input "$PROMPT_FILE" --output "$TEMP_OUTPUT" -- "$@"; then
  preserve_failed_result
  die "Claude $ROLE lane failed"
fi

if [ -n "$EXPECTED_MODEL" ]; then
  set -- validate --model "$MODEL" --expected-model "$EXPECTED_MODEL" "$TEMP_OUTPUT"
else
  set -- validate --model "$MODEL" "$TEMP_OUTPUT"
fi
if ! run_helper "$@"; then
  preserve_failed_result
  die "Claude result validation failed"
fi

if ! ln -- "$TEMP_OUTPUT" "$OUTPUT_FILE"; then
  die "could not publish result without overwriting: $OUTPUT_FILE"
fi
rm -f -- "$TEMP_OUTPUT"
TEMP_OUTPUT=
printf '%s\n' "$OUTPUT_FILE"
