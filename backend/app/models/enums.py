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
