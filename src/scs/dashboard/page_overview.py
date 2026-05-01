"""Portfolio overview page."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from scs.compliance.pipeline import run as run_comp
from scs.data import load_suppliers
from scs.evaluation.ground_truth import load_labels
from scs.evaluation.metrics import RISK_THRESHOLD
from scs.risk.pipeline import run as run_risk
from scs.scoring.fusion import fuse

from scs.dashboard import charts
from scs.dashboard.components import section, kpi, status_pill, grade_pill
from scs.dashboard.styling import PALETTE, score_color


@st.cache_data
def _portfolio(use_defense: bool):
    suppliers = list(load_suppliers())
    by_id = {s.id: s for s in suppliers}
    scores = {}
    risk_profiles = {}
    comp_reports = {}
    for s in suppliers:
        comp = run_comp(s)
        risk = run_risk(s)
        scr = fuse(s.id, comp, risk, use_defense=use_defense)
        scores[s.id] = scr
        risk_profiles[s.id] = risk
        comp_reports[s.id] = comp
    return by_id, scores, risk_profiles, comp_reports


def render(use_defense: bool, threshold: float) -> None:
    st.title("Portfolio overview")
    st.caption(
        "Aggregate view across all 25 seed suppliers. Toggle the defense in the "
        "sidebar to see how trust-calibrated fusion shifts the distribution."
    )

    by_id, scores, risk_profiles, comp_reports = _portfolio(use_defense)
    labels_gt = load_labels()

    # ---------- KPI strip ----------
    n_total = len(scores)
    n_risky = sum(1 for s in scores.values() if s.score < threshold)
    n_clean = n_total - n_risky
    avg_score = sum(s.score for s in scores.values()) / n_total
    n_compliance_fails = sum(r.fail_count > 0 for r in comp_reports.values())
    n_articles = sum(p.article_count for p in risk_profiles.values())

    # accuracy vs ground truth
    correct = 0
    for sid, s in scores.items():
        gt_risky = labels_gt.get(sid)
        if gt_risky is None:
            continue
        if (s.score < threshold) == gt_risky:
            correct += 1
    acc = correct / sum(1 for sid in scores if sid in labels_gt) if labels_gt else None

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1: kpi("Suppliers", str(n_total))
    with c2: kpi("Predicted risky", str(n_risky), color=PALETTE["danger"])
    with c3: kpi("Predicted safe",  str(n_clean), color=PALETTE["ok"])
    with c4: kpi("Avg score", f"{avg_score:.1f}", color=score_color(avg_score))
    with c5: kpi("With compliance flags", str(n_compliance_fails), color=PALETTE["warn"])
    with c6:
        kpi("Accuracy vs GT", f"{acc:.0%}" if acc is not None else "—",
            color=PALETTE["ok"] if (acc or 0) > 0.85 else PALETTE["warn"])

    # ---------- Distributions row ----------
    section("Score distribution")
    col_a, col_b = st.columns([3, 2])
    with col_a:
        st.plotly_chart(charts.score_distribution(scores), use_container_width=True)
    with col_b:
        st.plotly_chart(charts.signal_event_pie(risk_profiles), use_container_width=True)

    # ---------- Category + country ----------
    section("Score by supplier category")
    col_a, col_b = st.columns([3, 2])
    with col_a:
        st.plotly_chart(charts.category_box(scores, by_id), use_container_width=True)
    with col_b:
        st.plotly_chart(charts.country_sunburst(scores, by_id), use_container_width=True)

    # ---------- Compliance heatmap ----------
    section("Compliance status grid")
    st.plotly_chart(charts.compliance_heatmap(comp_reports, by_id), use_container_width=True)

    # ---------- Top risky / safest tables ----------
    section("Watchlist")
    rows = []
    for sid, s in scores.items():
        gt = labels_gt.get(sid)
        rows.append({
            "Supplier": by_id[sid].name,
            "Country": by_id[sid].country,
            "Category": by_id[sid].category.value.replace("_", " "),
            "Score": s.score,
            "Grade": s.grade,
            "Belief safe": s.belief_safe,
            "Belief risky": s.belief_risky,
            "Compliance fails": comp_reports[sid].fail_count,
            "Articles": risk_profiles[sid].article_count,
            "Ground truth": "RISKY" if gt else ("SAFE" if gt is False else "—"),
        })
    df = pd.DataFrame(rows).sort_values("Score")

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**Lowest 5 scores**")
        st.dataframe(
            df.head(5),
            use_container_width=True, hide_index=True,
            column_config={
                "Score": st.column_config.ProgressColumn(
                    "Score", format="%.1f", min_value=0, max_value=100,
                ),
                "Belief safe":  st.column_config.NumberColumn(format="%.2f"),
                "Belief risky": st.column_config.NumberColumn(format="%.2f"),
            },
        )
    with col_b:
        st.markdown("**Highest 5 scores**")
        st.dataframe(
            df.tail(5).iloc[::-1],
            use_container_width=True, hide_index=True,
            column_config={
                "Score": st.column_config.ProgressColumn(
                    "Score", format="%.1f", min_value=0, max_value=100,
                ),
                "Belief safe":  st.column_config.NumberColumn(format="%.2f"),
                "Belief risky": st.column_config.NumberColumn(format="%.2f"),
            },
        )

    # ---------- Full table ----------
    with st.expander("All suppliers (sortable)", expanded=False):
        st.dataframe(
            df,
            use_container_width=True, hide_index=True,
            column_config={
                "Score": st.column_config.ProgressColumn(
                    "Score", format="%.1f", min_value=0, max_value=100,
                ),
                "Belief safe":  st.column_config.NumberColumn(format="%.2f"),
                "Belief risky": st.column_config.NumberColumn(format="%.2f"),
            },
        )
