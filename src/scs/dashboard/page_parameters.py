"""Parameters page - exposes every parameter the analyser uses.

This page is the system's "what does it look at" disclosure for a
teacher / reviewer / procurement team. It lists all 35 parameters
defined in scs.metrics_taxonomy.SPECS, groups them, shows whether
each is currently used in scoring, the healthy/concerning thresholds,
how many of the seeded suppliers actually have a value for it, and
the distribution of the values.

A second section shows, for one selected supplier, every parameter
contribution actually fed into the fusion layer.
"""
from __future__ import annotations

import math
from collections import Counter

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from scs.data import load_suppliers
from scs.metrics_taxonomy import SPECS, ParameterSpec
from scs.profile import SupplierProfile, load_profiles
from scs.scoring.parameters import parameter_contributions

from scs.dashboard.components import section, kpi
from scs.dashboard.styling import PALETTE, plotly_layout


# ---------------------------------------------------------------------------
# Map taxonomy keys -> attribute on SupplierProfile
# Some don't have a 1:1 mapping; we leave those as None so the coverage
# stats honestly reflect what data we currently hold.
# ---------------------------------------------------------------------------

_KEY_TO_PROFILE = {
    "employee_count":             "employees",
    "annual_revenue_usd_m":       None,            # derived from annual_turnover_cr
    "current_ratio":              "current_ratio",
    "debt_to_equity_ratio":       "debt_to_equity",
    "days_payables_outstanding":  "days_payable_outstanding",
    "on_time_delivery_pct":       "on_time_delivery_pct",
    "defect_rate_ppm":            "defect_rate_ppm",
    "capacity_utilization_pct":   "capacity_utilization_pct",
    "iso_9001_status":            "iso_9001",
    "iso_14001_status":           "iso_14001",
    "iatf_16949_status":          "iatf_16949",
    "as9100_status":              "as_9100",
}

# Aliases used by the reputation/regulatory rules (no taxonomy spec yet)
# We list them here so the Parameters page can surface them too.
_EXTRA_FIELDS_DESC = {
    "gst_compliance_score":         ("Financial health", "GST compliance score (govt portal)", "0-100"),
    "net_worth_cr":                 ("Financial health", "Net worth (₹ crore)",                 "₹ cr"),
    "annual_turnover_cr":           ("Financial health", "Annual turnover (₹ crore)",          "₹ cr"),
    "udyam_category":               ("Identity & scale", "Udyam (MSME) category",              "enum"),
    "ipc_a_610":                    ("Quality certification", "IPC-A-610 (acceptability)",     "status"),
    "iso_13485":                    ("Quality certification", "ISO 13485 (medical devices)",   "status"),
    "bis_crs_active":               ("Quality certification", "BIS CRS active",                "yes/no"),
    "mca_status_active":            ("Regulatory", "MCA registration active",                  "yes/no"),
    "pollution_noc_kspcb":          ("Regulatory", "KSPCB pollution NOC",                      "yes/no"),
    "fire_noc":                     ("Regulatory", "Fire NOC current",                         "yes/no"),
    "factories_act_license":        ("Regulatory", "Factories Act licence",                    "yes/no"),
    "epf_dues_clear":               ("Regulatory", "EPF dues clear",                           "yes/no"),
    "income_tax_returns_filed":     ("Regulatory", "Income-tax returns filed",                 "yes/no"),
    "epfo_registration":            ("Regulatory", "EPFO registered",                          "yes/no"),
    "esic_registration":            ("Regulatory", "ESIC registered",                          "yes/no"),
    "shop_estab_license":           ("Regulatory", "Shop & Estab. licence",                    "yes/no"),
    "domain_age_years":             ("Reputation", "Domain age (years)",                       "years"),
    "online_review_score":          ("Reputation", "Online review score (1-5)",                "rating"),
    "customer_references_count":    ("Reputation", "Customer references",                      "count"),
    "labor_cases_3y":               ("Reputation", "Labour disputes (3 yr)",                   "count"),
    "media_coverage_breadth":       ("Reputation", "Media coverage breadth",                   "count"),
    "plant_area_sqft":              ("Identity & scale", "Plant area",                         "sqft"),
    "monthly_capacity_units":       ("Operational", "Monthly capacity",                        "units"),
    "cin":                          ("Identity & scale", "CIN",                                "id"),
    "pan":                          ("Identity & scale", "PAN",                                "id"),
    "gstin":                        ("Identity & scale", "GSTIN",                              "id"),
    "udyam_registration":           ("Identity & scale", "Udyam registration",                 "id"),
    "iec":                          ("Identity & scale", "IEC (import-export code)",           "id"),
    "days_sales_outstanding":       ("Financial health", "Days sales outstanding",             "days"),
}


# ---------------------------------------------------------------------------
# Coverage / distribution helpers
# ---------------------------------------------------------------------------


def _coverage_for(field_name: str | None) -> tuple[int, list]:
    """Return (count_known, list_of_known_values) across all profiles."""
    if field_name is None:
        return 0, []
    values = []
    for prof in load_profiles().values():
        v = getattr(prof, field_name, None)
        if v is None:
            continue
        # Some are enums — get .value
        if hasattr(v, "value"):
            v = v.value
        values.append(v)
    return len(values), values


