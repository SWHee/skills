#!/bin/sh

set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ADAPTER="$SCRIPT_DIR/claude-lane.sh"
TEST_ROOT=$(mktemp -d "${TMPDIR:-/tmp}/atelier-claude-lane.XXXXXX")
trap 'rm -rf "$TEST_ROOT"' EXIT HUP INT TERM

FAILURES=0

pass() {
  printf 'ok - %s\n' "$1"
}

fail() {
  printf 'not ok - %s\n' "$1" >&2
  FAILURES=$((FAILURES + 1))
}

assert_failure() {
  name=$1
  shift
  if "$@" >"$TEST_ROOT/stdout" 2>"$TEST_ROOT/stderr"; then
    fail "$name"
  else
    pass "$name"
  fi
}

assert_file_contains() {
  name=$1
  file=$2
  pattern=$3
  if grep -F -- "$pattern" "$file" >/dev/null 2>&1; then
    pass "$name"
  else
    fail "$name"
  fi
}

if [ ! -f "$ADAPTER" ]; then
  printf 'not ok - adapter exists at %s\n' "$ADAPTER" >&2
  exit 1
fi

FAKE_BIN="$TEST_ROOT/bin"
mkdir -p "$FAKE_BIN"

cat >"$FAKE_BIN/claude" <<'EOF'
#!/bin/sh
set -eu

if [ "${1:-}" = "auth" ] && [ "${2:-}" = "status" ]; then
  if [ "${FAKE_CLAUDE_AUTH:-yes}" = "yes" ]; then
    printf '%s\n' '{"loggedIn":true,"authMethod":"test"}'
    exit 0
  fi
  printf '%s\n' '{"loggedIn":false,"authMethod":"none"}'
  exit 0
fi

: "${FAKE_CLAUDE_ARGS:?}"
: "${FAKE_CLAUDE_STDIN:?}"
printf '%s\n' "$@" >"$FAKE_CLAUDE_ARGS"
cat >"$FAKE_CLAUDE_STDIN"

requested_model=
previous=
for argument in "$@"; do
  if [ "$previous" = "--model" ]; then
    requested_model=$argument
    break
  fi
  previous=$argument
done

canonical_model=${FAKE_CLAUDE_CANONICAL:-$requested_model}
if [ -n "${FAKE_CLAUDE_SECOND_CANONICAL:-}" ]; then
  printf '{"type":"result","is_error":false,"modelUsage":{"first":{"canonicalModel":"%s"},"second":{"canonicalModel":"%s"}},"result":"done"}\n' \
    "$canonical_model" "$FAKE_CLAUDE_SECOND_CANONICAL"
else
  printf '{"type":"result","is_error":false,"modelUsage":{"%s":{"canonicalModel":"%s"}},"result":"done"}\n' \
    "$canonical_model" "$canonical_model"
fi
EOF
chmod +x "$FAKE_BIN/claude"

PROMPT="$TEST_ROOT/prompt.md"
OUTPUT="$TEST_ROOT/result.json"
ARGS="$TEST_ROOT/args.txt"
STDIN_CAPTURE="$TEST_ROOT/stdin.txt"
printf '%s\n' 'Objective: make the requested change.' >"$PROMPT"

assert_failure "missing Claude CLI fails preflight" \
  env PATH="$TEST_ROOT/empty-bin" /bin/sh "$ADAPTER" --check

assert_failure "logged-out Claude CLI fails preflight" \
  env PATH="$FAKE_BIN:/usr/bin:/bin" FAKE_CLAUDE_AUTH=no /bin/sh "$ADAPTER" --check
assert_file_contains "logged-out failure explains authentication" "$TEST_ROOT/stderr" "not authenticated"

if env PATH="$FAKE_BIN:/usr/bin:/bin" FAKE_CLAUDE_AUTH=yes /bin/sh "$ADAPTER" --check \
  >"$TEST_ROOT/stdout" 2>"$TEST_ROOT/stderr"; then
  pass "logged-in Claude CLI passes preflight"
else
  fail "logged-in Claude CLI passes preflight"
fi

COMMON_ENV="PATH=$FAKE_BIN:/usr/bin:/bin"
assert_failure "invalid role is rejected" \
  env "$COMMON_ENV" FAKE_CLAUDE_AUTH=yes /bin/sh "$ADAPTER" \
  --role repair --model sonnet --effort medium --workdir "$TEST_ROOT" \
  --prompt-file "$PROMPT" --output-file "$OUTPUT"

