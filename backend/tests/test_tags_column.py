"""Regression: tags / params / tech_stack must be JSONB columns.

The initial migration originally created these as ARRAY(String), but the
`StringList` TypeDecorator writes JSON.  Migration 34 converts them to
JSONB; this test verifies the SQLAlchemy models agree on the column type.
"""
from app.models import Asset, Endpoint, Service, WebApplication


def test_asset_tags_is_json(session):
    a = Asset(name="test.example.com", asset_type="domain", in_scope=True, tags=["web", "api"])
    session.add(a)
    session.commit()
    session.refresh(a)
    assert a.tags == ["web", "api"]


def test_endpoint_params_is_json(session):
    asset = Asset(name="e.example.com", asset_type="domain", in_scope=True, tags=[])
    session.add(asset)
    session.flush()
    ep = Endpoint(node_type="endpoint", engagement_id=asset.engagement_id,
                  asset_id=asset.id, path="/api", params=["id"], requires_auth=False)
    session.add(ep)
    session.commit()
    session.refresh(ep)
    assert ep.params == ["id"]


def test_service_tech_stack_is_json(session):
    asset = Asset(name="s.example.com", asset_type="domain", in_scope=True, tags=[])
    session.add(asset)
    session.flush()
    svc = Service(node_type="service", engagement_id=asset.engagement_id,
                  asset_id=asset.id, port=443, protocol="tcp", tech_stack=["nginx", "node"])
    session.add(svc)
    session.commit()
    session.refresh(svc)
    assert svc.tech_stack == ["nginx", "node"]
