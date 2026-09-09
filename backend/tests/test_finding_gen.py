"""Tests for the AI finding generator (Phase 4)."""
from __future__ import annotations

from unittest.mock import MagicMock

from app.services.ai.finding_gen import (
    FindingGenOutcome,
    FindingSeverity,
    generate_findings,
)


# ── Stub provider ───────────────────────────────────────────────────────

class StubProvider:
    """Minimal stand-in for AIProvider."""

    is_configured: bool = True

    def __init__(self, text: str = "", model: str = "stub"):
        self._text = text
        self._model = model
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str, **kw):
        self.calls.append((system, user))
        result = MagicMock()
        result.ok = True
        result.text = self._text
        result.model = self._model
        return result


# ── Service-level tests ──────────────────────────────────────────────────


class TestFindingGenService:
    def test_unconfigured_provider_returns_error(self):
        fake = MagicMock()
        fake.is_configured = False
        fake.complete.return_value = MagicMock(
            ok=False, failure_message="No AI provider is configured"
        )

        outcome = generate_findings("Asset", {"name": "test"}, provider=fake)
        assert not outcome.ok
        assert outcome.findings == []
        assert outcome.error is not None

    def test_valid_response_parsed_into_findings(self):
        text = (
            '{"findings": [{"title": "SQLi", "description": "desc", "severity": "high", '
            '"cwe": "CWE-89", "owasp_category": "A03:2021", "cvss_score": 7.5, '
            '"cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H", '
            '"exploit_public": true, "auth_required": false, "remediation": "fix it", '
            '"affected_assets": ["app"], "evidence": null, "tags": ["injection"], '
            '"assumptions": ["assumed unauthenticated"]}], '
            '"assumptions": ["assumed unauthenticated"], "context_summary": "ctx"}'
        )
        stub = StubProvider(text=text, model="test-model")
        outcome = generate_findings("Asset", {"name": "test"}, provider=stub)

        assert outcome.ok
        assert len(outcome.findings) == 1
        assert outcome.findings[0].title == "SQLi"
        assert outcome.findings[0].severity == FindingSeverity.HIGH
        assert outcome.findings[0].cwe == "CWE-89"
        assert outcome.findings[0].cvss_score == 7.5
        assert outcome.model == "test-model"

    def test_malformed_response_returns_error(self):
        stub = StubProvider(text="Sorry, I cannot help with that.")
        outcome = generate_findings("Asset", {"name": "test"}, provider=stub)
        assert not outcome.ok
        assert "format" in outcome.error.lower()

    def test_empty_findings_list_is_ok(self):
        text = '{"findings": [], "assumptions": ["insufficient context"], "context_summary": ""}'
        stub = StubProvider(text=text)
        outcome = generate_findings("Asset", {"name": "test"}, provider=stub)
        assert outcome.ok
        assert outcome.findings == []

    def test_cvss_score_coerced_from_percentage(self):
        text = (
            '{"findings": [{"title": "X", "description": "d", "severity": "info", '
            '"cvss_score": "87%", "remediation": "r", "affected_assets": []}], '
            '"assumptions": [], "context_summary": ""}'
        )
        outcome = generate_findings("Asset", {"name": "test"}, provider=StubProvider(text=text))
        assert outcome.findings[0].cvss_score == 0.87

    def test_cvss_score_out_of_range_rejected(self):
        text = (
            '{"findings": [{"title": "X", "description": "d", "severity": "info", '
            '"cvss_score": "999", "remediation": "r", "affected_assets": []}], '
            '"assumptions": [], "context_summary": ""}'
        )
        outcome = generate_findings("Asset", {"name": "test"}, provider=StubProvider(text=text))
        assert outcome.findings[0].cvss_score is None

    def test_list_fields_coerced_from_string(self):
        text = (
            '{"findings": [{"title": "X", "description": "d", "severity": "info", '
            '"tags": "web", "affected_assets": "app1", "assumptions": "a", '
            '"remediation": "r"}], "assumptions": [], "context_summary": ""}'
        )
        outcome = generate_findings("Asset", {"name": "test"}, provider=StubProvider(text=text))
        f = outcome.findings[0]
        assert f.tags == ["web"]
        assert f.affected_assets == ["app1"]
        assert f.assumptions == ["a"]

    def test_empty_response_text_returns_error(self):
        stub = StubProvider(text="")
        outcome = generate_findings("Asset", {"name": "test"}, provider=stub)
        assert not outcome.ok

    def test_provider_failure_returns_error(self):
        fake = MagicMock()
        fake.is_configured = True
        fake.complete.return_value = MagicMock(ok=False, failure_message="timeout")

        outcome = generate_findings("Asset", {"name": "test"}, provider=fake)
        assert not outcome.ok

    def test_critical_severity_parsed(self):
        text = (
            '{"findings": [{"title": "RCE", "description": "remote code execution", '
            '"severity": "critical", "remediation": "patch now", "affected_assets": []}], '
            '"assumptions": [], "context_summary": ""}'
        )
        outcome = generate_findings("Asset", {"name": "test"}, provider=StubProvider(text=text))
        assert outcome.findings[0].severity == FindingSeverity.CRITICAL

    def test_target_assets_passed_to_prompt(self):
        stub = StubProvider(text='{"findings": [], "assumptions": [], "context_summary": ""}')
        generate_findings("Asset", {"name": "test"}, target_assets=["app1", "app2"], provider=stub)
        assert len(stub.calls) == 1
        system, user = stub.calls[0]
        assert "app1" in user
        assert "app2" in user

    def test_no_target_assets_omitted_from_prompt(self):
        stub = StubProvider(text='{"findings": [], "assumptions": [], "context_summary": ""}')
        generate_findings("Asset", {"name": "test"}, provider=stub)
        assert len(stub.calls) == 1
        _, user = stub.calls[0]
        assert "Additional target context" not in user
