"""Tests for set_orch.api.orchestration journal grouping with dynamic gates.

Regression context: the dashboard used a hardcoded `_GATES` tuple to group
journal entries. Profile-registered gates (design-fidelity, i18n_check,
lint, required-components) journaled `<name>_result` rows that the grouper
silently dropped. The dashboard then rendered every retry caused by those
gates as "retry · unknown" because there was no per-gate run history to
attribute it to.

These tests pin the discovery + grouping path so future profile gates
appear automatically without code changes here.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.api.orchestration import (
    _discover_gates_from_journal,
    _group_journal_by_gate,
)


def _entry(field, new, ts="2026-05-06T00:00:00+02:00"):
    return {"field": field, "new": new, "ts": ts}


class TestDiscoverGatesFromJournal:
    def test_finds_canonical_and_profile_gates(self):
        entries = [
            _entry("build_result", "pass"),
            _entry("design_fidelity_result", "fail"),
            _entry("i18n_check_result", "fail"),
        ]
        gates = _discover_gates_from_journal(entries)
        assert "build" in gates
        assert "design_fidelity" in gates
        assert "i18n_check" in gates

    def test_canonical_gates_appear_first(self):
        entries = [
            _entry("design_fidelity_result", "pass"),
            _entry("build_result", "pass"),
            _entry("i18n_check_result", "pass"),
            _entry("test_result", "pass"),
        ]
        gates = _discover_gates_from_journal(entries)
        # Canonical order preserved (build, test) before extras.
        assert gates.index("build") < gates.index("design_fidelity")
        assert gates.index("test") < gates.index("i18n_check")

    def test_excludes_non_gate_result_fields(self):
        entries = [
            _entry("build_result", "pass"),
            _entry("spec_coverage_result", "pass"),  # NOT a gate
        ]
        gates = _discover_gates_from_journal(entries)
        assert "build" in gates
        assert "spec_coverage" not in gates

    def test_ignores_non_result_fields(self):
        entries = [
            _entry("status", "running"),
            _entry("current_step", "fixing"),
            _entry("retry_context", "design fidelity failures..."),
            _entry("build_result", "pass"),
        ]
        gates = _discover_gates_from_journal(entries)
        assert gates == ("build",)

    def test_empty_journal_returns_empty(self):
        assert _discover_gates_from_journal([]) == ()


class TestGroupJournalByGate:
    def test_pairs_result_output_ms_for_profile_gate(self):
        ts = "2026-05-06T03:35:25.000+02:00"
        entries = [
            _entry("design_fidelity_result", "fail", ts=ts),
            _entry("design_fidelity_output", "skeleton mismatch", ts=ts),
            _entry("gate_design_fidelity_ms", 12345, ts=ts),
        ]
        grouped = _group_journal_by_gate(entries)
        assert "design_fidelity" in grouped
        runs = grouped["design_fidelity"]
        assert len(runs) == 1
        assert runs[0]["result"] == "fail"
        assert runs[0]["output"] == "skeleton mismatch"
        assert runs[0]["ms"] == 12345

    def test_multiple_runs_each_get_own_record(self):
        entries = [
            _entry("i18n_check_result", "fail", ts="2026-05-06T03:00:00+02:00"),
            _entry("i18n_check_result", "fail", ts="2026-05-06T03:10:00+02:00"),
            _entry("i18n_check_result", "pass", ts="2026-05-06T03:20:00+02:00"),
        ]
        grouped = _group_journal_by_gate(entries)
        runs = grouped["i18n_check"]
        assert len(runs) == 3
        assert [r["result"] for r in runs] == ["fail", "fail", "pass"]
        assert [r["run"] for r in runs] == [1, 2, 3]

    def test_canonical_and_profile_gates_coexist(self):
        ts = "2026-05-06T03:35:25.000+02:00"
        entries = [
            _entry("build_result", "pass", ts=ts),
            _entry("e2e_result", "pass", ts=ts),
            _entry("i18n_check_result", "fail", ts=ts),
            _entry("design_fidelity_result", "fail", ts=ts),
        ]
        grouped = _group_journal_by_gate(entries)
        assert set(grouped.keys()) == {"build", "e2e", "i18n_check", "design_fidelity"}

    def test_empty_gates_pruned_from_output(self):
        # Gates discovered but with no result entries should not appear.
        # (Currently impossible since discovery uses result entries, but
        # guard against future shape changes.)
        grouped = _group_journal_by_gate([])
        assert grouped == {}
