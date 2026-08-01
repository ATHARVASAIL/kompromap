from pathlib import Path

from app.parsers.nmap import parse_nmap_xml

FIXTURE = Path(__file__).parent / "fixtures" / "nmap_sample.xml"


def test_parses_up_hosts_only():
    result = parse_nmap_xml(FIXTURE)
    # 3 hosts in fixture, one is "down" and should be skipped
    assert len(result.assets) == 2


def test_prefers_hostname_over_ip():
    result = parse_nmap_xml(FIXTURE)
    names = {a.name for a in result.assets}
    assert "dev.client.com" in names
    assert "203.0.113.10" not in names  # kept as tag, not a separate asset


def test_ip_only_host_falls_back_to_ip_asset():
    result = parse_nmap_xml(FIXTURE)
    names = {a.name for a in result.assets}
    assert "203.0.113.11" in names
    ip_asset = next(a for a in result.assets if a.name == "203.0.113.11")
    assert ip_asset.asset_type == "ip"


def test_hostname_asset_carries_ip_tag():
    result = parse_nmap_xml(FIXTURE)
    dev_asset = next(a for a in result.assets if a.name == "dev.client.com")
    assert "ip:203.0.113.10" in dev_asset.tags


def test_only_open_ports_become_services():
    result = parse_nmap_xml(FIXTURE)
    ports = {(s.asset_name, s.port) for s in result.services}
    assert ("dev.client.com", 22) in ports
    assert ("dev.client.com", 443) in ports
    assert ("dev.client.com", 8080) not in ports  # closed, skipped


def test_service_captures_banner_and_tech_stack():
    result = parse_nmap_xml(FIXTURE)
    https_service = next(s for s in result.services if s.port == 443)
    assert https_service.protocol == "tcp"
    assert "nginx 1.18.0" == https_service.banner
    assert "nginx" in https_service.tech_stack


def test_parses_from_raw_xml_string():
    raw = FIXTURE.read_text()
    result = parse_nmap_xml(raw)
    assert len(result.assets) == 2


def test_parses_from_bytes():
    raw = FIXTURE.read_bytes()
    result = parse_nmap_xml(raw)
    assert len(result.assets) == 2