def _coverage_pct(known: int, total: int) -> float:
    return 100.0 * known / total if total else 0.0


def _value_distribution_chart(values: list, label: str) -> go.Figure | None:
    if not values:
        return None
    if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values):
        # Numeric histogram
        fig = go.Figure(go.Histogram(
            x=values, marker=dict(color=PALETTE["accent"]),
            hovertemplate=f"%{{x}}: %{{y}} suppliers<extra></extra>",
        ))
        fig.update_layout(**plotly_layout(height=200), bargap=0.05,
                          xaxis=dict(title=label),
                          yaxis=dict(title="Suppliers"))
        return fig
    else:
        # Categorical bar
        c = Counter(str(v) for v in values)
        fig = go.Figure(go.Bar(
            x=list(c.keys()), y=list(c.values()),
            marker=dict(color=PALETTE["accent"]),
            hovertemplate="%{x}: %{y}<extra></extra>",
        ))
        fig.update_layout(**plotly_layout(height=200),
                          xaxis=dict(title=label),
                          yaxis=dict(title="Suppliers"))
        return fig


# ---------------------------------------------------------------------------
# Build the master parameter table (taxonomy + extras)
# ---------------------------------------------------------------------------


def _master_table() -> pd.DataFrame:
    rows = []
    n_profiles = len(load_profiles())

    seen_keys: set[str] = set()

    # Pass 1: every taxonomy entry
    for spec in SPECS:
        seen_keys.add(spec.key)
        prof_field = _KEY_TO_PROFILE.get(spec.key)
        known, _ = _coverage_for(prof_field)
        rows.append({
            "Key":          spec.key,
            "Group":        spec.group,
            "Label":        spec.label,
            "Unit":         spec.unit,
            "Direction":    spec.direction.replace("_", " "),
            "Healthy":      _fmt_threshold(spec.healthy_min, spec.healthy_max, spec.direction),
            "Concerning":   _fmt_threshold(spec.concerning_min, spec.concerning_max, spec.direction),
            "Used in scoring": "✓" if spec.used_in_scoring else "—",
            "Coverage":     f"{known}/{n_profiles} ({_coverage_pct(known, n_profiles):.0f}%)",
            "Description":  spec.description,
            "Source":       spec.source_examples,
            "_field":       prof_field,
        })

    # Pass 2: extras with known descriptors not in taxonomy
    for field, (group, label, unit) in _EXTRA_FIELDS_DESC.items():
        known, _ = _coverage_for(field)
        if known == 0:
            continue
        rows.append({
            "Key":          field,
            "Group":        group,
            "Label":        label,
            "Unit":         unit,
            "Direction":    "—",
            "Healthy":      "—",
            "Concerning":   "—",
            "Used in scoring": "✓" if _is_in_scoring(field) else "—",
            "Coverage":     f"{known}/{n_profiles} ({_coverage_pct(known, n_profiles):.0f}%)",
            "Description":  "Extension parameter — see scoring.parameters rule body.",
            "Source":       "MCA21 / KSPCB / Udyam / labour court / company website",
            "_field":       field,
        })

    return pd.DataFrame(rows)


def _is_in_scoring(field: str) -> bool:
    """Quick heuristic: does scoring.parameters consume this profile field?"""
    scoring_fields = {
        "current_ratio", "debt_to_equity", "days_payable_outstanding",
        "gst_compliance_score", "net_worth_cr", "on_time_delivery_pct",
        "defect_rate_ppm", "capacity_utilization_pct",
        "iso_9001", "iso_14001", "iatf_16949", "as_9100", "iso_13485", "ipc_a_610",
        "bis_crs_active", "mca_status_active", "pollution_noc_kspcb",
        "fire_noc", "factories_act_license", "epf_dues_clear",
        "income_tax_returns_filed", "epfo_registration", "esic_registration",
        "shop_estab_license",
        "domain_age_years", "online_review_score", "customer_references_count",
        "labor_cases_3y", "media_coverage_breadth", "employees",
        "annual_turnover_cr",
    }
    return field in scoring_fields


def _fmt_threshold(mn, mx, direction) -> str:
    if mn is None and mx is None:
        return "—"
    if direction == "lower_is_better":
        return f"≤ {mx}" if mx is not None else f"≤ {mn}"
    if direction == "higher_is_better":
        return f"≥ {mn}" if mn is not None else f"≥ {mx}"
    if direction == "in_range":
        return f"{mn}–{mx}"
    return "—"


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------


