"""Tests for set_orch.loop_prompt — action detection, prompt assembly."""

import json
import os
import sys
import tempfile
import shutil

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.loop_prompt import (
    detect_next_change_action,
    build_claude_prompt,
    get_spec_context,
    get_design_context,
    get_proposal_context,
    get_previous_iteration_summary,
)


@pytest.fixture
def tmp_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def wt(tmp_dir):
    wt = os.path.join(tmp_dir, "worktree")
    os.makedirs(os.path.join(wt, ".claude"))
    return wt


# ─── detect_next_change_action (targeted) ─────────────────────


class TestDetectTargeted:
    def test_no_change_dir_none(self, wt):
        os.makedirs(os.path.join(wt, "openspec", "changes"), exist_ok=True)
        assert detect_next_change_action(wt, "nonexistent") == "none"

    def test_archived_change_done(self, wt):
        archive_dir = os.path.join(
            wt, "openspec", "changes", "archive", "2024-01-01-my-change"
        )
        os.makedirs(archive_dir)
        assert detect_next_change_action(wt, "my-change") == "done"

    def test_no_tasks_ff(self, wt):
        change_dir = os.path.join(wt, "openspec", "changes", "my-change")
        os.makedirs(change_dir)
        assert detect_next_change_action(wt, "my-change") == "ff:my-change"

    def test_unchecked_tasks_apply(self, wt):
        change_dir = os.path.join(wt, "openspec", "changes", "my-change")
        os.makedirs(change_dir)
        with open(os.path.join(change_dir, "tasks.md"), "w") as f:
            f.write("- [x] Done\n- [ ] Pending\n")
        assert detect_next_change_action(wt, "my-change") == "apply:my-change"

    def test_all_checked_no_impl_apply(self, wt):
        """All tasks [x] but no implementation files in diff → apply (not done)."""
        change_dir = os.path.join(wt, "openspec", "changes", "my-change")
        os.makedirs(change_dir)
        with open(os.path.join(change_dir, "tasks.md"), "w") as f:
            f.write("- [x] Done\n- [x] Also done\n")
        # No git repo → _has_impl_files_in_diff returns False → apply
        assert detect_next_change_action(wt, "my-change") == "apply:my-change"

    def test_all_checked_with_impl_done(self, tmp_dir):
        """All tasks [x] AND impl files in git diff → done."""
        import subprocess

        wt = os.path.join(tmp_dir, "git-wt")
        os.makedirs(os.path.join(wt, ".claude"))
        subprocess.run(["git", "init", "-b", "main", wt], capture_output=True)
        subprocess.run(
            ["git", "-C", wt, "commit", "--allow-empty", "-m", "init"],
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", wt, "checkout", "-b", "change/my-change"],
            capture_output=True,
        )
        change_dir = os.path.join(wt, "openspec", "changes", "my-change")
        os.makedirs(change_dir)
        with open(os.path.join(change_dir, "tasks.md"), "w") as f:
            f.write("- [x] Done\n")
        os.makedirs(os.path.join(wt, "src"))
        with open(os.path.join(wt, "src", "app.tsx"), "w") as f:
            f.write("export default function App() {}\n")
        subprocess.run(["git", "-C", wt, "add", "-A"], capture_output=True)
        subprocess.run(
            ["git", "-C", wt, "commit", "-m", "impl"],
            capture_output=True,
        )
        assert detect_next_change_action(wt, "my-change") == "done"


# ─── detect_next_change_action (scan all) ─────────────────────


