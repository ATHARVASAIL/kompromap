"""Parse CVSS v3.x vector strings into the components the scoring model
actually needs.

Why this exists: the ease_score formula (spec §4) has a `complexity` term,
but complexity was never a stored Finding property — so it was a flat 0.5
placeholder applied to every finding regardless of how hard it actually is
to exploit. That's the single largest accuracy gap in path-finding: a
one-click unauthenticated RCE and a race condition requiring a
man-in-the-middle position scored identically on that term.

Attack Complexity is, however, a *first-class field in the CVSS vector
string itself* (`AC:L` / `AC:H`), and Nuclei templates carrying
`cvss-metrics` give it to us for free. Same for Privileges Required
(`PR:`) and User Interaction (`UI:`), which are better signals for
"can an attacker actually do this unattended" than the single
`auth_required` boolean the schema has.

So: when a vector is present, use the real values. When it isn't, fall
back to the configured default and *say so* — `ComplexityBasis` records
which happened, so the UI can distinguish a measured score from an
assumed one rather than presenting both with equal confidence.

Reference: CVSS v3.1 specification, section 2 (Base Metrics).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

# CVSS v3 vectors look like:
#   CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H
_VECTOR_RE = re.compile(r"^CVSS:3\.[01]/(?:[A-Z]+:[A-Z]+/?)+$", re.IGNORECASE)
_PART_RE = re.compile(r"([A-Z]+):([A-Z]+)", re.IGNORECASE)


class ComplexityBasis(str, Enum):
    """Where a complexity value came from — measured or assumed."""

    VECTOR = "vector"  # parsed from a real CVSS vector string
    DEFAULT = "default"  # configured fallback, no vector available


# Attack Complexity -> normalized 0..1 where 1 = hardest.
# CVSS only defines two levels here, so this is a faithful mapping rather
# than an invented gradient.
_AC_COMPLEXITY = {"L": 0.15, "H": 0.85}

# Privileges Required -> how much standing access the attacker needs.
_PR_COMPLEXITY = {"N": 0.0, "L": 0.4, "H": 0.8}

# User Interaction -> needing a victim to click something is a real
# obstacle to an unattended attack chain.
_UI_COMPLEXITY = {"N": 0.0, "R": 0.5}


@dataclass(frozen=True)
class CvssVector:
    """The subset of CVSS v3 metrics this scoring model uses."""

    attack_vector: str | None = None  # AV
    attack_complexity: str | None = None  # AC
    privileges_required: str | None = None  # PR
    user_interaction: str | None = None  # UI
    scope: str | None = None  # S
    confidentiality: str | None = None  # C
    integrity: str | None = None  # I
    availability: str | None = None  # A

    @property
    def is_network_reachable(self) -> bool:
        """AV:N — reachable over a network, as opposed to needing local or
        physical access. Relevant to whether a chain step is realistic at
        all from an external position."""
        return (self.attack_vector or "").upper() == "N"

    @property
    def is_unauthenticated(self) -> bool:
        """PR:N — no privileges needed. More precise than the schema's
        `auth_required` boolean, which conflates "needs a login" with
        "needs admin"."""
        return (self.privileges_required or "").upper() == "N"

    @property
    def needs_user_interaction(self) -> bool:
        return (self.user_interaction or "").upper() == "R"

    def effective_complexity(self) -> float | None:
        """Blend AC, PR and UI into a single 0..1 difficulty figure.

        Attack Complexity dominates because that's the metric the CVSS
        spec defines as difficulty proper; PR and UI are weighted lower
        because they describe preconditions rather than exploit
        difficulty, but they genuinely do make an unattended chain harder.

        Returns None when nothing usable was present, so the caller can
        fall back rather than silently scoring on a partial vector.
        """
        parts: list[tuple[float, float]] = []  # (value, weight)

        ac = _AC_COMPLEXITY.get((self.attack_complexity or "").upper())
        if ac is not None:
            parts.append((ac, 0.6))

        pr = _PR_COMPLEXITY.get((self.privileges_required or "").upper())
        if pr is not None:
            parts.append((pr, 0.25))

        ui = _UI_COMPLEXITY.get((self.user_interaction or "").upper())
        if ui is not None:
            parts.append((ui, 0.15))

        if not parts:
            return None

        total_weight = sum(w for _, w in parts)
        blended = sum(v * w for v, w in parts) / total_weight
        return max(0.0, min(1.0, blended))


def parse_cvss_vector(vector: str | None) -> CvssVector | None:
    """Parse a CVSS v3.x vector string. Returns None if it isn't one.

    Deliberately strict about the `CVSS:3.x/` prefix — CVSS v2 vectors use
    the same `AV:`/`AC:` letters with *different* meanings (v2's AC:M has
    no v3 equivalent), so silently parsing one as v3 would produce
    confidently wrong numbers.
    """
    if not vector:
        return None

    cleaned = vector.strip()
    if not _VECTOR_RE.match(cleaned):
        return None

    metrics = {k.upper(): v.upper() for k, v in _PART_RE.findall(cleaned)}
    # The leading "CVSS:3.1" also matches _PART_RE; drop it.
    metrics.pop("CVSS", None)

    return CvssVector(
        attack_vector=metrics.get("AV"),
        attack_complexity=metrics.get("AC"),
        privileges_required=metrics.get("PR"),
        user_interaction=metrics.get("UI"),
        scope=metrics.get("S"),
        confidentiality=metrics.get("C"),
        integrity=metrics.get("I"),
        availability=metrics.get("A"),
    )


def complexity_from_vector(
    vector: str | None, default: float
) -> tuple[float, ComplexityBasis]:
    """Resolve a complexity value and report where it came from."""
    parsed = parse_cvss_vector(vector)
    if parsed is not None:
        effective = parsed.effective_complexity()
        if effective is not None:
            return effective, ComplexityBasis.VECTOR
    return default, ComplexityBasis.DEFAULT
