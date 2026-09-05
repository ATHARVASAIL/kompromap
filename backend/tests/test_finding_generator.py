"""AI finding generator tests.

Tests the finding generation service and API endpoint.
"""
import uuid

import pytest

from app.models import Asset, Edge, EdgeType, Finding, NodeType
from app.schemas.finding_gen import GenerationParseError, parse_generation_response
from app.services.ai.finding_generator import generate_finding_description


def _finding(title, **kw):
    return Finding(
        id=uuid.uuid4(),
        node_type=NodeType.FINDING.value,
        title=title,
        status="open",
        **kw,
    )


def _asset(name, **kw):
    return Asset(
        id=uuid.uuid4(),
        node_type=NodeType.ASSET.value,
        name=name,
        asset_type="domain",
        **kw,
    )


def _edge(source, target, edge_type, weight=None):
    return Edge(
        id=uuid.uuid4(),
        source_node_id=source.id,
        target_node_id=target.id,
        edge_type=edge_type.value,
        weight=weight,
    )


class TestParseGenerationResponse:
    def test_valid_json_parses(self):
        raw = '{"title": "XSS", "description": "Reflected XSS", "remediation_steps": ["encode output"], "references": ["https://cwe.mitre.org/data/definitions/79.html"], "confidence": 0.9}'
        result = parse_generation_response(raw)
        assert result.title == "XSS"
        assert result.confidence == 0.9

    def test_fence_removal(self):
        raw = '```json\n{"title": "XSS", "description": "test", "remediation_steps": [], "references": [], "confidence": 0.5}\n```'
        result = parse_generation_response(raw)
        assert result.title == "XSS"

    def test_empty_response_raises(self):
        with pytest.raises(GenerationParseError, match="empty"):
            parse_generation_response("")

    def test_no_json_raises(self):
        with pytest.raises(GenerationParseError, match="no JSON"):
            parse_generation_response("just some text")

    def test_confidence_coerce_percent(self):
        raw = '{"title": "XSS", "description": "test", "remediation_steps": [], "references": [], "confidence": "85%"}'
        result = parse_generation_response(raw)
        assert result.confidence == 0.85

    def test_list_coerce_string(self):
        raw = '{"title": "XSS", "description": "test", "remediation_steps": "single step", "references": [], "confidence": 0.5}'
        result = parse_generation_response(raw)
        assert result.remediation_steps == ["single step"]


class TestGenerateFindingDescription:
    def test_no_provider_returns_error(self, db_session):
        finding = _finding("test")
        db_session.add(finding)
        db_session.commit()
        result = generate_finding_description(db_session, finding)
        assert result.generated is None
        assert result.error is not None

    def test_finding_not_found_by_id(self, db_session):
        fake_id = str(uuid.uuid4())
        from app.models import Finding
        fake_finding = Finding(id=uuid.UUID(fake_id), node_type=NodeType.FINDING.value, title="ghost", status="open")
        db_session.add(fake_finding)
        db_session.commit()
        result = generate_finding_description(db_session, fake_finding)
        assert result.generated is None
        assert result.error is not None
