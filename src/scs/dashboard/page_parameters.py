"""Parameters page — displays every input the system uses for analysis.

This is the system's self-documentation. A reviewer can see at a glance
what data the scoring layer can consume, where it comes from in
production, and how a given supplier's profile compares against the
healthy / concerning thresholds.
"""
from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from scs.data import load_suppliers
from scs.metrics_taxonomy import (
    SPECS, ParameterSpec, health_label, specs_by_group,
)
from scs.profile import get_profile

from scs.dashboard.components import section, kpi
from scs.dashboard.styling import PALETTE, plotly_layout


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _direction_pill(direction: str) -> str:
    icon = {
        "higher_is_better": "↑",
        "lower_is_better":  "↓",
        "in_range":         "↕",
        "categorical":      "≡",
    }.get(direction, "·")
    label = direction.replace("_", " ")
    color = PALETTE["accent"]
    return (
        f"<span class='scs-pill' style='background:{color}22; color:{color};"
        f" border:1px solid {color}55;'>{icon} {label}</span>"
    )


def _scoring_pill(used: bool) -> str:
    if used:
        return (
            f"<span class='scs-pill' style='background:{PALETTE['ok']}22; "
            f"color:{PALETTE['ok']}; border:1px solid {PALETTE['ok']}55;'>"
            f"✓ used in scoring</span>"
        )
    return (
        f"<span class='scs-pill' style='background:{PALETTE['neutral']}22; "
        f"color:{PALETTE['neutral']}; border:1px solid {PALETTE['neutral']}55;'>"
        f"reference only</span>"
    )


def _healthy_band(spec: ParameterSpec) -> str:
    bits = []
    if spec.healthy_min is not None:
        bits.append(f"healthy ≥ {spec.healthy_min}")
    if spec.healthy_max is not None:
        bits.append(f"healthy ≤ {spec.healthy_max}")
    if spec.concerning_min is not None:
        bits.append(f"concerning ≥ {spec.concerning_min}")
    if spec.concerning_max is not None:
        bits.append(f"concerning ≤ {spec.concerning_max}")
    return " · ".join(bits) if bits else "—"


def _value_for_supplier(spec: ParameterSpec, supplier, profile, today_year: int) -> Any:
    """Look up a parameter's value on a given supplier."""
    key = spec.key

    # Identity / scale
    if key == "years_in_operation":
        if supplier.incorporated:
            return today_year - supplier.incorporated.year
        return None
    if key == "employee_count":
        return profile.employees if profile else None
    if key == "annual_revenue_usd_m":
        if profile and profile.annual_turnover_cr is not None:
            return round(profile.annual_turnover_cr * 0.012, 2)  # rough INR cr -> USD M
        return None
    if key == "number_of_facilities":
        # Not in profile; treat as unknown
        return None
    if key == "country":
        return supplier.country

    # Financial health
    fin_map = {
        "current_ratio":             "current_ratio",
        "debt_to_equity":            "debt_to_equity",
        "net_worth_inr_cr":          "net_worth_cr",
        "annual_turnover_inr_cr":    "annual_turnover_cr",
        "gst_compliance_score":      "gst_compliance_score",
        "days_payable_outstanding":  "days_payable_outstanding",
        "days_sales_outstanding":    "days_sales_outstanding",
        "udyam_category":            "udyam_category",
    }
    if key in fin_map and profile is not None:
        v = getattr(profile, fin_map[key], None)
        return v.value if hasattr(v, "value") else v

    # Operational
    ops_map = {
        "on_time_delivery_pct":      "on_time_delivery_pct",
        "defect_rate_ppm":           "defect_rate_ppm",
        "capacity_utilization_pct":  "capacity_utilization_pct",
        "monthly_capacity_units":    "monthly_capacity_units",
        "plant_area_sqft":           "plant_area_sqft",
    }
    if key in ops_map and profile is not None:
        return getattr(profile, ops_map[key], None)

    if key == "iso_9001_status" and profile is not None:
        return profile.iso_9001.value if profile.iso_9001 else None
    if key == "bis_crs_active" and profile is not None:
        return profile.bis_crs_active

    # Compliance / regulatory
    if key == "mca_active" and profile is not None:
        return profile.mca_status_active
    if key == "kspcb_noc" and profile is not None:
        return profile.pollution_noc_kspcb
    if key == "fire_noc" and profile is not None:
        return profile.fire_noc
    if key == "factories_act_license" and profile is not None:
        return profile.factories_act_license
    if key == "epf_dues_clear" and profile is not None:
        return profile.epf_dues_clear
    if key == "itr_filed" and profile is not None:
        return profile.income_tax_returns_filed

    # Cybersecurity / network — these mostly come from the news pipeline
    # so they don't have static values per supplier here. Return None.
    if key == "domain_age_years" and profile is not None:
        return profile.domain_age_years
    if key == "customer_references_count" and profile is not None:
        return profile.customer_references_count
    if key == "labor_cases_3y" and profile is not None:
        return profile.labor_cases_3y

    return None


