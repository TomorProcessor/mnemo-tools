"""Tests for WebProjectType E2E test infrastructure discovery."""

import os
import tempfile
from pathlib import Path

import pytest

from set_project_web.project_type import WebProjectType


@pytest.fixture
def profile():
    return WebProjectType()


@pytest.fixture
def project_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


class TestGetTestInfraSummary:
    def test_empty_project(self, profile, project_dir):
        result = profile.get_test_infra_summary(project_dir)
        assert result == {"helper_files": [], "fixture_dirs": [], "patterns_detected": []}

    def test_finds_helper_files(self, profile, project_dir):
        helpers = project_dir / "tests" / "e2e" / "helpers"
        helpers.mkdir(parents=True)
        (helpers / "ws-mock.ts").write_text("export function createMockWs() {}")
        (helpers / "seed-data.ts").write_text("export function seedChat() {}")

        result = profile.get_test_infra_summary(project_dir)
        assert len(result["helper_files"]) == 2
        assert "tests/e2e/helpers/seed-data.ts" in result["helper_files"]
        assert "tests/e2e/helpers/ws-mock.ts" in result["helper_files"]

    def test_finds_fixture_dirs(self, profile, project_dir):
        fixtures = project_dir / "tests" / "e2e" / "fixtures"
        fixtures.mkdir(parents=True)
        (fixtures / "users").mkdir()
        (fixtures / "products").mkdir()

        result = profile.get_test_infra_summary(project_dir)
        assert len(result["fixture_dirs"]) == 3  # root + 2 subdirs

    def test_detects_route_websocket_pattern(self, profile, project_dir):
        e2e = project_dir / "tests" / "e2e"
        e2e.mkdir(parents=True)
        (e2e / "chat.spec.ts").write_text(
            "test('ws', async ({ page }) => { await page.routeWebSocket('**/ws', (ws) => {}); });"
        )

        result = profile.get_test_infra_summary(project_dir)
        assert any("routeWebSocket" in p for p in result["patterns_detected"])

    def test_detects_test_api_pattern(self, profile, project_dir):
        e2e = project_dir / "tests" / "e2e"
        e2e.mkdir(parents=True)
        (e2e / "data.spec.ts").write_text(
            "await page.request.post('/api/__test/seed', { data: {} });"
        )

        result = profile.get_test_infra_summary(project_dir)
        assert any("__test" in p for p in result["patterns_detected"])

    def test_detects_test_route_pages(self, profile, project_dir):
        test_route = project_dir / "app" / "__test" / "workspace"
        test_route.mkdir(parents=True)
        (test_route / "page.tsx").write_text("export default function Page() {}")

        result = profile.get_test_infra_summary(project_dir)
        assert any("Test route pages" in p for p in result["patterns_detected"])


class TestCheckTestInfraUsage:
    def test_no_warnings_without_helpers_dir(self, profile, project_dir):
        spec = project_dir / "tests" / "e2e" / "chat.spec.ts"
        spec.parent.mkdir(parents=True)
        spec.write_text("async function waitForWs(page: any) {}\ntest('x', async () => {});")

        result = profile.check_test_infra_usage(["tests/e2e/chat.spec.ts"], project_dir)
        assert result == []

    def test_warns_on_inline_helper_when_helpers_exist(self, profile, project_dir):
        helpers = project_dir / "tests" / "e2e" / "helpers"
        helpers.mkdir(parents=True)
        (helpers / "navigation.ts").write_text("export function navigate() {}")

        spec = project_dir / "tests" / "e2e" / "chat.spec.ts"
        spec.write_text(
            "async function waitForWsConnected(page: any) {\n"
            "  await page.waitForFunction(() => true);\n"
            "}\n"
            "function freshTarget(name: string) { return '/tmp/' + name; }\n"
        )

        result = profile.check_test_infra_usage(["tests/e2e/chat.spec.ts"], project_dir)
        assert len(result) == 2
        assert any("waitForWsConnected" in w for w in result)
        assert any("freshTarget" in w for w in result)

    def test_ignores_non_spec_files(self, profile, project_dir):
        helpers = project_dir / "tests" / "e2e" / "helpers"
        helpers.mkdir(parents=True)
        (helpers / "base.ts").write_text("export function base() {}")

        result = profile.check_test_infra_usage(["src/app/page.tsx"], project_dir)
        assert result == []

    def test_ignores_test_prefixed_functions(self, profile, project_dir):
        helpers = project_dir / "tests" / "e2e" / "helpers"
        helpers.mkdir(parents=True)
        (helpers / "base.ts").write_text("export function base() {}")

        spec = project_dir / "tests" / "e2e" / "chat.spec.ts"
        spec.write_text("function testHelper() { return true; }\n")

        result = profile.check_test_infra_usage(["tests/e2e/chat.spec.ts"], project_dir)
        assert result == []
