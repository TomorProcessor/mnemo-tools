"""Tests for e2e-gate-diagnostic-context: webServer log extraction."""

from set_project_web.gates import _extract_webserver_diagnostics


class TestExtractWebserverDiagnostics:

    def test_structured_section_from_wrapper(self):
        output = (
            "Error: Timed out waiting 60000ms from config.webServer.\n"
            "\n--- [run-e2e] webServer output (captured for diagnostics) ---\n"
            "[WebServer] Error: listen EADDRINUSE: address already in use :::3000\n"
            "[WebServer] at Server.setupListenHandle [as _listen2]\n"
            "--- end webServer output ---\n"
        )
        result = _extract_webserver_diagnostics(output)
        assert "## webServer Log" in result
        assert "EADDRINUSE" in result

    def test_playwright_webserver_prefix_lines(self):
        output = (
            "[WebServer] ready - started server on 0.0.0.0:3000\n"
            "[WebServer] Error: Cannot find module './server.ts'\n"
            "some other line\n"
            "[WebServer] Node.js v20.0.0\n"
            "Error: Process from config.webServer was not able to start.\n"
        )
        result = _extract_webserver_diagnostics(output)
        assert "## webServer Log" in result
        assert "Cannot find module" in result
        assert "some other line" not in result

    def test_no_webserver_lines_falls_back_to_raw_tail(self):
        output = "line1\nline2\nline3\nError: something broke\n"
        result = _extract_webserver_diagnostics(output)
        assert "## Raw Output (tail)" in result
        assert "something broke" in result

    def test_empty_output_returns_empty(self):
        assert _extract_webserver_diagnostics("") == ""

    def test_max_lines_respected(self):
        lines = [f"[WebServer] line {i}" for i in range(100)]
        output = "\n".join(lines)
        result = _extract_webserver_diagnostics(output, max_lines=10)
        assert "## webServer Log" in result
        assert "line 90" in result
        assert "line 89" not in result

    def test_structured_section_takes_priority_over_prefix_lines(self):
        output = (
            "[WebServer] early noise\n"
            "--- [run-e2e] webServer output (captured for diagnostics) ---\n"
            "[WebServer] THE REAL ERROR\n"
            "--- end webServer output ---\n"
        )
        result = _extract_webserver_diagnostics(output)
        assert "THE REAL ERROR" in result
        assert "early noise" not in result
