"""Render an EngagementReport into deliverable formats.

Markdown for pasting into an existing report template, and a
self-contained HTML file (no external assets, print stylesheet included)
that opens in any browser and prints straight to PDF — which is what
clients actually want, and avoids adding a PDF toolchain to the image.
"""
from __future__ import annotations

import html
import json

from app.services.engagement_report import EngagementReport, SEVERITY_ORDER

SEVERITY_HEX = {
    "Critical": "#F2454E",
    "High": "#F5883A",
    "Medium": "#F0C93A",
    "Low": "#4C8DF0",
    "Informational": "#6B7488",
}


# --------------------------------------------------------------------------
# Markdown
# --------------------------------------------------------------------------
def render_markdown(report: EngagementReport) -> str:
    s = report.summary
    lines: list[str] = []
    add = lines.append

    title = report.engagement_name
    if report.client_name:
        title += f" — {report.client_name}"
    add(f"# Penetration Test Report: {title}")
    add("")
    add(f"*Generated {report.generated_at.strftime('%Y-%m-%d %H:%M UTC')} by Kompromap*")
    add("")

    # --- Executive summary ---
    add("## Executive summary")
    add("")
    counts = s["severity_counts"]
    add(
        f"This engagement identified **{s['total_findings']} findings** across "
        f"{s['total_nodes']} mapped assets and services."
    )
    add("")
    add("| Severity | Count |")
    add("|---|---|")
    for sev in SEVERITY_ORDER:
        add(f"| {sev} | {counts.get(sev, 0)} |")
    add("")

    if s["chain_count"]:
        add(
            f"More importantly, **{s['chain_count']} viable attack chains** were identified "
            f"linking an internet-facing entry point to a business-critical asset. "
            f"The most accessible of these carries a cost of **{s['easiest_chain_cost']}** — "
            "lower means easier for an attacker."
        )
        add("")
        add(
            f"{s['findings_on_a_chain']} of the {s['total_findings']} findings sit on at least "
            "one of these chains. Those are the ones worth fixing first, regardless of their "
            "individual severity ratings — breaking any single step breaks the whole chain."
        )
    else:
        add(
            "No complete attack chain from an entry point to a crown jewel was identified. "
            "See the caveats section for what that does and does not mean."
        )
    add("")

    # --- Attack chains ---
    add("## Attack chains")
    add("")
    if not report.chains:
        add("_No chains were computed. See caveats._")
        add("")
    for chain in report.chains:
        add(f"### Chain #{chain.rank}: {chain.entry_point} → {chain.crown_jewel}")
        add("")
        add(
            f"**Cost:** {chain.total_cost}  |  **Steps:** {len(chain.steps)}  |  "
            f"**Exploitation steps:** {chain.exploit_step_count}"
        )
        add("")
        if chain.narrative:
            add(chain.narrative)
            add("")
        add("| # | From | Relationship | To | Cost |")
        add("|---|---|---|---|---|")
        for st in chain.steps:
            marker = " **·exploit**" if st["is_exploit"] else ""
            add(
                f"| {st['index']} | {st['from']} | `{st['relationship']}`{marker} "
                f"| {st['to']} | {st['cost']} |"
            )
        add("")

    # --- Findings ---
    add("## Findings")
    add("")
    current = None
    for f in report.findings:
        if f.severity != current:
            current = f.severity
            add(f"### {current}")
            add("")
        add(f"#### {f.title}")
        add("")
        meta = [f"**Severity:** {f.severity}"]
        if f.cvss_score is not None:
            meta.append(f"**CVSS:** {f.cvss_score}")
        if f.cwe:
            meta.append(f"**CWE:** {f.cwe}")
        if f.owasp_category:
            meta.append(f"**OWASP:** {f.owasp_category}")
        meta.append(f"**Status:** {f.status}")
        add("  |  ".join(meta))
        add("")
        if f.cvss_vector:
            add(f"`{f.cvss_vector}`")
            add("")
        if f.affected:
            add(f"**Affected:** {', '.join(f.affected)}")
            add("")
        add(f"**Evidence:** {f.evidence}" if f.evidence else "_No evidence recorded._")
        add("")
        flags = []
        if f.exploit_public:
            flags.append("public exploit available")
        if not f.auth_required:
            flags.append("no authentication required")
        if f.in_chain:
            flags.append("**appears on an attack chain**")
        if not f.complexity_measured:
            flags.append("complexity assumed (no CVSS vector)")
        if flags:
            add(f"_{'; '.join(flags)}._")
            add("")

    # --- Remediation ---
    add("## Remediation priority")
    add("")
    add(
        "Ranked by chain impact rather than raw severity — a medium finding on the cheapest "
        "path to a crown jewel matters more than an unreachable critical."
    )
    add("")
    add("| # | Finding | Severity | Why | Breaks a chain |")
    add("|---|---|---|---|---|")
    for item in report.remediation[:25]:
        add(
            f"| {item['rank']} | {item['title']} | {item['severity']} | "
            f"{'; '.join(item['rationale'])} | {'yes' if item['breaks_chain'] else 'no'} |"
        )
    add("")

    # --- Scope ---
    add("## Scope")
    add("")
    for label, key in [
        ("Entry points", "entry_points"),
        ("Crown jewels", "crown_jewels"),
        ("Assets", "assets"),
        ("Services", "services"),
        ("Web applications", "web_applications"),
        ("Endpoints", "endpoints"),
        ("Data stores", "data_stores"),
    ]:
        values = report.scope.get(key) or []
        if values:
            add(f"**{label} ({len(values)}):** {', '.join(values[:60])}")
            if len(values) > 60:
                add(f"_…and {len(values) - 60} more._")
            add("")

    # --- Caveats ---
    if report.caveats:
        add("## Caveats and limitations")
        add("")
        for c in report.caveats:
            add(f"- {c}")
        add("")

    add("---")
    add("")
    add(
        "_Scoring model: ease = 0.4·CVSS + 0.3·public exploit + 0.2·no-auth + 0.1·(1−complexity), "
        "with complexity read from each finding's CVSS vector where available. "
        "Path cost = sum of (1 − ease) across exploitation steps; lower cost means an easier "
        "attack._"
    )
    return "\n".join(lines)


