"""Parse a Burp Suite or OWASP ZAP XML export into Endpoint nodes plus any
findings tagged within them.

Burp's classic issue-export XML (`<issues><issue>...`) and ZAP's report XML
(`<OWASPZAPReport><site><alerts><alertitem>...`) have different shapes, so
this module detects the root tag and dispatches to the matching parser
function. Both funnel into the same ParseResult shape.
"""
from __future__ import annotations

from pathlib import Path

from defusedxml import ElementTree as DET

from app.parsers.schema import ParsedEndpoint, ParsedFinding, ParseResult

SOURCE_TOOL = "burp_zap"

# Burp confidence/severity strings map roughly onto a 0-10 CVSS-like scale
# for path-finding purposes, since Burp issues don't carry a real CVSS
# score. This is an approximation, flagged as such in each finding's
# evidence field so a reviewer knows it wasn't a real CVSS calculation.
_BURP_SEVERITY_SCORE = {
    "information": 0.0,
    "low": 3.5,
    "medium": 5.5,
    "high": 8.0,
}

# ZAP risk codes: 0=Informational, 1=Low, 2=Medium, 3=High
_ZAP_RISKCODE_SCORE = {
    "0": 0.0,
    "1": 3.5,
    "2": 5.5,
    "3": 8.0,
}


def parse_burp_zap_xml(source: str | bytes | Path) -> ParseResult:
    """Parse a Burp or ZAP XML export. Auto-detects the format from the
    root element."""
    root = _load_root(source)

    if root.tag == "issues":
        return _parse_burp(root)
    if root.tag == "OWASPZAPReport":
        return _parse_zap(root)

    result = ParseResult(source_tool=SOURCE_TOOL)
    result.warnings.append(
        f"Unrecognized root element <{root.tag}> — expected <issues> (Burp) "
        "or <OWASPZAPReport> (ZAP)"
    )
    return result


def _parse_burp(root) -> ParseResult:
    result = ParseResult(source_tool="burp")
    seen_endpoints: set[tuple[str, str]] = set()

    for issue_el in root.findall("issue"):
        host_el = issue_el.find("host")
        path_el = issue_el.find("path")
        name_el = issue_el.find("name")
        severity_el = issue_el.find("severity")

        if host_el is None or host_el.text is None:
            result.warnings.append("Skipped an <issue> with no <host>")
            continue

        asset_name = _strip_scheme(host_el.text.strip())
        path = path_el.text.strip() if path_el is not None and path_el.text else "/"
        title = name_el.text.strip() if name_el is not None and name_el.text else "Untitled Burp issue"
        severity = (severity_el.text or "information").strip().lower() if severity_el is not None else "information"

        endpoint_key = (asset_name, path)
        if endpoint_key not in seen_endpoints:
            seen_endpoints.add(endpoint_key)
            result.endpoints.append(ParsedEndpoint(asset_name=asset_name, path=path))

        result.findings.append(
            ParsedFinding(
                target_ref=path,
                title=title,
                cvss_score=_BURP_SEVERITY_SCORE.get(severity, 0.0),
                exploit_public=False,
                auth_required=True,
                evidence=f"source=burp; severity={severity} (approximated, not a real CVSS score)",
                status="open",
            )
        )

    return result


def _parse_zap(root) -> ParseResult:
    result = ParseResult(source_tool="zap")
    seen_endpoints: set[tuple[str, str]] = set()

    for site_el in root.findall("site"):
        asset_name = _strip_scheme(site_el.get("host", "") or site_el.get("name", ""))
        if not asset_name:
            result.warnings.append("Skipped a <site> with no host/name")
            continue

        alerts_el = site_el.find("alerts")
        if alerts_el is None:
            continue

        for alert_el in alerts_el.findall("alertitem"):
            name_el = alert_el.find("name")
            riskcode_el = alert_el.find("riskcode")
            cweid_el = alert_el.find("cweid")
            title = name_el.text.strip() if name_el is not None and name_el.text else "Untitled ZAP alert"
            riskcode = riskcode_el.text.strip() if riskcode_el is not None and riskcode_el.text else "0"
            cwe = (
                f"CWE-{cweid_el.text.strip()}"
                if cweid_el is not None and cweid_el.text and cweid_el.text.strip() != "-1"
                else None
            )

            instances_el = alert_el.find("instances")
            uris = []
            if instances_el is not None:
                for instance_el in instances_el.findall("instance"):
                    uri_el = instance_el.find("uri")
                    if uri_el is not None and uri_el.text:
                        uris.append(uri_el.text.strip())
            if not uris:
                uris = ["/"]

            for uri in uris:
                path, params = _path_and_params_from_uri(uri)
                endpoint_key = (asset_name, path)
                if endpoint_key not in seen_endpoints:
                    seen_endpoints.add(endpoint_key)
                    result.endpoints.append(
                        ParsedEndpoint(asset_name=asset_name, path=path, params=params)
                    )

                result.findings.append(
                    ParsedFinding(
                        target_ref=path,
                        title=title,
                        cwe=cwe,
                        cvss_score=_ZAP_RISKCODE_SCORE.get(riskcode, 0.0),
                        exploit_public=False,
                        auth_required=True,
                        evidence=f"source=zap; riskcode={riskcode} (approximated, not a real CVSS score)",
                        status="open",
                    )
                )

    return result


def _load_root(source: str | bytes | Path):
    if isinstance(source, Path) or (isinstance(source, str) and _looks_like_path(source)):
        return DET.parse(str(source)).getroot()
    return DET.fromstring(source)


def _looks_like_path(s: str) -> bool:
    return "<" not in s and Path(s).suffix == ".xml"


def _strip_scheme(host: str) -> str:
    for prefix in ("https://", "http://"):
        if host.startswith(prefix):
            host = host[len(prefix):]
    return host.split("/")[0].split(":")[0]


def _path_and_params_from_uri(uri: str) -> tuple[str, list[str]]:
    for prefix in ("https://", "http://"):
        if uri.startswith(prefix):
            uri = uri[len(prefix):]
            slash = uri.find("/")
            uri = uri[slash:] if slash != -1 else "/"
            break
    else:
        uri = uri if uri.startswith("/") else f"/{uri}"

    path, _, query = uri.partition("?")
    params = [pair.split("=", 1)[0] for pair in query.split("&") if pair] if query else []
    return path or "/", params
