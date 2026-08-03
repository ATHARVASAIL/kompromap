"""Full engagement report generation.

The report is the deliverable — the thing a client actually reads — so the
things worth pinning down are that it never invents data, that remediation
ranks by chain impact rather than reproducing a flat CVSS sort, and that
it states its own limitations rather than implying more rigour than was
performed.
"""
import pytest

TRIVIAL = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H"


def _node(client, node_type, **fields):
    r = client.post("/api/nodes", json={"node_type": node_type, **fields})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _edge(client, s, t, et):
    assert client.post(
        "/api/edges", json={"source_node_id": s, "target_node_id": t, "edge_type": et}
    ).status_code == 201


def _report(client, fmt="json", **kw):
    r = client.post("/api/reports/engagement", json={"format": fmt, **kw})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture()
def engagement(client):
    """A small but complete engagement: one chain, plus an off-chain
    critical that shouldn't outrank the on-chain finding."""
    entry = _node(client, "asset", name="api.test", asset_type="domain", is_entry_point=True)
    onchain = _node(
        client, "finding", title="Log4Shell", cvss_score=9.8,
        cvss_vector=TRIVIAL, exploit_public=True, auth_required=False,
        evidence="jndi callback observed",
    )
    cred = _node(client, "credential", cred_type="password")
    jewel = _node(client, "data_store", name="pii_db", is_crown_jewel=True)
    # Higher CVSS but connected to nothing — must NOT outrank the on-chain one.
    _node(client, "finding", title="Orphan critical", cvss_score=10.0, evidence="x")

    _edge(client, entry, onchain, "HAS_FINDING")
    _edge(client, onchain, cred, "YIELDS")
    _edge(client, cred, jewel, "GRANTS_ACCESS_TO")
    return {"entry": entry, "onchain": onchain, "jewel": jewel}


class TestStructure:
    def test_json_report_has_every_section(self, engagement, client):
        d = _report(client)["data"]
        for key in ("summary", "scope", "findings", "chains", "remediation", "caveats"):
            assert key in d

    def test_summary_counts_match_the_findings_list(self, engagement, client):
        d = _report(client)["data"]
        assert d["summary"]["total_findings"] == len(d["findings"])
        assert sum(d["summary"]["severity_counts"].values()) == len(d["findings"])

    def test_findings_sorted_most_severe_first(self, engagement, client):
        d = _report(client)["data"]
        order = ["Critical", "High", "Medium", "Low", "Informational"]
        ranks = [order.index(f["severity"]) for f in d["findings"]]
        assert ranks == sorted(ranks)

    def test_severity_derived_from_cvss(self, engagement, client):
        d = _report(client)["data"]
        by_title = {f["title"]: f for f in d["findings"]}
        assert by_title["Log4Shell"]["severity"] == "Critical"

    def test_findings_record_what_they_affect(self, engagement, client):
        d = _report(client)["data"]
        log4shell = next(f for f in d["findings"] if f["title"] == "Log4Shell")
        assert "api.test" in log4shell["affected"]

    def test_scope_inventories_the_graph(self, engagement, client):
        scope = _report(client)["data"]["scope"]
        assert "api.test" in scope["assets"]
        assert "api.test" in scope["entry_points"]
        assert "pii_db" in scope["crown_jewels"]


class TestChains:
    def test_chains_are_included_with_their_steps(self, engagement, client):
        d = _report(client)["data"]
        assert d["chains"]
        chain = d["chains"][0]
        assert chain["entry_point"] == "api.test"
        assert chain["crown_jewel"] == "pii_db"
        assert chain["steps"]

    def test_exploitation_steps_are_distinguished_from_structural_ones(self, engagement, client):
        chain = _report(client)["data"]["chains"][0]
        assert any(s["is_exploit"] for s in chain["steps"])
        assert any(not s["is_exploit"] for s in chain["steps"])

    def test_findings_are_flagged_when_they_sit_on_a_chain(self, engagement, client):
        d = _report(client)["data"]
        by_title = {f["title"]: f for f in d["findings"]}
        assert by_title["Log4Shell"]["on_attack_chain"] is True
        assert by_title["Orphan critical"]["on_attack_chain"] is False


