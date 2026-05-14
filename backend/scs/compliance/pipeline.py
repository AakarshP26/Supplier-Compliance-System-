"""Compliance pipeline orchestrator.

Runs every registered check against a supplier in parallel (threaded for
the I/O-bound API checkers; the bundled offline checkers run instantly).
Returns a single ComplianceReport.

Adding a new check is one line — append to `_CHECKERS`.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from scs.compliance import bis_crs, ofac, world_bank
from scs.models import ComplianceCheck, ComplianceReport, Supplier

# Order is preserved in the resulting report.
_CHECKERS: list[Callable[[Supplier], ComplianceCheck]] = [
    ofac.check,
    world_bank.check,
    bis_crs.check,
]


def run(supplier: Supplier, max_workers: int = 4) -> ComplianceReport:
    """Run every registered checker against the supplier in parallel."""
    checks: list[ComplianceCheck] = [None] * len(_CHECKERS)  # type: ignore[list-item]

    def _run_one(idx: int, fn: Callable[[Supplier], ComplianceCheck]) -> None:
        checks[idx] = fn(supplier)

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = [ex.submit(_run_one, i, fn) for i, fn in enumerate(_CHECKERS)]
        for f in futures:
            f.result()  # propagate exceptions, if any

    return ComplianceReport(supplier_id=supplier.id, checks=list(checks))


def run_all(suppliers: list[Supplier]) -> dict[str, ComplianceReport]:
    """Convenience: run pipeline across many suppliers."""
    return {s.id: run(s) for s in suppliers}
