"""High-level scoring service.

Wraps compliance + risk + fusion behind one function call so the dashboard
doesn't depend on the pipeline internals.
"""
from __future__ import annotations

from dataclasses import dataclass

from scs.compliance.pipeline import run as run_compliance
from scs.models import ComplianceReport, RiskProfile, Supplier, SupplierScore
from scs.profile import SupplierProfile, get_profile
from scs.risk.pipeline import run as run_risk
from scs.scoring.fusion import fuse


@dataclass
class FullReport:
    supplier: Supplier
    compliance: ComplianceReport
    risk: RiskProfile
    score: SupplierScore
    profile: SupplierProfile | None


def assess(supplier: Supplier, *, use_defense: bool = True) -> FullReport:
    comp = run_compliance(supplier)
    risk = run_risk(supplier)
    profile = get_profile(supplier.id)
    incorporation_year = supplier.incorporated.year if supplier.incorporated else None
    score = fuse(
        supplier.id, comp, risk,
        use_defense=use_defense,
        profile=profile,
        incorporation_year=incorporation_year,
    )
    return FullReport(
        supplier=supplier, compliance=comp, risk=risk,
        score=score, profile=profile,
    )
