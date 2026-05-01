"""Domain models shared across compliance, risk, scoring, and dashboard.

These are the contract between modules. Keep them small and immutable
where possible — every other module imports from here.
"""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SupplierCategory(str, Enum):
    """High-level role within an electronics supply chain.

    Maps to the categories from the literature (Liu & Meidani 2024) but
    specialised for electronics manufacturing.
    """

    OEM = "oem"
    EMS = "ems"  # Electronics Manufacturing Services
    COMPONENT_MANUFACTURER = "component_manufacturer"
    DISTRIBUTOR_AUTHORISED = "distributor_authorised"
    DISTRIBUTOR_BROKER = "distributor_broker"
    PCB_FABRICATOR = "pcb_fabricator"
    SEMICONDUCTOR_FAB = "semiconductor_fab"
    TEST_HOUSE = "test_house"


class Supplier(BaseModel):
    """A single supplier we are evaluating."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(..., description="Stable identifier, e.g. 'dixon-tech'")
    name: str
    legal_name: str | None = None
    country: str = Field(..., description="ISO-3166 alpha-2, e.g. 'IN'")
    category: SupplierCategory
    cin: str | None = Field(
        default=None,
        description="Indian Corporate Identification Number, if applicable",
    )
    website: str | None = None
    incorporated: date | None = None
    aliases: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Other names this supplier is known by — used for fuzzy matching",
    )

    @field_validator("country")
    @classmethod
    def _country_upper(cls, v: str) -> str:
        return v.strip().upper()


# ---------------------------------------------------------------------------
# Compliance
# ---------------------------------------------------------------------------


CheckStatus = Literal["pass", "fail", "unknown"]


class ComplianceCheck(BaseModel):
    """Result of a single compliance check against one source."""

    source: str = Field(..., description="e.g. 'OFAC SDN', 'World Bank Debarred', 'BIS CRS'")
    status: CheckStatus
    detail: str = ""
    evidence_url: str | None = None
    checked_at: datetime = Field(default_factory=datetime.utcnow)


class ComplianceReport(BaseModel):
    """All compliance check results for one supplier."""

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
    POSITIVE = "positive"  # awards, expansions — counted negatively in risk
    OTHER = "other"


class RiskSignal(BaseModel):
    """Single structured signal extracted from one news article."""

    event_type: RiskEventType
    severity: int = Field(..., ge=0, le=5, description="0 = info, 5 = catastrophic")
    sentiment: float = Field(..., ge=-1.0, le=1.0)
    summary: str
    source_title: str
    source_url: str | None = None
    extracted_at: datetime = Field(default_factory=datetime.utcnow)


class RiskProfile(BaseModel):
    """Aggregated risk signals for one supplier."""

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


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


class FeatureContribution(BaseModel):
    """One line of the score breakdown — what fed in and how much."""

    feature: str
    raw_value: float
    weight: float
    contribution: float  # weight * normalised(raw_value), in score units


class SupplierScore(BaseModel):
    """Composite score plus the audit trail explaining how it got there."""

    supplier_id: str
    score: float = Field(..., ge=0.0, le=100.0)
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
