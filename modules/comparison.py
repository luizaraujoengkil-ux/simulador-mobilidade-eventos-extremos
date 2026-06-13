"""
comparison.py
=============
Tela "Comparação antes/depois": tabela O-D, gráficos e cards comparativos.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd
import streamlit as st

from . import maps, ui_theme, utils, validation
from .utils import INF, PALETTE

# Plotly é opcional — protegido por try/except
try:
    import plotly.express as px
    import plotly.graph_objects as go
    PLOTLY_OK = True
except Exception:  # pragma: no cover
    PLOTLY_OK = False

STATUS_COLOR = {
    "normal": PALETTE["accent"],
    "afetado": PALETTE["attention"],
    "severamente afetado": PALETTE["amber"],
    "desconectado": PALETTE["critical"],
    "sem rota na base": PALETTE["neutral"],
}


def comparison_dataframe(comparison: dict, points_by_id: dict) -> pd.DataFrame:
    rows = []
    for (o, d), c in comparison.items():
        rows.append({
            "origem": points_by_id.get(o, {}).get("name", o),
            "destino": points_by_id.get(d, {}).get("name", d),
            "tempo_base_min": c["base_time"] if utils.is_finite_number(c["base_time"]) else None,
            "tempo_impactado_min": c["imp_time"] if utils.is_finite_number(c["imp_time"]) else None,
            "delta_min": c["delta_min"] if utils.is_finite_number(c["delta_min"]) else None,
            "aumento_pct": c["pct"] if utils.is_finite_number(c["pct"]) else None,
            "status": c["status"],
            "rota_disponivel": "sim" if c["connected_imp"] else "não",
        })
    return pd.DataFrame(rows)


def _display_table(df: pd.DataFrame) -> pd.DataFrame:
    show = df.copy()
    show["tempo_base"] = show["tempo_base_min"].map(lambda v: utils.fmt_minutes(v) if v is not None else "—")
    show["tempo_impactado"] = show.apply(
        lambda r: "sem rota" if r["rota_disponivel"] == "não" else utils.fmt_minutes(r["tempo_impactado_min"]),
        axis=1)
    show["diferença"] = show["delta_min"].map(
        lambda v: utils.fmt_minutes(v) if v is not None else "—")
    show["aumento"] = show["aumento_pct"].map(
        lambda v: utils.fmt_pct(v) if v is not None else ("∞" if False else "—"))
    return show[["origem", "destino", "tempo_base", "tempo_impactado",
                 "diferença", "aumento", "status", "rota_disponivel"]]


def render() -> None:
    ui_theme.page_title("Comparação antes/depois", kicker="Etapa 8 · Resultados")

    if not validation.guard("comparacao"):
        return

    results = st.session_state["impact_results"]
    comparison = results["comparison"]
    ind = results["indicators"]
    points_by_id = {p["point_id"]: p for p in st.session_state["points"]}

    # Cards
    ui_theme.render_metric_cards([
        ("Tempo médio base", utils.fmt_minutes(ind["mean_time_before"]), PALETTE["accent"]),
        ("Tempo médio impactado", utils.fmt_minutes(ind["mean_time_after"]), PALETTE["attention"]),
        ("Aumento médio", utils.fmt_pct(ind["mean_pct"]), PALETTE["amber"]),
        ("Pares desconectados", utils.fmt_int(ind["pairs_disconnected"]),
         PALETTE["critical"] if ind["pairs_disconnected"] else PALETTE["neutral"]),
    ], columns=4)

    df = comparison_dataframe(comparison, points_by_id)

    tab_tab, tab_chart, tab_map = st.tabs(["📋 Tabela O-D", "📊 Gráficos", "🗺️ Mapa"])

    with tab_tab:
        st.dataframe(_display_table(df), use_container_width=True, hide_index=True,
                     height=420)
        st.download_button(
            "⬇️ Exportar tabela O-D (CSV)",
            data=df.to_csv(index=False).encode("utf-8-sig"),
            file_name="comparacao_od.csv", mime="text/csv")

    with tab_chart:
        _render_charts(df, ind)

    with tab_map:
        maps.render_comparison_map()


def _render_charts(df: pd.DataFrame, ind: dict) -> None:
    if not PLOTLY_OK:
        validation.msg_info(
            "Plotly não está instalado. Instale com `pip install plotly` para "
            "ver os gráficos. A tabela e os indicadores permanecem disponíveis."
        )
        _render_charts_fallback(df)
        return

    valid = df.dropna(subset=["tempo_base_min"]).copy()

    # 1. Tempo médio antes/depois
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Tempo médio antes/depois**")
        bar = go.Figure(data=[go.Bar(
            x=["Base", "Impactado"],
            y=[ind["mean_time_before"] or 0, ind["mean_time_after"] or 0],
            marker_color=[PALETTE["accent"], PALETTE["attention"]],
        )])
        bar.update_layout(yaxis_title="minutos", height=320, margin=dict(t=20))
        st.plotly_chart(bar, use_container_width=True)

    # 2. Distribuição dos aumentos (%)
    with c2:
        st.markdown("**Distribuição dos aumentos (%)**")
        pct_vals = valid["aumento_pct"].dropna()
        if len(pct_vals):
            hist = px.histogram(pct_vals, nbins=20,
                                color_discrete_sequence=[PALETTE["amber"]])
            hist.update_layout(showlegend=False, height=320, margin=dict(t=20),
                               xaxis_title="aumento (%)", yaxis_title="pares")
            st.plotly_chart(hist, use_container_width=True)
        else:
            validation.msg_info("Sem aumentos finitos para histograma.")

    # 3. Ranking dos maiores aumentos
    st.markdown("**Ranking dos maiores aumentos de tempo**")
    rank = valid.dropna(subset=["delta_min"]).copy()
    rank["par"] = rank["origem"] + " → " + rank["destino"]
    rank = rank.sort_values("delta_min", ascending=False).head(15)
    if len(rank):
        fig = px.bar(rank, x="delta_min", y="par", orientation="h",
                     color="status", color_discrete_map=STATUS_COLOR)
        fig.update_layout(height=420, margin=dict(t=20),
                          xaxis_title="aumento (min)", yaxis_title="")
        fig.update_yaxes(autorange="reversed")
        st.plotly_chart(fig, use_container_width=True)
    else:
        validation.msg_info("Sem pares com aumento finito para ranquear.")

    # 4. Pares por classe de impacto
    st.markdown("**Pares por classe de impacto**")
    counts = df["status"].value_counts().reset_index()
    counts.columns = ["status", "pares"]
    pie = px.bar(counts, x="status", y="pares", color="status",
                 color_discrete_map=STATUS_COLOR)
    pie.update_layout(showlegend=False, height=320, margin=dict(t=20))
    st.plotly_chart(pie, use_container_width=True)


def _render_charts_fallback(df: pd.DataFrame) -> None:
    counts = df["status"].value_counts()
    st.bar_chart(counts)
