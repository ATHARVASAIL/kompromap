"""Knowledge base service.

Provides CRUD for vulnerability reference entries and a similarity
search that scores how well a finding matches known CWE entries.

Scoring: exact CWE match (1.0), Jaccard on tags, keyword overlap on
descriptions. Returns top-N results above a minimum threshold.
"""
from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.models import KnowledgeBaseEntry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Seed data — common CWEs relevant to pentesting engagements.
# Each entry gives the CWE ID, a concise name, description, remediation
# steps, references, and tags.
# ---------------------------------------------------------------------------
SEED_ENTRIES: list[dict[str, Any]] = [
    {
        "cwe_id": "CWE-79",
        "name": "Cross-site Scripting (XSS)",
        "description": "The application takes untrusted data and embeds it in web content without proper validation or escaping, allowing an attacker to execute arbitrary scripts in the victim's browser.",
        "remediation": "Apply context-sensitive output encoding. Use a modern templating engine that auto-escapes by default. Implement a strong Content-Security-Policy header. Validate and sanitize all user input on the server side.",
        "references": [
            "https://cwe.mitre.org/data/definitions/79.html",
            "https://owasp.org/www-community/attacks/xss/",
            "https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html",
        ],
        "tags": ["xss", "injection", "web", "client-side", "owasp-top10-a03"],
        "owasp_category": "A03:2021-Injection",
        "severity_guidance": "Medium to High depending on context",
    },
    {
        "cwe_id": "CWE-89",
        "name": "SQL Injection",
        "description": "The application constructs SQL queries using user-controlled input without proper neutralisation, allowing an attacker to modify query logic, extract data, or execute arbitrary SQL commands.",
        "remediation": "Use parameterised queries or prepared statements exclusively. Never concatenate user input into SQL strings. Apply the principle of least privilege to database accounts. Validate input against an allow-list where possible.",
        "references": [
            "https://cwe.mitre.org/data/definitions/89.html",
            "https://owasp.org/www-community/attacks/SQL_Injection",
            "https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html",
        ],
        "tags": ["sqli", "injection", "web", "database", "owasp-top10-a03"],
        "owasp_category": "A03:2021-Injection",
        "severity_guidance": "Critical",
    },
    {
        "cwe_id": "CWE-78",
        "name": "OS Command Injection",
        "description": "The application passes user-supplied data to a system shell or external command without adequate validation, allowing an attacker to execute arbitrary operating-system commands.",
        "remediation": "Avoid passing user input to system commands. Where unavoidable, use strict allow-lists and validate against them. Run the application under a low-privilege account. Consider using language-native libraries instead of shelling out.",
        "references": [
            "https://cwe.mitre.org/data/definitions/78.html",
            "https://owasp.org/www-community/attacks/Command_Injection",
        ],
        "tags": ["command-injection", "rce", "injection", "owasp-top10-a03"],
        "owasp_category": "A03:2021-Injection",
        "severity_guidance": "Critical",
    },
    {
        "cwe_id": "CWE-352",
        "name": "Cross-Site Request Forgery (CSRF)",
        "description": "The application allows an attacker to trick a user's browser into sending a forged HTTP request, including the user's session cookie and other automatically-attached credentials, to a vulnerable endpoint.",
        "remediation": "Require anti-CSRF tokens for all state-changing operations. Validate the Origin or Referer header. Use SameSite cookie attributes. Consider requiring user interaction (re-authentication) for sensitive actions.",
        "references": [
            "https://cwe.mitre.org/data/definitions/352.html",
            "https://owasp.org/www-community/attacks/csrf/",
            "https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html",
        ],
        "tags": ["csrf", "web", "session", "owasp-top10-a01"],
        "owasp_category": "A01:2021-Broken_Access_Control",
        "severity_guidance": "Medium",
    },
    {
        "cwe_id": "CWE-918",
        "name": "Server-Side Request Forgery (SSRF)",
        "description": "The application fetches a remote resource using a URL supplied by the user without sufficient validation, allowing an attacker to cause the server to request internal resources or external systems.",
        "remediation": "Validate and sanitise all user-supplied URLs against an allow-list. Use a dedicated egress proxy with strict network segmentation. Deny requests to private and link-local IP ranges. Apply network-layer controls (firewall rules) as defence in depth.",
        "references": [
            "https://cwe.mitre.org/data/definitions/918.html",
            "https://owasp.org/www-community/attacks/Server_Side_Request_Forgery",
        ],
        "tags": ["ssrf", "web", "network", "owasp-top10-a10"],
        "owasp_category": "A10:2021-Server-Side_Request_Forgery",
        "severity_guidance": "High to Critical",
    },
    {
        "cwe_id": "CWE-22",
        "name": "Path Traversal",
        "description": "The application uses user input to construct a file path without properly neutralising special elements, allowing an attacker to access files outside the intended directory.",
        "remediation": "Validate user-supplied file names against a strict allow-list. Canonicalise paths before operating on them. Run the application in a chroot or container with minimal filesystem access. Never pass user input directly to file-system APIs.",
        "references": [
            "https://cwe.mitre.org/data/definitions/22.html",
            "https://owasp.org/www-community/attacks/Path_Traversal",
        ],
        "tags": ["path-traversal", "lfi", "web", "file-access", "owasp-top10-a01"],
        "owasp_category": "A01:2021-Broken_Access_Control",
        "severity_guidance": "High to Critical",
    },
    {
        "cwe_id": "CWE-287",
        "name": "Improper Authentication",
        "description": "The software's authentication mechanism does not adequately verify the claimed identity of a user, allowing attackers to gain access to functionality or data as another user.",
        "remediation": "Use multi-factor authentication. Enforce strong password policies. Implement account lockout after failed attempts. Protect authentication cookies with Secure and HttpOnly flags. Never expose credentials in error messages or logs.",
        "references": [
            "https://cwe.mitre.org/data/definitions/287.html",
            "https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html",
        ],
        "tags": ["auth", "authentication", "credentials", "owasp-top10-a07"],
        "owasp_category": "A07:2021-Identification_and_Authentication_Failures",
        "severity_guidance": "High to Critical",
    },
    {
        "cwe_id": "CWE-502",
        "name": "Deserialisation of Untrusted Data",
        "description": "The application deserialises user-supplied data without sufficient verification, allowing an attacker to craft a payload that executes arbitrary code when deserialised.",
        "remediation": "Avoid deserialising untrusted data. Where unavoidable, implement integrity checks (digital signatures) and enforce strict type constraints. Use safe serialisation formats (JSON) instead of native object serialisation.",
        "references": [
            "https://cwe.mitre.org/data/definitions/502.html",
            "https://owasp.org/www-community/vulnerabilities/Deserialization_of_untrusted_data",
        ],
        "tags": ["deserialization", "rce", "injection", "owasp-top10-a08"],
        "owasp_category": "A08:2021-Software_and_Data_Integrity_Failures",
        "severity_guidance": "Critical",
    },
    {
        "cwe_id": "CWE-20",
        "name": "Improper Input Validation",
        "description": "The application receives user input but does not validate or only partially validates its properties (type, length, range, etc.), leading to unexpected behaviour.",
        "remediation": "Validate all input at the boundary — type, length, format, range, and accepted values. Use a centralised validation library. Apply allow-lists over deny-lists. Reject invalid input rather than sanitising it.",
        "references": [
            "https://cwe.mitre.org/data/definitions/20.html",
        ],
        "tags": ["input-validation", "web", "general", "owasp-top10-a03"],
        "owasp_category": "A03:2021-Injection",
        "severity_guidance": "Variable",
    },
    {
        "cwe_id": "CWE-611",
        "name": "XML External Entity (XXE)",
        "description": "The application processes XML input containing a reference to an external entity, allowing an attacker to read local files, perform SSRF, or cause denial of service.",
        "remediation": "Disable DTD processing and external entity resolution in XML parsers. Use JSON where XML is not required. Keep XML-parsing libraries up to date. Run parsers in a sandboxed environment.",
        "references": [
            "https://cwe.mitre.org/data/definitions/611.html",
            "https://cheatsheetseries.owasp.org/cheatsheets/XML_External_Entity_Prevention_Cheat_Sheet.html",
        ],
        "tags": ["xxe", "xml", "injection", "owasp-top10-a03", "owasp-top10-a05"],
        "owasp_category": "A03:2021-Injection",
        "severity_guidance": "High to Critical",
    },
    {
        "cwe_id": "CWE-269",
        "name": "Improper Privilege Management",
        "description": "The software does not properly assign, modify, track, or control privileges of actors, allowing an attacker to gain unauthorised access to resources or functionality.",
        "remediation": "Enforce the principle of least privilege. Validate authorisation on every request, not just at entry points. Use role-based access control (RBAC) with a centralised authorisation service. Log privilege changes.",
        "references": [
            "https://cwe.mitre.org/data/definitions/269.html",
            "https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html",
        ],
        "tags": ["privilege-escalation", "authz", "access-control", "owasp-top10-a01"],
        "owasp_category": "A01:2021-Broken_Access_Control",
        "severity_guidance": "High to Critical",
    },
    {
        "cwe_id": "CWE-601",
        "name": "URL Redirection to Untrusted Site",
        "description": "The application redirects users to a URL supplied via untrusted input without proper validation, enabling phishing attacks by redirecting users to attacker-controlled sites.",
        "remediation": "Validate all redirect URLs against an allow-list of trusted destinations. Use indirect references (route names, IDs) instead of raw URLs. Inform the user when a redirect to an external site is about to occur.",
        "references": [
            "https://cwe.mitre.org/data/definitions/601.html",
            "https://cheatsheetseries.owasp.org/cheatsheets/Unvalidated_Redirects_and_Forwards_Cheat_Sheet.html",
        ],
        "tags": ["open-redirect", "web", "phishing", "owasp-top10-a01"],
        "owasp_category": "A01:2021-Broken_Access_Control",
        "severity_guidance": "Medium",
    },
]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SimilarEntry:
    """A knowledge-base entry ranked by similarity to a query."""

    entry_id: str
    cwe_id: str | None
    name: str
    score: float
    match_reason: str


