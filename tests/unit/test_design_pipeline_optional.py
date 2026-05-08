"""Tests for v0-design-optional: has_design_pipeline + conditional gate registration."""

from pathlib import Path

import pytest


class TestHasDesignPipelineBase:
    """ProjectType ABC base implementation."""

    def test_base_returns_false(self, tmp_path: Path):
        from set_orch.profile_types import ProjectType

        class Concrete(ProjectType):
            @property
            def info(self):
                raise NotImplementedError

            def get_templates(self):
                return []

        p = Concrete()
        assert p.has_design_pipeline(tmp_path) is False

    def test_base_returns_false_even_with_auto_directive(self, tmp_path: Path):
        from set_orch.profile_types import ProjectType

        class Concrete(ProjectType):
            @property
            def info(self):
                raise NotImplementedError

            def get_templates(self):
                return []

        p = Concrete()
        assert p.has_design_pipeline(tmp_path, {"design_pipeline": "auto"}) is False


class TestHasDesignPipelineWeb:
    """WebProjectType inherits has_design_pipeline, delegates to detect_design_source."""

    def test_true_when_v0_export_exists(self, tmp_path: Path):
        from set_project_web.project_type import WebProjectType

        (tmp_path / "v0-export").mkdir()
        profile = WebProjectType()
        assert profile.has_design_pipeline(tmp_path) is True

    def test_false_when_no_v0_export(self, tmp_path: Path):
        from set_project_web.project_type import WebProjectType

        profile = WebProjectType()
        assert profile.has_design_pipeline(tmp_path) is False

    def test_directive_none_overrides_detection(self, tmp_path: Path):
        from set_project_web.project_type import WebProjectType

        (tmp_path / "v0-export").mkdir()
        profile = WebProjectType()
        assert profile.has_design_pipeline(
            tmp_path, {"design_pipeline": "none"},
        ) is False

    def test_directive_auto_preserves_detection(self, tmp_path: Path):
        from set_project_web.project_type import WebProjectType

        (tmp_path / "v0-export").mkdir()
        profile = WebProjectType()
        assert profile.has_design_pipeline(
            tmp_path, {"design_pipeline": "auto"},
        ) is True

    def test_no_directive_defaults_to_auto(self, tmp_path: Path):
        from set_project_web.project_type import WebProjectType

        (tmp_path / "v0-export").mkdir()
        profile = WebProjectType()
        assert profile.has_design_pipeline(tmp_path, {}) is True
        assert profile.has_design_pipeline(tmp_path, None) is True


class TestDirectiveDefault:
    """design_pipeline appears in DIRECTIVE_DEFAULTS."""

    def test_default_is_auto(self):
        from set_orch.config import DIRECTIVE_DEFAULTS

        assert DIRECTIVE_DEFAULTS["design_pipeline"] == "auto"


class TestConditionalGateRegistration:
    """design-fidelity gate is only included when design pipeline is active."""

    def test_register_gates_includes_fidelity_with_v0(self, tmp_path: Path):
        from set_project_web.project_type import WebProjectType

        (tmp_path / "v0-export").mkdir()
        profile = WebProjectType()
        gates = profile.register_gates()
        names = [g.name for g in gates]
        assert "design-fidelity" in names

    def test_register_gates_always_includes_fidelity(self, tmp_path: Path):
        """register_gates() always returns design-fidelity — filtering
        happens at the verifier pipeline level, not in the profile."""
        from set_project_web.project_type import WebProjectType

        profile = WebProjectType()
        gates = profile.register_gates()
        names = [g.name for g in gates]
        assert "design-fidelity" in names
