import uuid

from app.models import Account, Asset, DataStore, Edge, EdgeType, Endpoint, Finding, NodeType
from app.services.pathfinding import find_best_paths_report
from app.services.scoring import DEFAULT_WEIGHTS


def _asset(name, **kw):
    return Asset(id=uuid.uuid4(), node_type=NodeType.ASSET.value, name=name, asset_type="domain", **kw)


def _finding(title, **kw):
    return Finding(id=uuid.uuid4(), node_type=NodeType.FINDING.value, title=title, status="open", **kw)


def _account(username, **kw):
    return Account(id=uuid.uuid4(), node_type=NodeType.ACCOUNT.value, username=username, privilege_level="admin", **kw)


def _datastore(name, **kw):
    return DataStore(id=uuid.uuid4(), node_type=NodeType.DATA_STORE.value, name=name, data_classification="PII", **kw)


def _edge(source, target, edge_type, weight=None):
    return Edge(id=uuid.uuid4(), source_node_id=source.id, target_node_id=target.id, edge_type=edge_type.value, weight=weight)


def test_finds_easy_chain_over_direct_hard_hop():
    """Two routes to the same crown jewel: a hard direct exploit, and an
    easier multi-hop chain. Dijkstra-on-cost should prefer the chain even
    though it has more hops — that's the whole point of the ease_score
    formula per spec §4."""
    entry = _asset("dev.client.com", is_entry_point=True)
    hard_finding = _finding("Hard RCE", cvss_score=9.0, exploit_public=False, auth_required=True)
    easy_finding = _finding("Easy subdomain takeover", cvss_score=8.0, exploit_public=True, auth_required=False)
    account = _account("svc-account")
    crown_jewel = _datastore("customer_pii", is_crown_jewel=True)

    edges = [
        _edge(entry, hard_finding, EdgeType.HAS_FINDING),
        _edge(hard_finding, crown_jewel, EdgeType.YIELDS),  # direct but hard
        _edge(entry, easy_finding, EdgeType.HAS_FINDING),
        _edge(easy_finding, account, EdgeType.YIELDS),
        _edge(account, crown_jewel, EdgeType.GRANTS_ACCESS_TO),  # structural, free
    ]
    nodes = [entry, hard_finding, easy_finding, account, crown_jewel]

    report = find_best_paths_report(nodes, edges, [entry], [crown_jewel], DEFAULT_WEIGHTS)

    assert len(report.paths) == 1
    best = report.paths[0]
    assert best.crown_jewel.id == crown_jewel.id
    # the easy chain (through easy_finding) should win over the hard direct hop
    assert easy_finding.id in [n.id for n in best.nodes]
    assert hard_finding.id not in [n.id for n in best.nodes]


def test_unreachable_entry_point_is_reported_separately():
    entry = _asset("isolated.client.com", is_entry_point=True)
    crown_jewel = _datastore("customer_pii", is_crown_jewel=True)
    # no edges connecting them at all

    report = find_best_paths_report([entry, crown_jewel], [], [entry], [crown_jewel], DEFAULT_WEIGHTS)

    assert report.paths == []
    assert report.unreachable_entry_points == [entry]


def test_picks_easiest_of_multiple_reachable_crown_jewels():
    entry = _asset("dev.client.com", is_entry_point=True)
    finding = _finding("XSS", cvss_score=7.0, exploit_public=True, auth_required=False)
    near_jewel = _datastore("near_pii", is_crown_jewel=True)
    far_jewel = _datastore("far_pii", is_crown_jewel=True)

    edges = [
        _edge(entry, finding, EdgeType.HAS_FINDING),
        _edge(finding, near_jewel, EdgeType.YIELDS),
        _edge(finding, far_jewel, EdgeType.YIELDS, weight=0.1),  # manually marked much harder
    ]
    nodes = [entry, finding, near_jewel, far_jewel]

    report = find_best_paths_report(nodes, edges, [entry], [near_jewel, far_jewel], DEFAULT_WEIGHTS)

    assert len(report.paths) == 1
    assert report.paths[0].crown_jewel.id == near_jewel.id


def test_multiple_entry_points_each_get_their_own_best_path():
    entry1 = _asset("a.client.com", is_entry_point=True)
    entry2 = _asset("b.client.com", is_entry_point=True)
    finding1 = _finding("F1", cvss_score=5.0, exploit_public=False, auth_required=True)
    finding2 = _finding("F2", cvss_score=9.0, exploit_public=True, auth_required=False)
    crown_jewel = _datastore("pii", is_crown_jewel=True)

    edges = [
        _edge(entry1, finding1, EdgeType.HAS_FINDING),
        _edge(finding1, crown_jewel, EdgeType.YIELDS),
        _edge(entry2, finding2, EdgeType.HAS_FINDING),
        _edge(finding2, crown_jewel, EdgeType.YIELDS),
    ]
    nodes = [entry1, entry2, finding1, finding2, crown_jewel]

    report = find_best_paths_report(nodes, edges, [entry1, entry2], [crown_jewel], DEFAULT_WEIGHTS)

    assert len(report.paths) == 2
    # sorted cheapest-first: entry2's chain (easier finding) should come first
    assert report.paths[0].entry_point.id == entry2.id


def test_endpoint_can_participate_in_chain():
    entry = _asset("dev.client.com", is_entry_point=True)
    endpoint = Endpoint(id=uuid.uuid4(), node_type=NodeType.ENDPOINT.value, path="/admin")
    finding = _finding("Stored XSS", cvss_score=6.0, exploit_public=True, auth_required=True)
    crown_jewel = _datastore("pii", is_crown_jewel=True)

    edges = [
        _edge(entry, endpoint, EdgeType.EXPOSES),
        _edge(endpoint, finding, EdgeType.HAS_FINDING),
        _edge(finding, crown_jewel, EdgeType.YIELDS),
    ]
    nodes = [entry, endpoint, finding, crown_jewel]

    report = find_best_paths_report(nodes, edges, [entry], [crown_jewel], DEFAULT_WEIGHTS)
    assert len(report.paths) == 1
    assert [n.id for n in report.paths[0].nodes] == [entry.id, endpoint.id, finding.id, crown_jewel.id]
