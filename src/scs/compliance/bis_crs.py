"""BIS Compulsory Registration Scheme (CRS) lookup.

CRS is mandatory for 65+ electronics & IT product categories sold in India
(MeitY notification under BIS Act 2016). A supplier without a current
R-number for a product they're shipping to India is non-compliant.

Live source: https://crsbis.in/  (we bundle a sample for offline demos).
"""
from __future__ import annotations

import json
from datetime import date, datetime
from functools import lru_cache

from rapidfuzz import fuzz

from scs.config import CONFIG
from scs.models import ComplianceCheck, Provenance, Supplier

SOURCE_NAME = "BIS CRS"
MATCH_THRESHOLD = 85
EVIDENCE_BASE = "https://www.crsbis.in/"


@lru_cache(maxsize=1)
def _load_registrations() -> list[dict]:
    path = CONFIG.reference_dir / "bis_crs_sample.json"
    if not path.exists():
        return []
    return json.loads(path.read_text()).get("registrations", [])


def _is_valid(entry: dict, today: date | None = None) -> bool:
    today = today or date.today()
    try:
        until = datetime.fromisoformat(entry["valid_until"]).date()
    except (KeyError, ValueError):
        return False
    return today <= until


def check(supplier: Supplier) -> ComplianceCheck:
    """Pass if supplier has at least one current CRS registration.

    Non-Indian suppliers exporting to India *should* hold a CRS; missing
    registration is reported as 'unknown' (not a fail) for foreign firms
    so we don't penalise legitimate non-Indian operations that aren't
    selling into India.
    """
    registrations = _load_registrations()
    if not registrations:
        return ComplianceCheck(
            source=SOURCE_NAME,
            status="unknown",
            detail="BIS CRS reference data not loaded.",
            provenance=Provenance(source_name=SOURCE_NAME, source_url=EVIDENCE_BASE),
        )

    names = [supplier.name]
    if supplier.legal_name:
        names.append(supplier.legal_name)
    names.extend(supplier.aliases)

    best_score = 0
    best_entry: dict | None = None
    for n in names:
        for entry in registrations:
            score = fuzz.WRatio(n.lower(), entry["firm_name"].lower())
            if score > best_score:
                best_score = score
                best_entry = entry

    if best_entry and best_score >= MATCH_THRESHOLD:
        if _is_valid(best_entry):
            return ComplianceCheck(
                source=SOURCE_NAME,
                status="pass",
                detail=(
                    f"Active CRS registration {best_entry['r_number']} "
                    f"valid to {best_entry['valid_until']} "
                    f"({len(best_entry.get('products', []))} product line(s))."
                ),
                provenance=Provenance(source_name=SOURCE_NAME, source_url=EVIDENCE_BASE),
            )
        return ComplianceCheck(
            source=SOURCE_NAME,
            status="fail",
            detail=(
                f"CRS registration {best_entry['r_number']} expired on "
                f"{best_entry['valid_until']}. Renewal required before "
                "further shipments."
            ),
            provenance=Provenance(source_name=SOURCE_NAME, source_url=EVIDENCE_BASE),
        )

    # No match
    if supplier.country == "IN":
        return ComplianceCheck(
            source=SOURCE_NAME,
            status="fail",
            detail=(
                "No CRS registration found for an Indian supplier. "
                "Likely non-compliant for any CRS-notified product category."
            ),
            provenance=Provenance(source_name=SOURCE_NAME, source_url=EVIDENCE_BASE),
        )
    return ComplianceCheck(
        source=SOURCE_NAME,
        status="unknown",
        detail=(
            "No CRS registration found. Required only if exporting "
            "CRS-notified products into India; verify import scope."
        ),
        provenance=Provenance(source_name=SOURCE_NAME, source_url=EVIDENCE_BASE),
    )
