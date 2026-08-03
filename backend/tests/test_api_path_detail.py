"""Path response accuracy.

Fixes a real bug: the API reported each edge's cost as `1 - edge.weight`,
which is only meaningful for a *manual* override — every computed edge came
back as 0.0. So the per-step costs shown in the UI didn't add up to the
total cost that produced the ranking, making the explanation quietly wrong.
The response now recomputes through the same edge_cost() Dijkstra used.
"""
import pytest

TRIVIAL = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H"
HARD = "CVSS:3.1/AV:N/AC:H/PR:H/UI:R/S:U/C:L/I:N/A:N"


def _node(client, node_type, **fields):
    r = client.post("/api/nodes", json={"node_type": node_type, **fields})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _edge(client, source, target, edge_type, weight=None):
    payload = {"source_node_id": source, "target_node_id": target, "edge_type": edge_type}
    if weight is not None:
        payload["weight"] = weight
    r = client.post("/api/edges", json=payload)
    assert r.status_code == 201, r.text


@pytest.fixture()
def chain(client):
    """entry -> [trivial finding] -> cred -> [hard finding] -> crown jewel"""
    ids = {
        "entry": _node(client, "asset", name="api.test", asset_type="domain", is_entry_point=True),
        "easy": _node(
            client, "finding", title="Log4Shell", cvss_score=10.0,
            cvss_vector=TRIVIAL, exploit_public=True,
        ),
        "cred": _node(client, "credential", cred_type="password"),
        "hard": _node(client, "finding", title="Race condition", cvss_score=9.0, cvss_vector=HARD),
        "jewel": _node(client, "data_store", name="pii", is_crown_jewel=True),
    }
    _edge(client, ids["entry"], ids["easy"], "HAS_FINDING")
    _edge(client, ids["easy"], ids["cred"], "YIELDS")
    _edge(client, ids["cred"], ids["hard"], "GRANTS_ACCESS_TO")
    _edge(client, ids["hard"], ids["jewel"], "YIELDS")
    return ids


def _first_path(client):
    r = client.post("/api/pathfind/best", json={})
    assert r.status_code == 200, r.text
    paths = r.json()["paths"]
    assert paths, "expected at least one path"
    return paths[0]


def test_edge_costs_sum_to_total_cost(chain, client):
    """The core guarantee — an explanation that doesn't add up is worse
    than no explanation."""
    path = _first_path(client)
    assert sum(e["cost"] for e in path["edges"]) == pytest.approx(path["total_cost"])


def test_computed_edges_report_a_real_cost_not_zero(chain, client):
    path = _first_path(client)
    yields = [e for e in path["edges"] if e["edge_type"] == "YIELDS"]
    assert yields
    assert any(e["cost"] > 0 for e in yields)


def test_structural_edges_are_free(chain, client):
    """HOSTS/EXPOSES/HAS_FINDING are observed relationships, not
    exploitation steps — they shouldn't add cost."""
    path = _first_path(client)
    structural = [e for e in path["edges"] if e["edge_type"] in ("HAS_FINDING", "GRANTS_ACCESS_TO")]
    assert structural
    assert all(e["cost"] == 0.0 for e in structural)


def test_only_exploitation_steps_carry_a_breakdown(chain, client):
    path = _first_path(client)
    for e in path["edges"]:
        if e["edge_type"] == "YIELDS":
            assert e["breakdown"] is not None
        else:
            assert e["breakdown"] is None


def test_breakdown_contributions_sum_to_its_ease_score(chain, client):
    path = _first_path(client)
    for e in path["edges"]:
        if e["breakdown"]:
            b = e["breakdown"]
            assert sum(b["contributions"].values()) == pytest.approx(b["ease_score"])


def test_breakdown_reports_measured_complexity_for_vectored_findings(chain, client):
    path = _first_path(client)
    vectored = [e["breakdown"] for e in path["edges"] if e["breakdown"]]
    assert vectored
    assert all(b["complexity_measured"] for b in vectored)


def test_hard_step_costs_more_than_trivial_step(chain, client):
    """Same chain, two exploits — the AC:H/PR:H/UI:R one must dominate."""
    path = _first_path(client)
    costs = sorted(e["cost"] for e in path["edges"] if e["breakdown"])
    assert costs[-1] > costs[0]


def test_hardest_step_cost_identifies_the_bottleneck(chain, client):
    path = _first_path(client)
    assert path["hardest_step_cost"] == pytest.approx(max(e["cost"] for e in path["edges"]))


def test_exploit_step_count_counts_only_real_exploits(chain, client):
    """A 7-hop chain with 2 exploits is easier than a 3-hop with 3 — hop
    count alone is misleading, so this is reported separately."""
    path = _first_path(client)
    assert path["exploit_step_count"] == 2
    assert len(path["edges"]) == 4


def test_path_nodes_carry_severity_for_inline_display(chain, client):
    path = _first_path(client)
    findings = [n for n in path["nodes"] if n["node_type"] == "finding"]
    assert findings
    assert all(n["cvss_score"] is not None for n in findings)
    assert all(n["cvss_vector"] for n in findings)


def test_path_nodes_flag_entry_point_and_crown_jewel(chain, client):
    path = _first_path(client)
    assert path["nodes"][0]["is_entry_point"] is True
    assert path["nodes"][-1]["is_crown_jewel"] is True


def test_custom_weights_change_the_reported_costs(chain, client):
    """The breakdown must reflect the weights actually used, not defaults."""
    default = client.post("/api/pathfind/best", json={}).json()["paths"][0]
    tweaked = client.post(
        "/api/pathfind/best",
        json={"weights": {"cvss": 1.0, "exploit_public": 0, "auth_required": 0, "complexity": 0}},
    ).json()["paths"][0]
    assert tweaked["total_cost"] != pytest.approx(default["total_cost"])
    assert sum(e["cost"] for e in tweaked["edges"]) == pytest.approx(tweaked["total_cost"])


def test_manual_edge_weight_still_overrides_the_computed_cost(client):
    """A tester's explicit judgement must beat the model."""
    entry = _node(client, "asset", name="a.test", asset_type="domain", is_entry_point=True)
    finding = _node(client, "finding", title="F", cvss_score=10.0, cvss_vector=TRIVIAL)
    jewel = _node(client, "data_store", name="db", is_crown_jewel=True)
    _edge(client, entry, finding, "HAS_FINDING")
    _edge(client, finding, jewel, "YIELDS", weight=0.1)  # marked as hard by hand

    path = _first_path(client)
    yields = [e for e in path["edges"] if e["edge_type"] == "YIELDS"][0]
    assert yields["cost"] == pytest.approx(0.9)
