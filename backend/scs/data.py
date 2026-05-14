"""Load seed suppliers from JSON and provide lookup helpers.

Kept deliberately simple — for production we'd back this with SQLite or
similar, but at 25 rows the JSON is a feature, not a bug: the data file
is the audit trail.
"""
from __future__ import annotations

import json
from functools import lru_cache

from rapidfuzz import fuzz, process

from scs.config import CONFIG
from scs.models import Supplier


@lru_cache(maxsize=1)
def load_suppliers() -> tuple[Supplier, ...]:
    """Return all suppliers as an immutable tuple, cached after first load."""
    raw = json.loads(CONFIG.suppliers_file.read_text())
    return tuple(Supplier.model_validate(item) for item in raw)


def get_supplier(supplier_id: str) -> Supplier | None:
    """Look up a supplier by its stable id."""
    for s in load_suppliers():
        if s.id == supplier_id:
            return s
    return None


def search_suppliers(query: str, limit: int = 5) -> list[tuple[Supplier, int]]:
    """Fuzzy-match against name + aliases, returning (supplier, score) pairs."""
    query = query.strip()
    if not query:
        return []

    suppliers = load_suppliers()
    candidates: dict[str, Supplier] = {}
    for s in suppliers:
        candidates[s.name] = s
        for alias in s.aliases:
            candidates[alias] = s
        if s.legal_name:
            candidates[s.legal_name] = s

    matches = process.extract(
        query,
        candidates.keys(),
        scorer=fuzz.WRatio,
        limit=limit * 2,  # over-fetch to dedupe
    )

    seen: set[str] = set()
    out: list[tuple[Supplier, int]] = []
    for matched_name, score, _ in matches:
        s = candidates[matched_name]
        if s.id in seen:
            continue
        seen.add(s.id)
        out.append((s, int(score)))
        if len(out) >= limit:
            break
    return out