assert_failure "invalid effort is rejected" \
  env "$COMMON_ENV" FAKE_CLAUDE_AUTH=yes /bin/sh "$ADAPTER" \
  --role plan --model sonnet --effort extreme --workdir "$TEST_ROOT" \
  --prompt-file "$PROMPT" --output-file "$OUTPUT"

assert_failure "invalid maximum turns is rejected" \
  env "$COMMON_ENV" FAKE_CLAUDE_AUTH=yes /bin/sh "$ADAPTER" \
  --role plan --model sonnet --effort medium --max-turns 0 --workdir "$TEST_ROOT" \
  --prompt-file "$PROMPT" --output-file "$OUTPUT"

run_lane() {
  role=$1
  expected_mode=$2
  result="$TEST_ROOT/$role.json"
  args="$TEST_ROOT/$role-args.txt"
  stdin_capture="$TEST_ROOT/$role-stdin.txt"

  if env "$COMMON_ENV" FAKE_CLAUDE_AUTH=yes \
    FAKE_CLAUDE_ARGS="$args" FAKE_CLAUDE_STDIN="$stdin_capture" \
    /bin/sh "$ADAPTER" --role "$role" --model claude-sonnet-test \
    --effort high --max-turns 7 --workdir "$TEST_ROOT" \
    --prompt-file "$PROMPT" --output-file "$result" \
    >"$TEST_ROOT/stdout" 2>"$TEST_ROOT/stderr"; then
    pass "$role lane completes"
  else
    fail "$role lane completes"
    return
  fi

  assert_file_contains "$role forwards model" "$args" "claude-sonnet-test"
  assert_file_contains "$role forwards effort" "$args" "high"
  assert_file_contains "$role uses permission mode" "$args" "$expected_mode"
  assert_file_contains "$role requests JSON" "$args" "json"
  assert_file_contains "$role disables session persistence" "$args" "--no-session-persistence"
  assert_file_contains "$role disables nested Claude agents" "$args" "Agent"
  assert_file_contains "$role forwards maximum turns" "$args" "7"
  assert_file_contains "$role receives prompt on stdin" "$stdin_capture" "Objective: make the requested change."
  assert_file_contains "$role stores successful result" "$result" '"result":"done"'
}

run_lane plan plan
run_lane review plan
run_lane implement auto

MISMATCH_OUTPUT="$TEST_ROOT/mismatch.json"
assert_failure "silent model substitution is rejected" \
  env "$COMMON_ENV" FAKE_CLAUDE_AUTH=yes FAKE_CLAUDE_CANONICAL=claude-sonnet-test \
  FAKE_CLAUDE_ARGS="$ARGS" FAKE_CLAUDE_STDIN="$STDIN_CAPTURE" \
  /bin/sh "$ADAPTER" --role review --model haiku --effort low \
  --workdir "$TEST_ROOT" --prompt-file "$PROMPT" --output-file "$MISMATCH_OUTPUT"
if [ ! -e "$MISMATCH_OUTPUT" ]; then
  pass "mismatched model result is not published"
else
  fail "mismatched model result is not published"
fi

MIXED_OUTPUT="$TEST_ROOT/mixed.json"
assert_failure "mixed canonical model usage is rejected" \
  env "$COMMON_ENV" FAKE_CLAUDE_AUTH=yes FAKE_CLAUDE_CANONICAL=claude-haiku-test \
  FAKE_CLAUDE_SECOND_CANONICAL=claude-sonnet-test \
  FAKE_CLAUDE_ARGS="$ARGS" FAKE_CLAUDE_STDIN="$STDIN_CAPTURE" \
  /bin/sh "$ADAPTER" --role review --model haiku --effort low \
  --workdir "$TEST_ROOT" --prompt-file "$PROMPT" --output-file "$MIXED_OUTPUT"

printf '%s\n' 'preserve me' >"$OUTPUT"
assert_failure "existing output is not overwritten" \
  env "$COMMON_ENV" FAKE_CLAUDE_AUTH=yes \
  FAKE_CLAUDE_ARGS="$ARGS" FAKE_CLAUDE_STDIN="$STDIN_CAPTURE" \
  /bin/sh "$ADAPTER" --role plan --model sonnet --effort medium \
  --workdir "$TEST_ROOT" --prompt-file "$PROMPT" --output-file "$OUTPUT"
assert_file_contains "existing output remains intact" "$OUTPUT" "preserve me"

if [ "$FAILURES" -ne 0 ]; then
  printf '%s\n' "$FAILURES test(s) failed" >&2
  exit 1
fi

printf '%s\n' 'all claude-lane tests passed'
