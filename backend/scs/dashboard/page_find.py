"""Find suppliers page - filter and search across the directory.

Lets a user browse the 80+ suppliers with multi-criteria filters and
hand-pick candidates for a procurement decision.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from scs.compliance.pipeline import run as run_comp
from scs.data import load_suppliers
from scs.evaluation.ground_truth import load_labels
from scs.models import SupplierCategory
from scs.risk.pipeline import run as run_risk
from scs.scoring.fusion import fuse

from scs.dashboard.components import section, kpi
from scs.dashboard.styling import PALETTE, score_color


@st.cache_data(show_spinner="Scoring all suppliers…")
def _score_directory(use_defense: bool) -> pd.DataFrame:
    """Run the full pipeline against every supplier and return a DataFrame
    with one row per supplier, ready for filtering."""
    rows = []
    for s in load_suppliers():
        comp = run_comp(s)
        risk = run_risk(s)
        from scs.profile import get_profile
        prof = get_profile(s.id)
        ipy = s.incorporated.year if s.incorporated else None
        scr = fuse(s.id, comp, risk, use_defense=use_defense,
                   profile=prof, incorporation_year=ipy)

        risk_events = sorted({sg.event_type.value for sg in risk.signals
                              if sg.event_type.value != "positive"})

        rows.append({
            "id":                 s.id,
            "Supplier":           s.name,
            "Legal name":         s.legal_name or "",
            "Country":            s.country,
            "Category":           s.category.value,
            "CIN":                s.cin or "",
            "Year":               s.incorporated.year if s.incorporated else None,
            "Score":              scr.score,
            "Grade":              scr.grade,
            "Belief safe":        scr.belief_safe,
            "Belief risky":       scr.belief_risky,
            "Uncertainty":        scr.uncertainty,
            "Compliance fails":   comp.fail_count,
            "Articles":           risk.article_count,
            "Max severity":       risk.max_severity,
            "Risk events":        ", ".join(risk_events) if risk_events else "—",
            "Illustrative":       s.is_illustrative,
            "Note":               s.note or "",
        })
    return pd.DataFrame(rows)


def render(use_defense: bool, threshold: float) -> None:
    st.title("🔍 Find suppliers")
    st.caption(
        "Filter the directory by country, category, score band, compliance "
        "status, and risk type. Use this to shortlist candidates before "
        "drilling into the detail page."
    )

    df = _score_directory(use_defense)

    # ---------- Filter row ----------
    st.markdown("### Filters")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        countries = sorted(df["Country"].unique().tolist())
        sel_countries = st.multiselect(
            "Country", options=countries, default=[],
            placeholder="Any country",
        )
    with col2:
        cats = sorted(df["Category"].unique().tolist())
        sel_cats = st.multiselect(
            "Category", options=cats, default=[],
            placeholder="Any category",
            format_func=lambda v: v.replace("_", " "),
        )
    with col3:
        sel_grades = st.multiselect(
            "Grade", options=["A", "B", "C", "D", "F"], default=[],
            placeholder="Any grade",
        )
    with col4:
        score_band = st.slider(
            "Score range", min_value=0, max_value=100,
            value=(0, 100), step=5,
        )

    col5, col6, col7, col8 = st.columns(4)
    with col5:
        compliance_filter = st.selectbox(
            "Compliance",
            options=["Any", "Clean only (0 fails)", "Has at least 1 fail"],
            index=0,
        )
    with col6:
        # Collect every distinct risk-event token across the directory
        all_events = set()
        for cell in df["Risk events"]:
            if cell == "—":
                continue
            for tok in cell.split(","):
                tok = tok.strip()
                if tok:
                    all_events.add(tok)
        sel_events = st.multiselect(
            "Risk events present",
            options=sorted(all_events), default=[],
            placeholder="Any risk profile",
        )
    with col7:
        include_illustrative = st.selectbox(
            "Source data",
            options=["All (real + illustrative)", "Real only", "Illustrative only"],
            index=0,
            help=(
                "Real entities have public-record analogues. Illustrative "
                "suppliers are SME-scale fictitious entities marked clearly "
                "so the dashboard can demonstrate score variation across the "
                "spectrum without misrepresenting any real firm."
            ),
        )
    with col8:
        text_query = st.text_input(
            "Search name or legal name", placeholder="e.g. Tata, Foxconn, IS 16333",
        )

    # ---------- Apply filters ----------
    filtered = df.copy()
    if sel_countries:
        filtered = filtered[filtered["Country"].isin(sel_countries)]
    if sel_cats:
        filtered = filtered[filtered["Category"].isin(sel_cats)]
    if sel_grades:
        filtered = filtered[filtered["Grade"].isin(sel_grades)]
    filtered = filtered[
        (filtered["Score"] >= score_band[0]) & (filtered["Score"] <= score_band[1])
    ]
    if compliance_filter == "Clean only (0 fails)":
        filtered = filtered[filtered["Compliance fails"] == 0]
    elif compliance_filter == "Has at least 1 fail":
        filtered = filtered[filtered["Compliance fails"] > 0]
    if sel_events:
        mask = filtered["Risk events"].apply(
            lambda cell: any(e in cell for e in sel_events) if cell != "—" else False
        )
        filtered = filtered[mask]
    if include_illustrative == "Real only":
        filtered = filtered[~filtered["Illustrative"]]
    elif include_illustrative == "Illustrative only":
        filtered = filtered[filtered["Illustrative"]]
    if text_query.strip():
        q = text_query.strip().lower()
        mask = (
            filtered["Supplier"].str.lower().str.contains(q, na=False)
            | filtered["Legal name"].str.lower().str.contains(q, na=False)
            | filtered["CIN"].str.lower().str.contains(q, na=False)
        )
        filtered = filtered[mask]

    # ---------- Result KPIs ----------
    section(f"Results — {len(filtered)} of {len(df)} suppliers")
    if filtered.empty:
        st.info("No suppliers match the current filter combination. Loosen one filter and try again.")
        return

    avg_score = filtered["Score"].mean()
    pct_clean = (filtered["Compliance fails"] == 0).mean() * 100
    median_articles = filtered["Articles"].median()

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: kpi("Matches", str(len(filtered)))
    with c2: kpi("Avg score", f"{avg_score:.1f}", color=score_color(avg_score))
    with c3:
        n_a = (filtered["Grade"] == "A").sum()
        kpi("Grade A", str(n_a), color=PALETTE["grade_a"])
    with c4:
        n_f = (filtered["Grade"] == "F").sum()
        kpi("Grade F", str(n_f), color=PALETTE["grade_f"])
    with c5:
        kpi("% compliance-clean", f"{pct_clean:.0f}%",
            color=PALETTE["ok"] if pct_clean > 70 else PALETTE["warn"])

    # ---------- Result table ----------
    sort_col = st.radio(
        "Sort by",
        options=["Score (high to low)", "Score (low to high)", "Supplier", "Country", "Grade"],
        horizontal=True, index=0,
    )
    sort_map = {
        "Score (high to low)": ("Score", False),
        "Score (low to high)": ("Score", True),
        "Supplier": ("Supplier", True),
        "Country": ("Country", True),
        "Grade": ("Grade", True),
    }
    col, asc = sort_map[sort_col]
    out = filtered.sort_values(col, ascending=asc).reset_index(drop=True)

    # Render category prettily
    out_view = out.copy()
    out_view["Category"] = out_view["Category"].str.replace("_", " ")

    # Decorate name with illustrative badge inline
    out_view["Supplier"] = out_view.apply(
        lambda r: f"{r['Supplier']}  ⓘ" if r["Illustrative"] else r["Supplier"],
        axis=1,
    )

    columns_to_show = [
        "Supplier", "Country", "Category", "Score", "Grade",
        "Compliance fails", "Articles", "Risk events",
    ]

    st.dataframe(
        out_view[columns_to_show],
        use_container_width=True, hide_index=True,
        column_config={
            "Score": st.column_config.ProgressColumn(
                "Score", format="%.1f", min_value=0, max_value=100,
            ),
            "Compliance fails": st.column_config.NumberColumn(
                "Fails", format="%d",
            ),
            "Articles": st.column_config.NumberColumn(format="%d"),
            "Supplier": st.column_config.TextColumn(
                help="Suffix ⓘ marks an illustrative SME (clearly fictitious; see Methodology page)."
            ),
        },
    )

    # ---------- Detail expander on selection-by-id ----------
    section("Drill into a result")
    pick = st.selectbox(
        "Select a supplier to see top contributions",
        options=["—"] + out["Supplier"].tolist(),
        index=0,
    )
    if pick and pick != "—":
        row = out[out["Supplier"] == pick].iloc[0]
        c1, c2, c3 = st.columns(3)
        with c1: kpi("Score", f"{row['Score']:.1f}", color=score_color(row["Score"]))
        with c2: kpi("Grade", row["Grade"], color=PALETTE["grade_a"] if row["Grade"]=="A" else PALETTE["grade_f"] if row["Grade"]=="F" else PALETTE["warn"])
        with c3: kpi("Articles", str(int(row["Articles"])))

        if row["Note"]:
            st.info(f"📝 {row['Note']}")

        st.caption(
            f"To see the full report — belief decomposition, risk topology, "
            f"news timeline, contribution waterfall — open **{row['Supplier'].rstrip(' ⓘ')}** "
            f"in the **Supplier detail** page."
        )

    # ---------- CSV export ----------
    csv_bytes = out.drop(columns=["id"]).to_csv(index=False).encode()
    st.download_button(
        "⬇️ Download filtered list as CSV",
        data=csv_bytes,
        file_name="supplier_shortlist.csv",
        mime="text/csv",
    )

    # ---------- Disclosure note ----------
    n_illus = int(filtered["Illustrative"].sum())
    if n_illus > 0:
        st.caption(
            f"📌 **Note.** {n_illus} of the {len(filtered)} matches are "
            f"illustrative SME-scale fictitious entities, marked with ⓘ. "
            f"They exist to demonstrate score variation across realistic "
            f"risk profiles without misrepresenting any real firm. Toggle "
            f"\"Real only\" above to exclude them."
        )
