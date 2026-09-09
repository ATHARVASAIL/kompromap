"""Shared graph utility functions used by both the API and service layers."""
from __future__ import annotations

from app.models import Asset, Credential, Endpoint, Finding, Node, Service, WebApplication


def node_label(node: Node) -> str:
    if isinstance(node, Finding):
        return node.title
    if isinstance(node, Asset):
        return node.name
    if isinstance(node, Service):
        return f"{node.protocol}/{node.port}"
    if isinstance(node, WebApplication):
        return node.name
    if isinstance(node, Endpoint):
        return node.path
    if isinstance(node, Credential):
        return node.cred_type.value
    return str(node.id)


def node_properties(node: Node) -> dict:
    result: dict = {}
    if isinstance(node, Finding):
        result = {
            "title": node.title,
            "cwe": node.cwe,
            "cvss_score": node.cvss_score,
            "cvss_vector": node.cvss_vector,
            "exploit_public": node.exploit_public,
            "status": node.status.value,
            "verification_status": node.verification_status,
            "owasp_category": node.owasp_category,
            "evidence": node.evidence,
        }
    elif isinstance(node, Asset):
        result = {
            "name": node.name,
            "asset_type": node.asset_type.value,
            "in_scope": node.in_scope,
            "tags": node.tags,
            "is_entry_point": node.is_entry_point,
            "is_crown_jewel": node.is_crown_jewel,
        }
    elif isinstance(node, Service):
        result = {
            "port": node.port,
            "protocol": node.protocol,
            "banner": node.banner,
            "tech_stack": node.tech_stack,
        }
    elif isinstance(node, WebApplication):
        result = {
            "name": node.name,
            "base_url": node.base_url,
            "tech_stack": node.tech_stack,
            "auth_type": node.auth_type,
        }
    elif isinstance(node, Endpoint):
        result = {
            "path": node.path,
            "method": node.method,
            "params": node.params,
            "requires_auth": node.requires_auth,
            "documented": node.documented,
        }
    return {k: v for k, v in result.items() if v is not None and v != []}
