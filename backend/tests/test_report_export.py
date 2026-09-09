"""Tests for DOCX/PDF report export."""
from __future__ import annotations

import json

import pytest

from app.services.engagement_report import build_engagement_report
from app.services.report_export import render_report_docx, render_report_pdf


SAMPLE_REPORT = {
    "engagement_name": "test-engagement",
    "summary": {
        "finding_count": 3,
        "confirmed": 1,
        "unverified": 2,
        "false_positives": 0,
        "avg_cvss": 6.5,
        "attack_path_count": 1,
        "findings_by_severity": {
            "Critical": 1,
            "High": 1,
            "Medium": 1,
        },
    },
    "caveats": ["Complexity is assumed for some findings."],
    "remediation": [
        {
            "rank": 1,
            "title": "Fix the SQL injection",
            "severity": "Critical",
            "breaks_chain": True,
            "rationale": ["Blocks the cheapest path"],
        }
    ],
    "chains": [
        {
            "rank": 1,
            "entry_point": "10.0.0.1",
            "crown_jewel": "db.internal",
            "total_cost": 0.35,
            "steps": [
                {"node_type": "Finding", "title": "SQLi", "cost": 0.35},
                {"node_type": "Credential", "title": "admin creds", "cost": 0.0},
            ],
        }
    ],
    "findings": [
        {
            "title": "SQL Injection",
            "severity": "Critical",
            "cwe": "CWE-89",
            "cvss_score": 9.8,
            "description": "SQL injection in login form.",
            "remediation": "Use parameterised queries.",
        }
    ],
}


class TestDocxExport:
    def test_returns_bytes(self):
        result = render_report_docx(SAMPLE_REPORT)
        assert isinstance(result, bytes)
        assert len(result) > 0
        # DOCX files start with PK (ZIP)
        assert result[:2] == b"PK"

    def test_contains_engagement_name(self):
        result = render_report_docx(SAMPLE_REPORT)
        text = result.decode("latin-1", errors="ignore")
        assert "test-engagement" in text


class TestPdfExport:
    def test_returns_bytes(self):
        result = render_report_pdf(SAMPLE_REPORT)
        assert isinstance(result, bytes)
        assert len(result) > 0
        # PDF files start with %PDF
        assert result[:4] == b"%PDF"

    def test_contains_engagement_name(self):
        result = render_report_pdf(SAMPLE_REPORT)
        text = result.decode("latin-1", errors="ignore")
        assert "test-engagement" in text

    def test_contains_findings(self):
        result = render_report_pdf(SAMPLE_REPORT)
        text = result.decode("latin-1", errors="ignore")
        assert "SQL Injection" in text
