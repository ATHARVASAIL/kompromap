"""Parse Amass or Subfinder subdomain-enumeration output into Asset nodes.

Both tools' plain-text mode is identical for this purpose: one subdomain per
line. Both also support JSON/JSONL; Amass JSON uses a `name` field, and
Subfinder's `-oJ` output (when piped through subfinder itself) uses `host`.
This parser auto-detects which of those is present per line/record.
"""
from __future__ import annotations

import json
from pathlib import Path

from app.parsers.schema import ParsedAsset, ParseResult

SOURCE_TOOL = "amass_subfinder"


def parse_amass_output(source: str | bytes | Path) -> ParseResult:
    """Parse Amass/Subfinder output — plain text (one subdomain per line) or
    JSON Lines with a `name` or `host` field."""
    result = ParseResult(source_tool=SOURCE_TOOL)
    text = _read_text(source)

    seen: set[str] = set()
    for lineno, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue

        subdomain = None
        if line.startswith("{"):
            try:
                record = json.loads(line)
            except json.JSONDecodeError as e:
                result.warnings.append(f"Skipped unparsable JSON line {lineno}: {e}")
                continue
            subdomain = record.get("name") or record.get("host")
            if not subdomain:
                result.warnings.append(f"Skipped line {lineno}: no 'name' or 'host' field")
                continue
        else:
            subdomain = line

        subdomain = subdomain.strip().lower().rstrip(".")
        if not subdomain or subdomain in seen:
            continue
        seen.add(subdomain)

        asset_type = "subdomain" if subdomain.count(".") > 1 else "domain"
        result.assets.append(ParsedAsset(name=subdomain, asset_type=asset_type))

    return result


def _read_text(source: str | bytes | Path) -> str:
    if isinstance(source, Path):
        return source.read_text()
    if isinstance(source, bytes):
        return source.decode("utf-8")
    if isinstance(source, str) and _looks_like_path(source):
        return Path(source).read_text()
    return source


def _looks_like_path(s: str) -> bool:
    return "\n" not in s and (s.endswith(".txt") or s.endswith(".json") or s.endswith(".jsonl"))
