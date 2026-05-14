"""News corpus loading.

The seed corpus is intentionally small (~12 articles) and per-supplier so
both the LLM extractor and the adversarial harness work offline.

In production, replace `load_corpus` with a fetcher hitting GDELT, NewsAPI,
or RSS feeds; the in-memory shape is unchanged.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from functools import lru_cache

from pydantic import BaseModel, Field, field_validator

from scs.config import CONFIG


class NewsArticle(BaseModel):
    id: str
    supplier_id: str
    title: str
    body: str
    url: str | None = None
    published_at: datetime | None = None

    is_synthetic: bool = Field(default=False, exclude=True)

    @field_validator("published_at")
    @classmethod
    def _ensure_aware(cls, v: datetime | None) -> datetime | None:
        if v is None:
            return v
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v


@lru_cache(maxsize=1)
def load_corpus() -> dict[str, list[NewsArticle]]:
    """Return {supplier_id: [NewsArticle, ...]} from the seed corpus."""
    path = CONFIG.news_dir / "seed_corpus.json"
    if not path.exists():
        return {}
    raw = json.loads(path.read_text())
    out: dict[str, list[NewsArticle]] = {}
    for supplier_id, articles in raw.get("corpus", {}).items():
        out[supplier_id] = [
            NewsArticle(supplier_id=supplier_id, **a) for a in articles
        ]
    return out


def articles_for(supplier_id: str) -> list[NewsArticle]:
    return list(load_corpus().get(supplier_id, []))


def all_articles() -> list[NewsArticle]:
    out: list[NewsArticle] = []
    for arts in load_corpus().values():
        out.extend(arts)
    return out
