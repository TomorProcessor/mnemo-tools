#!/usr/bin/env bash
# Unit tests for lib/loop/tasks.sh — task detection modes
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/helpers.sh"

# Source dependencies
source "$SCRIPT_DIR/../../bin/set-common.sh"

# Source loop modules in order
LIB_DIR="$SCRIPT_DIR/../../lib/loop"
source "$LIB_DIR/state.sh"
source "$LIB_DIR/tasks.sh"
source "$LIB_DIR/prompt.sh"

# Create temp worktree structure for testing
TEST_WT=$(mktemp -d)
_GIT_WT=""
trap 'rm -rf "$TEST_WT" "$_GIT_WT"' EXIT

test_find_tasks_file_root() {
    echo "- [ ] task one" > "$TEST_WT/tasks.md"
    local result
    result=$(find_tasks_file "$TEST_WT")
    assert_contains "$result" "tasks.md" "finds root tasks.md"
    rm -f "$TEST_WT/tasks.md"
}

test_find_tasks_file_nested() {
    mkdir -p "$TEST_WT/openspec/changes/test-change"
    echo "- [ ] task one" > "$TEST_WT/openspec/changes/test-change/tasks.md"
    local result
    result=$(find_tasks_file "$TEST_WT")
    assert_contains "$result" "tasks.md" "finds nested tasks.md"
    rm -rf "$TEST_WT/openspec"
}

test_find_tasks_file_missing() {
    if find_tasks_file "$TEST_WT" 2>/dev/null; then
        echo "    FAIL: should return 1 when no tasks.md"
        return 1
    fi
}

test_check_tasks_done_complete() {
    cat > "$TEST_WT/tasks.md" <<'EOF'
- [x] task one
- [x] task two
EOF
    check_tasks_done "$TEST_WT"
    assert_equals "0" "$?" "all tasks complete"
    rm -f "$TEST_WT/tasks.md"
}

test_check_tasks_done_incomplete() {
    cat > "$TEST_WT/tasks.md" <<'EOF'
- [x] task one
- [ ] task two
- [x] task three
EOF
    if check_tasks_done "$TEST_WT" 2>/dev/null; then
        echo "    FAIL: should return 1 when tasks incomplete"
        return 1
    fi
    rm -f "$TEST_WT/tasks.md"
}

test_count_manual_tasks() {
    cat > "$TEST_WT/tasks.md" <<'EOF'
- [x] task one
- [?] 3.1 Set up API key [input:API_KEY]
- [ ] task three
- [?] 3.2 Verify webhook [confirm]
EOF
    local result
    result=$(count_manual_tasks "$TEST_WT")
    assert_equals "2" "$result" "counts 2 manual tasks"
    rm -f "$TEST_WT/tasks.md"
}

test_detect_next_change_action_ff() {
    mkdir -p "$TEST_WT/openspec/changes/my-change"
    # No tasks.md → needs ff
    local result
    result=$(detect_next_change_action "$TEST_WT" "my-change")
    assert_equals "ff:my-change" "$result" "needs ff when no tasks.md"
    rm -rf "$TEST_WT/openspec"
}

test_detect_next_change_action_apply() {
    mkdir -p "$TEST_WT/openspec/changes/my-change"
    echo "- [ ] implement something" > "$TEST_WT/openspec/changes/my-change/tasks.md"
    local result
    result=$(detect_next_change_action "$TEST_WT" "my-change")
    assert_equals "apply:my-change" "$result" "needs apply when tasks unchecked"
    rm -rf "$TEST_WT/openspec"
}

test_detect_next_change_action_done() {
    mkdir -p "$TEST_WT/openspec/changes/my-change"
    echo "- [x] implement something" > "$TEST_WT/openspec/changes/my-change/tasks.md"
    local result
    result=$(detect_next_change_action "$TEST_WT" "my-change")
    # Without a git repo, _has_impl_files_in_diff fails gracefully → "apply"
    # (safe direction: no git = no proof of impl = keep going)
    assert_equals "apply:my-change" "$result" "apply when no git repo (no impl proof)"
    rm -rf "$TEST_WT/openspec"
}

# ─── Tests requiring a real git repo (impl file check) ──────

_GIT_WT=""
_setup_git_wt() {
    _GIT_WT=$(mktemp -d)
    git -C "$_GIT_WT" init -b main --quiet
    git -C "$_GIT_WT" commit --allow-empty -m "init" --quiet
    mkdir -p "$_GIT_WT/openspec/changes/my-change"
}
_teardown_git_wt() {
    [[ -n "$_GIT_WT" ]] && rm -rf "$_GIT_WT"
    _GIT_WT=""
}

test_impl_check_all_checked_no_impl_returns_apply() {
    _setup_git_wt
    git -C "$_GIT_WT" checkout -b change/my-change --quiet
    echo "- [x] build component" > "$_GIT_WT/openspec/changes/my-change/tasks.md"
    git -C "$_GIT_WT" add -A && git -C "$_GIT_WT" commit -m "spec only" --quiet
    local result
    result=$(detect_next_change_action "$_GIT_WT" "my-change")
    assert_equals "apply:my-change" "$result" "apply when tasks [x] but no impl files in diff"
    _teardown_git_wt
}

test_impl_check_all_checked_with_impl_returns_done() {
    _setup_git_wt
    git -C "$_GIT_WT" checkout -b change/my-change --quiet
    echo "- [x] build component" > "$_GIT_WT/openspec/changes/my-change/tasks.md"
    mkdir -p "$_GIT_WT/src"
    echo "export default function App() {}" > "$_GIT_WT/src/app.tsx"
    git -C "$_GIT_WT" add -A && git -C "$_GIT_WT" commit -m "impl + spec" --quiet
    local result
    result=$(detect_next_change_action "$_GIT_WT" "my-change")
    assert_equals "done" "$result" "done when tasks [x] AND impl files exist"
    _teardown_git_wt
}

test_impl_check_scan_all_no_impl_returns_apply() {
    _setup_git_wt
    git -C "$_GIT_WT" checkout -b change/my-change --quiet
    echo "- [x] done" > "$_GIT_WT/openspec/changes/my-change/tasks.md"
    git -C "$_GIT_WT" add -A && git -C "$_GIT_WT" commit -m "spec only" --quiet
    local result
    result=$(detect_next_change_action "$_GIT_WT")
    assert_equals "apply:my-change" "$result" "scan-all: apply when no impl files"
    _teardown_git_wt
}

test_impl_check_scan_all_with_impl_returns_done() {
    _setup_git_wt
    git -C "$_GIT_WT" checkout -b change/my-change --quiet
    echo "- [x] done" > "$_GIT_WT/openspec/changes/my-change/tasks.md"
    mkdir -p "$_GIT_WT/app"
    echo "page" > "$_GIT_WT/app/page.tsx"
    git -C "$_GIT_WT" add -A && git -C "$_GIT_WT" commit -m "impl" --quiet
    local result
    result=$(detect_next_change_action "$_GIT_WT")
    assert_equals "done" "$result" "scan-all: done when impl files exist"
    _teardown_git_wt
}

run_tests
