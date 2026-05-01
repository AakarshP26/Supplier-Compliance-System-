"""Plotly chart factories.

Every chart used in the dashboard is built here so styling is consistent
and the page modules stay declarative.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Iterable

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from scs.dashboard.styling import (
    PALETTE, TIER_COLORS, grade_color, plotly_layout, score_color, status_color,
)
from scs.models import (
    ComplianceReport, FeatureContribution, RiskProfile, RiskSignal, SupplierScore,
)


# ---------------------------------------------------------------------------
# Single-supplier charts
# ---------------------------------------------------------------------------


def belief_donut(score: SupplierScore) -> go.Figure:
    """Dempster-Shafer belief masses as a donut: safe / risky / Θ."""
    fig = go.Figure(
        data=[
            go.Pie(
                labels=["Belief safe", "Belief risky", "Uncertainty (Θ)"],
                values=[score.belief_safe, score.belief_risky, score.uncertainty],
                hole=0.62,
                sort=False,
                marker=dict(
                    colors=[PALETTE["ok"], PALETTE["danger"], PALETTE["unknown"]],
                    line=dict(color="rgba(255,255,255,0.05)", width=2),
                ),
                textinfo="label+percent",
                textfont=dict(size=11),
                hovertemplate="<b>%{label}</b><br>m=%{value:.3f}<extra></extra>",
            )
        ]
    )
    fig.update_layout(
        **plotly_layout(height=280),
        annotations=[
            dict(
                text=f"<b>{score.score:.0f}</b><br><span style='font-size:11px;color:#64748B'>score</span>",
                x=0.5, y=0.5, showarrow=False, font=dict(size=22, color=score_color(score.score)),
            )
        ],
        showlegend=False,
    )
    return fig


def risk_radar(risk: RiskProfile) -> go.Figure:
    """Multi-dimensional risk profile across event categories."""
    # Aggregate severity per event type, capped at 5
    by_type: dict[str, float] = {}
    for s in risk.signals:
        if s.event_type.value == "positive":
            continue
        # Multiply severity by credibility — gives "credible severity"
        by_type[s.event_type.value] = max(
            by_type.get(s.event_type.value, 0.0),
            s.severity * (s.credibility * (1.0 if s.is_corroborated else 0.6)),
        )

    canonical = [
        "sanctions", "litigation", "labor_dispute", "environmental",
        "financial_distress", "cybersecurity", "quality_recall",
        "counterfeit", "leadership_change",
    ]
    values = [by_type.get(k, 0.0) for k in canonical]
    labels = [k.replace("_", " ") for k in canonical]
    # Close the loop
    values.append(values[0])
    labels.append(labels[0])

    fig = go.Figure(
        go.Scatterpolar(
            r=values,
            theta=labels,
            fill="toself",
            line=dict(color=PALETTE["accent"], width=2),
            fillcolor="rgba(99,102,241,0.18)",
            hovertemplate="<b>%{theta}</b><br>severity=%{r:.2f}<extra></extra>",
            name="Credible severity",
        )
    )
    fig.update_layout(
        **plotly_layout(height=320),
        polar=dict(
            radialaxis=dict(range=[0, 5], showline=False, ticks="", tickfont=dict(size=10)),
            angularaxis=dict(tickfont=dict(size=10)),
            bgcolor="rgba(0,0,0,0)",
        ),
        showlegend=False,
    )
    return fig


def contributions_waterfall(score: SupplierScore, top_n: int = 12) -> go.Figure:
    """Top-contributing features as a horizontal bar chart, signed."""
    contribs = score.contributions[:top_n]
    df = pd.DataFrame(
        [
            {
                "feature": c.feature.replace("compliance::", "✔ ").replace("news::", "📰 "),
                "contribution": c.contribution,
                "weight": c.weight,
            }
            for c in contribs
        ]
    ).sort_values("contribution")

    colors = [PALETTE["ok"] if v > 0 else PALETTE["danger"] for v in df["contribution"]]
    fig = go.Figure(
        go.Bar(
            x=df["contribution"], y=df["feature"], orientation="h",
            marker=dict(color=colors),
            customdata=df[["weight"]].values,
            hovertemplate=(
                "<b>%{y}</b><br>"
                "contribution=%{x:+.1f}<br>"
                "effective weight=%{customdata[0]:.2f}<extra></extra>"
            ),
        )
    )
    fig.update_layout(
        **plotly_layout(height=max(260, 26 * len(df))),
        xaxis=dict(title="Contribution to score (points)", zeroline=True, zerolinecolor="rgba(120,120,120,0.4)"),
        yaxis=dict(title=None),
    )
    return fig


def news_timeline(signals: Iterable[RiskSignal]) -> go.Figure | None:
    """Vertical-axis: severity. X-axis: time. Bubble = one signal."""
    signals = [s for s in signals if s.provenance.published_at is not None]
    if not signals:
        return None

    df = pd.DataFrame([
        {
            "time": s.provenance.published_at,
            "severity": s.severity if s.event_type.value != "positive" else 0,
            "event": s.event_type.value,
            "summary": s.summary[:90] + ("…" if len(s.summary) > 90 else ""),
            "source": s.provenance.source_name,
            "credibility": s.credibility,
            "corroborated": "✓" if s.is_corroborated else "—",
            "color": PALETTE["ok"] if s.event_type.value == "positive" else PALETTE["danger"],
            "size": 12 + 2 * s.severity,
        }
        for s in signals
    ])

    fig = go.Figure(
        go.Scatter(
            x=df["time"], y=df["severity"],
            mode="markers",
            marker=dict(size=df["size"], color=df["color"], opacity=0.85,
                        line=dict(width=1, color="rgba(255,255,255,0.6)")),
            customdata=df[["event", "summary", "source", "credibility", "corroborated"]].values,
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "%{customdata[1]}<br>"
                "<i>%{customdata[2]}</i> · cred=%{customdata[3]:.2f} · corrob=%{customdata[4]}<br>"
                "severity=%{y}<extra></extra>"
            ),
        )
    )
    fig.update_layout(
        **plotly_layout(height=240),
        xaxis=dict(title=None),
        yaxis=dict(title="Severity", range=[-0.5, 5.5], dtick=1),
    )
    return fig


def credibility_breakdown(report: ComplianceReport, risk: RiskProfile) -> go.Figure:
    """Stacked horizontal bar: weighted evidence mass per source tier."""
    rows = []
    for c in report.checks:
        rows.append({"source": c.source, "credibility": c.provenance.credibility, "kind": "Compliance"})
    for s in risk.signals:
        rows.append({
            "source": s.provenance.source_name,
            "credibility": s.credibility,
            "kind": "News",
        })
    if not rows:
        return go.Figure()
    df = pd.DataFrame(rows).sort_values("credibility", ascending=True)

    fig = go.Figure(
        go.Bar(
            x=df["credibility"], y=df["source"], orientation="h",
            marker=dict(color=df["credibility"], colorscale="Viridis", cmin=0, cmax=1,
                        showscale=False),
            customdata=df[["kind"]].values,
            hovertemplate="<b>%{y}</b><br>%{customdata[0]} · cred=%{x:.2f}<extra></extra>",
        )
    )
    fig.update_layout(
        **plotly_layout(height=max(220, 22 * len(df))),
        xaxis=dict(title="Source credibility", range=[0, 1], dtick=0.2),
        yaxis=dict(title=None),
    )
    return fig


# ---------------------------------------------------------------------------
# Portfolio / overview charts
# ---------------------------------------------------------------------------


def score_distribution(scores: dict[str, SupplierScore]) -> go.Figure:
    """Histogram with grade-band shading."""
    values = [s.score for s in scores.values()]
    fig = go.Figure(
        go.Histogram(
            x=values, xbins=dict(start=0, end=100, size=5),
            marker=dict(color=PALETTE["accent"], line=dict(width=1, color="rgba(255,255,255,0.2)")),
            hovertemplate="%{x}: %{y} suppliers<extra></extra>",
        )
    )
    # Grade band shading
    bands = [
        (0, 35, PALETTE["grade_f"]),
        (35, 50, PALETTE["grade_d"]),
        (50, 65, PALETTE["grade_c"]),
        (65, 80, PALETTE["grade_b"]),
        (80, 100, PALETTE["grade_a"]),
    ]
    shapes = []
    for x0, x1, c in bands:
        shapes.append(dict(type="rect", xref="x", yref="paper", x0=x0, x1=x1,
                           y0=0, y1=1, fillcolor=c, opacity=0.06, layer="below", line_width=0))
    fig.update_layout(
        **plotly_layout(height=260),
        xaxis=dict(title="Score", range=[0, 100], dtick=10),
        yaxis=dict(title="Suppliers"),
        shapes=shapes,
        bargap=0.05,
    )
    return fig


def category_box(scores: dict[str, SupplierScore], suppliers_by_id: dict) -> go.Figure:
    """Box plot: score distribution per supplier category."""
    rows = [
        {
            "category": suppliers_by_id[sid].category.value.replace("_", " "),
            "score": s.score,
            "name": suppliers_by_id[sid].name,
        }
        for sid, s in scores.items()
    ]
    df = pd.DataFrame(rows)
    fig = px.box(df, x="category", y="score", points="all", hover_data=["name"],
                 color_discrete_sequence=[PALETTE["accent_2"]])
    fig.update_layout(
        **plotly_layout(height=280),
        xaxis=dict(title=None, tickangle=-25),
        yaxis=dict(title="Score", range=[0, 100]),
    )
    return fig


def country_sunburst(scores: dict[str, SupplierScore], suppliers_by_id: dict) -> go.Figure:
    """Hierarchical: country -> grade -> supplier."""
    rows = [
        {
            "country": suppliers_by_id[sid].country,
            "grade": s.grade,
            "supplier": suppliers_by_id[sid].name,
            "score": s.score,
        }
        for sid, s in scores.items()
    ]
    df = pd.DataFrame(rows)
    fig = px.sunburst(
        df, path=["country", "grade", "supplier"], values=None,
        color="score", color_continuous_scale=[
            (0.0, PALETTE["grade_f"]),
            (0.4, PALETTE["grade_d"]),
            (0.55, PALETTE["grade_c"]),
            (0.75, PALETTE["grade_b"]),
            (1.0, PALETTE["grade_a"]),
        ],
        range_color=[0, 100],
    )
    fig.update_layout(**plotly_layout(height=380))
    fig.update_traces(hovertemplate="<b>%{label}</b><br>score=%{color:.1f}<extra></extra>")
    return fig


def compliance_heatmap(
    reports: dict[str, ComplianceReport],
    suppliers_by_id: dict,
) -> go.Figure:
    """Suppliers × compliance source grid; cell color = pass/fail/unknown."""
    sources = ["OFAC SDN", "World Bank Debarred", "BIS CRS"]
    z = []
    text = []
    y_labels = []

    # Sort by total fails desc so the dirtiest rows are at top
    items = sorted(
        reports.items(),
        key=lambda kv: -kv[1].fail_count,
    )
    for sid, rep in items:
        row_z = []
        row_t = []
        by_source = {c.source: c for c in rep.checks}
        for src in sources:
            c = by_source.get(src)
            if c is None or c.status == "unknown":
                row_z.append(0)
                row_t.append("?")
            elif c.status == "pass":
                row_z.append(1)
                row_t.append("✓")
            else:
                row_z.append(-1)
                row_t.append("✗")
        z.append(row_z)
        text.append(row_t)
        y_labels.append(suppliers_by_id[sid].name)

    fig = go.Figure(
        go.Heatmap(
            z=z, x=sources, y=y_labels, text=text, texttemplate="%{text}",
            textfont=dict(size=14, color="white"),
            zmin=-1, zmax=1,
            colorscale=[
                [0.0, PALETTE["danger"]],
                [0.5, PALETTE["unknown"]],
                [1.0, PALETTE["ok"]],
            ],
            showscale=False,
            hovertemplate="<b>%{y}</b><br>%{x}<extra></extra>",
        )
    )
    fig.update_layout(
        **plotly_layout(height=max(320, 22 * len(y_labels))),
        xaxis=dict(side="top"),
        yaxis=dict(autorange="reversed"),
    )
    return fig


def signal_event_pie(scores_dict_signals: dict[str, RiskProfile]) -> go.Figure:
    """Donut: distribution of risk-event types across the whole portfolio."""
    counts: Counter[str] = Counter()
    for prof in scores_dict_signals.values():
        for s in prof.signals:
            counts[s.event_type.value] += 1
    if not counts:
        return go.Figure()
    labels = list(counts.keys())
    values = [counts[k] for k in labels]
    fig = go.Figure(go.Pie(
        labels=labels, values=values, hole=0.55,
        marker=dict(colors=px.colors.qualitative.Set3),
        textinfo="label+percent",
        textfont=dict(size=10),
    ))
    fig.update_layout(**plotly_layout(height=300), showlegend=False)
    return fig


# ---------------------------------------------------------------------------
# Compare-multiple charts
# ---------------------------------------------------------------------------


def compare_radar(scores: dict[str, SupplierScore], risk_profiles: dict[str, RiskProfile]) -> go.Figure:
    """Overlay radar of multiple suppliers across same risk dimensions."""
    canonical = [
        "sanctions", "litigation", "labor_dispute", "environmental",
        "financial_distress", "cybersecurity", "quality_recall",
        "counterfeit", "leadership_change",
    ]
    labels = [k.replace("_", " ") for k in canonical]
    fig = go.Figure()
    palette = [PALETTE["accent"], PALETTE["accent_2"], PALETTE["accent_3"],
               PALETTE["warn"], PALETTE["ok"]]

    for i, (sid, prof) in enumerate(risk_profiles.items()):
        by_type: dict[str, float] = {}
        for sg in prof.signals:
            if sg.event_type.value == "positive":
                continue
            by_type[sg.event_type.value] = max(
                by_type.get(sg.event_type.value, 0.0),
                sg.severity * sg.credibility * (1.0 if sg.is_corroborated else 0.6),
            )
        values = [by_type.get(k, 0.0) for k in canonical]
        values.append(values[0])
        c = palette[i % len(palette)]
        rgba = c.lstrip("#")
        rgb_tuple = tuple(int(rgba[i:i+2], 16) for i in (0, 2, 4))
        fillcolor = f"rgba({rgb_tuple[0]},{rgb_tuple[1]},{rgb_tuple[2]},0.15)"
        fig.add_trace(go.Scatterpolar(
            r=values, theta=labels + [labels[0]], fill="toself",
            line=dict(color=c, width=2), fillcolor=fillcolor,
            name=scores[sid].supplier_id,
            hovertemplate="<b>%{theta}</b><br>severity=%{r:.2f}<extra></extra>",
        ))
    fig.update_layout(
        **plotly_layout(height=420),
        polar=dict(radialaxis=dict(range=[0, 5], showline=False, tickfont=dict(size=10)),
                   angularaxis=dict(tickfont=dict(size=10)),
                   bgcolor="rgba(0,0,0,0)"),
    )
    return fig


def compare_parallel_coords(
    rows: list[dict],
) -> go.Figure:
    """Parallel coordinates plot — one line per supplier across many metrics."""
    if not rows:
        return go.Figure()
    df = pd.DataFrame(rows)
    fig = go.Figure(go.Parcoords(
        line=dict(
            color=df["score"], colorscale=[
                (0.0, PALETTE["grade_f"]),
                (0.4, PALETTE["grade_d"]),
                (0.55, PALETTE["grade_c"]),
                (0.75, PALETTE["grade_b"]),
                (1.0, PALETTE["grade_a"]),
            ],
            cmin=0, cmax=100,
            showscale=True, colorbar=dict(title="Score"),
        ),
        dimensions=[
            dict(label="Score",        values=df["score"], range=[0, 100]),
            dict(label="Belief safe",  values=df["belief_safe"], range=[0, 1]),
            dict(label="Belief risky", values=df["belief_risky"], range=[0, 1]),
            dict(label="Uncertainty",  values=df["uncertainty"], range=[0, 1]),
            dict(label="Articles",     values=df["articles"]),
            dict(label="Max severity", values=df["max_severity"], range=[0, 5]),
            dict(label="Compliance fails", values=df["fail_count"]),
        ],
    ))
    fig.update_layout(**plotly_layout(height=440))
    return fig


def compare_bars(rows: list[dict]) -> go.Figure:
    """Side-by-side score bars."""
    df = pd.DataFrame(rows).sort_values("score")
    colors = [score_color(v) for v in df["score"]]
    fig = go.Figure(go.Bar(
        x=df["score"], y=df["name"], orientation="h",
        marker=dict(color=colors),
        text=[f"{v:.1f}" for v in df["score"]],
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>score=%{x:.1f}<extra></extra>",
    ))
    fig.update_layout(
        **plotly_layout(height=max(220, 28 * len(df))),
        xaxis=dict(range=[0, 110], title="Score"),
        yaxis=dict(title=None),
    )
    return fig


# ---------------------------------------------------------------------------
# Adversarial-lab charts
# ---------------------------------------------------------------------------


def attack_curve(rows: list[dict]) -> go.Figure:
    """Line chart: score vs attack budget, no-defense vs defended."""
    df = pd.DataFrame(rows)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["budget"], y=df["no_defense"], mode="lines+markers", name="No defense",
        line=dict(color=PALETTE["danger"], width=3), marker=dict(size=7),
    ))
    fig.add_trace(go.Scatter(
        x=df["budget"], y=df["with_defense"], mode="lines+markers", name="Trust-calibrated defense",
        line=dict(color=PALETTE["ok"], width=3), marker=dict(size=7),
    ))
    # Threshold line
    fig.add_hline(y=50, line_dash="dash", line_color="rgba(120,120,120,0.6)",
                  annotation_text="risky / safe threshold", annotation_position="top right")
    fig.update_layout(
        **plotly_layout(height=320),
        xaxis=dict(title="Attack budget B (synthetic articles)"),
        yaxis=dict(title="Score", range=[0, 100]),
    )
    return fig


def attack_heatmap(matrix: list[list[float]], budgets: list[int], vectors: list[str]) -> go.Figure:
    """Heatmap of score lift across (vector × budget)."""
    fig = go.Figure(go.Heatmap(
        z=matrix, x=budgets, y=vectors,
        colorscale="RdBu_r", zmid=0,
        colorbar=dict(title="Δ score"),
        hovertemplate="vector=%{y}<br>B=%{x}<br>Δ=%{z:.1f}<extra></extra>",
    ))
    fig.update_layout(
        **plotly_layout(height=180 + 40 * len(vectors)),
        xaxis=dict(title="Attack budget B"),
        yaxis=dict(title=None),
    )
    return fig


def credibility_pyramid() -> go.Figure:
    """Static-ish chart of the credibility tier hierarchy used by fusion."""
    tiers = [
        ("government / authoritative", 0.95, "OFAC, World Bank, BIS, SEC, MeitY"),
        ("tier-1 news", 0.80, "Reuters, FT, The Hindu, Bloomberg, BBC"),
        ("trade press", 0.70, "EE Times, Electronics Weekly, Evertiq, IEEE Spectrum"),
        ("general news", 0.55, "NDTV, Moneycontrol, India Times"),
        ("press release / self-published", 0.30, "PR Newswire, Business Wire, Globe Newswire"),
        ("low-credibility / anonymous", 0.20, "Medium, blogspot, X, LinkedIn posts"),
    ]
    df = pd.DataFrame(tiers, columns=["tier", "credibility", "examples"])
    fig = go.Figure(go.Bar(
        x=df["credibility"], y=df["tier"], orientation="h",
        marker=dict(color=[TIER_COLORS[t] for t in df["tier"]]),
        text=[f"{v:.2f}" for v in df["credibility"]],
        textposition="outside",
        customdata=df[["examples"]].values,
        hovertemplate="<b>%{y}</b><br>prior=%{x:.2f}<br><i>%{customdata[0]}</i><extra></extra>",
    ))
    fig.update_layout(
        **plotly_layout(height=300),
        xaxis=dict(range=[0, 1.1], title="Credibility prior"),
        yaxis=dict(title=None, autorange="reversed"),
    )
    return fig