# --------------------------------------------------------------------------
# HTML
# --------------------------------------------------------------------------
def render_html(report: EngagementReport) -> str:
    """Self-contained HTML. No external assets, print stylesheet included —
    opens anywhere and prints to PDF without a toolchain in the image."""
    e = html.escape
    s = report.summary
    counts = s["severity_counts"]

    title = e(report.engagement_name)
    if report.client_name:
        title += f" — {e(report.client_name)}"

    def sev_pill(sev: str) -> str:
        c = SEVERITY_HEX.get(sev, "#6B7488")
        return (
            f'<span class="pill" style="color:{c};border-color:{c}55;background:{c}18">'
            f"{e(sev)}</span>"
        )

    parts: list[str] = []
    add = parts.append

    add(f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Penetration Test Report — {title}</title>
<style>
  :root {{ --bg:#0A0D12; --panel:#0F131B; --line:#232A38; --text:#E7EAF0;
           --muted:#9099AC; --dim:#5C6478; --accent:#2DD4E8; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--text);
    font:15px/1.65 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif; }}
  .wrap {{ max-width:940px; margin:0 auto; padding:48px 32px 96px; }}
  h1 {{ font-size:30px; margin:0 0 6px; letter-spacing:-.02em; }}
  h2 {{ font-size:20px; margin:52px 0 16px; padding-bottom:8px;
        border-bottom:1px solid var(--line); }}
  h3 {{ font-size:16px; margin:32px 0 10px; }}
  h4 {{ font-size:14px; margin:22px 0 6px; }}
  .sub {{ color:var(--dim); font-size:13px; margin-bottom:28px; }}
  table {{ width:100%; border-collapse:collapse; margin:14px 0; font-size:13px; }}
  th,td {{ text-align:left; padding:8px 10px; border-bottom:1px solid var(--line);
           vertical-align:top; }}
  th {{ color:var(--muted); font-weight:600; font-size:12px;
        text-transform:uppercase; letter-spacing:.04em; }}
  code,.mono {{ font-family:ui-monospace,"JetBrains Mono",Menlo,monospace; font-size:12.5px; }}
  code {{ background:var(--panel); border:1px solid var(--line);
          border-radius:4px; padding:1px 5px; color:var(--muted); }}
  .pill {{ display:inline-block; border:1px solid; border-radius:99px;
           padding:1px 9px; font-size:11px; font-weight:600; }}
  .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr));
            gap:12px; margin:20px 0; }}
  .card {{ background:var(--panel); border:1px solid var(--line);
           border-radius:10px; padding:14px 16px; }}
  .card .n {{ font-size:26px; font-weight:600; }}
  .card .l {{ color:var(--dim); font-size:11px; text-transform:uppercase;
              letter-spacing:.05em; }}
  .bar {{ display:flex; height:8px; border-radius:99px; overflow:hidden;
          background:var(--panel); margin:6px 0 22px; }}
  .chain {{ background:var(--panel); border:1px solid var(--line);
            border-radius:10px; padding:16px 18px; margin:16px 0; }}
  .finding {{ border-left:3px solid var(--line); padding-left:14px; margin:22px 0; }}
  .note {{ background:var(--panel); border:1px solid var(--line);
           border-left:3px solid var(--accent); border-radius:6px;
           padding:12px 16px; margin:14px 0; font-size:13.5px; color:var(--muted); }}
  .flags {{ color:var(--dim); font-size:12.5px; font-style:italic; }}
  footer {{ margin-top:56px; padding-top:18px; border-top:1px solid var(--line);
            color:var(--dim); font-size:12px; }}
  @media print {{
    :root {{ --bg:#fff; --panel:#f7f8fa; --line:#dfe3ea; --text:#11151c;
             --muted:#4a5261; --dim:#6b7280; }}
    body {{ font-size:11pt; }}
    .wrap {{ max-width:none; padding:0; }}
    h2 {{ page-break-after:avoid; }}
    .chain,.finding {{ page-break-inside:avoid; }}
  }}
</style></head><body><div class="wrap">""")

    add(f"<h1>Penetration Test Report</h1>")
    add(f'<div class="sub">{title} · generated '
        f'{report.generated_at.strftime("%Y-%m-%d %H:%M UTC")} by Kompromap</div>')

    # Summary cards
    add("<h2>Executive summary</h2>")
    add('<div class="cards">')
    for label, val, color in [
        ("Findings", s["total_findings"], None),
        ("Attack chains", s["chain_count"], "#F2454E" if s["chain_count"] else None),
        ("Entry points", s["entry_point_count"], "#2DD4E8"),
        ("Crown jewels", s["crown_jewel_count"], "#F2454E"),
        ("Mapped nodes", s["total_nodes"], None),
    ]:
        style = f' style="color:{color}"' if color else ""
        add(f'<div class="card"><div class="l">{e(label)}</div>'
            f'<div class="n"{style}>{val}</div></div>')
    add("</div>")

    total = max(sum(counts.values()), 1)
    add('<div class="bar">')
    for sev in SEVERITY_ORDER:
        n = counts.get(sev, 0)
        if n:
            add(f'<span style="width:{n / total * 100:.1f}%;'
                f'background:{SEVERITY_HEX[sev]}"></span>')
    add("</div>")

    add("<table><tr><th>Severity</th><th>Count</th></tr>")
    for sev in SEVERITY_ORDER:
        add(f"<tr><td>{sev_pill(sev)}</td><td>{counts.get(sev, 0)}</td></tr>")
    add("</table>")

    if s["chain_count"]:
        add(f'<div class="note"><b>{s["chain_count"]} viable attack chains</b> link an '
            f"internet-facing entry point to a business-critical asset. The most accessible "
            f'carries a cost of <b>{s["easiest_chain_cost"]}</b> — lower means easier. '
            f'{s["findings_on_a_chain"]} of {s["total_findings"]} findings sit on at least one '
            "chain; breaking any single step breaks the whole chain, so those are the ones "
            "worth fixing first regardless of individual severity.</div>")
    else:
        add('<div class="note">No complete attack chain from an entry point to a crown jewel '
            "was identified. See caveats for what that does and does not mean.</div>")

    # Chains
    add("<h2>Attack chains</h2>")
    if not report.chains:
        add("<p class='flags'>No chains were computed. See caveats.</p>")
    for c in report.chains:
        add('<div class="chain">')
        add(f"<h3>Chain #{c.rank}: {e(c.entry_point)} → {e(c.crown_jewel)}</h3>")
        add(f'<div class="flags">cost {c.total_cost} · {len(c.steps)} steps · '
            f"{c.exploit_step_count} exploitation steps</div>")
        if c.narrative:
            add(f"<p>{e(c.narrative)}</p>")
        add("<table><tr><th>#</th><th>From</th><th>Relationship</th><th>To</th><th>Cost</th></tr>")
        for st in c.steps:
            mark = ' <span class="pill" style="color:#F2454E;border-color:#F2454E55;background:#F2454E18">exploit</span>' if st["is_exploit"] else ""
            add(f"<tr><td>{st['index']}</td><td>{e(str(st['from']))}</td>"
                f"<td><code>{e(str(st['relationship']))}</code>{mark}</td>"
                f"<td>{e(str(st['to']))}</td><td class='mono'>{st['cost']}</td></tr>")
        add("</table></div>")

    # Findings
    add("<h2>Findings</h2>")
    current = None
    for f in report.findings:
        if f.severity != current:
            current = f.severity
            add(f"<h3>{e(current)}</h3>")
        color = SEVERITY_HEX.get(f.severity, "#6B7488")
        add(f'<div class="finding" style="border-left-color:{color}">')
        add(f"<h4>{e(f.title)}</h4>")
        meta = [sev_pill(f.severity)]
        if f.cvss_score is not None:
            meta.append(f'<span class="mono">CVSS {f.cvss_score}</span>')
        if f.cwe:
            meta.append(f"<code>{e(f.cwe)}</code>")
        if f.owasp_category:
            meta.append(e(f.owasp_category))
        meta.append(f'<span class="flags">{e(f.status)}</span>')
        add("<div>" + " &nbsp; ".join(meta) + "</div>")
        if f.cvss_vector:
            add(f'<div style="margin-top:6px"><code>{e(f.cvss_vector)}</code></div>')
        if f.affected:
            add(f'<div style="margin-top:6px"><b>Affected:</b> '
                f'{e(", ".join(f.affected))}</div>')
        add(f'<p>{e(f.evidence) if f.evidence else "<i>No evidence recorded.</i>"}</p>'
            if f.evidence else '<p class="flags">No evidence recorded.</p>')
        flags = []
        if f.exploit_public:
            flags.append("public exploit available")
        if not f.auth_required:
            flags.append("no authentication required")
        if f.in_chain:
            flags.append("appears on an attack chain")
        if not f.complexity_measured:
            flags.append("complexity assumed (no CVSS vector)")
        if flags:
            add(f'<div class="flags">{e("; ".join(flags))}.</div>')
        add("</div>")

    # Remediation
    add("<h2>Remediation priority</h2>")
    add('<div class="note">Ranked by chain impact rather than raw severity — a medium finding '
        "on the cheapest path to a crown jewel matters more than an unreachable critical.</div>")
    add("<table><tr><th>#</th><th>Finding</th><th>Severity</th><th>Why</th>"
        "<th>Breaks a chain</th></tr>")
    for item in report.remediation[:25]:
        add(f"<tr><td>{item['rank']}</td><td>{e(item['title'])}</td>"
            f"<td>{sev_pill(item['severity'])}</td>"
            f"<td class='flags'>{e('; '.join(item['rationale']))}</td>"
            f"<td>{'yes' if item['breaks_chain'] else 'no'}</td></tr>")
    add("</table>")

    # Scope
    add("<h2>Scope</h2><table>")
    for label, key in [
        ("Entry points", "entry_points"), ("Crown jewels", "crown_jewels"),
        ("Assets", "assets"), ("Services", "services"),
        ("Web applications", "web_applications"), ("Endpoints", "endpoints"),
        ("Data stores", "data_stores"),
    ]:
        vals = report.scope.get(key) or []
        if vals:
            shown = ", ".join(vals[:60])
            more = f" <span class='flags'>…and {len(vals) - 60} more</span>" if len(vals) > 60 else ""
            add(f"<tr><th>{e(label)} ({len(vals)})</th><td>{e(shown)}{more}</td></tr>")
    add("</table>")

    if report.caveats:
        add("<h2>Caveats and limitations</h2><ul>")
        for c in report.caveats:
            add(f"<li>{e(c)}</li>")
        add("</ul>")

    add("<footer>Scoring model: ease = 0.4·CVSS + 0.3·public exploit + 0.2·no-auth + "
        "0.1·(1−complexity), with complexity read from each finding's CVSS vector where "
        "available. Path cost = sum of (1 − ease) across exploitation steps; lower cost "
        "means an easier attack.</footer>")
    add("</div></body></html>")
    return "\n".join(parts)


# --------------------------------------------------------------------------
# JSON
# --------------------------------------------------------------------------
def render_json(report: EngagementReport) -> dict:
    return {
        "engagement": {"name": report.engagement_name, "client": report.client_name},
        "generated_at": report.generated_at.isoformat(),
        "summary": report.summary,
        "scope": report.scope,
        "chains": [
            {
                "rank": c.rank,
                "entry_point": c.entry_point,
                "crown_jewel": c.crown_jewel,
                "total_cost": c.total_cost,
                "exploit_step_count": c.exploit_step_count,
                "narrative": c.narrative,
                "steps": c.steps,
            }
            for c in report.chains
        ],
        "findings": [
            {
                "id": str(f.id),
                "title": f.title,
                "severity": f.severity,
                "cvss_score": f.cvss_score,
                "cvss_vector": f.cvss_vector,
                "cwe": f.cwe,
                "owasp_category": f.owasp_category,
                "status": f.status,
                "evidence": f.evidence,
                "affected": f.affected,
                "exploit_public": f.exploit_public,
                "auth_required": f.auth_required,
                "ease_score": f.ease_score,
                "complexity_measured": f.complexity_measured,
                "on_attack_chain": f.in_chain,
            }
            for f in report.findings
        ],
        "remediation": report.remediation,
        "caveats": report.caveats,
    }
