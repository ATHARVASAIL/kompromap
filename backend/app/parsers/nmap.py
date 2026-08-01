"""Parse Nmap XML output (`nmap -oX`) into Asset + Service nodes.

One Asset per <host>, keyed by its first hostname if present, else its IP.
When a host has both an IP and a hostname, the IP is kept as a tag
(`ip:1.2.3.4`) on the asset rather than a separate node — Phase 2 ingestion
can promote it to a TRUSTS-linked Asset later if that turns out to matter
for a given engagement; nothing here forecloses that.
"""
from __future__ import annotations

from pathlib import Path

from defusedxml import ElementTree as DET

from app.parsers.schema import ParsedAsset, ParsedService, ParseResult

SOURCE_TOOL = "nmap"


def parse_nmap_xml(source: str | bytes | Path) -> ParseResult:
    """Parse Nmap XML content. `source` may be a file path, raw XML bytes,
    or raw XML string."""
    root = _load_root(source)
    result = ParseResult(source_tool=SOURCE_TOOL)

    for host_el in root.findall("host"):
        if not _host_is_up(host_el):
            continue

        name, asset_type, tags = _resolve_host_identity(host_el)
        if name is None:
            result.warnings.append("Skipped a <host> with no address or hostname")
            continue

        result.assets.append(ParsedAsset(name=name, asset_type=asset_type, tags=tags))

        ports_el = host_el.find("ports")
        if ports_el is None:
            continue

        for port_el in ports_el.findall("port"):
            state_el = port_el.find("state")
            if state_el is None or state_el.get("state") != "open":
                continue

            service_el = port_el.find("service")
            banner = None
            tech_stack: list[str] = []
            if service_el is not None:
                product = service_el.get("product")
                version = service_el.get("version")
                svc_name = service_el.get("name")
                banner = " ".join(p for p in [product, version] if p) or None
                if svc_name:
                    tech_stack.append(svc_name)
                if product:
                    tech_stack.append(product)

            try:
                port_num = int(port_el.get("portid"))
            except (TypeError, ValueError):
                result.warnings.append(f"Skipped a <port> with invalid portid on host {name}")
                continue

            result.services.append(
                ParsedService(
                    asset_name=name,
                    port=port_num,
                    protocol=port_el.get("protocol", "tcp"),
                    banner=banner,
                    tech_stack=tech_stack,
                )
            )

    return result


def _load_root(source: str | bytes | Path):
    if isinstance(source, Path) or (isinstance(source, str) and _looks_like_path(source)):
        return DET.parse(str(source)).getroot()
    return DET.fromstring(source)


def _looks_like_path(s: str) -> bool:
    return "<" not in s and Path(s).suffix == ".xml"


def _host_is_up(host_el) -> bool:
    status_el = host_el.find("status")
    return status_el is None or status_el.get("state") == "up"


def _resolve_host_identity(host_el) -> tuple[str | None, str, list[str]]:
    """Prefer the first hostname (domain/subdomain) as the asset's identity;
    fall back to the IP. Returns (name, asset_type, tags)."""
    hostnames_el = host_el.find("hostnames")
    hostname = None
    if hostnames_el is not None:
        hostname_el = hostnames_el.find("hostname")
        if hostname_el is not None:
            hostname = hostname_el.get("name")

    ip = None
    for addr_el in host_el.findall("address"):
        if addr_el.get("addrtype") in ("ipv4", "ipv6"):
            ip = addr_el.get("addr")
            break

    tags = [f"ip:{ip}"] if ip else []

    if hostname:
        asset_type = "subdomain" if hostname.count(".") > 1 else "domain"
        return hostname, asset_type, tags
    if ip:
        return ip, "ip", []
    return None, "ip", []
