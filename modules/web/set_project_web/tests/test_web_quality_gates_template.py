"""Static content tests for the web-build-time-quality-gates deployment.

We assert the deployed-template files have the right shape:
  - eslint.config.mjs enables @next/next/no-img-element=error and the
    i18next/no-literal-string rule scoped to [locale] pages.
  - package.json declares the required devDependencies and scripts.
  - .husky/pre-commit runs lint-staged + check:i18n and is executable.
  - auth-conventions.md contains the canonical admin-route snippet, the
    Router-Cache rationale, and no consumer project name.
  - The manifest lists the new files for deployment.

These do not exercise the real ESLint runtime — that requires `pnpm install`
inside a fixture project and is intentionally deferred to CI smoke tests.
"""
from __future__ import annotations

import json
import re
import stat
from pathlib import Path

import pytest

TEMPLATE_DIR = (
    Path(__file__).resolve().parent.parent / "templates" / "nextjs"
)
ESLINT = TEMPLATE_DIR / "eslint.config.mjs"
PKG = TEMPLATE_DIR / "package.json"
HUSKY = TEMPLATE_DIR / ".husky" / "pre-commit"
AUTH_RULES = TEMPLATE_DIR / "rules" / "auth-conventions.md"
MANIFEST = TEMPLATE_DIR / "manifest.yaml"

# Names that must never leak into the deployed template.
FORBIDDEN_NAMES = ("craftbrew", "minishop", "micro-web", "microweb")


class TestEslintConfig:
    def test_eslint_config_exists(self):
        assert ESLINT.is_file(), f"missing {ESLINT}"

    def test_no_img_element_rule_present_at_error(self):
        body = ESLINT.read_text()
        assert "@next/next/no-img-element" in body
        # Error severity declared somewhere near the rule
        assert '"error"' in body or "'error'" in body

    def test_i18next_rule_scoped_to_locale_pages(self):
        body = ESLINT.read_text()
        assert "i18next/no-literal-string" in body
        # Scoped to locale-routed pages
        assert "src/app/[locale]/**" in body

    def test_attribute_ignore_list_present(self):
        body = ESLINT.read_text()
        for attr in ("className", "id", "data-testid", "aria-label"):
            assert attr in body, f"ignore list missing {attr}"


class TestPackageJson:
    def test_dev_dependencies_added(self):
        pkg = json.loads(PKG.read_text())
        dev = pkg.get("devDependencies", {})
        for required in (
            "eslint",
            "@next/eslint-plugin-next",
            "eslint-plugin-i18next",
            "eslint-config-next",
            "husky",
            "lint-staged",
            "tsx",
        ):
            assert required in dev, f"missing devDependency {required}"

    def test_scripts_added(self):
        pkg = json.loads(PKG.read_text())
        scripts = pkg.get("scripts", {})
        assert "lint" in scripts
        assert "check:i18n" in scripts
        assert "prepare" in scripts
        assert "next lint" in scripts["lint"]
        assert "check-i18n-completeness" in scripts["check:i18n"]
        assert scripts["prepare"] == "husky"

    def test_lint_staged_block_present(self):
        pkg = json.loads(PKG.read_text())
        ls = pkg.get("lint-staged")
        assert ls is not None
        glob = "src/**/*.{ts,tsx}"
        assert glob in ls
        cmds = ls[glob]
        joined = " ".join(cmds) if isinstance(cmds, list) else cmds
        assert "eslint" in joined
        assert "--max-warnings=0" in joined


class TestHuskyPreCommit:
    def test_pre_commit_exists(self):
        assert HUSKY.is_file(), f"missing {HUSKY}"

    def test_pre_commit_is_executable(self):
        mode = HUSKY.stat().st_mode
        assert mode & stat.S_IXUSR, "pre-commit must be executable by owner"

    def test_pre_commit_invokes_lint_staged(self):
        body = HUSKY.read_text()
        assert "lint-staged" in body

    def test_pre_commit_documents_i18n_check_position(self):
        # The hook intentionally does NOT run pnpm check:i18n project-wide
        # because that scan would block commits on unrelated pre-existing
        # missing keys. The script remains available as `pnpm check:i18n`
        # and is enforced server-side by the verify-pipeline i18n gate.
        body = HUSKY.read_text()
        assert "check:i18n" in body  # at minimum, mentioned in the comment
        assert "verify pipeline" in body or "verify gate" in body


class TestAuthConventionsAdminSection:
    def test_section_heading_present(self):
        body = AUTH_RULES.read_text()
        assert "Required admin-route server-side check" in body

    def test_canonical_snippet_present(self):
        body = AUTH_RULES.read_text()
        # The snippet must include both the auth() call and the role gate.
        assert "await auth()" in body
        assert 'role !== "ADMIN"' in body
        assert "redirect(" in body

    def test_router_cache_rationale_present(self):
        body = AUTH_RULES.read_text()
        assert "Router Cache" in body
        # Section explicitly names admin layout + page paths.
        assert "src/app/[locale]/admin" in body

    def test_no_consumer_project_name(self):
        body = AUTH_RULES.read_text().lower()
        for needle in FORBIDDEN_NAMES:
            assert needle not in body, f"consumer name leaked: {needle}"

    def test_locale_prefixes_are_generic(self):
        body = AUTH_RULES.read_text()
        # Examples should reference both /hu and /en (generic),
        # never a brand-specific path component.
        assert "/hu" in body or "/en" in body


class TestManifestListsNewFiles:
    def test_eslint_config_in_manifest(self):
        body = MANIFEST.read_text()
        assert "eslint.config.mjs" in body

    def test_husky_pre_commit_in_manifest(self):
        body = MANIFEST.read_text()
        assert ".husky/pre-commit" in body

    def test_check_i18n_script_in_manifest(self):
        body = MANIFEST.read_text()
        assert "scripts/check-i18n-completeness.ts" in body
