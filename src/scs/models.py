"""Domain models shared across compliance, risk, scoring, and dashboard.

Every piece of evidence in this system carries provenance — the source it
came from, when it was observed, and a credibility prior. This is the
schema-level commitment that makes trust-calibrated fusion possible.
"""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from scs.credibility import credibility_of


# ---------------------------------------------------------------------------
# Supplier
# ---------------------------------------------------------------------------


class SupplierCategory(str, Enum):
    """High-level role within an electronics supply chain."""

    OEM = "oem"
    EMS = "ems"
    COMPONENT_MANUFACTURER = "component_manufacturer"
    DISTRIBUTOR_AUTHORISED = "distributor_authorised"
    DISTRIBUTOR_BROKER = "distributor_broker"
    PCB_FABRICATOR = "pcb_fabricator"
    SEMICONDUCTOR_FAB = "semiconductor_fab"
    TEST_HOUSE = "test_house"


class Supplier(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    legal_name: str | None = None
    country: str = Field(..., description="ISO-3166 alpha-2")
    category: SupplierCategory
    cin: str | None = None
    website: str | None = None
    incorporated: date | None = None
    aliases: tuple[str, ...] = Field(default_factory=tuple)

    @field_validator("country")
    @classmethod
    def _country_upper(cls, v: str) -> str:
        return v.strip().upper()


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------


class Provenance(BaseModel):
    """Where an evidence item came from. Mandatory on every signal."""

    source_name: str = Field(
        ...,
        description="Human-readable source label, e.g. 'Reuters', 'OFAC SDN'",
    )
    source_url: str | None = None
    observed_at: datetime = Field(default_factory=datetime.utcnow)
    published_at: datetime | None = None

    @property
    def credibility(self) -> float:
        """Credibility prior in [0, 1] derived from the source URL/name."""
        # Prefer URL-based lookup; fall back to name-based
        url_prior = credibility_of(self.source_url) if self.source_url else None
        name_prior = credibility_of(self.source_name)
        if url_prior is not None and self.source_url:
            return url_prior
        return name_prior


# ---------------------------------------------------------------------------
# Compliance
# ---------------------------------------------------------------------------


CheckStatus = Literal["pass", "fail", "unknown"]


class ComplianceCheck(BaseModel):
    """Result of a single compliance check.

    Compliance sources have very high credibility priors (built into the
    Provenance) but they're not infallible — a debarment list might be
    out of date, a sanctions match might be a homonym. Fusion still
    weights them, just heavily.
    """

    source: str
    status: CheckStatus
    detail: str = ""
    provenance: Provenance

    # Convenience for older code paths
    @property
    def evidence_url(self) -> str | None:
        return self.provenance.source_url

    @property
    def checked_at(self) -> datetime:
        return self.provenance.observed_at


class ComplianceReport(BaseModel):
    supplier_id: str
    checks: list[ComplianceCheck]

    @property
    def is_clean(self) -> bool:
        return all(c.status == "pass" for c in self.checks)

    @property
    def fail_count(self) -> int:
        return sum(1 for c in self.checks if c.status == "fail")


# ---------------------------------------------------------------------------
# Risk sensing
# ---------------------------------------------------------------------------


class RiskEventType(str, Enum):
    SANCTIONS = "sanctions"
    LITIGATION = "litigation"
    LABOR_DISPUTE = "labor_dispute"
    ENVIRONMENTAL = "environmental"
    FINANCIAL_DISTRESS = "financial_distress"
    CYBERSECURITY = "cybersecurity"
    QUALITY_RECALL = "quality_recall"
    COUNTERFEIT = "counterfeit"
    LEADERSHIP_CHANGE = "leadership_change"
    POSITIVE = "positive"
    OTHER = "other"


class RiskSignal(BaseModel):
    """Single structured signal extracted from one news article.

    The provenance carries the credibility prior of the originating source;
    the fusion layer reads it directly.
    """

    event_type: RiskEventType
    severity: int = Field(..., ge=0, le=5)
    sentiment: float = Field(..., ge=-1.0, le=1.0)
    summary: str
    provenance: Provenance
    is_corroborated: bool = Field(
        default=False,
        description=(
            "True when at least one other signal of the same event_type for "
            "the same supplier exists from an independent source. Set by the "
            "aggregation step, not by the LLM."
        ),
    )

    @property
    def credibility(self) -> float:
        return self.provenance.credibility


class RiskProfile(BaseModel):
    supplier_id: str
    signals: list[RiskSignal]
    article_count: int

    @property
    def avg_sentiment(self) -> float:
        if not self.signals:
            return 0.0
        return sum(s.sentiment for s in self.signals) / len(self.signals)

    @property
    def max_severity(self) -> int:
        return max((s.severity for s in self.signals), default=0)

    @property
    def credibility_weighted_severity(self) -> float:
        """Severity weighted by source credibility — used by the defense."""
        if not self.signals:
            return 0.0
        num = sum(s.severity * s.credibility for s in self.signals)
        den = sum(s.credibility for s in self.signals)
        return num / den if den > 0 else 0.0


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


class FeatureContribution(BaseModel):
    """One line of the score breakdown."""

    feature: str
    raw_value: float
    weight: float
    contribution: float


class SupplierScore(BaseModel):
    """Composite trust score with full audit trail.

    `belief_safe` and `belief_risky` are the Dempster–Shafer belief masses
    on the two singletons; `uncertainty` is the mass on the universe set
    {safe, risky} that the evidence couldn't resolve. They sum to 1.
    """

    supplier_id: str
    score: float = Field(..., ge=0.0, le=100.0)
    belief_safe: float = Field(..., ge=0.0, le=1.0)
    belief_risky: float = Field(..., ge=0.0, le=1.0)
    uncertainty: float = Field(..., ge=0.0, le=1.0)
    contributions: list[FeatureContribution]
    computed_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def grade(self) -> str:
        s = self.score
        if s >= 80:
            return "A"
        if s >= 65:
            return "B"
        if s >= 50:
            return "C"
        if s >= 35:
            return "D"
        return "F"
