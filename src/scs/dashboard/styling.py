"""Dashboard design system.

Centralised colour palette, grade tokens, and CSS injection so the look
is consistent across pages. Inspired by terminal-style risk dashboards
(Bloomberg / Palantir Foundry) but kept readable.
"""
from __future__ import annotations

import streamlit as st


# ---------------------------------------------------------------------------
# Colour palette (Tailwind-ish, accessible on both light and dark)
# ---------------------------------------------------------------------------

PALETTE = {
    # Status / grade colours
    "grade_a": "#0F9D58",   # green-600
    "grade_b": "#7CB342",   # lime-600
    "grade_c": "#FB8C00",   # orange-600
    "grade_d": "#E64A19",   # deep-orange-700
    "grade_f": "#C62828",   # red-700

    # Semantic
    "ok":       "#0F9D58",
    "warn":     "#FB8C00",
    "danger":   "#C62828",
    "unknown":  "#90A4AE",
    "neutral":  "#546E7A",

    # Brand / chart accents
    "accent":   "#6366F1",   # indigo-500
    "accent_2": "#06B6D4",   # cyan-500
    "accent_3": "#A855F7",   # purple-500

    # Surfaces
    "bg":       "#0F172A",   # slate-900 (dark) — only used inside chart specs
    "panel":    "#1E293B",
    "muted":    "#64748B",
}

# Source-credibility tier colours (used in the credibility pyramid + tables)
TIER_COLORS = {
    "government / authoritative": "#0F9D58",
    "tier-1 news":                "#1976D2",
    "trade press":                "#00897B",
    "general news":               "#FB8C00",
    "press release / self-published": "#E64A19",
    "low-credibility / anonymous": "#C62828",
}


def grade_color(grade: str) -> str:
    return {
        "A": PALETTE["grade_a"],
        "B": PALETTE["grade_b"],
        "C": PALETTE["grade_c"],
        "D": PALETTE["grade_d"],
        "F": PALETTE["grade_f"],
    }.get(grade, PALETTE["neutral"])


def score_color(score: float) -> str:
    if score >= 80: return PALETTE["grade_a"]
    if score >= 65: return PALETTE["grade_b"]
    if score >= 50: return PALETTE["grade_c"]
    if score >= 35: return PALETTE["grade_d"]
    return PALETTE["grade_f"]


def status_color(status: str) -> str:
    return {
        "pass": PALETTE["ok"],
        "fail": PALETTE["danger"],
        "unknown": PALETTE["unknown"],
    }.get(status.lower(), PALETTE["neutral"])


# ---------------------------------------------------------------------------
# Custom CSS — injected once per page render
# ---------------------------------------------------------------------------

_CSS = """
<style>
/* Tighter top padding; viva audiences sit far away */
.block-container { padding-top: 1.5rem; padding-bottom: 2rem; max-width: 1400px; }

/* Hero card — large grade badge */
.scs-hero {
    background: linear-gradient(135deg, var(--scs-grade) 0%, rgba(0,0,0,0.35) 100%);
    border-radius: 16px;
    padding: 1.5rem 2rem;
    margin-bottom: 1rem;
    color: #fff;
    box-shadow: 0 8px 24px rgba(0,0,0,0.18);
}
.scs-hero h1 { color: #fff; margin: 0 0 0.25rem 0; font-size: 1.75rem; }
.scs-hero .scs-meta { opacity: 0.9; font-size: 0.95rem; }
.scs-hero .scs-grade-letter {
    font-size: 4rem; font-weight: 800; letter-spacing: -0.02em;
    line-height: 1; opacity: 0.95;
}

/* KPI tile */
.scs-kpi {
    background: rgba(99,102,241,0.05);
    border: 1px solid rgba(99,102,241,0.18);
    border-radius: 12px;
    padding: 0.85rem 1rem;
}
.scs-kpi .scs-kpi-label {
    font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.06em;
    color: var(--scs-muted, #64748B); margin-bottom: 0.15rem;
}
.scs-kpi .scs-kpi-value {
    font-size: 1.6rem; font-weight: 700; line-height: 1.1;
}
.scs-kpi .scs-kpi-delta { font-size: 0.78rem; margin-top: 0.2rem; }

/* Status pill */
.scs-pill {
    display: inline-block;
    padding: 0.15rem 0.6rem;
    border-radius: 999px;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
}

/* Section header with rule */
.scs-section {
    display: flex; align-items: center; gap: 0.75rem;
    margin: 1.4rem 0 0.8rem 0;
}
.scs-section h3 { margin: 0; font-size: 1.05rem; font-weight: 600; letter-spacing: 0.01em; }
.scs-section .scs-rule { flex: 1; height: 1px; background: rgba(120,120,120,0.2); }

/* Sidebar polish */
section[data-testid="stSidebar"] .scs-brand {
    font-weight: 700; font-size: 1.05rem; line-height: 1.2;
    margin-bottom: 0.2rem;
}
section[data-testid="stSidebar"] .scs-tag {
    font-size: 0.72rem; opacity: 0.65; letter-spacing: 0.04em;
    text-transform: uppercase;
}

/* Tighten tab labels */
button[data-baseweb="tab"] { padding-top: 0.4rem; padding-bottom: 0.4rem; }

/* Make code blocks denser */
code { font-size: 0.85em; }
</style>
"""


def inject_css() -> None:
    """Inject custom CSS once. Idempotent — calling many times is fine."""
    st.markdown(_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Plotly default layout
# ---------------------------------------------------------------------------

def plotly_layout(title: str | None = None, height: int = 320) -> dict:
    """Returns kwargs that should be merged into a Plotly figure layout
    for consistency."""
    layout = dict(
        height=height,
        margin=dict(t=40 if title else 16, l=12, r=12, b=12),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, system-ui, sans-serif", size=12),
        legend=dict(orientation="h", yanchor="bottom", y=-0.18, xanchor="left", x=0),
        hoverlabel=dict(font_size=12),
    )
    if title:
        layout["title"] = dict(text=title, x=0, xanchor="left", font=dict(size=14))
    return layout