@dataclass(frozen=True)
class SearchResult:
    """Result of a similarity search."""

    query_cwe: str | None
    query_tags: list[str]
    matches: list[SimilarEntry]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_WORD_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> set[str]:
    return set(_WORD_RE.findall(text.lower()))


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


def _keyword_overlap(query: str, candidate: str) -> float:
    qt = _tokenize(query)
    ct = _tokenize(candidate)
    if not qt or not ct:
        return 0.0
    return len(qt & ct) / len(qt)


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------
def create_entry(
    db: Session,
    *,
    cwe_id: str | None = None,
    name: str,
    description: str,
    remediation: str = "",
    references: list[str] | None = None,
    tags: list[str] | None = None,
    owasp_category: str | None = None,
    severity_guidance: str | None = None,
) -> KnowledgeBaseEntry:
    entry = KnowledgeBaseEntry(
        cwe_id=cwe_id,
        name=name,
        description=description,
        remediation=remediation,
        references=references or [],
        tags=tags or [],
        owasp_category=owasp_category,
        severity_guidance=severity_guidance,
    )
    db.add(entry)
    db.flush()
    return entry


def get_entry(db: Session, entry_id: uuid.UUID) -> KnowledgeBaseEntry | None:
    return db.get(KnowledgeBaseEntry, entry_id)


