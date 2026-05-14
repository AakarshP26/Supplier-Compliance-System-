"""Reusable Streamlit UI components.

Each function renders a piece of UI. Pages compose these.
"""
from __future__ import annotations

import streamlit as st

from scs.dashboard.styling import (
    grade_color, score_color, status_color, PALETTE,
)
from scs.models import Supplier, SupplierScore


def section(title: str) -> None:
    """Section header with a thin rule on the right."""
    st.markdown(
        f"""<div class="scs-section"><h3>{title}</h3><div class="scs-rule"></div></div>""",
        unsafe_allow_html=True,
    )


def hero(supplier: Supplier, score: SupplierScore) -> None:
    """Big banner with grade and meta. Background tinted by grade."""
    color = grade_color(score.grade)
    meta = f"{supplier.country} · {supplier.category.value.replace('_', ' ')}"
    if supplier.cin:
        meta += f" · CIN {supplier.cin}"
    legal = supplier.legal_name or supplier.name

    st.markdown(
        f"""
<div class="scs-hero" style="--scs-grade: {color}">
  <div style="display:flex; align-items:center; justify-content:space-between; gap:1.5rem;">
    <div style="flex:1;">
      <h1>{supplier.name}</h1>
      <div class="scs-meta">{legal}</div>
      <div class="scs-meta" style="margin-top:0.35rem;">{meta}</div>
    </div>
    <div style="text-align:right;">
      <div class="scs-grade-letter">{score.grade}</div>
      <div style="font-size:0.85rem; opacity:0.85;">{score.score:.1f} / 100</div>
    </div>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )


def kpi(label: str, value: str, delta: str | None = None, color: str | None = None) -> None:
    """Custom KPI tile (richer than st.metric)."""
    color_style = f"color:{color};" if color else ""
    delta_html = (
        f"<div class='scs-kpi-delta' style='color:{color or PALETTE['muted']}'>{delta}</div>"
        if delta else ""
    )
    st.markdown(
        f"""
<div class="scs-kpi">
  <div class="scs-kpi-label">{label}</div>
  <div class="scs-kpi-value" style="{color_style}">{value}</div>
  {delta_html}
</div>
        """,
        unsafe_allow_html=True,
    )


def status_pill(label: str, kind: str = "neutral") -> str:
    """Return HTML for an inline status pill. Use with st.markdown(unsafe_allow_html=True)."""
    color = {
        "ok":      PALETTE["ok"],
        "warn":    PALETTE["warn"],
        "danger":  PALETTE["danger"],
        "neutral": PALETTE["neutral"],
        "unknown": PALETTE["unknown"],
    }.get(kind, PALETTE["neutral"])
    return (
        f"<span class='scs-pill' style='background:{color}22; color:{color};"
        f" border:1px solid {color}55;'>{label}</span>"
    )


def grade_pill(grade: str) -> str:
    color = grade_color(grade)
    return (
        f"<span class='scs-pill' style='background:{color}22; color:{color};"
        f" border:1px solid {color}55; font-weight:700; font-size:0.85rem;'>"
        f"GRADE {grade}</span>"
    )


def compliance_status_html(status: str) -> str:
    color = status_color(status)
    icon = {"pass": "✓", "fail": "✗", "unknown": "?"}.get(status.lower(), "?")
    return (
        f"<span style='color:{color}; font-weight:700'>{icon} {status.upper()}</span>"
    )