def render(use_defense: bool, threshold: float) -> None:
    st.title("📑 Parameters used in analysis")
    st.caption(
        "Every parameter the trust-calibrated scorer reads, end to end. "
        "This page is the system's full disclosure: what gets measured, "
        "where the data comes from, what counts as healthy, what counts "
        "as a red flag, and how much of the directory currently has data "
        "for each one."
    )

    df = _master_table()

    # ---------- KPI strip ----------
    n_total = len(df)
    n_scoring = (df["Used in scoring"] == "✓").sum()
    groups = df["Group"].nunique()
    avg_cov = df["Coverage"].apply(
        lambda s: float(s.split("(")[1].split("%")[0])
    ).mean()

    c1, c2, c3, c4 = st.columns(4)
    with c1: kpi("Parameters defined", str(n_total))
    with c2: kpi("Used in scoring", str(n_scoring), color=PALETTE["accent"])
    with c3: kpi("Categories", str(groups))
    with c4: kpi("Avg coverage", f"{avg_cov:.0f}%",
                  color=PALETTE["ok"] if avg_cov > 70 else PALETTE["warn"])

    # ---------- Group filter ----------
    section("Browse the taxonomy")
    sel_groups = st.multiselect(
        "Group filter",
        options=sorted(df["Group"].unique().tolist()),
        default=[],
        placeholder="All groups",
    )
    only_scoring = st.checkbox("Show only parameters that influence the score", value=False)

    show = df.copy()
    if sel_groups:
        show = show[show["Group"].isin(sel_groups)]
    if only_scoring:
        show = show[show["Used in scoring"] == "✓"]

    visible = show.drop(columns=["_field"])
    st.dataframe(
        visible,
        use_container_width=True, hide_index=True,
    )

    csv_bytes = visible.to_csv(index=False).encode()
    st.download_button(
        "⬇️ Download parameter taxonomy as CSV",
        data=csv_bytes, file_name="parameters_taxonomy.csv", mime="text/csv",
    )

    # ---------- Distribution drill-in ----------
    section("Per-parameter distribution across the directory")
    pick = st.selectbox(
        "Inspect a parameter",
        options=[r["Key"] for _, r in show.iterrows()],
        format_func=lambda k: f"{k} — {df[df['Key']==k]['Label'].iloc[0]}",
    )
    row = df[df["Key"] == pick].iloc[0]
    field = row["_field"]
    known, values = _coverage_for(field)

    c1, c2, c3 = st.columns(3)
    with c1: kpi("Known values", f"{known} / {len(load_profiles())}")
    with c2: kpi("Group", row["Group"])
    with c3: kpi("Used in scoring", row["Used in scoring"],
                  color=PALETTE["accent"] if row["Used in scoring"] == "✓" else PALETTE["muted"])

    if not values:
        st.info("No supplier in the directory currently has a value for this parameter.")
    else:
        st.markdown(f"**{row['Label']}**  ·  unit: `{row['Unit']}`")
        if row["Description"] not in (None, "—"):
            st.caption(row["Description"])
        chart = _value_distribution_chart(values, row["Label"])
        if chart is not None:
            st.plotly_chart(chart, use_container_width=True)

    # ---------- Per-supplier contribution view ----------
    section("Parameter contributions for one supplier")

    suppliers = sorted(load_suppliers(), key=lambda s: s.name)
    by_name = {s.name: s for s in suppliers}
    name = st.selectbox(
        "Supplier",
        options=list(by_name.keys()),
        index=0,
    )
    s = by_name[name]
    profile = load_profiles().get(s.id)

    if profile is None:
        st.warning(
            f"No extended profile data for **{s.name}**. The system would "
            "score this supplier on compliance + news only."
        )
        return

    incorp_year = s.incorporated.year if s.incorporated else None
    contribs = parameter_contributions(profile, incorp_year)

    if not contribs:
        st.info("No parameter contributions for this supplier (all values unknown).")
        return

    rows = []
    for pc in contribs:
        rows.append({
            "Group":  pc.group,
            "Label":  pc.label,
            "Value":  str(pc.raw_value),
            "Safe mass":   round(pc.bpa.safe, 3),
            "Risky mass":  round(pc.bpa.risky, 3),
            "Net push":    round((pc.bpa.safe - pc.bpa.risky) * 100, 1),
        })
    cdf = pd.DataFrame(rows).sort_values("Net push", ascending=False)
    st.dataframe(
        cdf,
        use_container_width=True, hide_index=True,
        column_config={
            "Safe mass":  st.column_config.ProgressColumn(format="%.2f", min_value=0.0, max_value=0.85),
            "Risky mass": st.column_config.ProgressColumn(format="%.2f", min_value=0.0, max_value=0.85),
            "Net push":   st.column_config.NumberColumn(format="%+.1f"),
        },
    )

    # Bar chart of contributions
    bar_df = cdf.sort_values("Net push")
    colors = [PALETTE["ok"] if v > 0 else PALETTE["danger"] for v in bar_df["Net push"]]
    fig = go.Figure(go.Bar(
        x=bar_df["Net push"], y=bar_df["Label"], orientation="h",
        marker=dict(color=colors),
        hovertemplate="<b>%{y}</b><br>net push=%{x:+.1f}<extra></extra>",
    ))
    fig.update_layout(
        **plotly_layout(height=max(280, 22 * len(bar_df))),
        xaxis=dict(title="Net push on score (points)",
                   zeroline=True, zerolinecolor="rgba(120,120,120,0.4)"),
        yaxis=dict(title=None),
    )
    st.plotly_chart(fig, use_container_width=True)
