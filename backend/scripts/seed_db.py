"""Seed the PostgreSQL database from JSON flat files.

Skips suppliers with country == 'CN' (Chinese-based suppliers).
Run once:
    python scripts/seed_db.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Make scs importable from repo root
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from scs.db import Base, engine, SessionLocal
from scs.orm_models import SupplierRow, NewsArticleRow, ReferenceListRow

DATA = Path(__file__).resolve().parents[1] / "data"


def create_tables():
    Base.metadata.create_all(bind=engine)
    print("Tables created.")


def seed_suppliers(session):
    with open(DATA / "seed_suppliers.json") as f:
        suppliers = json.load(f)

    skipped = []
    inserted = 0

    for s in suppliers:
        country = s.get("country", "").upper()
        if country == "CN":
            skipped.append(s["name"])
            continue

        # Upsert: delete existing then insert
        session.query(SupplierRow).filter_by(id=s["id"]).delete()
        row = SupplierRow(
            id=s["id"],
            name=s["name"],
            legal_name=s.get("legal_name"),
            country=country,
            category=s["category"],
            cin=s.get("cin"),
            website=s.get("website"),
            incorporated=s.get("incorporated"),
            aliases=list(s.get("aliases", [])),
            is_illustrative=s.get("is_illustrative", False),
            note=s.get("note"),
        )
        session.add(row)
        inserted += 1

    session.commit()
    print(f"Suppliers: {inserted} inserted, {len(skipped)} skipped (CN): {skipped}")


def seed_news(session):
    with open(DATA / "news" / "seed_corpus.json") as f:
        raw = json.load(f)
    corpus = raw if isinstance(raw, list) else raw.get("corpus", {})

    session.query(NewsArticleRow).delete()
    total = 0
    if isinstance(corpus, dict):
        # {supplier_id: [article, ...]}
        for supplier_id, articles in corpus.items():
            for a in articles:
                session.add(NewsArticleRow(
                    article_id=a.get("id", ""),
                    supplier_id=supplier_id,
                    title=a.get("title"),
                    body=a.get("body", ""),
                    url=a.get("url"),
                    published_at=str(a.get("published_at", "")),
                ))
                total += 1
    else:
        for a in corpus:
            session.add(NewsArticleRow(
                article_id=a.get("id", ""),
                supplier_id=a.get("supplier_id", ""),
                title=a.get("title"),
                body=a.get("body", ""),
                url=a.get("url"),
                published_at=str(a.get("published_at", "")),
            ))
            total += 1
    session.commit()
    print(f"News articles: {total} inserted.")


def seed_reference_lists(session):
    session.query(ReferenceListRow).delete()
    lists = {
        "ofac_sdn": DATA / "reference" / "ofac_sdn_sample.json",
        "bis_crs": DATA / "reference" / "bis_crs_sample.json",
        "wb_debarred": DATA / "reference" / "wb_debarred_sample.json",
    }
    total = 0
    for list_name, path in lists.items():
        with open(path) as f:
            raw = json.load(f)
        # Normalise: could be list or dict with a nested list
        if isinstance(raw, list):
            entries = raw
        elif isinstance(raw, dict):
            # Find the first list value
            entries = next((v for v in raw.values() if isinstance(v, list)), [])
        else:
            entries = []
        for entry in entries:
            if isinstance(entry, dict):
                name = (entry.get("name") or entry.get("firm_name")
                        or entry.get("entity_name") or str(entry))
                raw_str = json.dumps(entry)
            else:
                name = str(entry)
                raw_str = json.dumps(entry)
            session.add(ReferenceListRow(
                list_name=list_name,
                entity_name=name,
                raw=raw_str,
            ))
            total += 1
    session.commit()
    print(f"Reference list entries: {total} inserted.")


if __name__ == "__main__":
    create_tables()
    db = SessionLocal()
    try:
        seed_suppliers(db)
        seed_news(db)
        seed_reference_lists(db)
        print("\nDone. Database is ready.")
    finally:
        db.close()
