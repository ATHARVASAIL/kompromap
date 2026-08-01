"""Common internal schema for parser output.

Each tool-specific parser (nmap, nuclei, amass, burp) reads its own file
format and returns a ParseResult built from these dataclasses. Nothing here
touches the database — that wiring (resolving `asset_name`/`target_ref`
references to actual Node rows and creating edges between them) is Phase 2's
job, when ingestion becomes a real API endpoint. Keeping parsers pure
functions of "bytes/path in, ParseResult out" is also what makes them easy
to unit test in isolation.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ParsedAsset:
    """Maps to models.Asset. `name` is the natural key parsers/ingestion
    use to de-duplicate and to link services/endpoints/findings to it."""

    name: str
    asset_type: str  # domain | subdomain | ip | cloud_resource
    in_scope: bool = True
    tags: list[str] = field(default_factory=list)


@dataclass
class ParsedService:
    """Maps to models.Service. `asset_name` links back to a ParsedAsset.name
    (or an existing Asset in the DB) for the eventual HOSTS edge."""

    asset_name: str
    port: int
    protocol: str
    banner: str | None = None
    tech_stack: list[str] = field(default_factory=list)


@dataclass
class ParsedEndpoint:
    """Maps to models.Endpoint. `asset_name` links back to the asset it was
    discovered on, for the eventual EXPOSES edge."""

    asset_name: str
    path: str
    method: str = "GET"
    params: list[str] = field(default_factory=list)
    requires_auth: bool | None = None
    documented: bool = False


@dataclass
class ParsedFinding:
    """Maps to models.Finding. `target_ref` is either an asset name or an
    endpoint path — ingestion resolves it to the right node for the
    HAS_FINDING edge."""

    target_ref: str
    title: str
    cwe: str | None = None
    owasp_category: str | None = None
    cvss_score: float | None = None
    exploit_public: bool = False
    auth_required: bool = True
    evidence: str | None = None
    status: str = "open"


@dataclass
class ParseResult:
    """Everything one parser run extracted from one input file."""

    source_tool: str
    assets: list[ParsedAsset] = field(default_factory=list)
    services: list[ParsedService] = field(default_factory=list)
    endpoints: list[ParsedEndpoint] = field(default_factory=list)
    findings: list[ParsedFinding] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def merge(self, other: "ParseResult") -> "ParseResult":
        """Combine two results (e.g. Amass + Subfinder output for the same
        engagement) into one, keeping the earlier source_tool label."""
        return ParseResult(
            source_tool=self.source_tool,
            assets=[*self.assets, *other.assets],
            services=[*self.services, *other.services],
            endpoints=[*self.endpoints, *other.endpoints],
            findings=[*self.findings, *other.findings],
            warnings=[*self.warnings, *other.warnings],
        )