class TestDetectScanAll:
    def test_no_changes_none(self, wt):
        assert detect_next_change_action(wt) == "none"

    def test_single_change_ff(self, wt):
        change_dir = os.path.join(wt, "openspec", "changes", "feature-a")
        os.makedirs(change_dir)
        assert detect_next_change_action(wt) == "ff:feature-a"

    def test_single_change_apply(self, wt):
        change_dir = os.path.join(wt, "openspec", "changes", "feature-a")
        os.makedirs(change_dir)
        with open(os.path.join(change_dir, "tasks.md"), "w") as f:
            f.write("- [ ] Task\n")
        assert detect_next_change_action(wt) == "apply:feature-a"

    def test_all_checked_no_impl_apply(self, wt):
        """Scan-all: all tasks [x] but no impl files → apply."""
        change_dir = os.path.join(wt, "openspec", "changes", "feature-a")
        os.makedirs(change_dir)
        with open(os.path.join(change_dir, "tasks.md"), "w") as f:
            f.write("- [x] Done\n")
        # No git repo → no impl files → apply
        assert detect_next_change_action(wt) == "apply:feature-a"

    def test_all_checked_with_impl_done(self, tmp_dir):
        """Scan-all: all tasks [x] AND impl files → done."""
        import subprocess

        wt = os.path.join(tmp_dir, "git-wt")
        os.makedirs(os.path.join(wt, ".claude"))
        subprocess.run(["git", "init", "-b", "main", wt], capture_output=True)
        subprocess.run(
            ["git", "-C", wt, "commit", "--allow-empty", "-m", "init"],
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", wt, "checkout", "-b", "change/feature-a"],
            capture_output=True,
        )
        change_dir = os.path.join(wt, "openspec", "changes", "feature-a")
        os.makedirs(change_dir)
        with open(os.path.join(change_dir, "tasks.md"), "w") as f:
            f.write("- [x] Done\n")
        os.makedirs(os.path.join(wt, "src"))
        with open(os.path.join(wt, "src", "index.ts"), "w") as f:
            f.write("console.log('hi')\n")
        subprocess.run(["git", "-C", wt, "add", "-A"], capture_output=True)
        subprocess.run(
            ["git", "-C", wt, "commit", "-m", "impl"],
            capture_output=True,
        )
        assert detect_next_change_action(wt) == "done"

    def test_multiple_changes_first_unchecked(self, wt):
        """First change with unchecked tasks is returned."""
        d1 = os.path.join(wt, "openspec", "changes", "aaa-first")
        os.makedirs(d1)
        with open(os.path.join(d1, "tasks.md"), "w") as f:
            f.write("- [ ] Not started\n")
        d2 = os.path.join(wt, "openspec", "changes", "bbb-second")
        os.makedirs(d2)
        with open(os.path.join(d2, "tasks.md"), "w") as f:
            f.write("- [ ] Also not started\n")
        assert detect_next_change_action(wt) == "apply:aaa-first"

    def test_archive_skipped(self, wt):
        """Archive directory is excluded from scan."""
        archive = os.path.join(wt, "openspec", "changes", "archive")
        os.makedirs(archive)
        assert detect_next_change_action(wt) == "none"


# ─── build_claude_prompt ──────────────────────────────────────


class TestBuildClaudePrompt:
    def test_basic_prompt(self, wt):
        prompt = build_claude_prompt("do stuff", 1, 10, wt)
        assert "do stuff" in prompt
        assert "iteration 1 of 10" in prompt
        assert "first iteration" in prompt.lower()

    def test_openspec_ff_prompt(self, wt):
        os.makedirs(os.path.join(wt, "openspec", "changes", "my-change"))
        prompt = build_claude_prompt(
            "task", 1, 10, wt, done_criteria="openspec", target_change="my-change"
        )
        assert "/opsx:ff my-change" in prompt

    def test_openspec_apply_prompt(self, wt):
        change_dir = os.path.join(wt, "openspec", "changes", "my-change")
        os.makedirs(change_dir)
        with open(os.path.join(change_dir, "tasks.md"), "w") as f:
            f.write("- [ ] Task\n")
        prompt = build_claude_prompt(
            "task", 1, 10, wt, done_criteria="openspec", target_change="my-change"
        )
        assert "/opsx:apply my-change" in prompt

    def test_openspec_done_prompt(self, tmp_dir):
        import subprocess

        wt = os.path.join(tmp_dir, "git-wt")
        os.makedirs(os.path.join(wt, ".claude"))
        subprocess.run(["git", "init", "-b", "main", wt], capture_output=True)
        subprocess.run(
            ["git", "-C", wt, "commit", "--allow-empty", "-m", "init"],
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", wt, "checkout", "-b", "change/my-change"],
            capture_output=True,
        )
        change_dir = os.path.join(wt, "openspec", "changes", "my-change")
        os.makedirs(change_dir)
        with open(os.path.join(change_dir, "tasks.md"), "w") as f:
            f.write("- [x] Done\n")
        os.makedirs(os.path.join(wt, "src"))
        with open(os.path.join(wt, "src", "app.tsx"), "w") as f:
            f.write("export default function App() {}\n")
        subprocess.run(["git", "-C", wt, "add", "-A"], capture_output=True)
        subprocess.run(
            ["git", "-C", wt, "commit", "-m", "impl"],
            capture_output=True,
        )
        prompt = build_claude_prompt(
            "task", 1, 10, wt, done_criteria="openspec", target_change="my-change"
        )
        assert "ALL CHANGES COMPLETE" in prompt
        assert "Reflection" not in prompt

    def test_manual_tasks_instruction(self, wt):
        tf = os.path.join(wt, "tasks.md")
        with open(tf, "w") as f:
            f.write("- [?] 1.1 Manual task [confirm]\n- [ ] Auto task\n")
        prompt = build_claude_prompt("task", 1, 10, wt)
        assert "Manual Tasks" in prompt

    def test_team_instructions(self, wt):
        prompt = build_claude_prompt("task", 1, 10, wt, team_mode=True)
        assert "Agent Teams" in prompt

    def test_previous_commits(self, wt):
        state_file = os.path.join(wt, ".claude", "loop-state.json")
        with open(state_file, "w") as f:
            json.dump(
                {"iterations": [{"commits": ["abc123", "def456"]}]},
                f,
            )
        prompt = build_claude_prompt("task", 2, 10, wt)
        assert "abc123" in prompt


