"""Compare 2-5 suppliers across multiple parameters."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from scs.data import load_suppliers
from scs.service import assess

from scs.dashboard import charts
from scs.dashboard.components import section, kpi, grade_pill
from scs.dashboard.styling import PALETTE, score_color


def render(use_defense: bool, threshold: float) -> None:
    st.title("Multi-supplier comparison")
    st.caption(
        "Compare up to five suppliers side-by-side across compliance, risk, "
        "and belief decomposition."
    )

    suppliers = list(load_suppliers())
    by_name = {s.name: s for s in suppliers}

    # Default selection: a clean PLI awardee + a debarred entity + a JV in distress
    defaults = [
        s.name for s in suppliers
        if s.id in {"dixon-tech", "shenzhen-shadow-corp", "vedanta-foxconn"}
    ]
    picked = st.multiselect(
        "Pick 2 to 5 suppliers",
        options=[s.name for s in suppliers],
        default=defaults if defaults else [s.name for s in suppliers[:3]],
        max_selections=5,
    )

    if len(picked) < 2:
        st.info("Select at least two suppliers to compare.")
        return

    reports = {}
    for name in picked:
        reports[by_name[name].id] = assess(by_name[name], use_defense=use_defense)

    # ---------- Metric strip per supplier ----------
    cols = st.columns(len(picked))
    for col, name in zip(cols, picked):
        sid = by_name[name].id
        rep = reports[sid]
        with col:
            kpi(
                name,
                f"{rep.score.score:.1f}",
                delta=f"Grade {rep.score.grade}",
                color=score_color(rep.score.score),
            )

    # ---------- Bar chart ----------
    section("Composite score")
    rows = [{"name": by_name[n].name, "score": reports[by_name[n].id].score.score}
            for n in picked]
    st.plotly_chart(charts.compare_bars(rows), use_container_width=True)

    # ---------- Radar overlay ----------
    section("Risk topology overlay")
    scores_dict = {by_name[n].id: reports[by_name[n].id].score for n in picked}
    risk_dict = {by_name[n].id: reports[by_name[n].id].risk for n in picked}
    st.plotly_chart(charts.compare_radar(scores_dict, risk_dict), use_container_width=True)
    st.caption(
        "Overlaid spider plots — same axes, one closed loop per supplier. "
        "Larger area = riskier topology."
    )

    # ---------- Parallel coordinates ----------
    section("Multi-dimensional parallel coordinates")
    pc_rows = []
    for n in picked:
        sid = by_name[n].id
        rep = reports[sid]
        pc_rows.append({
            "name": n,
            "score": rep.score.score,
            "belief_safe": rep.score.belief_safe,
            "belief_risky": rep.score.belief_risky,
            "uncertainty": rep.score.uncertainty,
            "articles": rep.risk.article_count,
            "max_severity": rep.risk.max_severity,
            "fail_count": rep.compliance.fail_count,
        })
    st.plotly_chart(charts.compare_parallel_coords(pc_rows), use_container_width=True)
    st.caption(
        "Drag along any axis to filter. Lines coloured by overall score: "
        "green = safe, red = risky."
    )

    # ---------- Detailed metric table ----------
    section("Metric matrix")
    rows = []
    for n in picked:
        sid = by_name[n].id
        rep = reports[sid]
        rows.append({
            "Supplier": n,
            "Country": by_name[n].country,
            "Category": by_name[n].category.value.replace("_", " "),
            "Score": rep.score.score,
            "Grade": rep.score.grade,
            "Belief safe": rep.score.belief_safe,
            "Belief risky": rep.score.belief_risky,
            "Uncertainty": rep.score.uncertainty,
            "Compliance fails": rep.compliance.fail_count,
            "Articles": rep.risk.article_count,
            "Max severity": rep.risk.max_severity,
            "Avg sentiment": round(rep.risk.avg_sentiment, 2),
        })
    df = pd.DataFrame(rows).set_index("Supplier")
    st.dataframe(
        df,
        use_container_width=True,
        column_config={
            "Score": st.column_config.ProgressColumn(format="%.1f", min_value=0, max_value=100),
            "Belief safe": st.column_config.ProgressColumn(format="%.2f", min_value=0.0, max_value=1.0),
            "Belief risky": st.column_config.ProgressColumn(format="%.2f", min_value=0.0, max_value=1.0),
            "Uncertainty": st.column_config.ProgressColumn(format="%.2f", min_value=0.0, max_value=1.0),
            "Max severity": st.column_config.ProgressColumn(format="%d", min_value=0, max_value=5),
        },
    )

    # ---------- Per-supplier detail expanders ----------
    section("Per-supplier audit trail")
    for n in picked:
        sid = by_name[n].id
        rep = reports[sid]
        with st.expander(f"{n} — top contributions", expanded=False):
            st.plotly_chart(
                charts.contributions_waterfall(rep.score, top_n=8),
                use_container_width=True,
                key=f"contrib_{sid}",
            )
