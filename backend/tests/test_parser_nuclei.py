from pathlib import Path

from app.parsers.nuclei import parse_nuclei_json

FIXTURE = Path(__file__).parent / "fixtures" / "nuclei_sample.jsonl"


def test_parses_all_findings_from_jsonl():
    result = parse_nuclei_json(FIXTURE)
    assert len(result.findings) == 3


def test_uses_matched_at_as_target_ref():
    result = parse_nuclei_json(FIXTURE)
    targets = {f.target_ref for f in result.findings}
    assert "https://dev.client.com/.env" in targets
    assert "https://dev.client.com/api/v2/users" in targets


def test_explicit_cvss_score_is_used_when_present():
    result = parse_nuclei_json(FIXTURE)
    log4j = next(f for f in result.findings if "Log4j" in f.title)
    assert log4j.cvss_score == 10.0
    assert log4j.cwe == "CWE-502"
    assert log4j.exploit_public is True


def test_missing_cvss_score_falls_back_to_severity_midpoint():
    result = parse_nuclei_json(FIXTURE)
    info_finding = next(f for f in result.findings if "Nginx Detected" in f.title)
    assert info_finding.cvss_score == 0.0

    high_finding = next(f for f in result.findings if "Tokens Leakage" in f.title)
    assert high_finding.cvss_score == 8.0
    assert high_finding.exploit_public is True


def test_parses_json_array_form():
    array_text = "[" + ",".join(
        FIXTURE.read_text().strip().splitlines()
    ) + "]"
    result = parse_nuclei_json(array_text)
    assert len(result.findings) == 3


def test_skips_unparsable_lines_with_warning():
    bad = FIXTURE.read_text() + "\nnot valid json\n"
    result = parse_nuclei_json(bad)
    assert len(result.findings) == 3
    assert any("Skipped unparsable line" in w for w in result.warnings)
