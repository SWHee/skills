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

assert_file_not_contains() {
  name=$1
  file=$2
  pattern=$3
  if grep -F -- "$pattern" "$file" >/dev/null 2>&1; then
    fail "$name"
  else
    pass "$name"
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
  if [ -n "${FAKE_CLAUDE_AUTH_EXIT:-}" ]; then
    printf '%s\n' 'secret-auth-diagnostic' >&2
    exit "$FAKE_CLAUDE_AUTH_EXIT"
  fi
  if [ -n "${FAKE_CLAUDE_AUTH_RESULT_FILE:-}" ]; then
    cat "$FAKE_CLAUDE_AUTH_RESULT_FILE"
    exit 0
  fi
  if [ "${FAKE_CLAUDE_AUTH:-yes}" = "yes" ]; then
    printf '%s\n' '{"loggedIn":true,"authMethod":"test"}'
    exit 0
  fi
  printf '%s\n' '{"loggedIn":false,"authMethod":"none"}'
  exit 0
fi

if [ -n "${FAKE_CLAUDE_SLEEP:-}" ]; then
  sleep "$FAKE_CLAUDE_SLEEP"
fi

if [ -n "${FAKE_CLAUDE_ORPHAN_PID_FILE:-}" ]; then
  /bin/sh -c 'trap "" TERM; printf "%s\n" "$$" >"$FAKE_CLAUDE_ORPHAN_PID_FILE"; while :; do sleep 1; done' &
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
if [ -n "${FAKE_CLAUDE_RESULT_FILE:-}" ]; then
  cat "$FAKE_CLAUDE_RESULT_FILE"
  exit "${FAKE_CLAUDE_EXIT:-0}"
fi
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

AUTH_STRING_FIXTURE="$TEST_ROOT/auth-string.fixture"
printf '%s\n' '{"loggedIn":"true","authMethod":"test"}' >"$AUTH_STRING_FIXTURE"
assert_failure "authentication requires a JSON boolean" \
  env PATH="$FAKE_BIN:/usr/bin:/bin" FAKE_CLAUDE_AUTH_RESULT_FILE="$AUTH_STRING_FIXTURE" \
  /bin/sh "$ADAPTER" --check

AUTH_MALFORMED_FIXTURE="$TEST_ROOT/auth-malformed.fixture"
printf '%s\n' '{"loggedIn":true' >"$AUTH_MALFORMED_FIXTURE"
assert_failure "malformed authentication JSON is rejected" \
  env PATH="$FAKE_BIN:/usr/bin:/bin" FAKE_CLAUDE_AUTH_RESULT_FILE="$AUTH_MALFORMED_FIXTURE" \
  /bin/sh "$ADAPTER" --check

assert_failure "failed authentication command is rejected" \
  env PATH="$FAKE_BIN:/usr/bin:/bin" FAKE_CLAUDE_AUTH_EXIT=7 /bin/sh "$ADAPTER" --check
assert_file_not_contains "authentication failure redacts subprocess output" \
  "$TEST_ROOT/stderr" "secret-auth-diagnostic"

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

assert_file_contains "plan limits tools to read-only built-ins" "$TEST_ROOT/plan-args.txt" "Read,Glob,Grep"
if grep -Fx -- "Bash" "$TEST_ROOT/plan-args.txt" >/dev/null 2>&1; then
  fail "plan does not grant Bash"
else
  pass "plan does not grant Bash"
fi
assert_file_contains "review context requires supplied diff and test evidence" "$TEST_ROOT/review-args.txt" "diff and test evidence"

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

write_result() {
  fixture=$1
  shift
  printf '%s\n' "$*" >"$fixture"
}

run_fixture_failure() {
  name=$1
  fixture=$2
  output=$3
  shift 3
  assert_failure "$name" env "$COMMON_ENV" FAKE_CLAUDE_AUTH=yes \
    FAKE_CLAUDE_RESULT_FILE="$fixture" FAKE_CLAUDE_ARGS="$ARGS" \
    FAKE_CLAUDE_STDIN="$STDIN_CAPTURE" /bin/sh "$ADAPTER" \
    --role review --model sonnet --effort low --workdir "$TEST_ROOT" \
    --prompt-file "$PROMPT" --output-file "$output" "$@"
}

MALFORMED_FIXTURE="$TEST_ROOT/malformed.fixture"
printf '%s\n' '{"type":"result","is_error":false,"result":"done"' >"$MALFORMED_FIXTURE"
run_fixture_failure "malformed JSON result is rejected" "$MALFORMED_FIXTURE" "$TEST_ROOT/malformed.json"

ERROR_FIXTURE="$TEST_ROOT/error.fixture"
write_result "$ERROR_FIXTURE" '{"type":"result","subtype":"success","is_error":true,"result":"failed","modelUsage":{"claude-sonnet-4-6":{}}}'
run_fixture_failure "error result is rejected" "$ERROR_FIXTURE" "$TEST_ROOT/error.json"
assert_file_contains "failed nonempty result is preserved" "$TEST_ROOT/error.failed.json" '"result":"failed"'
assert_file_contains "failed result diagnostic names preservation path" "$TEST_ROOT/stderr" "$TEST_ROOT/error.failed.json"

EMPTY_RESULT_FIXTURE="$TEST_ROOT/empty-result.fixture"
write_result "$EMPTY_RESULT_FIXTURE" '{"type":"result","subtype":"success","is_error":false,"result":"   ","modelUsage":{"claude-sonnet-4-6":{}}}'
run_fixture_failure "empty result string is rejected" "$EMPTY_RESULT_FIXTURE" "$TEST_ROOT/empty-result.json"

WRONG_TYPE_FIXTURE="$TEST_ROOT/wrong-type.fixture"
write_result "$WRONG_TYPE_FIXTURE" '{"type":"assistant","is_error":false,"result":"done","modelUsage":{"claude-sonnet-4-6":{}}}'
run_fixture_failure "non-result top-level type is rejected" "$WRONG_TYPE_FIXTURE" "$TEST_ROOT/wrong-type.json"

BAD_SUBTYPE_FIXTURE="$TEST_ROOT/bad-subtype.fixture"
write_result "$BAD_SUBTYPE_FIXTURE" '{"type":"result","subtype":"error_max_turns","is_error":false,"result":"partial","modelUsage":{"claude-sonnet-4-6":{}}}'
run_fixture_failure "non-success result subtype is rejected" "$BAD_SUBTYPE_FIXTURE" "$TEST_ROOT/bad-subtype.json"

FORMATTED_FIXTURE="$TEST_ROOT/formatted.fixture"
printf '%s\n' '{' '  "type": "result",' '  "subtype": "success",' '  "is_error": false,' '  "result": "done",' '  "modelUsage": {"claude-sonnet-4-6": {}}' '}' >"$FORMATTED_FIXTURE"
FORMATTED_OUTPUT="$TEST_ROOT/formatted.json"
if env "$COMMON_ENV" FAKE_CLAUDE_AUTH=yes FAKE_CLAUDE_RESULT_FILE="$FORMATTED_FIXTURE" \
  FAKE_CLAUDE_ARGS="$ARGS" FAKE_CLAUDE_STDIN="$STDIN_CAPTURE" /bin/sh "$ADAPTER" \
  --role review --model sonnet --effort low --workdir "$TEST_ROOT" \
  --prompt-file "$PROMPT" --output-file "$FORMATTED_OUTPUT" \
  >"$TEST_ROOT/stdout" 2>"$TEST_ROOT/stderr"; then
  pass "formatted JSON with canonical modelUsage key is accepted"
else
  fail "formatted JSON with canonical modelUsage key is accepted"
fi

EXACT_FIXTURE="$TEST_ROOT/exact.fixture"
write_result "$EXACT_FIXTURE" '{"type":"result","subtype":"success","is_error":false,"result":"done","modelUsage":{"entry":{"canonicalModel":"claude-sonnet-4-6"}}}'
run_fixture_failure "full model ID rejects a different exact version" "$EXACT_FIXTURE" "$TEST_ROOT/exact.json" \
  --model claude-sonnet-4-5

BOUNDARY_FIXTURE="$TEST_ROOT/boundary.fixture"
write_result "$BOUNDARY_FIXTURE" '{"type":"result","subtype":"success","is_error":false,"result":"done","modelUsage":{"mysonnet-preview":{}}}'
run_fixture_failure "bare alias matching is boundary-safe" "$BOUNDARY_FIXTURE" "$TEST_ROOT/boundary.json"

CUSTOM_OUTPUT="$TEST_ROOT/custom.json"
if env "$COMMON_ENV" FAKE_CLAUDE_AUTH=yes FAKE_CLAUDE_RESULT_FILE="$EXACT_FIXTURE" \
  FAKE_CLAUDE_ARGS="$ARGS" FAKE_CLAUDE_STDIN="$STDIN_CAPTURE" /bin/sh "$ADAPTER" \
  --role review --model team-alias --expected-model claude-sonnet-4-6 \
  --effort low --workdir "$TEST_ROOT" --prompt-file "$PROMPT" \
  --output-file "$CUSTOM_OUTPUT" >"$TEST_ROOT/stdout" 2>"$TEST_ROOT/stderr"; then
  pass "custom alias accepts an explicit exact expected model"
else
  fail "custom alias accepts an explicit exact expected model"
fi

NO_CLOBBER_FAILED="$TEST_ROOT/no-clobber.failed.json"
printf '%s\n' 'keep failed evidence' >"$NO_CLOBBER_FAILED"
run_fixture_failure "existing failed result is not overwritten" "$ERROR_FIXTURE" "$TEST_ROOT/no-clobber.json"
assert_file_contains "existing failed result remains intact" "$NO_CLOBBER_FAILED" "keep failed evidence"

TIMEOUT_OUTPUT="$TEST_ROOT/timeout.json"
assert_failure "lane subprocess timeout is enforced" env "$COMMON_ENV" FAKE_CLAUDE_AUTH=yes \
  FAKE_CLAUDE_SLEEP=3 FAKE_CLAUDE_ARGS="$ARGS" FAKE_CLAUDE_STDIN="$STDIN_CAPTURE" \
  /bin/sh "$ADAPTER" --role review --model sonnet --effort low --timeout 1 \
  --workdir "$TEST_ROOT" --prompt-file "$PROMPT" --output-file "$TIMEOUT_OUTPUT"
assert_file_contains "timeout is diagnosed" "$TEST_ROOT/stderr" "timed out"

ORPHAN_PID_FILE="$TEST_ROOT/orphan.pid"
assert_failure "timeout also kills subprocess descendants" env "$COMMON_ENV" FAKE_CLAUDE_AUTH=yes \
  FAKE_CLAUDE_ORPHAN_PID_FILE="$ORPHAN_PID_FILE" FAKE_CLAUDE_ARGS="$ARGS" \
  FAKE_CLAUDE_STDIN="$STDIN_CAPTURE" /bin/sh "$ADAPTER" --role review \
  --model sonnet --effort low --timeout 1 --workdir "$TEST_ROOT" \
  --prompt-file "$PROMPT" --output-file "$TEST_ROOT/orphan.json"
ORPHAN_PID=$(sed -n '1p' "$ORPHAN_PID_FILE")
if kill -0 "$ORPHAN_PID" 2>/dev/null; then
  fail "timed-out subprocess descendant is gone"
  kill -KILL "$ORPHAN_PID" 2>/dev/null || true
else
  pass "timed-out subprocess descendant is gone"
fi

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
