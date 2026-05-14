"""OFAC SDN sanctions screening.

We bundle a small offline copy of OFAC's Specially Designated Nationals
list (`data/reference/ofac_sdn_sample.json`) to make the demo deterministic
and avoid hitting Treasury's servers during a viva.

For production, replace `_load_sdn_list` with a fetcher that pulls
the official `sdn.xml` from https://sanctionslist.ofac.treas.gov/.
"""
from __future__ import annotations

import json
from functools import lru_cache

from rapidfuzz import fuzz

from scs.config import CONFIG
from scs.models import ComplianceCheck, Provenance, Supplier

SOURCE_NAME = "OFAC SDN"
MATCH_THRESHOLD = 88  # WRatio score above this -> hit

EVIDENCE_BASE = "https://sanctionssearch.ofac.treas.gov/"


@lru_cache(maxsize=1)
def _load_sdn_list() -> list[dict]:
    path = CONFIG.reference_dir / "ofac_sdn_sample.json"
    if not path.exists():
        return []
    return json.loads(path.read_text())


def _names_to_match(supplier: Supplier) -> list[str]:
    names = [supplier.name]
    if supplier.legal_name and supplier.legal_name != supplier.name:
        names.append(supplier.legal_name)
    names.extend(supplier.aliases)
    return names


def check(supplier: Supplier) -> ComplianceCheck:
    """Return a single ComplianceCheck against the OFAC SDN list."""
    sdn = _load_sdn_list()
    if not sdn:
        return ComplianceCheck(
            source=SOURCE_NAME,
            status="unknown",
            detail="OFAC reference list not loaded.",
            provenance=Provenance(source_name=SOURCE_NAME, source_url=EVIDENCE_BASE),
        )

    names = _names_to_match(supplier)
    sdn_names: list[tuple[str, dict]] = []
    for entry in sdn:
        sdn_names.append((entry["name"], entry))
        for alias in entry.get("aliases", []):
            sdn_names.append((alias, entry))

    best_score = 0
    best_entry: dict | None = None
    for n in names:
        for sdn_name, entry in sdn_names:
            score = fuzz.WRatio(n.lower(), sdn_name.lower())
            if score > best_score:
                best_score = score
                best_entry = entry

    if best_entry and best_score >= MATCH_THRESHOLD:
        programs = ", ".join(best_entry.get("programs", []))
        url = best_entry.get("evidence_url", EVIDENCE_BASE)
        return ComplianceCheck(
            source=SOURCE_NAME,
            status="fail",
            detail=(
                f"Match against '{best_entry['name']}' (score={best_score}). "
                f"Programs: {programs or 'unspecified'}."
            ),
            provenance=Provenance(source_name=SOURCE_NAME, source_url=url),
        )

    return ComplianceCheck(
        source=SOURCE_NAME,
        status="pass",
        detail=f"No SDN match (closest score={best_score}).",
        provenance=Provenance(source_name=SOURCE_NAME, source_url=EVIDENCE_BASE),
    )
