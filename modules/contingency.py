"""
contingency.py
==============
Tela "Cenários de contingência": ações de resposta que mitigam eventos e
recuperam conectividade/tempo. Compara base × impactado × contingência.
"""

from __future__ import annotations

import copy
from typing import Dict, List

import pandas as pd
import streamlit as st

from . import baseline as base_mod
from . import maps, simulation, ui_theme, utils, validation
from .utils import PALETTE

ACTIONS = {
    "manter": "Manter evento (sem intervenção)",
    "mitigar": "Mitigar / remover evento",
    "parcial": "Desbloqueio parcial (libera fluxo reduzido)",
}


def _effective_events(events: List[dict], actions: Dict[str, dict]) -> List[dict]:
    """Aplica as ações de contingência aos eventos, gerando a lista efetiva."""
    out = []
    for e in events:
        act = actions.get(e["event_id"], {"action": "manter"})
        action = act.get("action", "manter")
        if action == "mitigar":
            continue  # evento removido
        ev = copy.deepcopy(e)
        if action == "parcial":
            ev["impact_type"] = "parcial"
            ev["speed_factor"] = float(act.get("factor", 0.6))
        out.append(ev)
    return out


def render() -> None:
    ui_theme.page_title("Cenários de contingência",
                        kicker="Etapa 9 · Resposta e mitigação")

    if not validation.guard("contingencia"):
        return

    events = st.session_state.get("events") or []
    if not events:
        validation.msg_pending("Não há eventos para aplicar contingência.")
        return

    st.markdown(
        "Defina ações de resposta para cada evento e recalcule a rede. Compare "
        "o ganho de conectividade e a redução de tempo em relação ao cenário "
        "impactado."
    )

    actions: Dict[str, dict] = {}
    st.markdown("##### Ações por evento")
    for e in events:
        c1, c2, c3 = st.columns([3, 3, 2])
        c1.markdown(f"**{e['event_id']} · {e['name']}**  \n_{e['type']} · {e['severity']}_")
        action = c2.selectbox(
            "Ação", list(ACTIONS), format_func=lambda k: ACTIONS[k],
            key=f"cont_act_{e['event_id']}")
        factor = 0.6
        if action == "parcial":
            factor = c3.slider("Fluxo remanescente", 0.1, 0.95, 0.6, 0.05,
                               key=f"cont_fac_{e['event_id']}")
        actions[e["event_id"]] = {"action": action, "factor": factor}

    if st.button("🛟 Simular contingência", type="primary"):
        with st.spinner("Recalculando com ações de contingência..."):
            _run_contingency(actions)
        validation.set_step_status("contingencia", "concluido")
        validation.msg_success("Cenário de contingência calculado.")

    res = st.session_state.get("contingency_results")
    if res:
        _render_results(res)


def _run_contingency(actions: Dict[str, dict]) -> None:
    base_graph = st.session_state["graph_base"]
    events = st.session_state["events"]
    points = st.session_state["points"]
    points_by_id = {p["point_id"]: p for p in points}
    od_pairs = st.session_state["od_pairs"]
    base = st.session_state["baseline_results"]

    eff_events = _effective_events(events, actions)
    cont_graph, summary = simulation.apply_events(base_graph, eff_events)
    rg = simulation.routing_graph(cont_graph)
    cont_routes, _ = base_mod.compute_od_routes(rg, points_by_id, od_pairs)
    comparison = simulation.compare_scenarios(base["routes"], cont_routes)
    indicators = simulation.impact_indicators(
        comparison, summary, cont_graph, base["edge_usage"], points_by_id)

    st.session_state["graph_contingency"] = cont_graph
    st.session_state["contingency_actions"] = actions
    st.session_state["contingency_results"] = {
        "comparison": comparison,
        "cont_routes": cont_routes,
        "indicators": indicators,
        "events_summary": summary,
    }


def _render_results(res: dict) -> None:
    impact = st.session_state["impact_results"]["indicators"]
    cont = res["indicators"]

    st.divider()
    st.markdown("#### Comparação base × impactado × contingência")

    # recuperação
    pairs_recovered = _pairs_recovered(
        st.session_state["impact_results"]["comparison"], res["comparison"])
    time_reduction = _safe_delta(impact["mean_pct"], cont["mean_pct"])
    conn_gain = (cont["connectivity_index"] - impact["connectivity_index"]) * 100

    ui_theme.render_metric_cards([
        ("Pares recuperados", utils.fmt_int(pairs_recovered), PALETTE["improve"]),
        ("Redução do aumento médio", utils.fmt_pct(time_reduction), PALETTE["improve"]),
        ("Ganho de conectividade",
         utils.fmt_number(conn_gain, 1) + " p.p.", PALETTE["improve"]),
        ("Criticidade resultante", cont["criticality"].upper(),
         _crit_color(cont["criticality"])),
    ], columns=4)

    # tabela comparativa de indicadores
    rows = [
        ("Aumento médio de tempo", utils.fmt_pct(impact["mean_pct"]),
         utils.fmt_pct(cont["mean_pct"])),
        ("Pares desconectados", utils.fmt_int(impact["pairs_disconnected"]),
         utils.fmt_int(cont["pairs_disconnected"])),
        ("Pares afetados", utils.fmt_int(impact["pairs_affected"]),
         utils.fmt_int(cont["pairs_affected"])),
        ("Vias interditadas", utils.fmt_int(impact["n_blocked_edges"]),
         utils.fmt_int(cont["n_blocked_edges"])),
        ("Índice de conectividade",
         utils.fmt_number(impact["connectivity_index"] * 100, 1) + " %",
         utils.fmt_number(cont["connectivity_index"] * 100, 1) + " %"),
        ("População afetada", utils.fmt_int(impact["population_affected"]),
         utils.fmt_int(cont["population_affected"])),
    ]
    df = pd.DataFrame(rows, columns=["Indicador", "Impactado", "Contingência"])
    st.dataframe(df, use_container_width=True, hide_index=True)

    # prioridade de intervenção (heurística)
    priority = _intervention_priority(pairs_recovered, time_reduction, conn_gain)
    st.markdown(
        f"**Prioridade da intervenção:** "
        f"{ui_theme.status_pill(priority, _priority_color(priority))}",
        unsafe_allow_html=True)

    st.markdown("##### Mapa do cenário de contingência")
    maps.render_graph_map(st.session_state.get("graph_contingency"),
                          title="Rede sob contingência")


def _pairs_recovered(impact_comp: dict, cont_comp: dict) -> int:
    count = 0
    for key, ic in impact_comp.items():
        cc = cont_comp.get(key)
        if not cc:
            continue
        if not ic["connected_imp"] and cc["connected_imp"]:
            count += 1
    return count


def _safe_delta(a, b) -> float:
    if not (utils.is_finite_number(a) and utils.is_finite_number(b)):
        return 0.0
    return max(0.0, a - b)


def _intervention_priority(pairs_recovered: int, time_reduction: float,
                           conn_gain: float) -> str:
    score = pairs_recovered * 2 + time_reduction / 10 + conn_gain / 5
    if score >= 8:
        return "alta"
    if score >= 3:
        return "média"
    return "baixa"


def _crit_color(level: str) -> str:
    return {"baixo": PALETTE["improve"], "moderado": PALETTE["attention"],
            "alto": PALETTE["amber"], "crítico": PALETTE["critical"]}.get(
        level, PALETTE["neutral"])


def _priority_color(level: str) -> str:
    return {"alta": PALETTE["improve"], "média": PALETTE["attention"],
            "baixa": PALETTE["neutral"]}.get(level, PALETTE["neutral"])
