"""Score contributions derived from the extended SupplierProfile.

These produce additional Dempster-Shafer BPAs that fold into the existing
fusion. Each helper returns a list of `(label, BPA)` pairs; an empty
list means the profile didn't contribute (e.g. unknown values).

Scoring philosophy: the profile fills a gap that compliance lists miss —
small Indian suppliers with no OFAC/WB exposure are largely invisible to
sanctions screening but visible to operational and financial scoring.
"""
from __future__ import annotations

from scs.profile import CertStatus, SupplierProfile, UdyamCategory
from scs.scoring.fusion import BPA


# Reasonable strength caps so profile evidence can never single-handedly
# pin a supplier to one singleton.
_MAX_RISKY = 0.6
_MAX_SAFE  = 0.55


def _risky(mass: float, label: str) -> BPA:
    mass = min(_MAX_RISKY, max(0.0, mass))
    return BPA(safe=0.0, risky=mass, theta=1.0 - mass, label=label)


def _safe(mass: float, label: str) -> BPA:
    mass = min(_MAX_SAFE, max(0.0, mass))
    return BPA(safe=mass, risky=0.0, theta=1.0 - mass, label=label)


def bpas_from_profile(profile: SupplierProfile) -> list[tuple[str, BPA]]:
    """Translate the profile into a list of (feature_label, BPA) pairs."""
    out: list[tuple[str, BPA]] = []

    # ---------- Registrations (gov-issued; high-credibility evidence) ---
    if profile.gstin is None:
        out.append(("profile::missing GSTIN", _risky(0.30, "no_gstin")))
    elif profile.gstin:
        out.append(("profile::valid GSTIN", _safe(0.10, "gstin")))

    if profile.cin is None and profile.supplier_id != "":
        out.append(("profile::missing CIN", _risky(0.20, "no_cin")))

    if profile.pan is None:
        out.append(("profile::missing PAN", _risky(0.15, "no_pan")))

    # MSME registration — important positive for small suppliers
    if profile.udyam_registration:
        out.append(("profile::Udyam registered", _safe(0.10, "udyam")))

    # ---------- Financial health ---------------------------------------
    if profile.net_worth_cr is not None and profile.net_worth_cr < 0:
        out.append(("profile::negative net worth", _risky(0.45, "neg_net_worth")))

    if profile.current_ratio is not None:
        if profile.current_ratio < 1.0:
            out.append(("profile::current ratio < 1", _risky(0.30, "cr_lt_1")))
        elif profile.current_ratio >= 1.5:
            out.append(("profile::current ratio healthy", _safe(0.12, "cr_healthy")))

    if profile.debt_to_equity is not None and profile.debt_to_equity > 3.0:
        out.append(("profile::D/E > 3", _risky(0.25, "high_de")))

    if profile.gst_compliance_score is not None:
        if profile.gst_compliance_score < 60:
            out.append(("profile::GST score < 60", _risky(0.30, "low_gst")))
        elif profile.gst_compliance_score >= 90:
            out.append(("profile::GST score >= 90", _safe(0.15, "good_gst")))

    if profile.days_payable_outstanding is not None and profile.days_payable_outstanding > 120:
        out.append(("profile::DPO > 120 days", _risky(0.20, "high_dpo")))

    # ---------- Operational --------------------------------------------
    if profile.on_time_delivery_pct is not None:
        if profile.on_time_delivery_pct < 80:
            out.append(("profile::OTD < 80%", _risky(0.25, "low_otd")))
        elif profile.on_time_delivery_pct >= 95:
            out.append(("profile::OTD >= 95%", _safe(0.15, "high_otd")))

    if profile.defect_rate_ppm is not None:
        if profile.defect_rate_ppm > 10000:
            out.append(("profile::defect rate > 1%", _risky(0.30, "high_defect")))
        elif profile.defect_rate_ppm < 1000:
            out.append(("profile::defect rate < 0.1%", _safe(0.12, "low_defect")))

    if profile.capacity_utilization_pct is not None and profile.capacity_utilization_pct > 95:
        out.append(("profile::capacity > 95% (no headroom)", _risky(0.10, "high_cap")))

    # ---------- Quality certifications ---------------------------------
    if profile.iso_9001 == CertStatus.ACTIVE:
        out.append(("profile::ISO 9001 active", _safe(0.18, "iso9001")))
    elif profile.iso_9001 == CertStatus.EXPIRED:
        out.append(("profile::ISO 9001 expired", _risky(0.20, "iso9001_exp")))

    if profile.iatf_16949 == CertStatus.ACTIVE:
        out.append(("profile::IATF 16949 active", _safe(0.10, "iatf")))
    if profile.as_9100 == CertStatus.ACTIVE:
        out.append(("profile::AS9100 active", _safe(0.10, "as9100")))
    if profile.iso_13485 == CertStatus.ACTIVE:
        out.append(("profile::ISO 13485 active", _safe(0.10, "iso13485")))
    if profile.ipc_a_610 == CertStatus.ACTIVE:
        out.append(("profile::IPC-A-610 active", _safe(0.10, "ipc")))

    if profile.bis_crs_active == "no":
        # Only penalise if we explicitly know it's missing
        out.append(("profile::BIS CRS missing", _risky(0.25, "no_bis")))
    elif profile.bis_crs_active == "yes":
        out.append(("profile::BIS CRS active", _safe(0.12, "bis")))

    # ---------- Regulatory ---------------------------------------------
    if profile.mca_status_active == "no":
        out.append(("profile::MCA struck off", _risky(0.55, "mca_struck")))

    if profile.epf_dues_clear == "no":
        out.append(("profile::EPF dues outstanding", _risky(0.25, "epf_dues")))

    if profile.pollution_noc_kspcb == "no":
        out.append(("profile::no KSPCB pollution NOC", _risky(0.20, "no_kspcb")))

    if profile.fire_noc == "no":
        out.append(("profile::no fire NOC", _risky(0.15, "no_fire")))

    if profile.factories_act_license == "no":
        out.append(("profile::no Factories Act license", _risky(0.15, "no_factories")))

    if profile.income_tax_returns_filed == "no":
        out.append(("profile::ITR not filed", _risky(0.20, "no_itr")))

    # ---------- Reputation ---------------------------------------------
    if profile.domain_age_years is not None:
        if profile.domain_age_years < 1:
            out.append(("profile::domain age < 1y", _risky(0.20, "young_domain")))
        elif profile.domain_age_years >= 10:
            out.append(("profile::domain age >= 10y", _safe(0.08, "old_domain")))

    if profile.customer_references_count is not None:
        if profile.customer_references_count == 0:
            out.append(("profile::no customer references", _risky(0.15, "no_refs")))
        elif profile.customer_references_count >= 10:
            out.append(("profile::10+ customer references", _safe(0.10, "many_refs")))

    if profile.labor_cases_3y is not None and profile.labor_cases_3y >= 5:
        out.append(("profile::5+ labor cases (3y)", _risky(0.20, "labor_cases")))

    return out
