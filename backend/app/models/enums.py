"""Enumerations used across the node/edge data model.

Values are kept as the exact tokens used in the spec (kompromap-spec.md §4)
so that DB values, API payloads, and the spec read the same way.
"""
from enum import Enum


class NodeType(str, Enum):
    ASSET = "asset"
    SERVICE = "service"
    WEB_APPLICATION = "web_application"
    ENDPOINT = "endpoint"
    CREDENTIAL = "credential"
    ACCOUNT = "account"
    DATA_STORE = "data_store"
    FINDING = "finding"


class EdgeType(str, Enum):
    HOSTS = "HOSTS"
    EXPOSES = "EXPOSES"
    HAS_FINDING = "HAS_FINDING"
    YIELDS = "YIELDS"
    AUTHENTICATES_AS = "AUTHENTICATES_AS"
    GRANTS_ACCESS_TO = "GRANTS_ACCESS_TO"
    TRUSTS = "TRUSTS"


class AssetType(str, Enum):
    DOMAIN = "domain"
    SUBDOMAIN = "subdomain"
    IP = "ip"
    CLOUD_RESOURCE = "cloud_resource"


class CredentialType(str, Enum):
    PASSWORD = "password"
    API_KEY = "api_key"
    SESSION_TOKEN = "session_token"
    SSH_KEY = "ssh_key"


class PrivilegeLevel(str, Enum):
    ADMIN = "admin"
    STANDARD = "standard"
    SERVICE = "service"


class DataClassification(str, Enum):
    PII = "PII"
    PCI = "PCI"
    NONE = "none"


class FindingStatus(str, Enum):
    OPEN = "open"
    FIXED = "fixed"
    ACCEPTED_RISK = "accepted-risk"


class VerificationStatus(str, Enum):
    """Whether a tester has confirmed a finding is real.

    Deliberately separate from FindingStatus, which tracks *remediation*
    ("is it fixed?"). This tracks *triage* ("is it actually there?") — a
    finding can be confirmed-real and still open, or unverified and
    already fixed.

    Kompromap never sets this to CONFIRMED or FALSE_POSITIVE by itself.
    Deciding a finding is a false positive means verifying the
    vulnerability — sending the payload, reading the response — and this
    tool never touches the target; it only reads files you hand it. A
    heuristic guess presented as a verdict is actively dangerous: if the
    tool says "probably a false positive" and you skip verifying, and it
    was real, the report ships with a live vulnerability missed because
    software was confident. So the tool surfaces corroborating evidence
    and records the analyst's judgement.
    """

    UNVERIFIED = "unverified"
    CONFIRMED = "confirmed"
    FALSE_POSITIVE = "false-positive"
    NEEDS_RETEST = "needs-retest"