# ─── Context injection helpers ─────────────────────────────────


class TestContextHelpers:
    def test_spec_context(self, wt):
        specs_dir = os.path.join(wt, "openspec", "changes", "ch", "specs", "s1")
        os.makedirs(specs_dir)
        with open(os.path.join(specs_dir, "spec.md"), "w") as f:
            f.write("# Spec 1\nContent here.\n")
        result = get_spec_context(wt, "ch")
        assert "Spec 1" in result

    def test_spec_context_missing(self, wt):
        assert get_spec_context(wt, "nonexistent") == ""

    def test_design_context(self, wt):
        change_dir = os.path.join(wt, "openspec", "changes", "ch")
        os.makedirs(change_dir)
        with open(os.path.join(change_dir, "design.md"), "w") as f:
            f.write("# Design\n")
        assert "Design" in get_design_context(wt, "ch")

    def test_proposal_context(self, wt):
        change_dir = os.path.join(wt, "openspec", "changes", "ch")
        os.makedirs(change_dir)
        with open(os.path.join(change_dir, "proposal.md"), "w") as f:
            f.write("# Proposal\n")
        assert "Proposal" in get_proposal_context(wt, "ch")

    def test_previous_iteration_summary(self, wt):
        """Canonical path: .set/reflection.md (not blocked by Claude Code
        sensitive-file policy, unlike .claude/reflection.md)."""
        os.makedirs(os.path.join(wt, ".set"))
        with open(os.path.join(wt, ".set", "reflection.md"), "w") as f:
            f.write("- Found a bug\n- Fixed it\n")
        result = get_previous_iteration_summary(wt)
        assert "Found a bug" in result

    def test_previous_iteration_legacy_fallback(self, wt):
        """Fallback: pre-migration worktrees may still have .claude/reflection.md."""
        with open(os.path.join(wt, ".claude", "reflection.md"), "w") as f:
            f.write("- Legacy note\n")
        result = get_previous_iteration_summary(wt)
        assert "Legacy note" in result

    def test_previous_iteration_prefers_set_over_claude(self, wt):
        """If both exist, .set/reflection.md (canonical) wins."""
        os.makedirs(os.path.join(wt, ".set"))
        with open(os.path.join(wt, ".set", "reflection.md"), "w") as f:
            f.write("- canonical\n")
        with open(os.path.join(wt, ".claude", "reflection.md"), "w") as f:
            f.write("- legacy\n")
        result = get_previous_iteration_summary(wt)
        assert "canonical" in result
        assert "legacy" not in result

    def test_previous_iteration_missing(self, wt):
        assert get_previous_iteration_summary(wt) == ""


class TestPromptTextReflection:
    """Guard against regression to .claude/reflection.md — writes there are
    blocked by Claude Code's sensitive-file policy and caused ~100 permission
    denials per run in craftbrew-run-20260421-0025."""

    def test_prompt_instructs_set_reflection_path(self, wt):
        os.makedirs(os.path.join(wt, ".set"))
        prompt = build_claude_prompt(
            task="noop", iteration=1, max_iter=10, wt_path=wt,
        )
        assert ".set/reflection.md" in prompt, \
            "agent prompt must direct reflection write to .set/ (non-sensitive dir)"
        assert ".claude/reflection.md" not in prompt, \
            "agent prompt must NOT reference .claude/reflection.md (sensitive, blocked)"