# ---------------------------------------------------------------------------
# Page entrypoint
# ---------------------------------------------------------------------------


def render(use_defense: bool, threshold: float) -> None:
    st.title("📋 Parameters used in analysis")
    st.caption(
        "Every input the supplier-scoring engine can consume, organised "
        "by category. Together they cover the four signal buckets from "
        "the project's research framework — operational reliability, "
        "financial solvency, compliance & ESG trust, and early-warning "
        "patterns — plus identity/scale and capability."
    )

    by_group = specs_by_group()
    total = sum(len(v) for v in by_group.values())
    n_scored = sum(1 for s in SPECS if s.used_in_scoring)

    # ---------- Top KPIs ----------
    c1, c2, c3, c4 = st.columns(4)
    with c1: kpi("Total parameters", str(total))
    with c2: kpi("Used in scoring", str(n_scored), color=PALETTE["ok"])
    with c3: kpi("Categories", str(len(by_group)))
    with c4: kpi("Reference only", str(total - n_scored), color=PALETTE["neutral"])

    # ---------- Distribution chart ----------
    section("Coverage by category")
    rows = []
    for g, specs in by_group.items():
        rows.append({
            "group": g,
            "Used in scoring": sum(1 for s in specs if s.used_in_scoring),
            "Reference only": sum(1 for s in specs if not s.used_in_scoring),
        })
    df_dist = pd.DataFrame(rows).set_index("group")
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df_dist.index, y=df_dist["Used in scoring"], name="Used in scoring",
        marker=dict(color=PALETTE["ok"]),
    ))
    fig.add_trace(go.Bar(
        x=df_dist.index, y=df_dist["Reference only"], name="Reference only",
        marker=dict(color=PALETTE["neutral"]),
    ))
    fig.update_layout(
        **plotly_layout(height=300),
        barmode="stack",
        xaxis=dict(title=None),
        yaxis=dict(title="Parameter count"),
    )
    st.plotly_chart(fig, use_container_width=True)

    # ---------- Search / filter ----------
    col_a, col_b, col_c = st.columns([2, 2, 1])
    with col_a:
        text_q = st.text_input(
            "Search parameters", placeholder="e.g. ISO, GSTIN, OTD, defect",
        )
    with col_b:
        sel_groups = st.multiselect(
            "Filter by category",
            options=list(by_group.keys()),
            default=[],
            placeholder="All categories",
        )
    with col_c:
        only_scored = st.toggle("Used in scoring only", value=False)

    # ---------- Per-category sections ----------
    for group_name, specs in by_group.items():
        if sel_groups and group_name not in sel_groups:
            continue

        # Apply filters
        rows_filtered = []
        for spec in specs:
            if text_q.strip():
                hay = (spec.label + " " + spec.description + " " + spec.key).lower()
                if text_q.strip().lower() not in hay:
                    continue
            if only_scored and not spec.used_in_scoring:
                continue
            rows_filtered.append(spec)

        if not rows_filtered:
            continue

        section(f"{group_name} — {len(rows_filtered)} parameter(s)")

        for spec in rows_filtered:
            with st.expander(
                f"{'✓ ' if spec.used_in_scoring else '· '}"
                f"{spec.label}  ·  {spec.unit}",
                expanded=False,
            ):
                col_a, col_b = st.columns([3, 2])
                with col_a:
                    st.markdown(spec.description)
                    st.markdown(
                        f"{_direction_pill(spec.direction)}  "
                        f"{_scoring_pill(spec.used_in_scoring)}",
                        unsafe_allow_html=True,
                    )
                with col_b:
                    st.markdown(f"**Healthy / concerning band**  \n{_healthy_band(spec)}")
                    st.markdown(
                        f"**Production source**  \n"
                        f"_{spec.source_examples or 'configurable feed'}_"
                    )
                    st.markdown(
                        f"**Field key**  \n`{spec.key}`"
                    )

    # ---------- Per-supplier walkthrough ----------
    st.divider()
    section("How does one supplier look on every parameter?")

    suppliers = list(load_suppliers())
    by_name = {s.name: s for s in suppliers}
    name = st.selectbox(
        "Pick a supplier",
        options=[s.name for s in suppliers],
        key="param_supplier",
    )
    sup = by_name[name]
    prof = get_profile(sup.id)

    if prof is None:
        st.warning(
            f"No extended profile is on file for {sup.name}. "
            f"Only identity-level parameters are available."
        )

    today_year = pd.Timestamp.now().year

    rows = []
    for spec in SPECS:
        v = _value_for_supplier(spec, sup, prof, today_year)
        rows.append({
            "Category": spec.group,
            "Parameter": spec.label,
            "Value": v if v is not None else "—",
            "Unit": spec.unit,
            "Health": health_label(spec, v) if v is not None else "unknown",
            "Used in scoring": "✓" if spec.used_in_scoring else "—",
            "Source": spec.source_examples or "—",
        })
    df = pd.DataFrame(rows)

    # Stat strip
    n_known = (df["Value"] != "—").sum()
    n_concerning = (df["Health"] == "concerning").sum()
    n_warn = (df["Health"] == "warn").sum()
    n_healthy = (df["Health"] == "healthy").sum()

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: kpi("Parameters known", f"{n_known}/{len(df)}")
    with c2: kpi("Healthy", str(n_healthy), color=PALETTE["ok"])
    with c3: kpi("Warn", str(n_warn), color=PALETTE["warn"])
    with c4: kpi("Concerning", str(n_concerning), color=PALETTE["danger"])
    with c5:
        coverage = n_known / len(df)
        kpi("Profile coverage", f"{coverage:.0%}",
            color=PALETTE["ok"] if coverage > 0.7 else PALETTE["warn"])

    # Tabbed by category
    tabs = st.tabs(list(by_group.keys()))
    for tab, (gname, _specs) in zip(tabs, by_group.items()):
        with tab:
            sub = df[df["Category"] == gname].drop(columns=["Category"])

            def _color_health(val):
                if val == "healthy":
                    return f"background-color: {PALETTE['ok']}33; color: {PALETTE['ok']}; font-weight: 600"
                if val == "warn":
                    return f"background-color: {PALETTE['warn']}33; color: {PALETTE['warn']}; font-weight: 600"
                if val == "concerning":
                    return f"background-color: {PALETTE['danger']}33; color: {PALETTE['danger']}; font-weight: 600"
                return f"color: {PALETTE['unknown']}"

            styled = sub.style.map(_color_health, subset=["Health"])
            st.dataframe(
                styled,
                use_container_width=True, hide_index=True,
            )

    # ---------- CSV export of the schema itself ----------
    st.divider()
    section("Export")
    schema_rows = []
    for spec in SPECS:
        schema_rows.append({
            "key": spec.key,
            "group": spec.group,
            "label": spec.label,
            "description": spec.description,
            "unit": spec.unit,
            "direction": spec.direction,
            "healthy_min": spec.healthy_min,
            "healthy_max": spec.healthy_max,
            "concerning_min": spec.concerning_min,
            "concerning_max": spec.concerning_max,
            "used_in_scoring": spec.used_in_scoring,
            "production_source": spec.source_examples,
        })
    schema_df = pd.DataFrame(schema_rows)
    st.dataframe(schema_df, use_container_width=True, hide_index=True, height=320)
    st.download_button(
        "⬇️ Download parameter schema as CSV",
        data=schema_df.to_csv(index=False).encode(),
        file_name="parameters_schema.csv",
        mime="text/csv",
    )
