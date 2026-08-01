"""Tool-specific parsers, each normalizing to the common ParseResult schema
defined in app.parsers.schema before anything touches the database."""
from app.parsers.amass import parse_amass_output
from app.parsers.burp import parse_burp_zap_xml
from app.parsers.nmap import parse_nmap_xml
from app.parsers.nuclei import parse_nuclei_json
from app.parsers.schema import (
    ParsedAsset,
    ParsedEndpoint,
    ParsedFinding,
    ParsedService,
    ParseResult,
)

__all__ = [
    "parse_nmap_xml",
    "parse_nuclei_json",
    "parse_amass_output",
    "parse_burp_zap_xml",
    "ParsedAsset",
    "ParsedService",
    "ParsedEndpoint",
    "ParsedFinding",
    "ParseResult",
]
