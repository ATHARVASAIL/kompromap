"""Export renderer tests (DOCX, PDF/HTML fallback)."""
from datetime import datetime, timezone

import pytest

from app.services.engagement_report import EngagementReport
from app.services.report_render import render_docx, render_html, render_json, render_markdown, render_pdf


def _minimal_report() -> EngagementReport:
    return EngagementReport(
        id="test-report",
        engagement_name="Test Engagement",
        client_name=None,
        generated_at=datetime.now(timezone.utc),
        summary={
            "total_findings": 2,
            "severity_counts": {"High": 1, "Low": 1},
            "chain_count": 0,
            "easiest_chain_cost": None,
            "findings_on_a_chain": 0,
            "entry_point_count": 0,
            "crown_jewel_count": 0,
            "total_nodes": 5,
            "findings_with_measured_complexity": 0,
        },
        scope={"assets": ["a1"], "services": [], "web_applications": [], "endpoints": [], "data_stores": []},
        chains=[],
        findings=[],
        remediation=[],
        caveats=["No attack chains identified."],
    )


class TestRenderMarkdown:
    def test_returns_string(self):
        out = render_markdown(_minimal_report())
        assert isinstance(out, str)

    def test_contains_title(self):
        out = render_markdown(_minimal_report())
        assert "Test Engagement" in out

    def test_contains_caveats(self):
        out = render_markdown(_minimal_report())
        assert "Caveats" in out


class TestRenderHtml:
    def test_returns_self_contained_html(self):
        out = render_html(_minimal_report())
        assert "<!doctype html>" in out.lower()
        assert "</html>" in out

    def test_contains_scoring_note(self):
        out = render_html(_minimal_report())
        assert "ease =" in out or "Scoring" in out


class TestRenderJson:
    def test_returns_dict(self):
        out = render_json(_minimal_report())
        assert isinstance(out, dict)

    def test_contains_summary(self):
        out = render_json(_minimal_report())
        assert "summary" in out
        assert out["summary"]["total_findings"] == 2


class TestRenderDocx:
    def test_returns_bytes(self):
        out = render_docx(_minimal_report())
        assert isinstance(out, bytes)
        assert len(out) > 0

    def test_is_valid_docx_zip(self):
        """DOCX is a ZIP file — verify the magic bytes."""
        out = render_docx(_minimal_report())
        assert out[:4] == b"PK\x03\x04"


class TestRenderPdf:
    def test_returns_bytes_and_format(self):
        out, fmt = render_pdf(_minimal_report())
        assert isinstance(out, bytes)
        assert len(out) > 0
        assert fmt in ("pdf", "html-fallback")

    def test_pdf_fallback_still_contains_content(self):
        """Even if WeasyPrint is unavailable, the fallback HTML has the report."""
        out, fmt = render_pdf(_minimal_report())
        if fmt == "html-fallback":
            assert "Test Engagement" in out.decode()
