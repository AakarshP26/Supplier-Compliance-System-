"""Extended supplier profile — 30+ parameters for verifying small-scale
Indian electronics suppliers.

The core `Supplier` model holds identity. This module holds everything
*else* a procurement officer would want to verify before placing an
order: registrations, financial health, operational capacity, quality
certifications, regulatory filings, and reputation signals.

A profile is *optional*. Suppliers without a profile still score on the
basic compliance + news pipeline; suppliers with one get additional
signal contributions from this module.
"""
from __future__ import annotations

import json
from datetime import date
from enum import Enum
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from scs.config import CONFIG


# ---------------------------------------------------------------------------
# Enums and helper types
# ---------------------------------------------------------------------------


class UdyamCategory(str, Enum):
    """MSME classification under the Udyam scheme (Govt of India)."""
    MICRO  = "micro"     # Investment <= 1 cr OR Turnover <= 5 cr
    SMALL  = "small"     # Investment <= 10 cr OR Turnover <= 50 cr
    MEDIUM = "medium"    # Investment <= 50 cr OR Turnover <= 250 cr
    LARGE  = "large"     # Above MSME thresholds
    UNKNOWN = "unknown"


class CertStatus(str, Enum):
    ACTIVE   = "active"
    EXPIRED  = "expired"
    NA       = "not_applicable"
    PENDING  = "pending"
    UNKNOWN  = "unknown"


YesNoUnknown = Literal["yes", "no", "unknown"]


# ---------------------------------------------------------------------------
# The schema
# ---------------------------------------------------------------------------


