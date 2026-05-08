"""Tests for capability replan-domain-plan-reuse.

Validates the per-domain hash + reuse decision helpers introduced by
decompose-replan-optimization Tier A group 0b. The hash must be stable,
detect any input change, and the resolver must distinguish reusable vs
redecompose-needed domains correctly.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from set_orch.planner import (
    _compute_domain_input_hash,
    _save_domain_plans,
    load_saved_domain_plans,
    resolve_domain_reuse_decisions,
)


# ─── Hash function determinism ────────────────────────────────────────


def test_hash_is_deterministic():
    h1 = _compute_domain_input_hash("summary text", "[]", "{}", "conventions")
    h2 = _compute_domain_input_hash("summary text", "[]", "{}", "conventions")
    assert h1 == h2
    # sha256 hex is 64 chars.
    assert len(h1) == 64


def test_hash_changes_on_summary_change():
    h_a = _compute_domain_input_hash("summary A", "[]", "{}", "conv")
    h_b = _compute_domain_input_hash("summary B", "[]", "{}", "conv")
    assert h_a != h_b


def test_hash_changes_on_requirements_change():
    h_a = _compute_domain_input_hash("s", '{"r":1}', "{}", "conv")
    h_b = _compute_domain_input_hash("s", '{"r":2}', "{}", "conv")
    assert h_a != h_b


def test_hash_changes_on_brief_change():
    # Brief change should invalidate every domain hash — that's the point:
    # cross-domain coordination shifted.
    h_a = _compute_domain_input_hash("s", "[]", '{"prio":["a"]}', "conv")
    h_b = _compute_domain_input_hash("s", "[]", '{"prio":["b"]}', "conv")
    assert h_a != h_b


def test_hash_changes_on_conventions_change():
    h_a = _compute_domain_input_hash("s", "[]", "{}", "conv1")
    h_b = _compute_domain_input_hash("s", "[]", "{}", "conv2")
    assert h_a != h_b


# ─── Reuse decision ───────────────────────────────────────────────────


def _make_domain(name, summary="x", req_json="[]"):
    return {"name": name, "summary": summary, "requirements_json": req_json}


def test_resolve_reuse_all_match():
    brief = {}
    brief_json = json.dumps(brief, sort_keys=True)
    domains = [_make_domain("auth", "auth-summary"), _make_domain("cart", "cart-summary")]
    saved_hashes = {
        "auth": _compute_domain_input_hash("auth-summary", "[]", brief_json, "conv"),
        "cart": _compute_domain_input_hash("cart-summary", "[]", brief_json, "conv"),
    }
    domain_data = {"conventions": "conv", "domains": domains}
    reuse, redo = resolve_domain_reuse_decisions(saved_hashes, domain_data, brief)
    assert reuse == {"auth", "cart"}
    assert redo == set()


def test_resolve_reuse_mismatch_redecomposes():
    brief = {}
    brief_json = json.dumps(brief, sort_keys=True)
    domains = [_make_domain("auth", "auth-summary"), _make_domain("cart", "cart-CHANGED")]
    saved_hashes = {
        "auth": _compute_domain_input_hash("auth-summary", "[]", brief_json, "conv"),
        "cart": _compute_domain_input_hash("cart-original", "[]", brief_json, "conv"),
    }
    reuse, redo = resolve_domain_reuse_decisions(
        saved_hashes, {"conventions": "conv", "domains": domains}, brief,
    )
    assert reuse == {"auth"}
    assert redo == {"cart"}


def test_resolve_reuse_brief_change_invalidates_all():
    """A change in the planning brief invalidates every domain hash."""
    domains = [_make_domain("auth", "x"), _make_domain("cart", "y")]
    # Saved hashes computed against an old brief.
    old_brief_json = json.dumps({"phasing": "old"}, sort_keys=True)
    saved_hashes = {
        "auth": _compute_domain_input_hash("x", "[]", old_brief_json, "conv"),
        "cart": _compute_domain_input_hash("y", "[]", old_brief_json, "conv"),
    }
    new_brief = {"phasing": "new"}
    reuse, redo = resolve_domain_reuse_decisions(
        saved_hashes, {"conventions": "conv", "domains": domains}, new_brief,
    )
    assert reuse == set()
    assert redo == {"auth", "cart"}


def test_resolve_reuse_new_domain_in_redo():
    """A new domain in the current digest with no saved hash → redecompose."""
    brief = {}
    brief_json = json.dumps(brief, sort_keys=True)
    domains = [
        _make_domain("auth", "auth-summary"),
        _make_domain("payment", "payment-summary"),  # new domain
    ]
    saved_hashes = {
        "auth": _compute_domain_input_hash("auth-summary", "[]", brief_json, "conv"),
    }
    reuse, redo = resolve_domain_reuse_decisions(
        saved_hashes, {"conventions": "conv", "domains": domains}, brief,
    )
    assert reuse == {"auth"}
    assert redo == {"payment"}


def test_resolve_reuse_legacy_save_no_hashes():
    """Saved file from before capability lands: no hashes → redecompose all."""
    brief = {}
    domains = [_make_domain("auth"), _make_domain("cart")]
    saved_hashes: dict[str, str] = {}  # legacy save format
    reuse, redo = resolve_domain_reuse_decisions(
        saved_hashes, {"conventions": "conv", "domains": domains}, brief,
    )
    assert reuse == set()
    assert redo == {"auth", "cart"}


# ─── Persistence ──────────────────────────────────────────────────────


def test_save_writes_input_hashes(tmp_path, monkeypatch):
    # Stub LineagePaths so the save function lands the file in tmp_path.
    monkeypatch.chdir(tmp_path)

    class _StubLP:
        def __init__(self, *args, **kwargs):
            pass

        @classmethod
        def from_state_file(cls, state_file):
            return cls()

        @property
        def plan_domains_file(self):
            return str(tmp_path / "domains-plans.json")

    monkeypatch.setattr("set_orch.paths.LineagePaths", _StubLP)
    # Also patch SetRuntime to fail so the fallback path is used (and
    # writes into cwd which is tmp_path).
    import set_orch.paths as paths_mod
    monkeypatch.setattr(paths_mod, "SetRuntime", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("stub")))

    brief = {"phasing_strategy": "Foundation first"}
    domain_plans = {"auth": {"changes": [{"name": "auth-foundation"}]}}
    domain_data = {
        "conventions": "conv",
        "domains": [
            {"name": "auth", "summary": "auth-summary", "requirements_json": "[]"},
        ],
    }
    _save_domain_plans(brief, domain_plans, domain_data=domain_data)

    saved_path = tmp_path / "domains-plans.json"
    assert saved_path.is_file()
    saved = json.loads(saved_path.read_text())
    assert "domain_input_hashes" in saved
    assert "auth" in saved["domain_input_hashes"]
    assert len(saved["domain_input_hashes"]["auth"]) == 64  # sha256 hex
    assert saved["brief"] == brief
    assert saved["domain_plans"] == domain_plans


def test_save_without_domain_data_keeps_legacy_shape(tmp_path, monkeypatch):
    # Backwards compat: callers that don't pass domain_data still produce
    # a valid file (just with an empty hashes dict).
    monkeypatch.chdir(tmp_path)

    class _StubLP:
        def __init__(self, *args, **kwargs):
            pass

        @classmethod
        def from_state_file(cls, state_file):
            return cls()

        @property
        def plan_domains_file(self):
            return str(tmp_path / "domains-plans.json")

    monkeypatch.setattr("set_orch.paths.LineagePaths", _StubLP)
    import set_orch.paths as paths_mod
    monkeypatch.setattr(paths_mod, "SetRuntime", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("stub")))

    _save_domain_plans({}, {"auth": {}})
    saved = json.loads((tmp_path / "domains-plans.json").read_text())
    assert saved.get("domain_input_hashes") == {}


# ─── Loader ───────────────────────────────────────────────────────────


def test_load_returns_none_when_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # state_file path doesn't matter here; LineagePaths is stubbed below.
    state_file = str(tmp_path / "state.json")

    class _StubLP:
        def __init__(self, *args, **kwargs):
            pass

        @classmethod
        def from_state_file(cls, _):
            return cls()

        @property
        def plan_domains_file(self):
            return str(tmp_path / "missing-domains.json")

    monkeypatch.setattr("set_orch.paths.LineagePaths", _StubLP)
    assert load_saved_domain_plans(state_file) is None


def test_load_returns_none_on_malformed_json(tmp_path, monkeypatch, caplog):
    monkeypatch.chdir(tmp_path)
    domains_file = tmp_path / "broken.json"
    domains_file.write_text("not-json")
    state_file = str(tmp_path / "state.json")

    class _StubLP:
        def __init__(self, *args, **kwargs):
            pass

        @classmethod
        def from_state_file(cls, _):
            return cls()

        @property
        def plan_domains_file(self):
            return str(domains_file)

    monkeypatch.setattr("set_orch.paths.LineagePaths", _StubLP)
    import logging
    with caplog.at_level(logging.WARNING):
        result = load_saved_domain_plans(state_file)
    assert result is None
    assert any("could not load saved domain plans" in r.message for r in caplog.records)


def test_load_returns_three_tuple_on_success(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    domains_file = tmp_path / "saved.json"
    domains_file.write_text(json.dumps({
        "brief": {"x": 1},
        "domain_plans": {"auth": {"changes": []}},
        "domain_input_hashes": {"auth": "0" * 64},
        "created_at": "2026-05-08T10:00:00+02:00",
    }))
    state_file = str(tmp_path / "state.json")

    class _StubLP:
        def __init__(self, *args, **kwargs):
            pass

        @classmethod
        def from_state_file(cls, _):
            return cls()

        @property
        def plan_domains_file(self):
            return str(domains_file)

    monkeypatch.setattr("set_orch.paths.LineagePaths", _StubLP)
    result = load_saved_domain_plans(state_file)
    assert result is not None
    brief, plans, hashes = result
    assert brief == {"x": 1}
    assert plans == {"auth": {"changes": []}}
    assert hashes == {"auth": "0" * 64}
