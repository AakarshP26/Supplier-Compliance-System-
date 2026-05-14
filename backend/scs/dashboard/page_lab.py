"""Adversarial laboratory - the demo's headline page."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from scs.adversarial.attack import AttackConfig
from scs.adversarial.runner import run_attacked
from scs.compliance.pipeline import run as run_comp
from scs.data import load_suppliers
from scs.evaluation.ground_truth import load_labels
from scs.evaluation.metrics import (
    RISK_THRESHOLD, adversarial_metrics, classification_metrics,
)
from scs.risk.pipeline import run as run_risk
from scs.scoring.fusion import fuse

from scs.dashboard import charts
from scs.dashboard.components import section, kpi, status_pill, grade_pill
from scs.dashboard.styling import PALETTE, score_color


VECTORS = ["press_release", "anon_blog", "self_published"]


@st.cache_data(show_spinner=False)
def _attack_curve_data(supplier_id: str, vector: str, max_budget: int) -> list[dict]:
    """Pre-computes the score-vs-budget curve for one supplier and vector."""
    suppliers = {s.id: s for s in load_suppliers()}
    s = suppliers[supplier_id]
    comp = run_comp(s)

    rows = []
    for B in range(0, max_budget + 1):
        if B == 0:
            r = run_risk(s)
        else:
            r, _ = run_attacked(s, AttackConfig(budget=B, vector=vector))
        no_def = fuse(s.id, comp, r, use_defense=False).score
        with_def = fuse(s.id, comp, r, use_defense=True).score
        rows.append({"budget": B, "no_defense": no_def, "with_defense": with_def})
    return rows


@st.cache_data(show_spinner=False)
def _attack_heatmap_data(supplier_id: str, budgets: list[int], vectors: list[str]) -> list[list[float]]:
    suppliers = {s.id: s for s in load_suppliers()}
    s = suppliers[supplier_id]
    comp = run_comp(s)
    clean = fuse(s.id, comp, run_risk(s), use_defense=False).score
    matrix = []
    for vec in vectors:
        row = []
        for B in budgets:
            if B == 0:
                row.append(0.0)
                continue
            r, _ = run_attacked(s, AttackConfig(budget=B, vector=vec))
            attacked = fuse(s.id, comp, r, use_defense=False).score
            row.append(attacked - clean)
        matrix.append(row)
    return matrix


@st.cache_data(show_spinner=False)
def _portfolio_under_attack(budget: int, vector: str) -> dict:
    """Portfolio-wide accuracy under attack vs defense."""
    labels = load_labels()
    suppliers = list(load_suppliers())
    clean_scores = {}
    attacked_scores = {}
    defended_scores = {}
    for s in suppliers:
        comp = run_comp(s)
        risk_clean = run_risk(s)
        clean_scores[s.id] = fuse(s.id, comp, risk_clean, use_defense=False)
        if budget == 0:
            attacked_scores[s.id] = clean_scores[s.id]
            defended_scores[s.id] = fuse(s.id, comp, risk_clean, use_defense=True)
        else:
            risk_attacked, _ = run_attacked(s, AttackConfig(budget=budget, vector=vector))
            attacked_scores[s.id] = fuse(s.id, comp, risk_attacked, use_defense=False)
            defended_scores[s.id] = fuse(s.id, comp, risk_attacked, use_defense=True)

    return {
        "clean": classification_metrics(clean_scores, labels),
        "attacked": classification_metrics(attacked_scores, labels),
        "defended": classification_metrics(defended_scores, labels),
        "vs_attacked": adversarial_metrics(clean_scores, attacked_scores),
        "vs_defended": adversarial_metrics(clean_scores, defended_scores),
        "raw": {
            sid: {
                "clean": clean_scores[sid].score,
                "attacked": attacked_scores[sid].score,
                "defended": defended_scores[sid].score,
                "gt": labels.get(sid),
            }
            for sid in clean_scores
        },
    }


def render(use_defense: bool, threshold: float) -> None:
    st.title("🛡️ Adversarial laboratory")
    st.caption(
        "Inject synthetic positive articles and watch the supplier's score "
        "climb. The trust-calibrated defense catches coordinated drops; "
        "small artisanal attacks slip through. This is the paper's central "
        "experiment, made interactive."
    )

    suppliers = list(load_suppliers())
    by_name = {s.name: s for s in suppliers}

    # ---------- Controls ----------
    col_a, col_b, col_c = st.columns([2, 1, 1])
    with col_a:
        # Default to the World-Bank-debarred entity for impact
        default_idx = next(
            (i for i, s in enumerate(suppliers) if s.id == "shenzhen-shadow-corp"),
            0,
        )
        name = st.selectbox(
            "Supplier under attack",
            options=[s.name for s in suppliers],
            index=default_idx,
            key="adv_supplier",
        )
    with col_b:
        vector = st.selectbox(
            "Attack vector",
            options=VECTORS,
            index=0,
            help=(
                "Which low-credibility channel does the adversary plant on?\n\n"
                "• press_release: PR Newswire / Business Wire (cred=0.30)\n"
                "• anon_blog: Medium / blogspot (cred=0.20)\n"
                "• self_published: brand-new domain (cred=0.40 default)"
            ),
        )
    with col_c:
        max_budget = st.slider("Max budget B", min_value=2, max_value=20, value=15)

    supplier = by_name[name]

    # ---------- Score-vs-budget chart ----------
    section("Score under increasing attack budget")
    curve = _attack_curve_data(supplier.id, vector, max_budget)
    st.plotly_chart(charts.attack_curve(curve), use_container_width=True)

    cv = pd.DataFrame(curve)
    final = cv.iloc[-1]
    clean_row = cv.iloc[0]
    lift_no_def = final["no_defense"] - clean_row["no_defense"]
    lift_def = final["with_defense"] - clean_row["with_defense"]
    saved = lift_no_def - lift_def

    c1, c2, c3, c4 = st.columns(4)
    with c1: kpi("Clean score", f"{clean_row['no_defense']:.1f}",
                  color=score_color(clean_row["no_defense"]))
    with c2: kpi(f"Attacked (B={int(final['budget'])})", f"{final['no_defense']:.1f}",
                  delta=f"+{lift_no_def:.1f}", color=PALETTE["danger"])
    with c3: kpi("Defended", f"{final['with_defense']:.1f}",
                  delta=f"+{lift_def:.1f}", color=PALETTE["ok"])
    with c4: kpi("Lift neutralised", f"{saved:.1f} pts",
                  delta="by trust calibration", color=PALETTE["accent"])

    # ---------- Attack heatmap ----------
    section("Attack lift heatmap (no defense)")
    budgets = [0, 1, 2, 3, 5, 7, 10, 15, 20]
    matrix = _attack_heatmap_data(supplier.id, budgets, VECTORS)
    st.plotly_chart(charts.attack_heatmap(matrix, budgets, VECTORS), use_container_width=True)
    st.caption(
        "Rows = attack vectors. Cells = score lift over the clean baseline. "
        "Darker red = larger lift = more dangerous. "
        "Note that the press-release vector (highest credibility prior in the "
        "low-tier) consistently produces the largest lift."
    )

    # ---------- Portfolio-wide impact ----------
    section("Portfolio-wide impact at this attack configuration")
    fixed_budget = st.slider(
        "Apply this attack to every supplier with budget B = ",
        min_value=0, max_value=20, value=10, key="port_budget",
    )
    p = _portfolio_under_attack(fixed_budget, vector)

    c1, c2, c3 = st.columns(3)
    with c1: kpi("Clean F1", f"{p['clean'].f1:.2f}", color=PALETTE["accent"])
    with c2:
        col = PALETTE["danger"] if p["attacked"].f1 < 0.5 else PALETTE["warn"]
        kpi("Attacked F1", f"{p['attacked'].f1:.2f}",
            delta=f"flip rate {p['vs_attacked'].flip_rate:.0%}", color=col)
    with c3:
        kpi("Defended F1", f"{p['defended'].f1:.2f}",
            delta=f"flip rate {p['vs_defended'].flip_rate:.0%}", color=PALETTE["ok"])

    # ---------- Per-supplier flip table ----------
    rows = []
    for sid, vals in p["raw"].items():
        sup = next(s for s in suppliers if s.id == sid)
        rows.append({
            "Supplier": sup.name,
            "Country": sup.country,
            "Ground truth": "RISKY" if vals["gt"] else ("SAFE" if vals["gt"] is False else "—"),
            "Clean": vals["clean"],
            "Attacked": vals["attacked"],
            "Defended": vals["defended"],
            "Δ no defense": vals["attacked"] - vals["clean"],
            "Δ with defense": vals["defended"] - vals["clean"],
            "Flipped (no def)": (vals["clean"] < threshold) != (vals["attacked"] < threshold),
            "Flipped (defended)": (vals["clean"] < threshold) != (vals["defended"] < threshold),
        })
    df = pd.DataFrame(rows).sort_values("Δ no defense", ascending=False)
    st.dataframe(
        df,
        use_container_width=True, hide_index=True,
        column_config={
            "Clean":    st.column_config.ProgressColumn("Clean",   format="%.1f", min_value=0, max_value=100),
            "Attacked": st.column_config.ProgressColumn("Attacked", format="%.1f", min_value=0, max_value=100),
            "Defended": st.column_config.ProgressColumn("Defended", format="%.1f", min_value=0, max_value=100),
            "Δ no defense":   st.column_config.NumberColumn(format="%+.1f"),
            "Δ with defense": st.column_config.NumberColumn(format="%+.1f"),
            "Flipped (no def)":   st.column_config.CheckboxColumn(),
            "Flipped (defended)": st.column_config.CheckboxColumn(),
        },
    )