class SupplierProfile(BaseModel):
    """30+ parameters for verifying a small-scale supplier.

    Fields are grouped into 6 sections (registrations, financial,
    operational, quality, regulatory, reputation). Every field is
    optional — a missing value reads as `unknown` in scoring.
    """

    supplier_id: str = Field(..., description="Stable id matching scs.data seed_suppliers")

    # ===== Registrations & corporate identity (8) =====================
    cin: str | None = Field(default=None, description="MCA Corporate Identification Number")
    pan: str | None = Field(default=None, description="Permanent Account Number (income tax)")
    gstin: str | None = Field(default=None, description="Goods & Services Tax Identification Number")
    udyam_registration: str | None = Field(default=None, description="Udyam (MSME) registration number")
    iec: str | None = Field(default=None, description="Importer Exporter Code (DGFT)")
    shop_estab_license: YesNoUnknown = "unknown"  # Shops & Establishments Act
    epfo_registration: YesNoUnknown = "unknown"   # Provident Fund
    esic_registration: YesNoUnknown = "unknown"   # Employee State Insurance

    # ===== Financial health (8) =======================================
    udyam_category: UdyamCategory = UdyamCategory.UNKNOWN
    annual_turnover_cr: float | None = Field(default=None, description="Annual turnover in INR crore")
    net_worth_cr: float | None = None
    current_ratio: float | None = Field(default=None, description="Current assets / current liabilities")
    debt_to_equity: float | None = None
    days_payable_outstanding: int | None = Field(default=None, description="DPO — vendor payment days")
    days_sales_outstanding: int | None = Field(default=None, description="DSO — collection period")
    gst_compliance_score: float | None = Field(
        default=None, ge=0.0, le=100.0,
        description="GST filing punctuality 0–100 (real Indian GSTN metric)",
    )

    # ===== Operational capacity (6) ===================================
    employees: int | None = Field(default=None, description="Total headcount")
    plant_area_sqft: int | None = None
    monthly_capacity_units: int | None = Field(default=None, description="Production capacity in units/month")
    capacity_utilization_pct: float | None = Field(default=None, ge=0.0, le=100.0)
    on_time_delivery_pct: float | None = Field(default=None, ge=0.0, le=100.0,
                                               description="OTD over last 12 months")
    defect_rate_ppm: float | None = Field(default=None, ge=0.0,
                                          description="Parts per million defect / return rate")

    # ===== Quality & technical certifications (7) =====================
    iso_9001:    CertStatus = CertStatus.UNKNOWN  # General QMS
    iso_14001:   CertStatus = CertStatus.UNKNOWN  # Environmental
    iatf_16949:  CertStatus = CertStatus.UNKNOWN  # Automotive electronics
    as_9100:     CertStatus = CertStatus.UNKNOWN  # Aerospace
    iso_13485:   CertStatus = CertStatus.UNKNOWN  # Medical devices
    ipc_a_610:   CertStatus = CertStatus.UNKNOWN  # Electronic assembly acceptance
    bis_crs_active: YesNoUnknown = "unknown"      # BIS Compulsory Registration

    # ===== Regulatory & statutory compliance (6) ======================
    mca_status_active: YesNoUnknown = "unknown"   # Not struck off MCA register
    pollution_noc_kspcb: YesNoUnknown = "unknown" # Karnataka State Pollution Control Board
    fire_noc: YesNoUnknown = "unknown"
    factories_act_license: YesNoUnknown = "unknown"
    epf_dues_clear: YesNoUnknown = "unknown"      # No outstanding PF dues
    income_tax_returns_filed: YesNoUnknown = "unknown"

    # ===== Reputation & sentiment (5) =================================
    domain_age_years: int | None = Field(default=None, ge=0)
    customer_references_count: int | None = None
    online_review_score: float | None = Field(default=None, ge=0.0, le=5.0,
                                              description="Average JustDial / Google rating")
    labor_cases_3y: int | None = Field(default=None, ge=0,
                                       description="Count of labor cases filed in last 3 years")
    media_coverage_breadth: int | None = Field(default=None, ge=0,
                                               description="Count of distinct news outlets covering supplier in 12 months")

    @field_validator("gstin")
    @classmethod
    def _validate_gstin_shape(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        # GSTIN is 15 chars: 2 digits state + 10 char PAN + 1 entity + Z + 1 checksum
        if len(v) != 15:
            raise ValueError(f"GSTIN must be 15 characters, got {len(v)}")
        return v.upper()


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def load_profiles() -> dict[str, SupplierProfile]:
    """Load all supplier profiles keyed by supplier_id."""
    path = CONFIG.data_dir / "supplier_profiles.json"
    if not path.exists():
        return {}
    raw = json.loads(path.read_text())
    out: dict[str, SupplierProfile] = {}
    for item in raw:
        try:
            p = SupplierProfile.model_validate(item)
            out[p.supplier_id] = p
        except Exception:
            # Skip malformed entries silently — one bad row shouldn't break the load
            continue
    return out


def get_profile(supplier_id: str) -> SupplierProfile | None:
    """Return the profile for one supplier, or None if not present."""
    return load_profiles().get(supplier_id)


# ---------------------------------------------------------------------------
# Parameter catalogue (used by the dashboard's Parameters page)
# ---------------------------------------------------------------------------


class ParameterSpec(BaseModel):
    """Documentation entry for a single input parameter."""
    name: str
    section: str
    description: str
    source: str            # where the data comes from in production
    enters_score: bool     # does it currently feed scoring?
    field: str             # technical field name


PARAMETER_CATALOGUE: list[ParameterSpec] = [
    # --- Identity / Registrations --------------------------------------
    ParameterSpec(name="Trading name", section="Identity",
                  description="The name everyone calls the supplier by. Required.",
                  source="Supplier-provided", enters_score=True, field="supplier.name"),
    ParameterSpec(name="Legal name", section="Identity",
                  description="As registered with the Ministry of Corporate Affairs.",
                  source="MCA21 / Companies House", enters_score=True, field="supplier.legal_name"),
    ParameterSpec(name="Country of operation", section="Identity",
                  description="ISO-3166 alpha-2 country code.",
                  source="Supplier-provided", enters_score=False, field="supplier.country"),
    ParameterSpec(name="Supplier category", section="Identity",
                  description="Where in the value chain (OEM, EMS, PCB fab, distributor, etc.).",
                  source="Supplier-provided", enters_score=False, field="supplier.category"),
    ParameterSpec(name="Aliases", section="Identity",
                  description="Other names the supplier is known by — used for fuzzy matching against compliance lists.",
                  source="Supplier-provided + open-source", enters_score=True, field="supplier.aliases"),
    ParameterSpec(name="CIN (Corporate Identification Number)", section="Registrations",
                  description="Unique MCA21 corporate id. Absence on a non-trivial Indian supplier is a strong red flag.",
                  source="MCA21 portal", enters_score=True, field="profile.cin"),
    ParameterSpec(name="PAN", section="Registrations",
                  description="Permanent Account Number — issued by Income Tax Dept. No PAN = no tax-compliant business.",
                  source="Income Tax Dept", enters_score=True, field="profile.pan"),
    ParameterSpec(name="GSTIN", section="Registrations",
                  description="GST Identification Number — 15-char shape, mandatory for B2B Indian suppliers above threshold.",
                  source="GST portal (gst.gov.in)", enters_score=True, field="profile.gstin"),
    ParameterSpec(name="Udyam registration (MSME)", section="Registrations",
                  description="MSME classification under the Udyam scheme. Drives small-supplier scoring leniency.",
                  source="udyamregistration.gov.in", enters_score=True, field="profile.udyam_registration"),
    ParameterSpec(name="IEC (Importer Exporter Code)", section="Registrations",
                  description="DGFT code required for any import/export. Blank IEC + claimed exports = inconsistency.",
                  source="DGFT", enters_score=True, field="profile.iec"),
    ParameterSpec(name="Shop & Establishment licence", section="Registrations",
                  description="State-level commercial premises licence. BBMP issues for Bangalore.",
                  source="State labour dept (BBMP)", enters_score=True, field="profile.shop_estab_license"),
    ParameterSpec(name="EPFO registration", section="Registrations",
                  description="Provident Fund registration. Required if employees > 20.",
                  source="EPFO portal", enters_score=True, field="profile.epfo_registration"),
    ParameterSpec(name="ESIC registration", section="Registrations",
                  description="Employee State Insurance. Required if employees > 10 in most states.",
                  source="ESIC portal", enters_score=True, field="profile.esic_registration"),

    # --- Financial -----------------------------------------------------
    ParameterSpec(name="Udyam category", section="Financial",
                  description="micro / small / medium / large — drives expectations on every other metric.",
                  source="Udyam registration certificate", enters_score=True, field="profile.udyam_category"),
    ParameterSpec(name="Annual turnover (INR cr)", section="Financial",
                  description="Latest declared turnover. Sanity-check against Udyam category.",
                  source="MCA filings / GST returns", enters_score=True, field="profile.annual_turnover_cr"),
    ParameterSpec(name="Net worth (INR cr)", section="Financial",
                  description="Total assets minus total liabilities. Negative net worth is a serious red flag.",
                  source="MCA filings", enters_score=True, field="profile.net_worth_cr"),
    ParameterSpec(name="Current ratio", section="Financial",
                  description="Current assets / current liabilities. Healthy: 1.5–3.0.",
                  source="Audited financials", enters_score=True, field="profile.current_ratio"),
    ParameterSpec(name="Debt-to-equity ratio", section="Financial",
                  description="Total debt / shareholders' equity. Above 2.0 is risky for SMEs.",
                  source="Audited financials", enters_score=True, field="profile.debt_to_equity"),
    ParameterSpec(name="Days payable outstanding (DPO)", section="Financial",
                  description="Average days to pay vendors. Sudden rise often precedes default.",
                  source="Audited financials / accounts-payable ledger", enters_score=True, field="profile.days_payable_outstanding"),
    ParameterSpec(name="Days sales outstanding (DSO)", section="Financial",
                  description="Average collection period. Rising DSO = customer payment trouble.",
                  source="Audited financials / receivables ledger", enters_score=True, field="profile.days_sales_outstanding"),
    ParameterSpec(name="GST compliance score", section="Financial",
                  description="GSTN-published filing punctuality score 0–100.",
                  source="GST portal compliance dashboard", enters_score=True, field="profile.gst_compliance_score"),

    # --- Operational ---------------------------------------------------
    ParameterSpec(name="Employees", section="Operational",
                  description="Total headcount. Cross-check against Udyam category.",
                  source="EPFO / supplier-declared", enters_score=True, field="profile.employees"),
    ParameterSpec(name="Plant area (sqft)", section="Operational",
                  description="Manufacturing footprint.",
                  source="Factory licence / supplier-declared", enters_score=False, field="profile.plant_area_sqft"),
    ParameterSpec(name="Monthly production capacity", section="Operational",
                  description="Stated units-per-month capacity.",
                  source="Supplier-declared", enters_score=False, field="profile.monthly_capacity_units"),
    ParameterSpec(name="Capacity utilization (%)", section="Operational",
                  description="Current % of monthly capacity in use. Persistently >90% = no headroom for spikes.",
                  source="Supplier-declared", enters_score=True, field="profile.capacity_utilization_pct"),
    ParameterSpec(name="On-time delivery rate (%)", section="Operational",
                  description="Fraction of orders shipped by committed date over last 12 months.",
                  source="Supplier-declared / buyer-side ERP", enters_score=True, field="profile.on_time_delivery_pct"),
    ParameterSpec(name="Defect rate (PPM)", section="Operational",
                  description="Parts-per-million returns / non-conformances.",
                  source="Supplier-declared / buyer QC", enters_score=True, field="profile.defect_rate_ppm"),

    # --- Quality & certifications --------------------------------------
    ParameterSpec(name="ISO 9001", section="Quality",
                  description="General quality management system. Floor expectation for any serious supplier.",
                  source="Certificate from accredited body", enters_score=True, field="profile.iso_9001"),
    ParameterSpec(name="ISO 14001", section="Quality",
                  description="Environmental management.",
                  source="Certificate", enters_score=True, field="profile.iso_14001"),
    ParameterSpec(name="IATF 16949", section="Quality",
                  description="Automotive electronics QMS — required for tier-1/2 automotive supply.",
                  source="Certificate", enters_score=True, field="profile.iatf_16949"),
    ParameterSpec(name="AS9100", section="Quality",
                  description="Aerospace quality system.",
                  source="Certificate", enters_score=True, field="profile.as_9100"),
    ParameterSpec(name="ISO 13485", section="Quality",
                  description="Medical devices QMS.",
                  source="Certificate", enters_score=True, field="profile.iso_13485"),
    ParameterSpec(name="IPC-A-610", section="Quality",
                  description="Workmanship acceptance standard for electronic assemblies.",
                  source="IPC accreditation", enters_score=True, field="profile.ipc_a_610"),
    ParameterSpec(name="BIS CRS active", section="Quality",
                  description="Active R-number under the BIS Compulsory Registration Scheme.",
                  source="crsbis.in", enters_score=True, field="profile.bis_crs_active"),

    # --- Regulatory & statutory ---------------------------------------
    ParameterSpec(name="MCA active status", section="Regulatory",
                  description="Not struck off the Register of Companies. Defunct companies cannot transact.",
                  source="MCA21", enters_score=True, field="profile.mca_status_active"),
    ParameterSpec(name="KSPCB pollution NOC", section="Regulatory",
                  description="Karnataka State Pollution Control Board consent. Required for any manufacturing.",
                  source="KSPCB portal", enters_score=True, field="profile.pollution_noc_kspcb"),
    ParameterSpec(name="Fire NOC", section="Regulatory",
                  description="Local fire department clearance.",
                  source="State fire dept", enters_score=True, field="profile.fire_noc"),
    ParameterSpec(name="Factories Act licence", section="Regulatory",
                  description="Required under Factories Act 1948 for any factory > 10 workers.",
                  source="State factories dept", enters_score=True, field="profile.factories_act_license"),
    ParameterSpec(name="EPF dues clear", section="Regulatory",
                  description="No outstanding employee PF arrears.",
                  source="EPFO compliance dashboard", enters_score=True, field="profile.epf_dues_clear"),
    ParameterSpec(name="Income tax returns filed", section="Regulatory",
                  description="ITR filed for last assessment year.",
                  source="Income tax e-filing portal", enters_score=True, field="profile.income_tax_returns_filed"),

    # --- Reputation ---------------------------------------------------
    ParameterSpec(name="Web domain age (years)", section="Reputation",
                  description="Years since the supplier's primary domain was registered. <1 year is statistically risky.",
                  source="WHOIS lookup", enters_score=True, field="profile.domain_age_years"),
    ParameterSpec(name="Customer references", section="Reputation",
                  description="Verifiable named clients willing to provide a reference.",
                  source="Supplier-declared, then verified", enters_score=True, field="profile.customer_references_count"),
    ParameterSpec(name="Online review score", section="Reputation",
                  description="Average JustDial / Google business rating, 0–5.",
                  source="JustDial / Google Maps", enters_score=False, field="profile.online_review_score"),
    ParameterSpec(name="Labor cases in last 3y", section="Reputation",
                  description="Count of formal labor cases filed against the company.",
                  source="Labour court / e-courts portal", enters_score=True, field="profile.labor_cases_3y"),
    ParameterSpec(name="Media coverage breadth", section="Reputation",
                  description="Count of distinct news outlets covering the supplier in last 12 months.",
                  source="Aggregated from news pipeline", enters_score=False, field="profile.media_coverage_breadth"),

    # --- Compliance signals (already in core pipeline) -----------------
    ParameterSpec(name="OFAC SDN match", section="Compliance",
                  description="Match against US Treasury sanctions list.",
                  source="OFAC sanctions portal", enters_score=True, field="compliance.OFAC SDN"),
    ParameterSpec(name="World Bank debarment", section="Compliance",
                  description="Match against World Bank debarred firms list.",
                  source="World Bank procurement portal", enters_score=True, field="compliance.WB Debarred"),
    ParameterSpec(name="BIS CRS registration", section="Compliance",
                  description="Active CRS registration with valid R-number.",
                  source="crsbis.in", enters_score=True, field="compliance.BIS CRS"),

    # --- News / unstructured signals ----------------------------------
    ParameterSpec(name="News risk-event extraction", section="News",
                  description="LLM-extracted structured signals (sanctions, litigation, labor, financial distress, counterfeit, recall, ...) from news articles.",
                  source="LLM over public news + URL-derived credibility prior", enters_score=True, field="risk.signals"),
    ParameterSpec(name="Source credibility prior", section="News",
                  description="0–1 prior assigned by URL domain (gov / tier-1 / trade press / press-release / anon).",
                  source="Internal credibility registry", enters_score=True, field="risk.signals[].provenance.credibility"),
    ParameterSpec(name="Cross-source corroboration", section="News",
                  description="True iff the same event_type was reported by an independent registrable domain.",
                  source="Computed by risk pipeline", enters_score=True, field="risk.signals[].is_corroborated"),
    ParameterSpec(name="News sentiment (per article)", section="News",
                  description="LLM-estimated sentiment toward the supplier, -1 to +1.",
                  source="LLM extractor", enters_score=True, field="risk.signals[].sentiment"),
    ParameterSpec(name="Burst / template defense", section="News",
                  description="Multiplicative defense weight applied when many similar positive articles cluster temporally.",
                  source="Computed by scoring.defense", enters_score=True, field="defense.calibrated_signal_weights"),
]
