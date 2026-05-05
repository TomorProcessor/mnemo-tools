"""Tests for the re-positioned + re-formatted review-learnings rendering.

These cover the three guarantees promised by the
`web-build-time-quality-gates` change:

1. _build_review_learnings() emits MUST/MUST NOT bullets per cluster.
2. The rendered section appears BEFORE `## Scope` in input.md.
3. Empty filtered learnings produce empty output (no header).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from set_orch.dispatcher import (
    DispatchContext,
    _build_input_content,
    _build_review_learnings,
)


def _write_findings(path: Path, entries: list[dict]) -> None:
    with open(path, "w") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")


class TestBuildReviewLearningsRendering:
    def test_empty_findings_returns_empty_string(self, tmp_path):
        findings = tmp_path / "review-findings.jsonl"
        findings.write_text("")
        out = _build_review_learnings(str(findings), exclude_change="x")
        assert out == ""

    def test_missing_file_returns_empty_string(self, tmp_path):
        out = _build_review_learnings(
            str(tmp_path / "nope.jsonl"), exclude_change="x"
        )
        assert out == ""

    def test_renders_must_must_not_for_clustered_finding(self, tmp_path):
        findings = tmp_path / "review-findings.jsonl"
        _write_findings(findings, [
            {
                "change": "foundation",
                "issues": [
                    {
                        "severity": "CRITICAL",
                        "summary": "Hardcoded string in JSX — missing i18n keys for nav",
                    },
                ],
            },
            {
                "change": "auth-core",
                "issues": [
                    {
                        "severity": "CRITICAL",
                        "summary": "raw <img> tag in admin sidebar",
                    },
                ],
            },
        ])
        # Run from tmp_path so the LineagePaths relative-path computation is well-defined.
        cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            out = _build_review_learnings(str(findings), exclude_change="newchange")
        finally:
            os.chdir(cwd)
        assert out  # non-empty
        assert "MUST:" in out
        assert "MUST NOT:" in out
        # i18n category must surface
        assert "useTranslations" in out or "i18n" in out.lower()
        # ui-image category must surface
        assert "next/image" in out or "Image" in out
        # The transition line must close the section so the agent can locate scope.
        assert "scope/requirements follow below" in out

    def test_excludes_own_findings(self, tmp_path):
        findings = tmp_path / "review-findings.jsonl"
        _write_findings(findings, [
            {
                "change": "myself",
                "issues": [
                    {"severity": "CRITICAL", "summary": "Hardcoded UI string"},
                ],
            },
        ])
        cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            out = _build_review_learnings(str(findings), exclude_change="myself")
        finally:
            os.chdir(cwd)
        assert out == ""

    def test_no_consumer_project_name_in_output(self, tmp_path):
        findings = tmp_path / "review-findings.jsonl"
        _write_findings(findings, [
            {
                "change": "auth-core",
                "issues": [
                    {"severity": "CRITICAL", "summary": "Missing auth check"},
                ],
            },
        ])
        cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            out = _build_review_learnings(str(findings), exclude_change="x")
        finally:
            os.chdir(cwd)
        forbidden = ("craftbrew", "minishop", "micro-web", "microweb")
        for needle in forbidden:
            assert needle.lower() not in out.lower()


class TestInputMdLearningsPosition:
    def test_learnings_appears_before_scope(self):
        ctx = DispatchContext(
            review_learnings="- **Hardcoded UI** flagged in foundation\n  - MUST: ...\n  - MUST NOT: ...",
            review_learnings_checklist="- some persistent learning",
        )
        out = _build_input_content(
            change_name="myc",
            scope="Implement the X feature.",
            roadmap_item="",
            ctx=ctx,
        )
        # Learnings header position must be before scope.
        learn_pos = out.find("KOTELEZO ELLENORZES")
        scope_pos = out.find("## Scope")
        assert learn_pos != -1, "learnings header missing from input.md"
        assert scope_pos != -1, "scope header missing"
        assert learn_pos < scope_pos, (
            f"learnings header at {learn_pos} must be before scope at {scope_pos}"
        )

    def test_no_learnings_section_when_empty(self):
        ctx = DispatchContext(
            review_learnings="",
            review_learnings_checklist="",
        )
        out = _build_input_content(
            change_name="myc",
            scope="Implement the X feature.",
            roadmap_item="",
            ctx=ctx,
        )
        assert "KOTELEZO ELLENORZES" not in out
        # Old "Lessons from Prior Changes" placement must also be gone.
        assert "Lessons from Prior Changes" not in out
        # Scope still present.
        assert "## Scope" in out

    def test_checklist_wrapped_in_autorefresh_markers_at_top(self):
        ctx = DispatchContext(
            review_learnings="",
            review_learnings_checklist="- persistent learning A",
        )
        out = _build_input_content(
            change_name="myc",
            scope="Implement the X feature.",
            roadmap_item="",
            ctx=ctx,
        )
        marker_start = out.find("<!-- AUTOREFRESH:review-learnings -->")
        marker_end = out.find("<!-- /AUTOREFRESH:review-learnings -->")
        scope_pos = out.find("## Scope")
        assert marker_start != -1
        assert marker_end != -1
        assert marker_start < marker_end < scope_pos, (
            "AUTOREFRESH markers must wrap the checklist and appear above scope"
        )

    def test_old_bottom_position_is_gone(self):
        ctx = DispatchContext(
            review_learnings="- a finding",
            review_learnings_checklist="",
        )
        out = _build_input_content(
            change_name="myc",
            scope="Implement the X feature.",
            roadmap_item="",
            ctx=ctx,
        )
        # The old "## Lessons from Prior Changes" header must not appear.
        assert "## Lessons from Prior Changes" not in out
