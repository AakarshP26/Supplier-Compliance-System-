"""Load suppliers from PostgreSQL with JSON fallback.

Primary source is the `suppliers` table. If the DB is unreachable the
function falls back to the JSON flat file so dev without Postgres still works.
"""
from __future__ import annotations

import json
from datetime import date
from functools import lru_cache

from rapidfuzz import fuzz, process

from scs.config import CONFIG
from scs.models import Supplier


def _load_from_db() -> tuple[Supplier, ...]:
    from scs.db import SessionLocal
    from scs.orm_models import SupplierRow
    from scs.models import SupplierCategory

    db = SessionLocal()
    try:
        rows = db.query(SupplierRow).all()
        suppliers = []
        for r in rows:
            inc = None
            if r.incorporated:
                inc = r.incorporated if isinstance(r.incorporated, date) else date.fromisoformat(str(r.incorporated))
            suppliers.append(Supplier(
                id=r.id,
                name=r.name,
                legal_name=r.legal_name,
                country=r.country,
                category=SupplierCategory(r.category),
                cin=r.cin,
                website=r.website,
                incorporated=inc,
                aliases=tuple(r.aliases or []),
                is_illustrative=r.is_illustrative,
                note=r.note,
            ))
        return tuple(suppliers)
    finally:
        db.close()


def _load_from_json() -> tuple[Supplier, ...]:
    raw = json.loads(CONFIG.suppliers_file.read_text())
    return tuple(Supplier.model_validate(item) for item in raw)


@lru_cache(maxsize=1)
def load_suppliers() -> tuple[Supplier, ...]:
    """Return all suppliers as an immutable cached tuple.

    Reads from PostgreSQL; falls back to JSON if DB is unavailable.
    """
    try:
        suppliers = _load_from_db()
        if suppliers:
            return suppliers
    except Exception:
        pass
    return _load_from_json()


def get_supplier(supplier_id: str) -> Supplier | None:
    for s in load_suppliers():
        if s.id == supplier_id:
            return s
    return None


def search_suppliers(query: str, limit: int = 5) -> list[tuple[Supplier, int]]:
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

    matches = process.extract(query, candidates.keys(), scorer=fuzz.WRatio, limit=limit * 2)

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
