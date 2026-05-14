"""Parameter-level scoring.

Bridges the SupplierProfile (40+ fields per supplier) to the
trust-calibrated DS fusion. Each parameter is mapped to one or zero
BPAs depending on whether the value is present and known. Unknown /
missing values contribute mass to Θ, which is exactly what we want
for the small-supplier cold-start case the user cares about.

Each rule emits a tuple `(label, BPA, raw_value, weight)` so the
explainability layer (waterfall chart) can show *why* the parameter
moved the score.

Categories mirror the metrics_taxonomy.py groups so the Parameters
page and the scoring layer stay in lock-step.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Callable

from scs.profile import CertStatus, SupplierProfile, UdyamCategory
from scs.scoring.fusion import BPA


# ---------------------------------------------------------------------------
# Helper builders
# ---------------------------------------------------------------------------


def _bpa(safe: float, risky: float, label: str) -> BPA:
    """Build a BPA, clamping mass and routing the rest to Θ."""
    safe = max(0.0, min(0.85, safe))
    risky = max(0.0, min(0.85, risky))
    if safe + risky > 0.95:  # leave room for Θ
        scale = 0.95 / (safe + risky)
        safe, risky = safe * scale, risky * scale
    return BPA(safe=safe, risky=risky, theta=1.0 - safe - risky, label=label)


def _ramp(value: float, healthy: float, concerning: float, mass: float = 0.5) -> tuple[float, float]:
    """Map a numeric value to (safe_mass, risky_mass).

    Linear ramp:
      value >= healthy    -> safe = mass
      value <= concerning -> risky = mass
      between             -> linear interpolation
    Direction is derived from healthy vs concerning (handles both
    higher-is-better and lower-is-better).
    """
    if healthy == concerning:
        return (mass, 0.0) if value >= healthy else (0.0, mass)

    if healthy > concerning:  # higher is better
        if value >= healthy:
            return mass, 0.0
        if value <= concerning:
            return 0.0, mass
        frac = (value - concerning) / (healthy - concerning)
        return mass * frac, mass * (1.0 - frac)
    else:  # lower is better (e.g. defect rate)
        if value <= healthy:
            return mass, 0.0
        if value >= concerning:
            return 0.0, mass
        frac = (concerning - value) / (concerning - healthy)
        return mass * frac, mass * (1.0 - frac)


@dataclass
class ParamContribution:
    """One parameter's evidence — used both for fusion and for display."""
    key: str
    group: str
    label: str
    raw_value: Any
    safe_mass: float
    risky_mass: float
    bpa: BPA


# ---------------------------------------------------------------------------
# Rule implementations
# ---------------------------------------------------------------------------


def _identity_rules(p: SupplierProfile, supplier_incorp_year: int | None) -> list[ParamContribution]:
    out = []

    # years_in_operation
    if supplier_incorp_year:
        years = max(0, date.today().year - supplier_incorp_year)
        s, r = _ramp(years, healthy=3.0, concerning=1.0, mass=0.4)
        out.append(_make_pc("years_in_operation", "Identity & scale",
                            "Years in operation", years, s, r))

    # employee_count
    if p.employees is not None:
        s, r = _ramp(float(p.employees), healthy=10, concerning=2, mass=0.25)
        out.append(_make_pc("employee_count", "Identity & scale",
                            "Employee count", p.employees, s, r))

    # annual_revenue (turnover crore -> usd million, ~ /8.3)
    if p.annual_turnover_cr is not None:
        revenue_usd_m = p.annual_turnover_cr / 8.3
        s, r = _ramp(revenue_usd_m, healthy=1.0, concerning=0.05, mass=0.3)
        out.append(_make_pc("annual_revenue_usd_m", "Identity & scale",
                            "Annual revenue (USD M)", round(revenue_usd_m, 2), s, r))

    return out