class TestRemediation:
    def test_on_chain_finding_outranks_a_higher_cvss_orphan(self, engagement, client):
        """The whole point of the tool. Ranking by CVSS alone would put the
        10.0 orphan first and reproduce the flat table this replaces."""
        rem = _report(client)["data"]["remediation"]
        titles = [r["title"] for r in rem]
        assert titles.index("Log4Shell") < titles.index("Orphan critical")

    def test_every_item_explains_why_it_ranks_there(self, engagement, client):
        for item in _report(client)["data"]["remediation"]:
            assert item["rationale"], item

    def test_chain_membership_is_stated_explicitly(self, engagement, client):
        rem = _report(client)["data"]["remediation"]
        log4shell = next(r for r in rem if r["title"] == "Log4Shell")
        assert log4shell["breaks_chain"] is True
        assert any("chain" in reason for reason in log4shell["rationale"])

    def test_closed_findings_are_excluded(self, engagement, client):
        _node(client, "finding", title="Already fixed", cvss_score=9.0, status="fixed")
        titles = [r["title"] for r in _report(client)["data"]["remediation"]]
        assert "Already fixed" not in titles


class TestCaveats:
    def test_flags_findings_with_assumed_complexity(self, engagement, client):
        caveats = " ".join(_report(client)["data"]["caveats"])
        assert "no CVSS vector" in caveats

    def test_flags_missing_evidence(self, client):
        _node(client, "finding", title="No evidence here", cvss_score=5.0)
        caveats = " ".join(_report(client)["data"]["caveats"])
        assert "no recorded evidence" in caveats

    def test_explains_when_no_chains_could_be_computed(self, client):
        _node(client, "finding", title="Lonely", cvss_score=5.0)
        caveats = " ".join(_report(client)["data"]["caveats"])
        assert "No entry points were tagged" in caveats

    def test_distinguishes_untagged_from_genuinely_unreachable(self, client):
        """"No chain found" must not be read as "no path exists" when the
        real cause is that exploitation edges were never added."""
        _node(client, "asset", name="a.test", asset_type="domain", is_entry_point=True)
        _node(client, "data_store", name="db", is_crown_jewel=True)
        caveats = " ".join(_report(client)["data"]["caveats"])
        assert "not evidence that no path exists" in caveats

    def test_flags_high_severity_findings_that_are_off_chain(self, engagement, client):
        caveats = " ".join(_report(client)["data"]["caveats"])
        assert "do not appear on any computed chain" in caveats


class TestRenderers:
    def test_markdown_renders_the_key_sections(self, engagement, client):
        md = _report(client, "markdown")["content"]
        for heading in ("# Penetration Test Report", "## Executive summary",
                        "## Attack chains", "## Findings", "## Remediation priority",
                        "## Scope"):
            assert heading in md

    def test_markdown_includes_the_scoring_model(self, engagement, client):
        """A reader must be able to check the arithmetic."""
        assert "ease = 0.4" in _report(client, "markdown")["content"]

    def test_html_is_self_contained(self, engagement, client):
        html = _report(client, "html")["content"]
        assert html.startswith("<!doctype html>")
        assert "<style>" in html
        # No external assets — it has to open and print anywhere.
        assert "http://" not in html.split("<style>")[1].split("</style>")[0]

    def test_html_has_a_print_stylesheet(self, engagement, client):
        assert "@media print" in _report(client, "html")["content"]

    def test_html_escapes_content(self, client):
        _node(client, "finding", title="<script>alert(1)</script>", cvss_score=5.0)
        html = _report(client, "html")["content"]
        assert "<script>alert(1)</script>" not in html
        assert "&lt;script&gt;" in html

    def test_unknown_format_is_rejected(self, client):
        r = client.post("/api/reports/engagement", json={"format": "pdf"})
        assert r.status_code == 422
