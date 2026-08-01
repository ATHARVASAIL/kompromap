"""Turns parser output (a ParseResult — see app/parsers/schema.py) into
actual Node/Edge rows.

This is where the "common internal schema" the parsers produce gets
resolved into real graph structure: assets get get-or-created by name,
services/endpoints get linked to their asset with HOSTS/EXPOSES edges, and
findings get attached to whatever they were found on with a HAS_FINDING
edge. Re-running ingestion on the same file is safe — everything is
get-or-create/dedupe by natural key, not blind insert.

Design note on EXPOSES: per spec §4 it's Service -> Endpoint, but Burp/ZAP
exports only tell us host+path, not which port/service. Rather than
fabricate an unobserved Service node, ingestion looks for an existing web
service on that asset (port 443 or 80/tcp) and uses it if one was already
ingested (e.g. from an Nmap scan of the same asset); otherwise the EXPOSES
edge originates from the Asset directly. This keeps the graph honest about
what was actually observed instead of inventing service detail nobody
scanned.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Asset, Edge, EdgeType, Endpoint, Finding, Node, NodeType, Service
from app.parsers.schema import ParseResult


@dataclass
class IngestSummary:
    source_tool: str
    assets_created: int = 0
    assets_reused: int = 0
    services_created: int = 0
    services_reused: int = 0
    endpoints_created: int = 0
    endpoints_reused: int = 0
    findings_created: int = 0
    edges_created: int = 0
    warnings: list[str] = field(default_factory=list)


def ingest_parse_result(db: Session, result: ParseResult, engagement_id: uuid.UUID) -> IngestSummary:
    summary = IngestSummary(source_tool=result.source_tool, warnings=list(result.warnings))

    # asset name -> Asset, populated as we go so later entries in the same
    # file (services, endpoints, findings) can resolve against assets
    # created earlier in this same call.
    assets_by_name: dict[str, Asset] = {}

    for pa in result.assets:
        asset, created = _get_or_create_asset(
            db, pa.name, pa.asset_type, pa.in_scope, pa.tags, engagement_id
        )
        assets_by_name[pa.name] = asset
        summary.assets_created += created
        summary.assets_reused += not created

    seen_referenced_assets: set[str] = set(assets_by_name.keys())

    for ps in result.services:
        asset, created = _get_or_create_referenced_asset(db, assets_by_name, ps.asset_name, engagement_id)
        if ps.asset_name not in seen_referenced_assets:
            seen_referenced_assets.add(ps.asset_name)
            summary.assets_created += created
            summary.assets_reused += not created

        service, created = _get_or_create_service(
            db, asset, ps.port, ps.protocol, ps.banner, ps.tech_stack, engagement_id
        )
        summary.services_created += created
        summary.services_reused += not created

        if _ensure_edge(db, asset, service, EdgeType.HOSTS):
            summary.edges_created += 1

    # endpoint_key (asset_name, path) -> Endpoint, so findings in this same
    # result can resolve to the endpoint they were actually found on.
    endpoints_by_key: dict[tuple[str, str], Endpoint] = {}

    for pe in result.endpoints:
        asset, created = _get_or_create_referenced_asset(db, assets_by_name, pe.asset_name, engagement_id)
        if pe.asset_name not in seen_referenced_assets:
            seen_referenced_assets.add(pe.asset_name)
            summary.assets_created += created
            summary.assets_reused += not created

        endpoint, created = _get_or_create_endpoint(
            db, asset, pe.path, pe.method, pe.params, pe.requires_auth, pe.documented, engagement_id
        )
        endpoints_by_key[(pe.asset_name, pe.path)] = endpoint
        summary.endpoints_created += created
        summary.endpoints_reused += not created

        exposer = _find_web_service(db, asset) or asset
        if _ensure_edge(db, exposer, endpoint, EdgeType.EXPOSES):
            summary.edges_created += 1

    for pf in result.findings:
        target = _resolve_finding_target(
            db, pf.target_ref, assets_by_name, endpoints_by_key, summary, seen_referenced_assets, engagement_id
        )
        if target is None:
            summary.warnings.append(
                f"Finding '{pf.title}' has unresolvable target '{pf.target_ref}', skipped"
            )
            continue

        finding = Finding(
            node_type=NodeType.FINDING.value,
            engagement_id=engagement_id,
            title=pf.title,
            cwe=pf.cwe,
            owasp_category=pf.owasp_category,
            cvss_score=pf.cvss_score,
            exploit_public=pf.exploit_public,
            auth_required=pf.auth_required,
            evidence=pf.evidence,
            status=pf.status,
        )
        db.add(finding)
        db.flush()
        summary.findings_created += 1

        db.add(Edge(source_node_id=target.id, target_node_id=finding.id, edge_type=EdgeType.HAS_FINDING.value))
        summary.edges_created += 1

    db.commit()
    return summary


# --- resolution helpers -----------------------------------------------------


def _find_asset_by_name(db: Session, name: str, engagement_id: uuid.UUID) -> Asset | None:
    return db.scalar(
        select(Asset).where(Asset.name == name, Asset.engagement_id == engagement_id)
    )


def _get_or_create_referenced_asset(
    db: Session, assets_by_name: dict[str, Asset], name: str, engagement_id: uuid.UUID
) -> tuple[Asset, bool]:
    """Resolve an asset referenced by name from a Service/Endpoint entry.
    If it wasn't explicitly present in this file's asset list (e.g. a
    standalone Burp/ZAP export that only gives host+path, with no separate
    recon step), auto-create a minimal Asset for it rather than dropping
    the finding — a bare Burp import should still produce a usable graph.
    """
    existing = assets_by_name.get(name)
    if existing is not None:
        return existing, False

    existing = _find_asset_by_name(db, name, engagement_id)
    if existing is not None:
        assets_by_name[name] = existing
        return existing, False

    asset_type = _infer_asset_type(name)
    asset = Asset(
        node_type=NodeType.ASSET.value,
        engagement_id=engagement_id,
        name=name,
        asset_type=asset_type,
        in_scope=True,
        tags=[],
    )
    db.add(asset)
    db.flush()
    assets_by_name[name] = asset
    return asset, True


def _infer_asset_type(name: str) -> str:
    parts = name.split(".")
    if len(parts) == 4 and all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
        return "ip"
    return "subdomain" if name.count(".") > 1 else "domain"


def _get_or_create_asset(
    db: Session,
    name: str,
    asset_type: str,
    in_scope: bool,
    tags: list[str],
    engagement_id: uuid.UUID,
) -> tuple[Asset, bool]:
    existing = _find_asset_by_name(db, name, engagement_id)
    if existing is not None:
        # Merge in any new tags rather than overwriting.
        merged = sorted(set(existing.tags) | set(tags))
        if merged != sorted(existing.tags):
            existing.tags = merged
        return existing, False

    asset = Asset(
        node_type=NodeType.ASSET.value,
        engagement_id=engagement_id,
        name=name,
        asset_type=asset_type,
        in_scope=in_scope,
        tags=tags,
    )
    db.add(asset)
    db.flush()
    return asset, True


def _get_or_create_service(
    db: Session,
    asset: Asset,
    port: int,
    protocol: str,
    banner: str | None,
    tech_stack: list[str],
    engagement_id: uuid.UUID,
) -> tuple[Service, bool]:
    existing = db.scalar(
        select(Service)
        .join(Edge, Edge.target_node_id == Service.id)
        .where(
            Edge.source_node_id == asset.id,
            Edge.edge_type == EdgeType.HOSTS.value,
            Service.port == port,
            Service.protocol == protocol,
        )
    )
    if existing is not None:
        if banner and not existing.banner:
            existing.banner = banner
        existing.tech_stack = sorted(set(existing.tech_stack) | set(tech_stack))
        return existing, False

    service = Service(
        node_type=NodeType.SERVICE.value,
        engagement_id=engagement_id,
        port=port,
        protocol=protocol,
        banner=banner,
        tech_stack=tech_stack,
    )
    db.add(service)
    db.flush()
    return service, True


def _exposer_ids_for_asset(db: Session, asset: Asset) -> list:
    """IDs an EXPOSES edge could legitimately originate from for this asset:
    the asset itself, or any service it hosts (see _find_web_service)."""
    service_ids = list(
        db.scalars(
            select(Service.id)
            .join(Edge, Edge.target_node_id == Service.id)
            .where(Edge.source_node_id == asset.id, Edge.edge_type == EdgeType.HOSTS.value)
        )
    )
    return [asset.id, *service_ids]


def _get_or_create_endpoint(
    db: Session,
    asset: Asset,
    path: str,
    method: str,
    params: list[str],
    requires_auth: bool | None,
    documented: bool,
    engagement_id: uuid.UUID,
) -> tuple[Endpoint, bool]:
    existing = db.scalar(
        select(Endpoint)
        .join(Edge, Edge.target_node_id == Endpoint.id)
        .where(
            Edge.source_node_id.in_(_exposer_ids_for_asset(db, asset)),
            Edge.edge_type == EdgeType.EXPOSES.value,
            Endpoint.path == path,
        )
    )
    if existing is not None:
        existing.params = sorted(set(existing.params) | set(params))
        return existing, False

    endpoint = Endpoint(
        node_type=NodeType.ENDPOINT.value,
        engagement_id=engagement_id,
        path=path,
        method=method,
        params=params,
        requires_auth=requires_auth,
        documented=documented,
    )
    db.add(endpoint)
    db.flush()
    return endpoint, True


def _find_web_service(db: Session, asset: Asset) -> Service | None:
    return db.scalar(
        select(Service)
        .join(Edge, Edge.target_node_id == Service.id)
        .where(
            Edge.source_node_id == asset.id,
            Edge.edge_type == EdgeType.HOSTS.value,
            Service.protocol == "tcp",
            Service.port.in_([443, 80]),
        )
        .order_by(Service.port.desc())  # prefer 443 over 80
    )


def _resolve_finding_target(
    db: Session,
    target_ref: str,
    assets_by_name: dict[str, Asset],
    endpoints_by_key: dict[tuple[str, str], Endpoint],
    summary: IngestSummary,
    seen_referenced_assets: set[str],
    engagement_id: uuid.UUID,
) -> Node | None:
    """target_ref is either a bare path (Burp/ZAP — matches a ParsedEndpoint
    from the same file) or a full URL (Nuclei's matched-at)."""
    if target_ref.startswith("http://") or target_ref.startswith("https://"):
        parsed = urlparse(target_ref)
        host = parsed.netloc.split(":")[0]
        path = parsed.path or "/"

        endpoint = endpoints_by_key.get((host, path))
        if endpoint is not None:
            return endpoint

        # Auto-create the host asset if this is a standalone Nuclei run with
        # no preceding recon step — same rationale as
        # _get_or_create_referenced_asset for services/endpoints.
        asset, created = _get_or_create_referenced_asset(db, assets_by_name, host, engagement_id)
        if host not in seen_referenced_assets:
            seen_referenced_assets.add(host)
            summary.assets_created += created
            summary.assets_reused += not created

        return _find_endpoint_by_asset_and_path(db, asset, path) or asset

    # Bare path — look for a matching endpoint across whatever assets this
    # ingestion run touched. Ambiguous if more than one asset shares the
    # same path (rare for a single-target Burp/ZAP export); first match wins.
    for (asset_name, path), endpoint in endpoints_by_key.items():
        if path == target_ref:
            return endpoint

    return None


def _find_endpoint_by_asset_and_path(db: Session, asset: Asset, path: str) -> Endpoint | None:
    return db.scalar(
        select(Endpoint)
        .join(Edge, Edge.target_node_id == Endpoint.id)
        .where(
            Edge.source_node_id.in_(_exposer_ids_for_asset(db, asset)),
            Edge.edge_type == EdgeType.EXPOSES.value,
            Endpoint.path == path,
        )
    )


def _ensure_edge(db: Session, source: Node, target: Node, edge_type: EdgeType) -> bool:
    """Create the edge if it doesn't already exist. Returns True if created."""
    existing = db.scalar(
        select(Edge).where(
            Edge.source_node_id == source.id,
            Edge.target_node_id == target.id,
            Edge.edge_type == edge_type.value,
        )
    )
    if existing is not None:
        return False

    db.add(Edge(source_node_id=source.id, target_node_id=target.id, edge_type=edge_type.value))
    db.flush()
    return True
