"""LLM-based risk signal extraction.

Real backend uses Anthropic's API. A deterministic mock backend kicks in
when `CONFIG.use_mock_llm` is True (the default) so the project runs and
the paper experiments are reproducible without network access or API
credit. The mock uses simple keyword heuristics tuned to the seed corpus —
it is intentionally weaker than a real LLM, which makes it a useful
'lower-bound baseline' in the experiments.
"""
from __future__ import annotations

import json
import re
from typing import Any

from scs.config import CONFIG
from scs.models import Provenance, RiskEventType, RiskSignal
from scs.risk.news import NewsArticle
from scs.risk.prompts import EXTRACTION_SYSTEM, user_prompt_for

LLM_MODEL = "claude-haiku-4-5-20251001"


# ---------------------------------------------------------------------------
# Backends
# ---------------------------------------------------------------------------


def _call_anthropic(supplier_name: str, article: NewsArticle) -> dict[str, Any]:
    """Real Anthropic backend. Lazy import so we don't need the SDK in mock mode."""
    from anthropic import Anthropic

    client = Anthropic(api_key=CONFIG.anthropic_api_key)
    msg = client.messages.create(
        model=LLM_MODEL,
        max_tokens=400,
        system=EXTRACTION_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": user_prompt_for(supplier_name, article.title, article.body),
            }
        ],
    )
    text = "".join(block.text for block in msg.content if block.type == "text")
    return _parse_json_block(text)


# Keyword tables for the mock — sorted by precedence (first match wins).
_MOCK_RULES: list[tuple[str, RiskEventType, int, float]] = [
    # (regex, event_type, severity, sentiment)
    (r"\b(debarred|debarment|blacklist)\b", RiskEventType.SANCTIONS, 5, -0.9),
    (r"\b(sanction|ofac|sdn list)\b", RiskEventType.SANCTIONS, 4, -0.85),
    (r"\b(counterfeit|remarked|gidep)\b", RiskEventType.COUNTERFEIT, 4, -0.8),
    (r"\b(bankrupt|insolven|liquidation)\b", RiskEventType.FINANCIAL_DISTRESS, 5, -0.9),
    (r"\b(recall|defective)\b", RiskEventType.QUALITY_RECALL, 3, -0.6),
    (r"\b(strike|stoppage|protest)\b", RiskEventType.LABOR_DISPUTE, 2, -0.4),
    (r"\b(lawsuit|litigation|sued|criminal probe)\b", RiskEventType.LITIGATION, 3, -0.55),
    (r"\b(data breach|hack|ransomware)\b", RiskEventType.CYBERSECURITY, 3, -0.55),
    (r"\b(pollution|emission|environmental violation)\b", RiskEventType.ENVIRONMENTAL, 3, -0.5),
    (r"\b(ceo resign|cfo resign|board overhaul)\b", RiskEventType.LEADERSHIP_CHANGE, 1, -0.2),
    (r"\b(abandoned|dissolved|collapse|setback)\b", RiskEventType.FINANCIAL_DISTRESS, 3, -0.6),
    (
        r"\b(profit|wins? \w+ (order|contract)|expansion|expand|guidance|jump in|all-time high|raises? guidance|doubles? investment|new (plant|facility|line)|commission(s|ed))\b",
        RiskEventType.POSITIVE,
        0,
        0.7,
    ),
]


def _call_mock(supplier_name: str, article: NewsArticle) -> dict[str, Any]:
    """Deterministic keyword-based extractor.

    Honest about being weaker than a real LLM — this is the *baseline*,
    not the system under test for the headline experiments.
    """
    text = f"{article.title}. {article.body}".lower()
    for pattern, event, sev, sent in _MOCK_RULES:
        if re.search(pattern, text):
            return {
                "event_type": event.value,
                "severity": sev,
                "sentiment": sent,
                "summary": article.title[:140],
            }
    # No keyword hit -> low-stakes "other"
    return {
        "event_type": "other",
        "severity": 0,
        "sentiment": 0.0,
        "summary": article.title[:140],
    }


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


_JSON_RE = re.compile(r"\{[\s\S]*\}", re.MULTILINE)


def _parse_json_block(text: str) -> dict[str, Any]:
    """Parse an LLM response into a dict, tolerating extra prose or fences."""
    if "```" in text:
        text = text.split("```", 2)[1]
        if text.lower().startswith("json"):
            text = text[4:]
    match = _JSON_RE.search(text)
    if not match:
        raise ValueError(f"Could not find JSON object in LLM output: {text[:200]}")
    return json.loads(match.group(0))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_signal(supplier_name: str, article: NewsArticle) -> RiskSignal:
    """Extract one structured RiskSignal from one article."""
    if CONFIG.use_mock_llm or not CONFIG.anthropic_api_key:
        raw = _call_mock(supplier_name, article)
    else:
        raw = _call_anthropic(supplier_name, article)

    return RiskSignal(
        event_type=RiskEventType(raw["event_type"]),
        severity=int(raw["severity"]),
        sentiment=float(raw["sentiment"]),
        summary=str(raw["summary"]),
        provenance=Provenance(
            source_name=_source_name_from_url(article.url),
            source_url=article.url,
            published_at=article.published_at,
        ),
    )


def _source_name_from_url(url: str | None) -> str:
    if not url:
        return "unknown"
    from urllib.parse import urlparse

    host = urlparse(url).netloc
    return host.removeprefix("www.") or "unknown"
