"""Tests for capability planner-strategy-routing.

Validates the serial-by-default strategy router introduced by
decompose-replan-optimization: directive precedence, the auto threshold
rule, the pure-Python token estimator, and the canonical block ordering.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest import mock

import pytest

from set_orch.planner import (
    SINGLE_CALL_MAX_INPUT_TOKENS_DEFAULT,
    estimate_flat_prompt_tokens,
    _resolve_planner_strategy,
)


# ─── Token estimator ──────────────────────────────────────────────────


def test_estimator_returns_int_with_no_digest_dir():
    # AC-79: missing digest is graceful, not an exception.
    est = estimate_flat_prompt_tokens("/nonexistent/path", None)
    assert isinstance(est, int)
    # Just the fixed overhead (no files), divided by chars/token.
    assert est > 0
    assert est < 10_000  # safely below threshold; only fixed overhead


def test_estimator_sums_digest_files(tmp_path: Path):
    # AC-78: estimator reads conventions, requirements, deps, AMBs, domains.
    digest = tmp_path / "digest"
    digest.mkdir()
    (digest / "conventions.json").write_text("x" * 1500)
    (digest / "requirements.json").write_text("x" * 6000)
    (digest / "dependencies.json").write_text("x" * 1000)
    (digest / "ambiguities.json").write_text("x" * 500)
    (digest / "index.json").write_text("x" * 200)
    (digest / "domains").mkdir()
    (digest / "domains" / "auth.md").write_text("x" * 1500)
    (digest / "domains" / "cart.md").write_text("x" * 1500)

    est = estimate_flat_prompt_tokens(str(digest), None)
    # Total chars: 1500 + 6000 + 1000 + 500 + 200 + 3000 + ~9500 overhead
    # ≈ 21700 chars / 3.5 ≈ 6200 tokens. Allow tolerance.
    assert 5_000 < est < 8_000


def test_estimator_includes_replan_context(tmp_path: Path):
    # AC-80: replan_ctx adds to the estimate.
    digest = tmp_path / "digest"
    digest.mkdir()
    base = estimate_flat_prompt_tokens(str(digest), None)
    big_ctx = {"completed": ["a"] * 100, "memory": "x" * 5000}
    with_ctx = estimate_flat_prompt_tokens(str(digest), big_ctx)
    assert with_ctx > base


def test_estimator_handles_missing_files(tmp_path: Path):
    # AC-79: per-file missing is non-fatal.
    digest = tmp_path / "digest"
    digest.mkdir()
    # Only one file present; rest missing.
    (digest / "requirements.json").write_text("x" * 1000)
    est = estimate_flat_prompt_tokens(str(digest), None)
    assert est > 0


def test_estimator_does_not_invoke_subprocess(tmp_path: Path, monkeypatch):
    # AC-78: estimator MUST NOT call any subprocess / Claude.
    import subprocess
    called = []
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: called.append(a))
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: called.append(a))
    digest = tmp_path / "digest"
    digest.mkdir()
    (digest / "requirements.json").write_text("x" * 1000)
    estimate_flat_prompt_tokens(str(digest), None)
    assert called == []


# ─── Strategy resolution ──────────────────────────────────────────────


def _isolate_env(monkeypatch):
    """Remove env override so default/yaml/state win."""
    monkeypatch.delenv("SET_ORCH_PLANNER_STRATEGY", raising=False)


def test_default_resolves_to_auto_then_serial_for_small_digest(
    tmp_path: Path, monkeypatch,
):
    # AC-71: no directive set → auto rule → serial for small digest.
    _isolate_env(monkeypatch)
    monkeypatch.chdir(tmp_path)
    digest = tmp_path / "digest"
    digest.mkdir()
    (digest / "requirements.json").write_text("x" * 1000)

    chosen, debug = _resolve_planner_strategy(str(digest), None)
    assert chosen == "serial"
    assert debug["source"] == "default"
    assert debug["raw_directive"] == "auto"
    assert debug["estimated_tokens"] < debug["threshold"]


def test_auto_routes_to_parallel_above_threshold(tmp_path: Path, monkeypatch):
    # AC-75: auto + estimate above threshold → parallel.
    _isolate_env(monkeypatch)
    monkeypatch.chdir(tmp_path)
    digest = tmp_path / "digest"
    digest.mkdir()
    # 145k tokens × 3.5 chars/token = ~507k chars of file data.
    (digest / "requirements.json").write_text("x" * 600_000)

    chosen, debug = _resolve_planner_strategy(str(digest), None)
    assert chosen == "parallel"
    assert debug["estimated_tokens"] > debug["threshold"]


def test_env_override_forces_serial(tmp_path: Path, monkeypatch):
    # AC-72: explicit `serial` regardless of size.
    monkeypatch.setenv("SET_ORCH_PLANNER_STRATEGY", "serial")
    monkeypatch.chdir(tmp_path)
    digest = tmp_path / "digest"
    digest.mkdir()
    (digest / "requirements.json").write_text("x" * 600_000)  # huge

    chosen, debug = _resolve_planner_strategy(str(digest), None)
    assert chosen == "serial"
    assert debug["source"] == "env"


def test_env_override_forces_parallel(tmp_path: Path, monkeypatch):
    # AC-73: explicit `parallel` regardless of size.
    monkeypatch.setenv("SET_ORCH_PLANNER_STRATEGY", "parallel")
    monkeypatch.chdir(tmp_path)
    digest = tmp_path / "digest"
    digest.mkdir()
    (digest / "requirements.json").write_text("x" * 100)  # tiny

    chosen, debug = _resolve_planner_strategy(str(digest), None)
    assert chosen == "parallel"
    assert debug["source"] == "env"


def test_orchestration_yaml_strategy_directive(tmp_path: Path, monkeypatch):
    # AC-71/AC-77: orchestration.yaml::planner.strategy is honoured;
    # threshold override also flows through.
    _isolate_env(monkeypatch)
    monkeypatch.chdir(tmp_path)
    yaml_path = tmp_path / "orchestration.yaml"
    yaml_path.write_text(
        "planner:\n"
        "  strategy: auto\n"
        "  single_call_max_input_tokens: 5000\n",
        encoding="utf-8",
    )
    digest = tmp_path / "digest"
    digest.mkdir()
    (digest / "requirements.json").write_text("x" * 30_000)  # ~8.5k tokens

    chosen, debug = _resolve_planner_strategy(str(digest), None)
    # 8.5k tokens > 5k threshold → parallel
    assert chosen == "parallel"
    assert "orchestration.yaml" in debug["source"]
    assert debug["threshold"] == 5_000


def test_unknown_directive_falls_back_to_auto(tmp_path: Path, monkeypatch):
    # Invalid value → auto with WARNING (not exception).
    monkeypatch.setenv("SET_ORCH_PLANNER_STRATEGY", "garbage")
    monkeypatch.chdir(tmp_path)
    digest = tmp_path / "digest"
    digest.mkdir()
    chosen, debug = _resolve_planner_strategy(str(digest), None)
    assert chosen == "serial"  # small digest → auto resolves to serial


def test_threshold_default_120k():
    # AC-77: default threshold is 120k.
    assert SINGLE_CALL_MAX_INPUT_TOKENS_DEFAULT == 120_000


def test_decision_is_deterministic(tmp_path: Path, monkeypatch):
    # AC-74: the auto decision is deterministic for the same input.
    _isolate_env(monkeypatch)
    monkeypatch.chdir(tmp_path)
    digest = tmp_path / "digest"
    digest.mkdir()
    (digest / "requirements.json").write_text("x" * 50_000)

    runs = [_resolve_planner_strategy(str(digest), None) for _ in range(5)]
    chosen_set = {r[0] for r in runs}
    est_set = {r[1]["estimated_tokens"] for r in runs}
    assert len(chosen_set) == 1
    assert len(est_set) == 1


def test_legacy_min_reqs_constant_removed():
    # AC-81: DOMAIN_PARALLEL_MIN_REQS heuristic is removed.
    import set_orch.planner as planner
    assert not hasattr(planner, "DOMAIN_PARALLEL_MIN_REQS")
