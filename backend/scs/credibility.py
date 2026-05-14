"""Source credibility priors.

Central to the trust calibration: every piece of evidence carries
a numeric credibility prior in [0, 1] derived from the source it came
from. Higher = more trustworthy.

Priors are conservative defaults grounded in recognisable taxonomies:

* Government & multilateral compliance lists (OFAC, World Bank) — 0.95+,
  treated as near-ground-truth for what they cover.
* Tier-1 international news with editorial standards — 0.80.
* Trade press with domain expertise — 0.70.
* General-interest news — 0.55.
* Press releases / corporate self-publishing — 0.30 (the supplier
  has direct write access).
* Anonymous blogs, social media — 0.20.
* Unknown / unrecognised domain — 0.40 (cautious default).

These are *priors* — the fusion layer uses them, not absolute truth.
A high-credibility source can still be wrong; corroboration handles
that case.
"""
from __future__ import annotations

from urllib.parse import urlparse

# Curated tiers. Keys are domain suffixes, longest match wins.
_TIER_GOVERNMENT = 0.95
_TIER_TIER1_NEWS = 0.80
_TIER_TRADE_PRESS = 0.70
_TIER_GENERAL_NEWS = 0.55
_TIER_PRESS_RELEASE = 0.30
_TIER_ANON = 0.20
_TIER_UNKNOWN = 0.40

_DOMAIN_PRIORS: dict[str, float] = {
    # Government / multilateral
    "treasury.gov": _TIER_GOVERNMENT,
    "ofac.treas.gov": _TIER_GOVERNMENT,
    "worldbank.org": _TIER_GOVERNMENT,
    "sec.gov": _TIER_GOVERNMENT,
    "mca.gov.in": _TIER_GOVERNMENT,
    "bis.gov.in": _TIER_GOVERNMENT,
    "crsbis.in": _TIER_GOVERNMENT,
    "meity.gov.in": _TIER_GOVERNMENT,
    "europa.eu": _TIER_GOVERNMENT,
    # Tier-1 news
    "reuters.com": _TIER_TIER1_NEWS,
    "ft.com": _TIER_TIER1_NEWS,
    "bloomberg.com": _TIER_TIER1_NEWS,
    "wsj.com": _TIER_TIER1_NEWS,
    "nytimes.com": _TIER_TIER1_NEWS,
    "bbc.com": _TIER_TIER1_NEWS,
    "thehindu.com": _TIER_TIER1_NEWS,
    "indianexpress.com": _TIER_TIER1_NEWS,
    "livemint.com": _TIER_TIER1_NEWS,
    "business-standard.com": _TIER_TIER1_NEWS,
    "economictimes.indiatimes.com": _TIER_TIER1_NEWS,
    # Trade press
    "eetimes.com": _TIER_TRADE_PRESS,
    "electronicsweekly.com": _TIER_TRADE_PRESS,
    "evertiq.com": _TIER_TRADE_PRESS,
    "spectrum.ieee.org": _TIER_TRADE_PRESS,
    "semiwiki.com": _TIER_TRADE_PRESS,
    "anandtech.com": _TIER_TRADE_PRESS,
    "elcina.org": _TIER_TRADE_PRESS,
    # General news
    "ndtv.com": _TIER_GENERAL_NEWS,
    "indiatimes.com": _TIER_GENERAL_NEWS,
    "moneycontrol.com": _TIER_GENERAL_NEWS,
    # Press release distributors / corporate self-publishing
    "prnewswire.com": _TIER_PRESS_RELEASE,
    "businesswire.com": _TIER_PRESS_RELEASE,
    "globenewswire.com": _TIER_PRESS_RELEASE,
    "newswire.com": _TIER_PRESS_RELEASE,
    "einpresswire.com": _TIER_PRESS_RELEASE,
    # Social / anon
    "medium.com": _TIER_ANON,
    "blogspot.com": _TIER_ANON,
    "wordpress.com": _TIER_ANON,
    "linkedin.com": _TIER_ANON,
    "x.com": _TIER_ANON,
    "twitter.com": _TIER_ANON,
}


def credibility_of(url_or_domain: str | None) -> float:
    """Return the credibility prior for a source URL or domain.

    Falls back to the unknown tier when nothing matches. Matching is
    suffix-based so e.g. `markets.ft.com` inherits `ft.com`.
    """
    if not url_or_domain:
        return _TIER_UNKNOWN

    s = url_or_domain.strip().lower()
    if "://" in s:
        host = urlparse(s).netloc
    else:
        host = s
    host = host.removeprefix("www.")

    if not host:
        return _TIER_UNKNOWN

    # Try progressively shorter suffixes (a.b.c.com -> b.c.com -> c.com)
    parts = host.split(".")
    for i in range(len(parts)):
        suffix = ".".join(parts[i:])
        if suffix in _DOMAIN_PRIORS:
            return _DOMAIN_PRIORS[suffix]

    return _TIER_UNKNOWN


def tier_label(prior: float) -> str:
    """Human-readable label for a credibility prior — used in the dashboard."""
    if prior >= 0.90:
        return "government / authoritative"
    if prior >= 0.75:
        return "tier-1 news"
    if prior >= 0.60:
        return "trade press"
    if prior >= 0.45:
        return "general news"
    if prior >= 0.25:
        return "press release / self-published"
    return "low-credibility / anonymous"
