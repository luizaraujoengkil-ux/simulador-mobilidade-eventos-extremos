"""
events.py
=========
Tela "Eventos extremos": cadastro de eventos (alagamento, deslizamento,
interdições etc.) e definição do tipo de impacto na rede.

A localização do evento é definida por ponto + raio de afetação. As arestas
afetadas são (re)calculadas a partir da rede-base no momento da simulação, de
modo a sempre refletir a rede atual.
"""

from __future__ import annotations

from typing import List

import pandas as pd
import streamlit as st

from . import maps, ui_theme, utils, validation
from .utils import EVENT_TYPES, IMPACT_TYPES, SEVERITY_LEVELS

# Severidade -> sugestão de fator de velocidade remanescente (bloqueio parcial)
SEVERITY_SPEED_FACTOR = {"baixa": 0.75, "média": 0.5, "alta": 0.3, "crítica": 0.15}


def affected_edges(graph, lat: float, lon: float, radius_m: float) -> List:
    """Lista (u, v, key) cujas arestas têm ponto médio dentro do raio."""
    out = []
    for u, v, k in graph.edges(keys=True):
        mlat, mlon = utils.edge_midpoint(graph, u, v)
        if utils.haversine_m(lat, lon, mlat, mlon) <= radius_m:
            out.append((u, v, k))
    return out


def render() -> None:
    ui_theme.page_title("Eventos extremos e interdições",
                        kicker="Etapa 6 · Cadastro de eventos")

    if not validation.guard("eventos"):
        return

    graph = st.session_state["graph_base"]

    st.markdown(
        "Cadastre os eventos que afetam a rede. Cada evento é localizado por um "
        "ponto e um raio de afetação, e aplica um tipo de impacto às vias "
        "atingidas."
    )

    tab_list, tab_add = st.tabs(["📋 Eventos cadastrados", "➕ Cadastrar evento"])
    with tab_list:
        _ui_list(graph)
    with tab_add:
        _ui_add(graph)


def _next_id() -> str:
    n = len(st.session_state.get("events") or []) + 1
    return f"EV{n:03d}"


def _ui_add(graph) -> None:
    area = st.session_state.get("area") or {}
    with st.form("form_event"):
        c1, c2 = st.columns(2)
        name = c1.text_input("Nome do evento *", placeholder="Alagamento Av. Central")
        etype = c2.selectbox("Tipo", EVENT_TYPES, index=0)

        c3, c4, c5 = st.columns(3)
        severity = c3.selectbox("Severidade", SEVERITY_LEVELS, index=2)
        impact_type = c4.selectbox(
            "Tipo de impacto", list(IMPACT_TYPES),
            format_func=lambda k: IMPACT_TYPES[k])
        radius = c5.number_input("Raio de afetação (m)", min_value=20, max_value=3000,
                                 value=150, step=20)

        c6, c7 = st.columns(2)
        lat = c6.number_input("Latitude *", value=float(area.get("lat", -21.7642)),
                              format="%.6f")
        lon = c7.number_input("Longitude *", value=float(area.get("lon", -43.3496)),
                              format="%.6f")

        # parâmetros dependentes do tipo de impacto
        speed_factor = SEVERITY_SPEED_FACTOR.get(severity, 0.5)
        extra_delay = 0.0
        if impact_type == "parcial":
            speed_factor = st.slider(
                "Capacidade/velocidade remanescente", 0.05, 0.95,
                float(speed_factor), 0.05,
                help="Fração da velocidade que permanece na via (1.0 = sem efeito).")
        elif impact_type == "atraso":
            extra_delay = st.number_input("Atraso adicional (min)", min_value=0.0,
                                          value=5.0, step=1.0)

        c8, c9 = st.columns(2)
        duration = c8.text_input("Duração estimada", value="evento pontual")
        period = c9.text_input("Horário/período", value="—")
        notes = st.text_area("Observações")

        ok = st.form_submit_button("➕ Adicionar evento", type="primary")

    # pré-visualização da afetação
    n_aff = len(affected_edges(graph, lat, lon, radius))
    if n_aff == 0:
        validation.msg_pending(
            f"Nenhuma via dentro do raio de {radius} m no ponto informado. "
            "Aumente o raio ou ajuste as coordenadas."
        )
    else:
        st.caption(f"Pré-visualização: {n_aff} via(s) seriam afetadas neste raio.")

    if ok:
        if not utils.normalize_text(name):
            validation.msg_error("Informe o nome do evento.")
            return
        if n_aff == 0:
            validation.msg_error(
                "O evento precisa atingir ao menos uma via. Ajuste raio/local."
            )
            return
        event = {
            "event_id": _next_id(),
            "name": name.strip(),
            "type": etype,
            "severity": severity,
            "impact_type": impact_type,
            "lat": float(lat),
            "lon": float(lon),
            "radius_m": float(radius),
            "speed_factor": float(speed_factor),
            "extra_delay_min": float(extra_delay),
            "duration": duration.strip(),
            "period": period.strip(),
            "notes": notes.strip(),
        }
        st.session_state["events"].append(event)
        validation.set_step_status("eventos", "concluido")
        validation.set_step_status("simular", "pendente")
        st.session_state["impact_results"] = None
        validation.msg_success(
            f"Evento '{event['name']}' cadastrado ({n_aff} via(s) afetadas)."
        )


def _ui_list(graph) -> None:
    events = st.session_state.get("events") or []
    if not events:
        validation.msg_info("Nenhum evento cadastrado ainda.")
        return

    rows = []
    for e in events:
        n_aff = len(affected_edges(graph, e["lat"], e["lon"], e["radius_m"]))
        rows.append({
            "id": e["event_id"], "nome": e["name"], "tipo": e["type"],
            "severidade": e["severity"], "impacto": IMPACT_TYPES[e["impact_type"]],
            "raio (m)": e["radius_m"], "vias afetadas": n_aff,
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.markdown("#### Mapa dos eventos sobre a malha viária")
    st.caption(
        "Círculos: bloqueio total (vermelho), parcial (laranja), atraso (âmbar). "
        "O tamanho do círculo representa o raio de afetação. Marcadores = pontos "
        "estratégicos."
    )
    maps.render_graph_map(
        st.session_state.get("graph_base"),
        title="Eventos extremos",
        with_points=True,
        with_events=True,
        key="map_eventos",
    )

    c1, c2 = st.columns(2)
    to_remove = c1.selectbox(
        "Remover evento", ["—"] + [f"{e['event_id']} · {e['name']}" for e in events])
    if c1.button("🗑️ Remover selecionado") and to_remove != "—":
        eid = to_remove.split(" · ")[0]
        st.session_state["events"] = [e for e in events if e["event_id"] != eid]
        st.session_state["impact_results"] = None
        st.rerun()
    if c2.button("🧹 Limpar todos os eventos"):
        st.session_state["events"] = []
        st.session_state["impact_results"] = None
        validation.set_step_status("eventos", "pendente")
        st.rerun()
