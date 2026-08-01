from pathlib import Path

from app.models import Asset, Edge, EdgeType, Endpoint, Finding, Service
from app.parsers.amass import parse_amass_output
from app.parsers.burp import parse_burp_zap_xml
from app.parsers.nmap import parse_nmap_xml
from app.parsers.nuclei import parse_nuclei_json
from app.services.ingestion import ingest_parse_result

FIXTURES = Path(__file__).parent / "fixtures"


def test_nmap_ingestion_creates_assets_services_and_hosts_edges(db_session, engagement_id):
    result = parse_nmap_xml(FIXTURES / "nmap_sample.xml")
    summary = ingest_parse_result(db_session, result, engagement_id)

    assert summary.assets_created == 2
    assert summary.services_created == 3  # ssh + https on host1, http on host2
    assert summary.edges_created == 3

    assets = db_session.query(Asset).all()
    assert {a.name for a in assets} == {"dev.client.com", "203.0.113.11"}

    hosts_edges = db_session.query(Edge).filter(Edge.edge_type == EdgeType.HOSTS.value).all()
    assert len(hosts_edges) == 3


def test_reingesting_same_nmap_file_is_idempotent(db_session, engagement_id):
    result = parse_nmap_xml(FIXTURES / "nmap_sample.xml")
    ingest_parse_result(db_session, result, engagement_id)

    result2 = parse_nmap_xml(FIXTURES / "nmap_sample.xml")
    summary2 = ingest_parse_result(db_session, result2, engagement_id)

    assert summary2.assets_created == 0
    assert summary2.assets_reused == 2
    assert summary2.services_created == 0
    assert summary2.edges_created == 0

    assert db_session.query(Asset).count() == 2
    assert db_session.query(Service).count() == 3


def test_amass_then_nmap_reuses_the_same_asset(db_session, engagement_id):
    amass_result = parse_amass_output("dev.client.com\n")
    ingest_parse_result(db_session, amass_result, engagement_id)
    assert db_session.query(Asset).count() == 1

    nmap_result = parse_nmap_xml(FIXTURES / "nmap_sample.xml")
    summary = ingest_parse_result(db_session, nmap_result, engagement_id)

    # dev.client.com already existed from amass; only the second host is new
    assert summary.assets_created == 1
    assert summary.assets_reused == 1
    assert db_session.query(Asset).count() == 2


def test_burp_ingestion_creates_endpoints_findings_and_has_finding_edges(db_session, engagement_id):
    result = parse_burp_zap_xml(FIXTURES / "burp_sample.xml")
    summary = ingest_parse_result(db_session, result, engagement_id)

    assert summary.assets_created == 1  # dev.client.com, auto-created
    assert summary.endpoints_created == 3
    assert summary.findings_created == 3

    has_finding_edges = (
        db_session.query(Edge).filter(Edge.edge_type == EdgeType.HAS_FINDING.value).all()
    )
    assert len(has_finding_edges) == 3
    # each HAS_FINDING edge should originate from an Endpoint (Burp gives us path-level detail)
    endpoint_ids = {e.id for e in db_session.query(Endpoint).all()}
    assert all(e.source_node_id in endpoint_ids for e in has_finding_edges)


def test_nuclei_finding_resolves_to_existing_endpoint_when_available(db_session, engagement_id):
    # First ingest Burp so /api/v2/users/{id} exists as... different path,
    # so instead pre-create an endpoint matching nuclei's matched-at path.
    burp_result = parse_burp_zap_xml(FIXTURES / "burp_sample.xml")
    ingest_parse_result(db_session, burp_result, engagement_id)

    nuclei_result = parse_nuclei_json(FIXTURES / "nuclei_sample.jsonl")
    summary = ingest_parse_result(db_session, nuclei_result, engagement_id)

    # None of nuclei's paths (.env, /api/v2/users, /) match burp's endpoints
    # exactly, so all 3 nuclei findings should attach to the dev.client.com
    # Asset (auto-resolved from the matched-at URL's host).
    assert summary.findings_created == 3
    dev_asset = db_session.query(Asset).filter(Asset.name == "dev.client.com").one()
    has_finding_edges = (
        db_session.query(Edge)
        .filter(Edge.edge_type == EdgeType.HAS_FINDING.value, Edge.source_node_id == dev_asset.id)
        .all()
    )
    assert len(has_finding_edges) == 3


def test_nuclei_finding_attaches_to_matching_endpoint_when_path_matches(db_session, engagement_id):
    # Manually create an asset + endpoint whose path matches nuclei's matched-at
    from app.parsers.schema import ParsedAsset, ParsedEndpoint, ParseResult

    setup = ParseResult(
        source_tool="manual",
        assets=[ParsedAsset(name="dev.client.com", asset_type="subdomain")],
        endpoints=[ParsedEndpoint(asset_name="dev.client.com", path="/")],
    )
    ingest_parse_result(db_session, setup, engagement_id)

    nuclei_result = parse_nuclei_json(FIXTURES / "nuclei_sample.jsonl")
    ingest_parse_result(db_session, nuclei_result, engagement_id)

    root_endpoint = db_session.query(Endpoint).filter(Endpoint.path == "/").one()
    finding_ids = [f.id for f in db_session.query(Finding).all()]
    edges_to_root = (
        db_session.query(Edge)
        .filter(
            Edge.edge_type == EdgeType.HAS_FINDING.value,
            Edge.target_node_id.in_(finding_ids),
        )
        .all()
    )
    matched = [e for e in edges_to_root if e.source_node_id == root_endpoint.id]
    assert len(matched) == 1  # the "Nginx Detected" info finding at matched-at="https://dev.client.com/"


def test_finding_with_bare_path_and_no_matching_endpoint_is_skipped(db_session, engagement_id):
    from app.parsers.schema import ParsedFinding, ParseResult

    result = ParseResult(
        source_tool="test",
        findings=[ParsedFinding(target_ref="/some/path", title="Orphan finding")],
    )
    summary = ingest_parse_result(db_session, result, engagement_id)
    assert summary.findings_created == 0
    assert any("unresolvable target" in w for w in summary.warnings)


def test_finding_with_url_target_auto_creates_host_asset(db_session, engagement_id):
    """A standalone Nuclei-only ingestion (no preceding recon step) should
    still produce usable findings, not silently drop everything."""
    from app.parsers.schema import ParsedFinding, ParseResult

    result = ParseResult(
        source_tool="test",
        findings=[ParsedFinding(target_ref="https://nowhere.example/x", title="Standalone finding")],
    )
    summary = ingest_parse_result(db_session, result, engagement_id)
    assert summary.findings_created == 1
    assert summary.assets_created == 1
    assert db_session.query(Asset).filter(Asset.name == "nowhere.example").one()


def test_same_asset_name_in_different_engagements_stays_isolated(db_session, engagement_id):
    """Ingesting the same subdomain into two different engagements must
    create two separate Asset nodes, not merge/reuse across engagements —
    that would leak one client's data into another's graph."""
    from app.models import Engagement

    other_engagement = Engagement(name="Other Client")
    db_session.add(other_engagement)
    db_session.commit()

    result = parse_amass_output("shared.example.com\n")
    summary_a = ingest_parse_result(db_session, result, engagement_id)
    summary_b = ingest_parse_result(db_session, result, other_engagement.id)

    assert summary_a.assets_created == 1
    assert summary_b.assets_created == 1  # not "reused" — different engagement

    assets = db_session.query(Asset).filter(Asset.name == "shared.example.com").all()
    assert len(assets) == 2
    assert {a.engagement_id for a in assets} == {engagement_id, other_engagement.id}