def list_entries(
    db: Session,
    *,
    cwe_id: str | None = None,
    tag: str | None = None,
    search: str | None = None,
    limit: int = 100,
) -> list[KnowledgeBaseEntry]:
    q = db.query(KnowledgeBaseEntry)
    if cwe_id:
        q = q.filter(KnowledgeBaseEntry.cwe_id == cwe_id)
    if tag:
        q = q.filter(KnowledgeBaseEntry.tags.contains([tag]))
    if search:
        q = q.filter(KnowledgeBaseEntry.name.ilike(f"%{search}%"))
    return q.limit(limit).all()


def update_entry(
    db: Session, entry_id: uuid.UUID, **updates: Any
) -> KnowledgeBaseEntry | None:
    entry = db.get(KnowledgeBaseEntry, entry_id)
    if entry is None:
        return None
    for key, value in updates.items():
        if hasattr(entry, key):
            setattr(entry, key, value)
    db.flush()
    return entry


def delete_entry(db: Session, entry_id: uuid.UUID) -> bool:
    entry = db.get(KnowledgeBaseEntry, entry_id)
    if entry is None:
        return False
    db.delete(entry)
    db.flush()
    return True


def seed_knowledge_base(db: Session) -> int:
    """Insert seed entries if they don't already exist.

    Returns the number of newly inserted entries.
    """
    import uuid

    existing = {
        row.cwe_id
        for row in db.query(KnowledgeBaseEntry.cwe_id).filter(
            KnowledgeBaseEntry.cwe_id.is_not(None)
        )
    }
    inserted = 0
    for seed in SEED_ENTRIES:
        if seed["cwe_id"] in existing:
            continue
        create_entry(db, **seed)
        inserted += 1
    if inserted:
        db.commit()
    return inserted


