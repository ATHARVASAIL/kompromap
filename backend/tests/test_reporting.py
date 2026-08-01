import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.models import Asset, DataStore, Edge, EdgeType, Finding, NodeType
from app.services.reporting import (
    ChainResolutionError,
    build_chain_export,
    generate_narrative,
    render_markdown,
    resolve_chain,
)


def _seed_chain(db_session):
    asset = Asset(id=uuid.uuid4(), node_type=NodeType.ASSET.value, name="dev.client.com", asset_type="subdomain")
    finding = Finding(
        id=uuid.uuid4(),
        node_type=NodeType.FINDING.value,
        title="Subdomain takeover",
        cvss_score=8.1,
        exploit_public=True,
        auth_required=False,
        evidence="curl -I https://dev.client.com returned NXDOMAIN on the CNAME target",
        status="open",
    )
    jewel = DataStore(
        id=uuid.uuid4(), node_type=NodeType.DATA_STORE.value, name="users_db", data_classification="PII"
    )
    db_session.add_all([asset, finding, jewel])
    db_session.flush()

    e1 = Edge(source_node_id=asset.id, target_node_id=finding.id, edge_type=EdgeType.HAS_FINDING.value)
    e2 = Edge(source_node_id=finding.id, target_node_id=jewel.id, edge_type=EdgeType.YIELDS.value)
    db_session.add_all([e1, e2])
    db_session.commit()

    return asset, finding, jewel


def test_resolve_chain_returns_ordered_steps(db_session):
    asset, finding, jewel = _seed_chain(db_session)
    steps = resolve_chain(db_session, [asset.id, finding.id, jewel.id])

    assert len(steps) == 3
    assert steps[0].node.id == asset.id
    assert steps[0].incoming_edge is None
    assert steps[1].node.id == finding.id
    assert steps[1].incoming_edge.edge_type == EdgeType.HAS_FINDING.value
    assert steps[2].node.id == jewel.id
    assert steps[2].incoming_edge.edge_type == EdgeType.YIELDS.value


def test_resolve_chain_rejects_disconnected_nodes(db_session):
    asset, finding, jewel = _seed_chain(db_session)
    with pytest.raises(ChainResolutionError, match="No edge connects"):
        resolve_chain(db_session, [asset.id, jewel.id])  # skips finding, no direct edge


def test_resolve_chain_rejects_too_short(db_session):
    asset, _, _ = _seed_chain(db_session)
    with pytest.raises(ChainResolutionError, match="at least 2 nodes"):
        resolve_chain(db_session, [asset.id])


def test_resolve_chain_rejects_nonexistent_node(db_session):
    asset, finding, _ = _seed_chain(db_session)
    with pytest.raises(ChainResolutionError, match="does not exist"):
        resolve_chain(db_session, [asset.id, uuid.uuid4()])


def test_template_narrative_used_when_no_api_key(db_session, monkeypatch):
    monkeypatch.setattr("app.services.reporting.get_settings", lambda: MagicMock(anthropic_api_key=None))
    asset, finding, jewel = _seed_chain(db_session)
    steps = resolve_chain(db_session, [asset.id, finding.id, jewel.id])

    narrative, used_llm = generate_narrative(steps)
    assert used_llm is False
    assert "dev.client.com" in narrative
    assert "users_db" in narrative


def test_llm_narrative_used_when_api_call_succeeds(db_session, monkeypatch):
    fake_settings = MagicMock(anthropic_api_key="sk-fake-key", anthropic_model="claude-sonnet-5")
    monkeypatch.setattr("app.services.reporting.get_settings", lambda: fake_settings)

    fake_text_block = MagicMock()
    fake_text_block.type = "text"
    fake_text_block.text = "An attacker exploits a subdomain takeover to reach the users database."
    fake_message = MagicMock(content=[fake_text_block])

    mock_client = MagicMock()
    mock_client.messages.create.return_value = fake_message

    asset, finding, jewel = _seed_chain(db_session)
    steps = resolve_chain(db_session, [asset.id, finding.id, jewel.id])

    with patch("anthropic.Anthropic", return_value=mock_client):
        narrative, used_llm = generate_narrative(steps)

    assert used_llm is True
    assert narrative == "An attacker exploits a subdomain takeover to reach the users database."
    mock_client.messages.create.assert_called_once()
    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-sonnet-5"


def test_llm_failure_falls_back_to_template(db_session, monkeypatch):
    fake_settings = MagicMock(anthropic_api_key="sk-fake-key", anthropic_model="claude-sonnet-5")
    monkeypatch.setattr("app.services.reporting.get_settings", lambda: fake_settings)

    asset, finding, jewel = _seed_chain(db_session)
    steps = resolve_chain(db_session, [asset.id, finding.id, jewel.id])

    with patch("anthropic.Anthropic", side_effect=RuntimeError("network error")):
        narrative, used_llm = generate_narrative(steps)

    assert used_llm is False
    assert "dev.client.com" in narrative


def test_build_chain_export_includes_evidence(db_session):
    asset, finding, jewel = _seed_chain(db_session)
    steps = resolve_chain(db_session, [asset.id, finding.id, jewel.id])

    data = build_chain_export(steps, "test narrative", used_llm=False)
    assert data["entry_point"]["label"] == "dev.client.com"
    assert data["crown_jewel"]["label"] == "users_db"
    assert data["narrative"] == "test narrative"
    assert data["narrative_source"] == "template"
    assert len(data["steps"]) == 3
    finding_step = data["steps"][1]
    assert finding_step["node"]["evidence"] == "curl -I https://dev.client.com returned NXDOMAIN on the CNAME target"


def test_render_markdown_includes_chain_and_evidence(db_session):
    asset, finding, jewel = _seed_chain(db_session)
    steps = resolve_chain(db_session, [asset.id, finding.id, jewel.id])

    md = render_markdown(steps, "Test narrative paragraph.")
    assert "# Attack Chain: dev.client.com → users_db" in md
    assert "Test narrative paragraph." in md
    assert "Subdomain takeover" in md
    assert "## Evidence" in md
    assert "NXDOMAIN" in md
