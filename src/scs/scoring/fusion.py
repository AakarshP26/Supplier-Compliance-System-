"""Dempster–Shafer evidence combination.

Frame of discernment Θ = {safe, risky}. Each piece of evidence is mapped
to a basic probability assignment (BPA) — a function m: 2^Θ → [0, 1] over
the powerset:

    m(∅) = 0
    m({safe})  = ms        (mass on the singleton 'safe')
    m({risky}) = mr        (mass on the singleton 'risky')
    m(Θ)       = 1 - ms - mr   (mass on the universe = uncertainty)

Two BPAs m1, m2 combine via Dempster's rule:

    K = Σ over A∩B = ∅ of m1(A) · m2(B)              (conflict mass)
    (m1 ⊕ m2)(C) = (1 / (1-K)) · Σ over A∩B=C of m1(A) · m2(B)

We use the Yager modification when K is high (treat conflict as
uncertainty rather than redistributing it) — important here because
adversarial evidence creates exactly that high-conflict regime.

Each evidence item's BPA is shaped by:
  * its credibility prior (from credibility.py),
  * its corroboration status (uncorroborated -> mass shifts toward Θ),
  * for risk signals: severity (→ mr) and sentiment (→ ms or mr).

Output is a SupplierScore with belief_safe, belief_risky, uncertainty,
plus a 0-100 score (rescaled belief difference) and per-feature
contributions.
"""
from __future__ import annotations

from dataclasses import dataclass

from scs.models import (
    ComplianceCheck,
    ComplianceReport,
    FeatureContribution,
    RiskProfile,
    RiskSignal,
    SupplierScore,
)


# ---------------------------------------------------------------------------
# Basic Probability Assignment (BPA)
# ---------------------------------------------------------------------------


@dataclass
class BPA:
    """Mass over {{safe}, {risky}, Θ}. Must sum to 1.0."""

    safe: float
    risky: float
    theta: float
    label: str = ""

    def __post_init__(self) -> None:
        total = self.safe + self.risky + self.theta
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"BPA does not sum to 1: {total} ({self.label})")
        for v in (self.safe, self.risky, self.theta):
            if v < -1e-9 or v > 1 + 1e-9:
                raise ValueError(f"BPA mass out of range: {v} ({self.label})")


def combine_yager(a: BPA, b: BPA) -> BPA:
    """Yager's modified combination: route conflict to Θ (uncertainty).

    Cleaner than vanilla Dempster's rule in adversarial regimes where two
    sources actively disagree — vanilla normalisation away the conflict
    mass produces overconfident posteriors.
    """
    safe = a.safe * b.safe + a.safe * b.theta + a.theta * b.safe
    risky = a.risky * b.risky + a.risky * b.theta + a.theta * b.risky
    conflict = a.safe * b.risky + a.risky * b.safe
    theta = a.theta * b.theta + conflict  # conflict -> uncertainty
    return BPA(safe=safe, risky=risky, theta=theta, label=f"({a.label}⊕{b.label})")


def combine_many(bpas: list[BPA]) -> BPA:
    """Reduce a list of BPAs with Yager's rule. Empty -> total uncertainty."""
    if not bpas:
        return BPA(safe=0.0, risky=0.0, theta=1.0, label="∅")
    acc = bpas[0]
    for b in bpas[1:]:
        acc = combine_yager(acc, b)
    return acc


# ---------------------------------------------------------------------------
# Evidence → BPA
# ---------------------------------------------------------------------------


def bpa_from_check(check: ComplianceCheck) -> BPA:
    """Map a single compliance check to a BPA.

    Compliance checks have very high credibility priors so the mass
    sent to Θ is small — we don't want to throw away ground truth from
    OFAC just because a single news article disagreed.
    """
    cred = check.provenance.credibility
    if check.status == "fail":
        # Strong negative evidence
        risky = 0.85 * cred
        safe = 0.0
    elif check.status == "pass":
        # Mild positive evidence — passing a sanctions check doesn't make
        # a supplier good, just not flagged.
        safe = 0.4 * cred
        risky = 0.0
    else:  # unknown
        safe = 0.0
        risky = 0.0
    theta = 1.0 - safe - risky
    return BPA(safe=safe, risky=risky, theta=theta, label=check.source)


def bpa_from_signal(signal: RiskSignal, recency_decay: float = 1.0) -> BPA:
    """Map one risk signal to a BPA.

    Mass scales with credibility AND corroboration AND severity.
    Uncorroborated signals from low-credibility sources get heavily
    discounted toward Θ — this is the defense.
    """
    cred = signal.credibility
    corroboration_factor = 1.0 if signal.is_corroborated else 0.5

    # Effective evidence strength in [0, 1].
    strength = cred * corroboration_factor * recency_decay

    if signal.event_type.value == "positive":
        safe = 0.6 * strength
        risky = 0.0
    else:
        # Severity in 0..5 -> normalised 0..1
        sev_norm = signal.severity / 5.0
        # Sentiment in -1..1; only use the negative side for risk
        sent_neg = max(-signal.sentiment, 0.0)
        # Combine; clamp to <0.85 so we never assign 100% mass to a singleton
        risky = min(0.85, strength * (0.6 * sev_norm + 0.4 * sent_neg))
        safe = 0.0

    theta = 1.0 - safe - risky
    return BPA(
        safe=safe, risky=risky, theta=theta, label=f"news:{signal.event_type.value}"
    )


# ---------------------------------------------------------------------------
# Composite scoring
# ---------------------------------------------------------------------------


def fuse(
    supplier_id: str,
    compliance: ComplianceReport,
    risk: RiskProfile,
) -> SupplierScore:
    """Run DS fusion across all evidence and produce a SupplierScore."""
    bpas: list[BPA] = []
    contributions: list[FeatureContribution] = []

    # Compliance evidence
    for check in compliance.checks:
        b = bpa_from_check(check)
        bpas.append(b)
        contributions.append(
            FeatureContribution(
                feature=f"compliance::{check.source}",
                raw_value={"pass": 1.0, "fail": -1.0, "unknown": 0.0}[check.status],
                weight=check.provenance.credibility,
                # Sign of contribution mirrors safe vs risky pull
                contribution=(b.safe - b.risky) * 100.0,
            )
        )

    # Risk evidence
    for sig in risk.signals:
        b = bpa_from_signal(sig)
        bpas.append(b)
        contributions.append(
            FeatureContribution(
                feature=f"news::{sig.event_type.value}::{sig.provenance.source_name}",
                raw_value=float(sig.severity),
                weight=sig.credibility * (1.0 if sig.is_corroborated else 0.5),
                contribution=(b.safe - b.risky) * 100.0,
            )
        )

    fused = combine_many(bpas)

    # Score: rescale belief difference [-1, 1] -> [0, 100], origin at 50
    diff = fused.safe - fused.risky
    score = 50.0 + 50.0 * diff
    score = max(0.0, min(100.0, score))

    return SupplierScore(
        supplier_id=supplier_id,
        score=score,
        belief_safe=fused.safe,
        belief_risky=fused.risky,
        uncertainty=fused.theta,
        contributions=sorted(
            contributions, key=lambda c: abs(c.contribution), reverse=True
        ),
    )