# ---------------------------------------------------------------------------
# Similarity search
# ---------------------------------------------------------------------------
def similarity_search(
    db: Session,
    *,
    cwe_id: str | None = None,
    tags: Sequence[str] | None = None,
    description: str | None = None,
    top_n: int = 5,
    min_score: float = 0.2,
) -> SearchResult:
    """Find knowledge base entries similar to a query.

    Scoring components (combined as weighted average):
      * Exact CWE match: 1.0
      * Tag Jaccard: 0.0–1.0
      * Keyword overlap on description: 0.0–1.0
    """
    candidates = db.query(KnowledgeBaseEntry).limit(200).all()

    query_tags = set(t.lower().strip() for t in (tags or []) if t)
    query_cwe = (cwe_id or "").strip().upper()
    query_desc = (description or "").strip()

    scored: list[SimilarEntry] = []
    for entry in candidates:
        scores: list[tuple[float, str]] = []

        # Exact CWE match
        if query_cwe and entry.cwe_id and entry.cwe_id.upper() == query_cwe:
            scores.append((1.0, "exact CWE match"))

        # Tag overlap (Jaccard)
        if query_tags:
            entry_tags = set(t.lower().strip() for t in (entry.tags or []))
            j = _jaccard(query_tags, entry_tags)
            if j > 0:
                scores.append((j, f"tag overlap ({len(query_tags & entry_tags)} shared)"))

        # Keyword overlap on description
        if query_desc and entry.description:
            kw = _keyword_overlap(query_desc, entry.description)
            if kw > 0:
                scores.append((kw, "keyword match in description"))

        if not scores:
            continue

        combined = sum(s for s, _ in scores) / len(scores)
        if combined < min_score:
            continue

        best_reason = max(scores, key=lambda x: x[0])[1]
        scored.append(
            SimilarEntry(
                entry_id=str(entry.id),
                cwe_id=entry.cwe_id,
                name=entry.name,
                score=round(combined, 4),
                match_reason=best_reason,
            )
        )

    scored.sort(key=lambda e: e.score, reverse=True)
    return SearchResult(
        query_cwe=cwe_id, query_tags=list(query_tags), matches=scored[:top_n]
    )
