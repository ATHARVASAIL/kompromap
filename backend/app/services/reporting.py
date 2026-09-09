"""Chain narrative generation and export (spec §5 Phase 3 / §7 Phase 5):

- Resolve an ordered list of node IDs (typically a path-finding result, but
  any manually-assembled chain works too) into actual nodes + the edges
  connecting them.
- Generate a plain-English paragraph describing the chain, via the
  Anthropic API when a key is configured.
- Export the chain (graph + narrative + evidence) as Markdown or a
  structured JSON dict.

LLM integration is optional: if no ANTHROPIC_API_KEY is configured, or the
API call fails for any reason, narrative generation falls back to a
deterministic templated paragraph built directly from the chain data.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Edge, Finding, Node
from app.models.enums import EdgeType
from app.services.graph_utils import node_label, node_properties

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
    incoming_edge: Edge | None


def resolve_chain(db: Session, node_ids: list[uuid.UUID]) -> list[ChainStep]:
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
                f"No edge connects '{node_label(nodes[i - 1])}' to '{node_label(nodes[i])}'"
            )
        steps.append(ChainStep(node=nodes[i], incoming_edge=edge))

    return steps


def _describe_node_for_prompt(node: Node) -> dict:
    return {
        "type": node.node_type,
        "label": node_label(node),
        "properties": node_properties(node),
        "evidence": node.evidence if isinstance(node, Finding) else None,
    }


def _template_narrative(steps: list[ChainStep]) -> str:
    entry = steps[0].node
    crown_jewel = steps[-1].node
    parts = [f"Starting from {node_label(entry)}, an attacker can chain the following steps:"]
    for step in steps[1:]:
        phrase = EDGE_PHRASES.get(EdgeType(step.incoming_edge.edge_type), "leading to") if step.incoming_edge else ""
        n = step.node
        detail = ""
        if isinstance(n, Finding) and n.cvss_score is not None:
            detail = f" (CVSS {n.cvss_score}{', publicly exploitable' if n.exploit_public else ''})"
        parts.append(f"{phrase} {node_label(n)}{detail}.")
    parts.append(
        f"This chain gives an attacker a realistic path from {node_label(entry)} to {node_label(crown_jewel)}, "
        f"the engagement's tagged crown jewel."
    )
    return " ".join(parts)


def _llm_narrative(steps: list[ChainStep]) -> str | None:
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
    except Exception:
        return None


def generate_narrative(steps: list[ChainStep]) -> tuple[str, bool]:
    llm_result = _llm_narrative(steps)
    if llm_result:
        return llm_result, True
    return _template_narrative(steps), False


def build_chain_export(steps: list[ChainStep], narrative: str, used_llm: bool) -> dict:
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
        f"# Attack Chain: {node_label(entry)} → {node_label(crown_jewel)}",
        "",
        narrative,
        "",
        "## Chain",
        "",
    ]
    for i, step in enumerate(steps, start=1):
        n = step.node
        lines.append(f"{i}. **{node_label(n)}** ({n.node_type})")
        if step.incoming_edge:
            lines.append(f"   ↓ _{step.incoming_edge.edge_type}_")
        for key, value in node_properties(n).items():
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
