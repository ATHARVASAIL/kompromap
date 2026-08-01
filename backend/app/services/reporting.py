"""Chain narrative generation and export (spec §5 Phase 3 / §7 Phase 5):

- Resolve an ordered list of node IDs (typically a path-finding result, but
  any manually-assembled chain works too) into actual nodes + the edges
  connecting them.
- Generate a plain-English paragraph describing the chain, via the
  Anthropic API when a key is configured (spec §6: "Optional LLM
  integration... pass the winning path's nodes/edges/evidence as
  structured context, ask for a plain-English paragraph").
- Export the chain (graph + narrative + evidence) as Markdown or a
  structured JSON dict, designed to slot into an existing report builder.

LLM integration is optional by design, not just by spec wording: if no
ANTHROPIC_API_KEY is configured, or the API call fails for any reason,
narrative generation falls back to a deterministic templated paragraph
built directly from the chain data. Export should always work even without
an API key — a tester shouldn't be blocked from getting their report out
because of a missing credential or a transient API error.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.graph import _node_label, _node_properties
from app.core.config import get_settings
from app.models import Edge, Finding, Node
from app.models.enums import EdgeType

EDGE_PHRASES: dict[EdgeType, str] = {
    EdgeType.HOSTS: "which hosts",
    EdgeType.EXPOSES: "which exposes",
    EdgeType.HAS_FINDING: "on which the tester found",
    EdgeType.YIELDS: "exploiting which yields",
    EdgeType.AUTHENTICATES_AS: "which authenticates as",
    EdgeType.GRANTS_ACCESS_TO: "which grants access to",
    EdgeType.TRUSTS: "which trusts",
}


class ChainResolutionError(ValueError):
    """A chain of node_ids couldn't be resolved into a connected path."""


@dataclass
class ChainStep:
    node: Node
    incoming_edge: Edge | None  # None for the first step


def resolve_chain(db: Session, node_ids: list[uuid.UUID]) -> list[ChainStep]:
    """Turn an ordered list of node IDs into (node, edge-from-previous)
    steps, validating that consecutive nodes are actually connected."""
    if len(node_ids) < 2:
        raise ChainResolutionError("A chain needs at least 2 nodes")

    nodes: list[Node] = []
    for node_id in node_ids:
        node = db.get(Node, node_id)
        if node is None:
            raise ChainResolutionError(f"Node {node_id} does not exist")
        nodes.append(node)

    steps = [ChainStep(node=nodes[0], incoming_edge=None)]
    for i in range(1, len(nodes)):
        edge = db.scalar(
            select(Edge).where(
                Edge.source_node_id == nodes[i - 1].id,
                Edge.target_node_id == nodes[i].id,
            )
        )
        if edge is None:
            raise ChainResolutionError(
                f"No edge connects '{_node_label(nodes[i - 1])}' to '{_node_label(nodes[i])}' "
                "— the chain must be a connected path"
            )
        steps.append(ChainStep(node=nodes[i], incoming_edge=edge))

    return steps


def _describe_node_for_prompt(node: Node) -> dict:
    return {
        "type": node.node_type,
        "label": _node_label(node),
        "properties": _node_properties(node),
        "evidence": node.evidence if isinstance(node, Finding) else None,
    }


def _template_narrative(steps: list[ChainStep]) -> str:
    """Deterministic fallback narrative — no LLM required. Reads like the
    spec's own §1 example chain notation, in prose."""
    entry = steps[0].node
    crown_jewel = steps[-1].node

    parts = [f"Starting from {_node_label(entry)}, an attacker can chain the following steps:"]
    for step in steps[1:]:
        phrase = EDGE_PHRASES.get(EdgeType(step.incoming_edge.edge_type), "leading to") if step.incoming_edge else ""
        node = step.node
        detail = ""
        if isinstance(node, Finding) and node.cvss_score is not None:
            detail = f" (CVSS {node.cvss_score}{', publicly exploitable' if node.exploit_public else ''})"
        parts.append(f"{phrase} {_node_label(node)}{detail}.")

    parts.append(
        f"This chain gives an attacker a realistic path from {_node_label(entry)} to {_node_label(crown_jewel)}, "
        f"the engagement's tagged crown jewel."
    )
    return " ".join(parts)


def _llm_narrative(steps: list[ChainStep]) -> str | None:
    """Returns None (never raises) if no API key is configured or the call
    fails for any reason — callers fall back to the template narrative."""
    settings = get_settings()
    if not settings.anthropic_api_key:
        return None

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        chain_context = [_describe_node_for_prompt(s.node) for s in steps]
        prompt = (
            "You are helping write a penetration test report. Given this attack chain "
            "(a list of steps from an entry point to a crown jewel, each with its type, "
            "label, properties, and evidence where available), write ONE plain-English "
            "paragraph describing the chain for a pentest report. Be factual and specific "
            "to the data given — do not invent details not present in the input. "
            "Do not use markdown formatting.\n\n"
            f"Chain:\n{chain_context}"
        )
        message = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        text_blocks = [b.text for b in message.content if getattr(b, "type", None) == "text"]
        return "".join(text_blocks).strip() or None
    except Exception:  # noqa: BLE001 - any failure here should degrade, not break export
        return None


def generate_narrative(steps: list[ChainStep]) -> tuple[str, bool]:
    """Returns (narrative, used_llm)."""
    llm_result = _llm_narrative(steps)
    if llm_result:
        return llm_result, True
    return _template_narrative(steps), False


def build_chain_export(steps: list[ChainStep], narrative: str, used_llm: bool) -> dict:
    """Structured JSON export — graph + narrative + evidence, per spec §5:
    "Export a chain (graph + narrative + evidence) as Markdown/JSON —
    designed to slot into your existing report builder."""
    return {
        "entry_point": _describe_node_for_prompt(steps[0].node),
        "crown_jewel": _describe_node_for_prompt(steps[-1].node),
        "narrative": narrative,
        "narrative_source": "llm" if used_llm else "template",
        "steps": [
            {
                "node": _describe_node_for_prompt(step.node),
                "incoming_edge_type": step.incoming_edge.edge_type if step.incoming_edge else None,
            }
            for step in steps
        ],
    }


def render_markdown(steps: list[ChainStep], narrative: str) -> str:
    entry = steps[0].node
    crown_jewel = steps[-1].node

    lines = [
        f"# Attack Chain: {_node_label(entry)} → {_node_label(crown_jewel)}",
        "",
        narrative,
        "",
        "## Chain",
        "",
    ]

    for i, step in enumerate(steps, start=1):
        node = step.node
        lines.append(f"{i}. **{_node_label(node)}** ({node.node_type})")
        if step.incoming_edge:
            lines.append(f"   ↓ _{step.incoming_edge.edge_type}_")
        for key, value in _node_properties(node).items():
            if value not in (None, "", []):
                lines.append(f"   - {key}: {value}")

    findings_with_evidence = [s.node for s in steps if isinstance(s.node, Finding) and s.node.evidence]
    if findings_with_evidence:
        lines += ["", "## Evidence", ""]
        for finding in findings_with_evidence:
            lines.append(f"**{finding.title}**")
            lines.append(f"> {finding.evidence}")
            lines.append("")

    return "\n".join(lines)
