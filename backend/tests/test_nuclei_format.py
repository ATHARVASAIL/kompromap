"""Nuclei output-format conformance.

Both bugs covered here were found by checking the parser against Nuclei's
own `nuclei-jsonschema.json` rather than against hand-written fixtures —
the fixtures matched my assumptions, so they passed while real scanner
output would have failed. Neither bug raised an error; they produced
quietly wrong data, which is the worst failure mode for a tool whose
output goes into a client report.
"""
import json

import pytest

from app.parsers.nuclei import _first_of, parse_nuclei_json
from app.services.cvss import parse_cvss_vector


def _jsonl(*records) -> bytes:
    return "\n".join(json.dumps(r) for r in records).encode()


def _record(**overrides) -> dict:
    base = {
        "template-id": "test-template",
        "info": {"name": "Test finding", "severity": "high"},
        "type": "http",
        "host": "https://target.test",
        "matched-at": "https://target.test/path",
    }
    base.update(overrides)
    return base


class TestCvssVectorForms:
    """Nuclei's schema documents `cvss-metrics` *without* the CVSS: prefix
    (`3.1/AV:N/...`), while many real templates include it. Requiring the
    prefix silently rejected genuine output and fell back to an assumed
    complexity."""

    def test_accepts_the_bare_form_from_nucleis_own_schema(self):
        assert parse_cvss_vector("3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H") is not None

    def test_accepts_the_prefixed_canonical_form(self):
        assert parse_cvss_vector("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H") is not None

    def test_both_forms_parse_to_the_same_metrics(self):
        bare = parse_cvss_vector("3.1/AV:N/AC:H/PR:H/UI:R/S:U/C:L/I:N/A:N")
        prefixed = parse_cvss_vector("CVSS:3.1/AV:N/AC:H/PR:H/UI:R/S:U/C:L/I:N/A:N")
        assert bare == prefixed

    @pytest.mark.parametrize("version", ["3.0", "3.1"])
    def test_accepts_both_v3_minor_versions(self, version):
        assert parse_cvss_vector(f"{version}/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H") is not None

    def test_still_rejects_cvss_v2(self):
        """v2 reuses AV:/AC: with different meanings — parsing one as v3
        would produce confidently wrong complexity."""
        assert parse_cvss_vector("AV:N/AC:L/Au:N/C:P/I:P/A:P") is None
        assert parse_cvss_vector("2.0/AV:N/AC:L/Au:N") is None

    def test_a_bare_vector_reaches_the_parsed_finding(self):
        result = parse_nuclei_json(
            _jsonl(
                _record(
                    info={
                        "name": "Log4Shell",
                        "severity": "critical",
                        "classification": {
                            "cvss-metrics": "3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H",
                            "cvss-score": 10,
                        },
                    }
                )
            )
        )
        assert result.findings[0].cvss_vector.startswith("3.1/")
        # PR:N in the vector must override the conservative auth default.
        assert result.findings[0].auth_required is False


class TestStringOrSlice:
    """`cwe-id` and `cve-id` are `StringOrSlice` in Nuclei's schema — a bare
    string or a list. Indexing a string yielded its first *character*:
    "CWE-79" became "C"."""

    @pytest.mark.parametrize(
        "value,expected",
        [
            ("CWE-79", "CWE-79"),
            (["CWE-79"], "CWE-79"),
            (["CWE-79", "CWE-80"], "CWE-79"),
            (["", "CWE-89"], "CWE-89"),
            ("  CWE-22  ", "CWE-22"),
            (None, None),
            ([], None),
            ("", None),
            ([None, 5], None),
        ],
    )
    def test_first_of_handles_every_shape(self, value, expected):
        assert _first_of(value) == expected

    def test_string_cwe_is_not_truncated_to_one_character(self):
        result = parse_nuclei_json(
            _jsonl(_record(info={"name": "SQLi", "severity": "high",
                                 "classification": {"cwe-id": "CWE-89"}}))
        )
        assert result.findings[0].cwe == "CWE-89"

    def test_list_cwe_takes_the_first_entry(self):
        result = parse_nuclei_json(
            _jsonl(_record(info={"name": "SQLi", "severity": "high",
                                 "classification": {"cwe-id": ["CWE-89", "CWE-564"]}}))
        )
        assert result.findings[0].cwe == "CWE-89"

    def test_string_cve_reaches_the_evidence(self):
        result = parse_nuclei_json(
            _jsonl(_record(info={"name": "RCE", "severity": "critical",
                                 "classification": {"cve-id": "CVE-2021-44228"}}))
        )
        assert "CVE-2021-44228" in result.findings[0].evidence


class TestAdditionalRealWorldFields:
    def test_records_when_the_matcher_did_not_fire(self):
        """`-mts` emits non-matching records too. Without noting this, a
        debugging artifact reads as a confirmed finding."""
        result = parse_nuclei_json(_jsonl(_record(**{"matcher-status": False})))
        assert "matcher did not fire" in result.findings[0].evidence

    def test_a_normal_match_is_not_flagged(self):
        result = parse_nuclei_json(_jsonl(_record(**{"matcher-status": True})))
        assert "did not fire" not in result.findings[0].evidence

    def test_captures_resolved_ip(self):
        result = parse_nuclei_json(_jsonl(_record(ip="203.0.113.11")))
        assert "203.0.113.11" in result.findings[0].evidence

    def test_captures_extracted_results(self):
        result = parse_nuclei_json(
            _jsonl(_record(**{"extracted-results": ["nginx/1.18.0", "php/7.4"]}))
        )
        assert "nginx/1.18.0" in result.findings[0].evidence

    def test_tolerates_a_full_production_record(self):
        """Every field a real Nuclei run emits, together."""
        result = parse_nuclei_json(
            _jsonl(
                {
                    "template": "http/cves/2021/CVE-2021-44228.yaml",
                    "template-url": "https://templates.nuclei.sh/public/CVE-2021-44228",
                    "template-id": "CVE-2021-44228",
                    "template-path": "/root/nuclei-templates/http/cves/2021/CVE-2021-44228.yaml",
                    "info": {
                        "name": "Apache Log4j2 JNDI RCE",
                        "author": ["pdteam"],
                        "tags": ["cve", "rce"],
                        "reference": ["https://nvd.nist.gov/vuln/detail/CVE-2021-44228"],
                        "severity": "critical",
                        "classification": {
                            "cve-id": "CVE-2021-44228",
                            "cwe-id": "CWE-502",
                            "cvss-metrics": "3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H",
                            "cvss-score": 10,
                            "epss-score": 0.97,
                            "cpe": "cpe:2.3:a:apache:log4j:*:*:*:*:*:*:*:*",
                        },
                        "metadata": {"max-request": 2, "verified": True},
                    },
                    "type": "http",
                    "host": "https://api.test",
                    "port": "443",
                    "scheme": "https",
                    "url": "https://api.test",
                    "matched-at": "https://api.test/api/v2/search",
                    "ip": "203.0.113.11",
                    "timestamp": "2026-08-03T15:24:13.456951+05:30",
                    "curl-command": "curl 'https://api.test/api/v2/search'",
                    "matcher-status": True,
                }
            )
        )
        assert len(result.findings) == 1
        f = result.findings[0]
        assert f.cwe == "CWE-502"
        assert f.cvss_score == 10.0
        assert f.cvss_vector == "3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H"
        assert f.auth_required is False
        assert not result.warnings
