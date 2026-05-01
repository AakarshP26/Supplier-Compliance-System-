"""Enhanced single-supplier detail page."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from scs.data import load_suppliers
from scs.evaluation.ground_truth import load_rationales
from scs.service import assess

from scs.dashboard import charts
from scs.dashboard.components import (
    section, kpi, hero, status_pill, grade_pill, compliance_status_html,
)
from scs.dashboard.styling import PALETTE, score_color, status_color


def render(use_defense: bool, threshold: float) -> None:
    suppliers = list(load_suppliers())
    by_name = {s.name: s for s in suppliers}

    name = st.selectbox(
        "Supplier",
        options=[s.name for s in suppliers],
        index=0,
        key="detail_picker",
    )
    supplier = by_name[name]
    report = assess(supplier, use_defense=use_defense)
    score = report.score
    rationales = load_rationales()

    # Hero
    hero(supplier, score)

    # Illustrative banner
    if supplier.is_illustrative:
        st.warning(
            f"ⓘ **Illustrative entry.** This supplier is a fictitious "
            f"SME-scale entity included for demonstration purposes — its "
            f"compliance status, news, and scores are constructed to show "
            f"the system handling realistic risk profiles. It does not "
            f"represent any real firm."
            + (f"  \n\n📝 _{supplier.note}_" if supplier.note else "")
        )

    # ---------- KPI strip ----------
    pred = "RISKY" if score.score < threshold else "SAFE"
    pred_color = PALETTE["danger"] if score.score < threshold else PALETTE["ok"]

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1: kpi("Score", f"{score.score:.1f}", color=score_color(score.score))
    with c2: kpi("Belief safe",  f"{score.belief_safe:.2f}", color=PALETTE["ok"])
    with c3: kpi("Belief risky", f"{score.belief_risky:.2f}", color=PALETTE["danger"])
    with c4: kpi("Uncertainty",  f"{score.uncertainty:.2f}", color=PALETTE["unknown"])
    with c5: kpi("Compliance fails", str(report.compliance.fail_count),
                  color=PALETTE["danger"] if report.compliance.fail_count else PALETTE["ok"])
    with c6: kpi("Prediction", pred, color=pred_color)

    if supplier.id in rationales and rationales[supplier.id]:
        st.caption(f"📋 **Ground-truth rationale (offline):** {rationales[supplier.id]}")

    # ---------- Visual row 1 ----------
    section("Belief decomposition · risk topology")
    col_a, col_b = st.columns(2)
    with col_a:
        st.plotly_chart(charts.belief_donut(score), use_container_width=True)
        st.caption(
            "Dempster–Shafer mass assignment over {safe, risky, Θ}. "
            "Yager's rule routes conflicting evidence to Θ rather than "
            "renormalising it away."
        )
    with col_b:
        st.plotly_chart(charts.risk_radar(report.risk), use_container_width=True)
        st.caption(
            "Per-event-type credible severity. Severity is multiplied by "
            "source credibility and corroboration before being plotted."
        )

    # ---------- Visual row 2 ----------
    section("News timeline")
    timeline = charts.news_timeline(report.risk.signals)
    if timeline is None:
        st.info("No dated news in the corpus for this supplier.")
    else:
        st.plotly_chart(timeline, use_container_width=True)

    # ---------- Compliance + sources ----------
    section("Evidence sources")
    col_a, col_b = st.columns([3, 2])
    with col_a:
        st.markdown("**Compliance checks**")
        rows = []
        for c in report.compliance.checks:
            rows.append({
                "Source": c.source,
                "Status": c.status.upper(),
                "Credibility": c.provenance.credibility,
                "Detail": c.detail,
                "Reference": c.provenance.source_url or "",
            })
        cdf = pd.DataFrame(rows)
        st.dataframe(
            cdf,
            use_container_width=True, hide_index=True,
            column_config={
                "Credibility": st.column_config.ProgressColumn(
                    "Cred.", format="%.2f", min_value=0.0, max_value=1.0,
                ),
                "Reference": st.column_config.LinkColumn("Reference"),
            },
        )

    with col_b:
        st.markdown("**Source credibility (all evidence)**")
        st.plotly_chart(
            charts.credibility_breakdown(report.compliance, report.risk),
            use_container_width=True,
        )

    # ---------- Risk signals table ----------
    section("Extracted risk signals")
    if not report.risk.signals:
        st.info("No risk signals extracted from the corpus.")
    else:
        rows = []
        for sg in report.risk.signals:
            rows.append({
                "Event": sg.event_type.value,
                "Severity": sg.severity,
                "Sentiment": sg.sentiment,
                "Source": sg.provenance.source_name,
                "Credibility": sg.credibility,
                "Corroborated": "✓" if sg.is_corroborated else "—",
                "Summary": sg.summary,
                "Published": (sg.provenance.published_at.date()
                              if sg.provenance.published_at else None),
            })
        sdf = pd.DataFrame(rows)
        st.dataframe(
            sdf,
            use_container_width=True, hide_index=True,
            column_config={
                "Severity": st.column_config.ProgressColumn(
                    "Sev", format="%d", min_value=0, max_value=5,
                ),
                "Sentiment":  st.column_config.NumberColumn(format="%+.2f"),
                "Credibility": st.column_config.ProgressColumn(
                    "Cred.", format="%.2f", min_value=0.0, max_value=1.0,
                ),
            },
        )

    # ---------- Score breakdown ----------
    section("Score contribution waterfall")
    st.plotly_chart(charts.contributions_waterfall(score), use_container_width=True)
    st.caption(
        "Each row shows one piece of evidence and its push on the final score. "
        "Effective weight folds in source credibility, corroboration, and "
        "(when defense is on) burst + template-similarity penalties."
    )