def _financial_rules(p: SupplierProfile) -> list[ParamContribution]:
    out = []

    if p.current_ratio is not None:
        s, r = _ramp(p.current_ratio, healthy=1.5, concerning=1.0, mass=0.55)
        out.append(_make_pc("current_ratio", "Financial health",
                            "Current ratio", p.current_ratio, s, r))

    if p.debt_to_equity is not None:
        s, r = _ramp(p.debt_to_equity, healthy=1.0, concerning=2.5, mass=0.5)
        out.append(_make_pc("debt_to_equity_ratio", "Financial health",
                            "Debt-to-equity", p.debt_to_equity, s, r))

    if p.days_payable_outstanding is not None:
        # Very high DPO => not paying suppliers => distress signal
        s, r = _ramp(float(p.days_payable_outstanding),
                     healthy=45, concerning=120, mass=0.4)
        out.append(_make_pc("days_payables_outstanding", "Financial health",
                            "Days payable outstanding", p.days_payable_outstanding, s, r))

    if p.gst_compliance_score is not None:
        s, r = _ramp(p.gst_compliance_score, healthy=80, concerning=50, mass=0.4)
        out.append(_make_pc("gst_compliance_score", "Financial health",
                            "GST compliance score (govt)", p.gst_compliance_score, s, r))

    if p.net_worth_cr is not None:
        # Negative net worth = solvency red flag
        if p.net_worth_cr < 0:
            out.append(_make_pc("net_worth_cr", "Financial health",
                                "Net worth (₹ cr) — NEGATIVE", p.net_worth_cr,
                                safe=0.0, risky=0.7))
        else:
            s, r = _ramp(p.net_worth_cr, healthy=5.0, concerning=0.0, mass=0.3)
            out.append(_make_pc("net_worth_cr", "Financial health",
                                "Net worth (₹ cr)", p.net_worth_cr, s, r))

    return out


def _operational_rules(p: SupplierProfile) -> list[ParamContribution]:
    out = []

    if p.on_time_delivery_pct is not None:
        s, r = _ramp(p.on_time_delivery_pct, healthy=95.0, concerning=80.0, mass=0.4)
        out.append(_make_pc("on_time_delivery_pct", "Operational",
                            "On-time delivery %", p.on_time_delivery_pct, s, r))

    if p.defect_rate_ppm is not None:
        s, r = _ramp(float(p.defect_rate_ppm),
                     healthy=500, concerning=5000, mass=0.4)
        out.append(_make_pc("defect_rate_ppm", "Operational",
                            "Defect rate (ppm)", p.defect_rate_ppm, s, r))

    if p.capacity_utilization_pct is not None:
        # Sweet spot 50-85; both extremes are red flags
        v = p.capacity_utilization_pct
        if 50 <= v <= 85:
            s, r = 0.3, 0.0
        elif v < 30:  # idle factory
            s, r = 0.0, 0.4
        elif v > 95:  # cannot scale to demand spikes
            s, r = 0.0, 0.3
        else:
            s, r = 0.15, 0.0
        out.append(_make_pc("capacity_utilization_pct", "Operational",
                            "Capacity utilisation %", v, s, r))

    return out


def _quality_cert_rules(p: SupplierProfile) -> list[ParamContribution]:
    out = []
    cert_map = [
        ("iso_9001_status", "ISO 9001 (QMS)", p.iso_9001, 0.45),
        ("iso_14001_status", "ISO 14001 (env)", p.iso_14001, 0.25),
        ("iatf_16949_status", "IATF 16949 (auto)", p.iatf_16949, 0.20),
        ("as9100_status", "AS9100 (aerospace)", p.as_9100, 0.15),
        ("iso_13485_status", "ISO 13485 (medical)", p.iso_13485, 0.15),
        ("ipc_a_610_status", "IPC-A-610 (acceptability)", p.ipc_a_610, 0.20),
    ]
    for key, label, status, mass in cert_map:
        if status is None or status == CertStatus.UNKNOWN:
            continue
        if status == CertStatus.ACTIVE:
            out.append(_make_pc(key, "Quality certification",
                                label, "active", safe=mass, risky=0.0))
        elif status == CertStatus.EXPIRED:
            out.append(_make_pc(key, "Quality certification",
                                label, "EXPIRED", safe=0.0, risky=mass * 0.6))
        elif status == CertStatus.PENDING:
            out.append(_make_pc(key, "Quality certification",
                                label, "pending", safe=0.0, risky=mass * 0.2))
        elif status == CertStatus.NA:
            pass  # no signal

    if p.bis_crs_active is not None:
        if p.bis_crs_active == "yes":
            out.append(_make_pc("bis_crs_active", "Quality certification",
                                "BIS CRS active", "yes", safe=0.4, risky=0.0))
        elif p.bis_crs_active == "no":
            out.append(_make_pc("bis_crs_active", "Quality certification",
                                "BIS CRS active", "no", safe=0.0, risky=0.35))

    return out


