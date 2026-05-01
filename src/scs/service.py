"""High-level scoring service.

Wraps compliance + risk + fusion behind one function call so the dashboard
doesn't depend on the pipeline internals.
"""
from __future__ import annotations

from dataclasses import dataclass

from scs.compliance.pipeline import run as run_compliance
from scs.models import ComplianceReport, RiskProfile, Supplier, SupplierScore
from scs.risk.pipeline import run as run_risk
from scs.scoring.fusion import fuse


@dataclass
class FullReport:
    supplier: Supplier
    compliance: ComplianceReport
    risk: RiskProfile
    score: SupplierScore


def assess(supplier: Supplier, *, use_defense: bool = True) -> FullReport:
    comp = run_compliance(supplier)
    risk = run_risk(supplier)
    score = fuse(supplier.id, comp, risk, use_defense=use_defense)
    return FullReport(supplier=supplier, compliance=comp, risk=risk, score=score)
