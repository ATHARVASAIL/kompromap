from pathlib import Path

from app.parsers.burp import parse_burp_zap_xml

BURP_FIXTURE = Path(__file__).parent / "fixtures" / "burp_sample.xml"
ZAP_FIXTURE = Path(__file__).parent / "fixtures" / "zap_sample.xml"


def test_detects_burp_format_and_parses_all_issues():
    result = parse_burp_zap_xml(BURP_FIXTURE)
    assert result.source_tool == "burp"
    assert len(result.findings) == 3


def test_burp_creates_one_endpoint_per_unique_host_path():
    result = parse_burp_zap_xml(BURP_FIXTURE)
    paths = {e.path for e in result.endpoints}
    assert paths == {"/admin/login", "/api/v2/users/{id}", "/static/app.js"}
    assert all(e.asset_name == "dev.client.com" for e in result.endpoints)


def test_burp_severity_maps_to_approximate_score():
    result = parse_burp_zap_xml(BURP_FIXTURE)
    xss = next(f for f in result.findings if "Cross-site scripting" in f.title)
    assert xss.cvss_score == 8.0
    info = next(f for f in result.findings if "Cacheable" in f.title)
    assert info.cvss_score == 0.0


def test_detects_zap_format_and_parses_all_alerts():
    result = parse_burp_zap_xml(ZAP_FIXTURE)
    assert result.source_tool == "zap"
    assert len(result.findings) == 3


def test_zap_extracts_path_from_full_uri():
    result = parse_burp_zap_xml(ZAP_FIXTURE)
    paths = {e.path for e in result.endpoints}
    assert "/search" in paths
    assert "/account/settings" in paths
    assert all(e.asset_name == "dev.client.com" for e in result.endpoints)


def test_zap_splits_query_string_into_params():
    result = parse_burp_zap_xml(ZAP_FIXTURE)
    search_endpoint = next(e for e in result.endpoints if e.path == "/search")
    assert search_endpoint.params == ["q"]


def test_zap_riskcode_maps_to_approximate_score_and_cwe():
    result = parse_burp_zap_xml(ZAP_FIXTURE)
    xss = next(f for f in result.findings if "Reflected" in f.title)
    assert xss.cvss_score == 8.0
    assert xss.cwe == "CWE-79"

    missing_header = next(f for f in result.findings if "X-Content-Type-Options" in f.title)
    assert missing_header.cvss_score == 3.5
    assert missing_header.cwe is None  # cweid was -1, treated as absent


def test_unrecognized_root_element_produces_warning_not_crash():
    result = parse_burp_zap_xml("<somethingelse></somethingelse>")
    assert result.findings == []
    assert any("Unrecognized root element" in w for w in result.warnings)