def _regulatory_rules(p: SupplierProfile) -> list[ParamContribution]:
    out = []
    yn_signals = [
        ("mca_status_active", "Regulatory", "MCA registration active", p.mca_status_active, 0.45),
        ("pollution_noc_kspcb", "Regulatory", "Pollution Control NOC (KSPCB)", p.pollution_noc_kspcb, 0.25),
        ("fire_noc", "Regulatory", "Fire NOC current", p.fire_noc, 0.20),
        ("factories_act_license", "Regulatory", "Factories Act licence", p.factories_act_license, 0.20),
        ("epf_dues_clear", "Regulatory", "EPF dues clear", p.epf_dues_clear, 0.30),
        ("income_tax_returns_filed", "Regulatory", "Income-tax returns filed", p.income_tax_returns_filed, 0.30),
        ("epfo_registration", "Regulatory", "EPFO registered", p.epfo_registration, 0.15),
        ("esic_registration", "Regulatory", "ESIC registered", p.esic_registration, 0.15),
        ("shop_estab_license", "Regulatory", "Shop & Estab. licence", p.shop_estab_license, 0.10),
    ]
    for key, group, label, val, mass in yn_signals:
        if val == "yes":
            out.append(_make_pc(key, group, label, "yes", safe=mass, risky=0.0))
        elif val == "no":
            out.append(_make_pc(key, group, label, "NO", safe=0.0, risky=mass))

    return out


def _reputation_rules(p: SupplierProfile) -> list[ParamContribution]:
    out = []

    if p.domain_age_years is not None:
        # Domain < 1 year = potential shell
        s, r = _ramp(p.domain_age_years, healthy=3.0, concerning=1.0, mass=0.30)
        out.append(_make_pc("domain_age_years", "Reputation",
                            "Domain age (years)", p.domain_age_years, s, r))

    if p.online_review_score is not None:
        s, r = _ramp(p.online_review_score, healthy=4.0, concerning=2.5, mass=0.20)
        out.append(_make_pc("online_review_score", "Reputation",
                            "Online review score (1-5)", p.online_review_score, s, r))

    if p.customer_references_count is not None:
        s, r = _ramp(float(p.customer_references_count), healthy=3, concerning=0, mass=0.20)
        out.append(_make_pc("customer_references_count", "Reputation",
                            "Customer references", p.customer_references_count, s, r))

    if p.labor_cases_3y is not None:
        # Lower is better
        s, r = _ramp(float(p.labor_cases_3y), healthy=0, concerning=5, mass=0.30)
        out.append(_make_pc("labor_cases_3y", "Reputation",
                            "Labor disputes (3 yr)", p.labor_cases_3y, s, r))

    if p.media_coverage_breadth is not None:
        s, r = _ramp(float(p.media_coverage_breadth), healthy=3, concerning=0, mass=0.15)
        out.append(_make_pc("media_coverage_breadth", "Reputation",
                            "Media coverage breadth", p.media_coverage_breadth, s, r))

    return out


def _make_pc(key: str, group: str, label: str, raw: Any,
             safe: float, risky: float) -> ParamContribution:
    return ParamContribution(
        key=key, group=group, label=label, raw_value=raw,
        safe_mass=safe, risky_mass=risky,
        bpa=_bpa(safe, risky, f"param:{key}"),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parameter_contributions(
    profile: SupplierProfile | None,
    incorporation_year: int | None = None,
) -> list[ParamContribution]:
    """Return one ParamContribution per scoring-relevant parameter that has
    a known value on this profile.

    A supplier with no profile contributes nothing — its score is driven
    entirely by compliance + news, exactly as before.
    """
    if profile is None:
        return []

    out: list[ParamContribution] = []
    out += _identity_rules(profile, incorporation_year)
    out += _financial_rules(profile)
    out += _operational_rules(profile)
    out += _quality_cert_rules(profile)
    out += _regulatory_rules(profile)
    out += _reputation_rules(profile)
    return out
