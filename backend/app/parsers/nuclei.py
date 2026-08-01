"""Parse Nuclei output (JSON Lines, one finding object per line — also
tolerates a single JSON array) into Finding nodes.

Nuclei reports severity as a string (info/low/medium/high/critical) and only
sometimes includes an explicit CVSS score (`info.classification.cvss-score`
when the template carries CVE/CVSS metadata). When it's missing, we fall
back to a conservative severity->score midpoint so every finding still has
something for the Phase 4 ease_score formula to work with; `cvss_score` on
the resulting ParsedFinding is left as that estimate, not fabricated
precision — evidence carries the original severity string too.
"""
from __future__ import annotations

import json
from pathlib import Path

from app.parsers.schema import ParsedFinding, ParseResult

SOURCE_TOOL = "nuclei"

# Conservative midpoint of each Nuclei severity band, used only when a
# template has no explicit cvss-score.
_SEVERITY_SCORE_FALLBACK = {
    "info": 0.0,
    "low": 3.5,
    "medium": 5.5,
    "high": 8.0,
    "critical": 9.5,
}

# Nuclei's severity implies whether unauthenticated exploitation is typical
# for that class isn't reliable info by itself, so auth_required always
# defaults to True (safer/more conservative) unless a finding explicitly
# says otherwise via `info.classification` — Nuclei doesn't emit that today,
# so this is a documented placeholder ingestion can override on review.
_DEFAULT_AUTH_REQUIRED = True


def parse_nuclei_json(source: str | bytes | Path) -> ParseResult:
    """Parse Nuclei JSON output. Accepts a file path, JSONL text/bytes, or a
    JSON array."""
    result = ParseResult(source_tool=SOURCE_TOOL)
    records = _load_records(source, result)

    for i, record in enumerate(records):
        if not isinstance(record, dict):
            result.warnings.append(f"Skipped record {i}: not a JSON object")
            continue

        info = record.get("info") or {}
        target_ref = record.get("matched-at") or record.get("host")
        if not target_ref:
            result.warnings.append(f"Skipped record {i}: no 'matched-at' or 'host' field")
            continue

        title = info.get("name") or record.get("template-id") or "Untitled Nuclei finding"
        severity = (info.get("severity") or "info").lower()

        classification = info.get("classification") or {}
        cvss_score = classification.get("cvss-score")
        if cvss_score is None:
            cvss_score = _SEVERITY_SCORE_FALLBACK.get(severity, 0.0)

        cwe_list = classification.get("cwe-id") or []
        cwe = cwe_list[0] if cwe_list else None

        evidence_parts = [f"severity={severity}"]
        if record.get("curl-command"):
            evidence_parts.append(f"curl={record['curl-command']}")
        if record.get("matcher-name"):
            evidence_parts.append(f"matcher={record['matcher-name']}")

        result.findings.append(
            ParsedFinding(
                target_ref=target_ref,
                title=title,
                cwe=cwe,
                owasp_category=None,
                cvss_score=float(cvss_score),
                exploit_public=severity in ("high", "critical"),
                auth_required=_DEFAULT_AUTH_REQUIRED,
                evidence="; ".join(evidence_parts),
                status="open",
            )
        )

    return result


def _load_records(source: str | bytes | Path, result: ParseResult) -> list[dict]:
    text = _read_text(source)
    stripped = text.strip()
    if not stripped:
        return []

    # Try JSON array first.
    if stripped.startswith("["):
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError as e:
            result.warnings.append(f"Failed to parse as JSON array: {e}")
            return []

    # Otherwise treat as JSON Lines.
    records = []
    for lineno, line in enumerate(stripped.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as e:
            result.warnings.append(f"Skipped unparsable line {lineno}: {e}")
    return records


def _read_text(source: str | bytes | Path) -> str:
    if isinstance(source, Path):
        return source.read_text()
    if isinstance(source, bytes):
        return source.decode("utf-8")
    if isinstance(source, str) and _looks_like_path(source):
        return Path(source).read_text()
    return source


def _looks_like_path(s: str) -> bool:
    return ("{" not in s and "[" not in s) and (s.endswith(".json") or s.endswith(".jsonl"))
