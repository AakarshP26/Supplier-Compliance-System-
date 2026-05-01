"""World Bank Debarred Firms screening.

Live source: https://projects.worldbank.org/en/projects-operations/procurement/debarred-firms
We bundle a small offline snapshot for deterministic demos.
"""
from __future__ import annotations

import json
from datetime import date, datetime
from functools import lru_cache

from rapidfuzz import fuzz

from scs.config import CONFIG
from scs.models import ComplianceCheck, Provenance, Supplier

SOURCE_NAME = "World Bank Debarred"
MATCH_THRESHOLD = 88

EVIDENCE_BASE = (
    "https://projects.worldbank.org/en/projects-operations/procurement/debarred-firms"
)


@lru_cache(maxsize=1)
def _load_debarred() -> list[dict]:
    path = CONFIG.reference_dir / "wb_debarred_sample.json"
    if not path.exists():
        return []
    return json.loads(path.read_text())


def _is_currently_debarred(entry: dict, today: date | None = None) -> bool:
    today = today or date.today()
    try:
        until = datetime.fromisoformat(entry["to_date"]).date()
    except (KeyError, ValueError):
        return True
    return today <= until


def check(supplier: Supplier) -> ComplianceCheck:
    debarred = _load_debarred()
    if not debarred:
        return ComplianceCheck(
            source=SOURCE_NAME,
            status="unknown",
            detail="World Bank reference list not loaded.",
            provenance=Provenance(source_name=SOURCE_NAME, source_url=EVIDENCE_BASE),
        )

    names = [supplier.name]
    if supplier.legal_name:
        names.append(supplier.legal_name)
    names.extend(supplier.aliases)

    best_score = 0
    best_entry: dict | None = None
    for n in names:
        for entry in debarred:
            score = fuzz.WRatio(n.lower(), entry["firm_name"].lower())
            if score > best_score:
                best_score = score
                best_entry = entry

    if best_entry and best_score >= MATCH_THRESHOLD:
        url = best_entry.get("evidence_url", EVIDENCE_BASE)
        if _is_currently_debarred(best_entry):
            return ComplianceCheck(
                source=SOURCE_NAME,
                status="fail",
                detail=(
                    f"Currently debarred (until {best_entry['to_date']}). "
                    f"Grounds: {best_entry.get('grounds', 'not specified')}"
                ),
                provenance=Provenance(source_name=SOURCE_NAME, source_url=url),
            )
        return ComplianceCheck(
            source=SOURCE_NAME,
            status="pass",
            detail=(
                f"Past debarment expired on {best_entry['to_date']}; "
                "currently eligible."
            ),
            provenance=Provenance(source_name=SOURCE_NAME, source_url=url),
        )

    return ComplianceCheck(
        source=SOURCE_NAME,
        status="pass",
        detail=f"No debarment match (closest score={best_score}).",
        provenance=Provenance(source_name=SOURCE_NAME, source_url=EVIDENCE_BASE),
    )
