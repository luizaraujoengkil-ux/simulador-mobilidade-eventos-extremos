"""
social_cost.py
==============
Tela "Custo social preliminar": estimativa exploratória do custo do atraso.

Fórmulas:
    pessoas_afetadas = fluxo_afetado * ocupacao_media
    horas_perdidas   = pessoas_afetadas * atraso_min / 60
    custo_evento     = horas_perdidas * valor_hora
    custo_anual      = custo_evento * frequencia_anual

Quando não há fluxo, permite usar população/peso como aproximação (com aviso).
"""

from __future__ import annotations

import streamlit as st

from . import ui_theme, utils, validation
from .utils import PALETTE


def render() -> None:
    ui_theme.page_title("Custo social preliminar", kicker="Módulo · Estimativa exploratória")

    validation.msg_limitation(
        "O custo social é estimativo e exploratório, não substitui estudo "
        "econômico, EVTEA ou análise oficial."
    )

    impact = st.session_state.get("impact_results")
    suggested_delay = 0.0
    suggested_people = 0
    if impact:
        ind = impact["indicators"]
        if utils.is_finite_number(ind.get("mean_delta_min")):
            suggested_delay = float(ind["mean_delta_min"])
        suggested_people = int(ind.get("population_affected", 0) or 0)
    else:
        validation.msg_info(
            "Sem simulação de impacto carregada — o atraso médio não foi "
            "pré-preenchido. Você ainda pode estimar manualmente."
        )

    st.markdown("##### Parâmetros")
    c1, c2, c3 = st.columns(3)
    valor_hora = c1.number_input("Valor da hora por pessoa (R$)", min_value=0.0,
                                 value=20.0, step=1.0)
    ocupacao = c2.number_input("Ocupação média por veículo", min_value=1.0,
                               value=1.5, step=0.1)
    frequencia = c3.number_input("Dias de ocorrência por ano", min_value=0.0,
                                 value=5.0, step=1.0)

    st.markdown("##### Demanda afetada")
    use_population = st.checkbox(
        "Usar população/peso como aproximação (sem dado de fluxo)", value=not bool(impact))
    c4, c5 = st.columns(2)
    if use_population:
        pessoas_afetadas = c4.number_input(
            "Pessoas potencialmente afetadas", min_value=0,
            value=int(suggested_people), step=100)
        validation.msg_limitation(
            "Aproximação por população/peso na ausência de contagem volumétrica "
            "ou pesquisa O-D."
        )
    else:
        fluxo = c4.number_input("Fluxo afetado (veículos/dia)", min_value=0.0,
                                value=1000.0, step=100.0)
        pessoas_afetadas = fluxo * ocupacao

    atraso_min = c5.number_input("Atraso médio por viagem (min)", min_value=0.0,
                                 value=float(round(suggested_delay, 1)), step=1.0)

    if st.button("💰 Calcular custo social", type="primary"):
        horas_perdidas = pessoas_afetadas * atraso_min / 60.0
        custo_evento = horas_perdidas * valor_hora
        custo_anual = custo_evento * frequencia
        result = {
            "valor_hora": valor_hora,
            "ocupacao": ocupacao,
            "frequencia": frequencia,
            "pessoas_afetadas": pessoas_afetadas,
            "atraso_min": atraso_min,
            "horas_perdidas": horas_perdidas,
            "custo_evento": custo_evento,
            "custo_anual": custo_anual,
        }
        st.session_state["social_cost"] = result
        validation.msg_success("Custo social preliminar calculado.")

    result = st.session_state.get("social_cost")
    if result:
        st.divider()
        ui_theme.render_metric_cards([
            ("Pessoas afetadas", utils.fmt_int(result["pessoas_afetadas"]), PALETTE["accent"]),
            ("Horas perdidas (evento)", utils.fmt_number(result["horas_perdidas"], 1),
             PALETTE["attention"]),
            ("Custo por evento (R$)", utils.fmt_number(result["custo_evento"], 2),
             PALETTE["amber"]),
            ("Custo anual estimado (R$)", utils.fmt_number(result["custo_anual"], 2),
             PALETTE["critical"]),
        ], columns=4)
        st.caption(
            "Cálculo: horas_perdidas = pessoas × atraso/60; "
            "custo_evento = horas × valor_hora; custo_anual = custo_evento × dias/ano."
        )
