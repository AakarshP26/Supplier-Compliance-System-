"""Supplier metrics taxonomy.

The 35-parameter framework matches the four signal buckets from the
Parameters.docx requirements (operational reliability, financial
solvency, compliance/ESG trust, early-warning patterns) plus an
identity/scale and capability group.

Each parameter carries:
  * a numeric or categorical value;
  * a `confidence` in [0, 1] reflecting how the value was obtained
    (verified filing -> 1.0, self-reported -> 0.4, inferred -> 0.2);
  * a `source` label.

The dashboard surfaces every parameter on the Parameters page and on
each supplier's detail page; the scoring layer reads a curated subset
into Dempster-Shafer fusion so financial distress, ESG controversies,
and certification gaps actually move the trust score for very small
suppliers that have little news footprint.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Metadata about each parameter (descriptions, healthy ranges, units).
# Used by the Parameters page and by the scoring layer.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ParameterSpec:
    """Metadata for one parameter — drives display + scoring thresholds."""

    key: str
    group: str
    label: str
    description: str
    unit: str
    direction: Literal["higher_is_better", "lower_is_better", "in_range", "categorical"]
    healthy_min: float | None = None  # for higher_is_better / in_range
    healthy_max: float | None = None  # for lower_is_better / in_range
    concerning_min: float | None = None
    concerning_max: float | None = None
    used_in_scoring: bool = False
    source_examples: str = ""


SPECS: list[ParameterSpec] = [
    # ========================================================================
    # Group 1 — Identity & Scale (verifiable via filings; no scoring)
    # ========================================================================
    ParameterSpec(
        "years_in_operation", "Identity & scale",
        "Years in operation",
        "How long the legal entity has existed. Very young entities (<1 yr) are a "
        "common shell-company indicator borrowed from the cybersecurity domain.",
        "years", "higher_is_better", healthy_min=3.0, concerning_max=1.0,
        used_in_scoring=True,
        source_examples="MCA21 / Companies House / SEC EDGAR incorporation date",
    ),
    ParameterSpec(
        "employee_count", "Identity & scale",
        "Employee count", "Headcount disclosed in annual filings.",
        "people", "higher_is_better", healthy_min=10,
        source_examples="Annual report, MCA Form AOC-4",
    ),
    ParameterSpec(
        "annual_revenue_usd_m", "Identity & scale",
        "Annual revenue", "Most recent reported annual revenue in million USD.",
        "USD M", "higher_is_better", healthy_min=1.0,
        source_examples="P&L from MCA filings, 10-K, audited statements",
    ),
    ParameterSpec(
        "number_of_facilities", "Identity & scale",
        "Manufacturing facilities", "Number of plants / production sites.",
        "sites", "higher_is_better", healthy_min=1,
        source_examples="Company website, regulatory filings",
    ),
    ParameterSpec(
        "registered_capital_usd_m", "Identity & scale",
        "Registered / paid-up capital",
        "Paid-up capital from corporate registry filings.",
        "USD M", "higher_is_better", healthy_min=0.05,
        source_examples="MCA Master Data, Companies House",
    ),

    # ========================================================================
    # Group 2 — Financial health (Solvency score — scoring-relevant)
    # ========================================================================
    ParameterSpec(
        "current_ratio", "Financial health",
        "Current ratio",
        "Current assets / current liabilities. Below 1.0 = cannot cover short-term "
        "obligations from current assets.",
        "ratio", "higher_is_better", healthy_min=1.5, concerning_max=1.0,
        used_in_scoring=True,
        source_examples="Balance sheet from audited financials",
    ),
    ParameterSpec(
        "quick_ratio", "Financial health",
        "Quick ratio (acid test)",
        "(Current assets - inventory) / current liabilities. Strict liquidity test.",
        "ratio", "higher_is_better", healthy_min=1.0, concerning_max=0.7,
        used_in_scoring=True,
        source_examples="Balance sheet",
    ),
    ParameterSpec(
        "debt_to_equity_ratio", "Financial health",
        "Debt-to-equity",
        "Total liabilities / shareholder equity. High ratio = leveraged, fragile to demand shocks.",
        "ratio", "lower_is_better", healthy_max=1.5, concerning_min=2.5,
        used_in_scoring=True,
        source_examples="Balance sheet",
    ),
    ParameterSpec(
        "net_profit_margin_pct", "Financial health",
        "Net profit margin",
        "Net income / revenue. Sustained negative margins = insolvency risk.",
        "%", "higher_is_better", healthy_min=3.0, concerning_max=0.0,
        used_in_scoring=True,
        source_examples="P&L statement",
    ),
    ParameterSpec(
        "revenue_growth_yoy_pct", "Financial health",
        "Revenue growth (YoY)",
        "Year-on-year revenue growth percentage. Steep decline can precede bankruptcy.",
        "%", "higher_is_better", healthy_min=0.0, concerning_max=-15.0,
        used_in_scoring=True,
        source_examples="Comparative P&L",
    ),
    ParameterSpec(
        "days_payables_outstanding", "Financial health",
        "Days payables outstanding (DPO)",
        "Average days the supplier takes to pay their own vendors. Elongating DPO often precedes supplier bankruptcy.",
        "days", "lower_is_better", healthy_max=60, concerning_min=120,
        used_in_scoring=True,
        source_examples="Trade-credit databases, vendor surveys",
    ),
    ParameterSpec(
        "credit_score", "Financial health",
        "Credit score (D&B-style)",
        "1-100 composite credit health score. Below 40 = high risk.",
        "0-100", "higher_is_better", healthy_min=70, concerning_max=40,
        used_in_scoring=True,
        source_examples="Dun & Bradstreet PAYDEX, Experian, CRIF Highmark",
    ),
    ParameterSpec(
        "cash_runway_months", "Financial health",
        "Cash runway",
        "Months of operations the cash on hand can fund at current burn rate.",
        "months", "higher_is_better", healthy_min=6.0, concerning_max=3.0,
        used_in_scoring=True,
        source_examples="Cash flow statement, internal MIS",
    ),

    # ========================================================================
    # Group 3 — Operational reliability (Reliability score — scoring-relevant)
    # ========================================================================
    ParameterSpec(
        "on_time_delivery_pct", "Operational",
        "On-time delivery rate",
        "Percentage of orders delivered by the committed date.",
        "%", "higher_is_better", healthy_min=95.0, concerning_max=85.0,
        used_in_scoring=True,
        source_examples="ERP shipment vs PO commit-date logs",
    ),
    ParameterSpec(
        "defect_rate_ppm", "Operational",
        "Defect rate (PPM)",
        "Defective units per million shipped. Industry norm for electronics is < 1000 PPM.",
        "PPM", "lower_is_better", healthy_max=1000, concerning_min=5000,
        used_in_scoring=True,
        source_examples="Incoming-quality QC records",
    ),
    ParameterSpec(
        "order_fulfillment_accuracy_pct", "Operational",
        "Order fulfillment accuracy",
        "Ratio of ordered quantities to received quantities, by line item.",
        "%", "higher_is_better", healthy_min=98.0, concerning_max=92.0,
        source_examples="ERP receiving records",
    ),
    ParameterSpec(
        "avg_lead_time_days", "Operational",
        "Average lead time", "Mean order-to-delivery time across last 12 months.",
        "days", "lower_is_better", healthy_max=45, concerning_min=120,
        source_examples="ERP cycle-time data",
    ),
    ParameterSpec(
        "lead_time_variability_days", "Operational",
        "Lead-time variability",
        "Standard deviation of lead times. High variability = high operational risk.",
        "days", "lower_is_better", healthy_max=5.0, concerning_min=15.0,
        used_in_scoring=True,
        source_examples="ERP cycle-time data",
    ),
    ParameterSpec(
        "capacity_utilization_pct", "Operational",
        "Capacity utilisation",
        "Current production utilisation. Both ends are bad: > 90% = no headroom for demand spikes; < 40% = revenue stress.",
        "%", "in_range", healthy_min=55.0, healthy_max=85.0,
        concerning_min=90.0, concerning_max=40.0,
        source_examples="MIS reports, plant manager interviews",
    ),
    ParameterSpec(
        "customer_concentration_top1_pct", "Operational",
        "Customer concentration",
        "Percentage of revenue from the top single customer. > 40% = fragile to one-customer loss.",
        "%", "lower_is_better", healthy_max=30.0, concerning_min=50.0,
        used_in_scoring=True,
        source_examples="Annual report customer disclosures",
    ),

    # ========================================================================
    # Group 4 — Compliance & ESG trust (scoring-relevant)
    # ========================================================================
    ParameterSpec(
        "iso_9001_status", "Compliance & ESG",
        "ISO 9001 (QMS)", "Quality management system certification status.",
        "status", "categorical",
        used_in_scoring=True,
        source_examples="IAF MLA accredited certificate body, supplier portal",
    ),
    ParameterSpec(
        "iatf_16949_status", "Compliance & ESG",
        "IATF 16949 (automotive)", "Automotive QMS — required for tier-N automotive electronics.",
        "status", "categorical",
        source_examples="IATF Database",
    ),
    ParameterSpec(
        "as9100_status", "Compliance & ESG",
        "AS9100 (aerospace)", "Aerospace/defense QMS.",
        "status", "categorical",
        source_examples="OASIS Aerospace database",
    ),
    ParameterSpec(
        "iso_14001_status", "Compliance & ESG",
        "ISO 14001 (environmental)", "Environmental management system certification.",
        "status", "categorical",
        source_examples="Accredited cert body",
    ),
    ParameterSpec(
        "rohs_compliance_status", "Compliance & ESG",
        "RoHS compliance", "EU 2011/65 hazardous substance restriction declaration.",
        "status", "categorical",
        used_in_scoring=True,
        source_examples="Supplier RoHS declaration, IEC 62321 test reports",
    ),
    ParameterSpec(
        "conflict_minerals_disclosure", "Compliance & ESG",
        "Conflict minerals disclosure",
        "Has the supplier filed an SEC Form SD-equivalent disclosure for 3TG sourcing?",
        "yes/no", "categorical",
        source_examples="SEC EDGAR Form SD, RMI Conformant Smelter list",
    ),
    ParameterSpec(
        "esg_controversy_count_12mo", "Compliance & ESG",
        "ESG controversies (12 months)",
        "Count of distinct ESG-flagged events (modern slavery, environmental, governance) in last 12 months.",
        "events", "lower_is_better", healthy_max=0, concerning_min=2,
        used_in_scoring=True,
        source_examples="GDELT, RepRisk, news monitoring",
    ),
    ParameterSpec(
        "labor_audit_findings_severe_count", "Compliance & ESG",
        "Severe labour audit findings",
        "Number of severe non-conformities in latest social audit (SA8000 / SMETA / RBA).",
        "findings", "lower_is_better", healthy_max=0, concerning_min=1,
        used_in_scoring=True,
        source_examples="Sedex SMETA, RBA-VAP audits",
    ),

    # ========================================================================
    # Group 5 — Cybersecurity & capability
    # ========================================================================
    ParameterSpec(
        "iso_27001_status", "Cybersecurity & capability",
        "ISO 27001 (infosec)", "Information security management system certification.",
        "status", "categorical",
        source_examples="IAF MLA database",
    ),
    ParameterSpec(
        "cyber_incident_count_24mo", "Cybersecurity & capability",
        "Cyber incidents (24 months)",
        "Disclosed cybersecurity incidents (breaches, ransomware) in last 24 months.",
        "incidents", "lower_is_better", healthy_max=0, concerning_min=1,
        used_in_scoring=True,
        source_examples="NVD CVE references, news, regulatory disclosures",
    ),
    ParameterSpec(
        "patent_count", "Cybersecurity & capability",
        "Patent count", "Number of granted patents (rough capability indicator).",
        "patents", "higher_is_better", healthy_min=0,
        source_examples="USPTO, Indian Patent Office, EPO",
    ),
    ParameterSpec(
        "rd_spend_pct_revenue", "Cybersecurity & capability",
        "R&D spend % of revenue", "Research expenditure as a fraction of revenue.",
        "%", "higher_is_better", healthy_min=2.0,
        source_examples="P&L disclosures",
    ),

    # ========================================================================
    # Group 6 — Network & trust signals (Early-warning score — scoring-relevant)
    # ========================================================================
    ParameterSpec(
        "entity_age_months", "Network & trust",
        "Entity age", "Months since legal-entity registration. < 12 months = shell-company indicator.",
        "months", "higher_is_better", healthy_min=24, concerning_max=12,
        used_in_scoring=True,
        source_examples="MCA21, Companies House, OpenCorporates",
    ),
    ParameterSpec(
        "domain_age_months", "Network & trust",
        "Web domain age",
        "Months since the supplier's primary web domain was registered. Very fresh domain on a small entity is suspicious.",
        "months", "higher_is_better", healthy_min=24, concerning_max=12,
        used_in_scoring=True,
        source_examples="WHOIS lookups",
    ),
    ParameterSpec(
        "profile_last_updated_days", "Network & trust",
        "Profile freshness",
        "Days since the supplier last updated their corporate profile / catalog. Stagnant data = red flag.",
        "days", "lower_is_better", healthy_max=180, concerning_min=540,
        source_examples="Supplier portals, registry change history",
    ),
]


CERT_VALUES = ["active", "expiring_within_12mo", "expired", "none"]


# ---------------------------------------------------------------------------
# Pydantic model for one supplier's metrics
# ---------------------------------------------------------------------------


class SupplierMetrics(BaseModel):
    """All 35 parameters for one supplier. Optional means missing/unknown."""

    model_config = ConfigDict(frozen=True)

    supplier_id: str

    # Identity & scale
    years_in_operation: float | None = None
    employee_count: int | None = None
    annual_revenue_usd_m: float | None = None
    number_of_facilities: int | None = None
    registered_capital_usd_m: float | None = None

    # Financial health
    current_ratio: float | None = None
    quick_ratio: float | None = None
    debt_to_equity_ratio: float | None = None
    net_profit_margin_pct: float | None = None
    revenue_growth_yoy_pct: float | None = None
    days_payables_outstanding: int | None = None
    credit_score: int | None = None
    cash_runway_months: float | None = None

    # Operational
    on_time_delivery_pct: float | None = None
    defect_rate_ppm: int | None = None
    order_fulfillment_accuracy_pct: float | None = None
    avg_lead_time_days: float | None = None
    lead_time_variability_days: float | None = None
    capacity_utilization_pct: float | None = None
    customer_concentration_top1_pct: float | None = None

    # Compliance & ESG
    iso_9001_status: str | None = None
    iatf_16949_status: str | None = None
    as9100_status: str | None = None
    iso_14001_status: str | None = None
    rohs_compliance_status: str | None = None
    conflict_minerals_disclosure: bool | None = None
    esg_controversy_count_12mo: int | None = None
    labor_audit_findings_severe_count: int | None = None

    # Cybersecurity & capability
    iso_27001_status: str | None = None
    cyber_incident_count_24mo: int | None = None
    patent_count: int | None = None
    rd_spend_pct_revenue: float | None = None

    # Network & trust
    entity_age_months: int | None = None
    domain_age_months: int | None = None
    profile_last_updated_days: int | None = None

    # Provenance
    confidence: float = Field(default=0.7, ge=0.0, le=1.0,
                              description="Average confidence across the parameter set.")
    source: str = "synthetic"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def specs_by_group() -> dict[str, list[ParameterSpec]]:
    out: dict[str, list[ParameterSpec]] = {}
    for spec in SPECS:
        out.setdefault(spec.group, []).append(spec)
    return out


def spec_for(key: str) -> ParameterSpec | None:
    for s in SPECS:
        if s.key == key:
            return s
    return None


def health_label(spec: ParameterSpec, value: Any) -> Literal["healthy", "warn", "concerning", "unknown"]:
    """Bucket a value for one parameter into healthy / warn / concerning / unknown."""
    if value is None:
        return "unknown"
    if spec.direction == "categorical":
        if value in ("active",) or value is True:
            return "healthy"
        if value in ("expiring_within_12mo",):
            return "warn"
        if value in ("expired", "none") or value is False:
            return "concerning"
        return "unknown"

    try:
        v = float(value)
    except (TypeError, ValueError):
        return "unknown"

    if spec.direction == "higher_is_better":
        if spec.healthy_min is not None and v >= spec.healthy_min:
            return "healthy"
        if spec.concerning_max is not None and v <= spec.concerning_max:
            return "concerning"
        return "warn"

    if spec.direction == "lower_is_better":
        if spec.healthy_max is not None and v <= spec.healthy_max:
            return "healthy"
        if spec.concerning_min is not None and v >= spec.concerning_min:
            return "concerning"
        return "warn"

    if spec.direction == "in_range":
        if spec.healthy_min is not None and spec.healthy_max is not None:
            if spec.healthy_min <= v <= spec.healthy_max:
                return "healthy"
        if spec.concerning_min is not None and v >= spec.concerning_min:
            return "concerning"
        if spec.concerning_max is not None and v <= spec.concerning_max:
            return "concerning"
        return "warn"

    return "unknown"
