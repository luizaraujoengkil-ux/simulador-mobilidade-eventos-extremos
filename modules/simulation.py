"""
simulation.py
=============
Aplicação dos eventos à rede e cálculo do cenário impactado.

Funções reutilizáveis:
- :func:`apply_events` — gera a rede impactada (cópia da base com status);
- :func:`routing_graph` — versão para roteamento (remove vias bloqueadas);
- :func:`compare_scenarios` — compara rotas base x impactado;
- :func:`impact_indicators` — indicadores e nível de criticidade.
"""

from __future__ import annotations

import copy
from typing import Dict, List, Tuple

import networkx as nx
import pandas as pd
import streamlit as st

from . import baseline as base_mod
from . import network_processing as netproc
from . import ui_theme, utils, validation
from .events import affected_edges
from .strategic_points import ESSENTIAL
from .utils import INF, PALETTE

# Limiares de classificação de pares
PCT_NORMAL = 5.0
PCT_AFFECTED = 30.0


# ----------------------------------------------------------------------------
# Aplicação de eventos
# ----------------------------------------------------------------------------
def _apply_impact(data: dict, event: dict) -> None:
    base_t = float(data.get("base_travel_time", data.get("travel_time", 0.0)))
    itype = event["impact_type"]
    if itype == "total":
        data["status"] = "bloqueada"
        data["blocked"] = True
        data["travel_time"] = INF
        data["capacity"] = 0.0
    elif itype == "parcial":
        f = max(0.05, float(event.get("speed_factor", 0.5)))
        # já penalizado por outro evento? mantém o pior caso
        new_t = base_t / f
        data["travel_time"] = max(float(data.get("travel_time", base_t)), new_t)
        if data.get("status") != "bloqueada":
            data["status"] = "parcialmente bloqueada"
        data["capacity"] = min(float(data.get("capacity", 1.0)), f)
    elif itype == "atraso":
        add = float(event.get("extra_delay_min", 0.0)) * 60.0
        if data.get("travel_time", base_t) != INF:
            data["travel_time"] = float(data.get("travel_time", base_t)) + add
        if data.get("status") == "normal":
            data["status"] = "atencao"
    data.setdefault("event_ids", [])
    data["event_ids"].append(event["event_id"])


def apply_events(base_graph: nx.MultiDiGraph, events: List[dict]) -> Tuple[nx.MultiDiGraph, list]:
    """Retorna (grafo_impactado, resumo_por_evento)."""
    g = copy.deepcopy(base_graph)
    netproc.reset_status(g)
    for _, _, d in g.edges(data=True):
        d.pop("blocked", None)
        d["event_ids"] = []

    summary = []
    for e in events:
        edges = affected_edges(g, e["lat"], e["lon"], e["radius_m"])
        for (u, v, k) in edges:
            _apply_impact(g[u][v][k], e)
        summary.append({**e, "n_affected": len(edges)})
    return g, summary


def routing_graph(impacted: nx.MultiDiGraph) -> nx.MultiDiGraph:
    """Grafo para roteamento: remove arestas bloqueadas (bloqueio total)."""
    rg = impacted.copy()
    to_remove = [
        (u, v, k) for u, v, k, d in impacted.edges(keys=True, data=True)
        if d.get("blocked")
    ]
    rg.remove_edges_from(to_remove)
    return rg


# ----------------------------------------------------------------------------
# Comparação
# ----------------------------------------------------------------------------
def classify_pair(base_r: dict, imp_r: dict) -> Tuple[str, float, float]:
    """Retorna (status, delta_min, pct)."""
    if not base_r["connected"]:
        return "sem rota na base", 0.0, 0.0
    if not imp_r["connected"]:
        return "desconectado", INF, INF
    delta = imp_r["time_min"] - base_r["time_min"]
    if base_r["time_min"] <= 0:
        return "normal", delta, 0.0
    pct = (delta / base_r["time_min"]) * 100.0
    if pct < PCT_NORMAL:
        status = "normal"
    elif pct < PCT_AFFECTED:
        status = "afetado"
    else:
        status = "severamente afetado"
    return status, delta, pct


def compare_scenarios(base_routes: dict, imp_routes: dict) -> Dict[Tuple[str, str], dict]:
    comparison = {}
    for key, base_r in base_routes.items():
        imp_r = imp_routes.get(key, base_mod._disconnected_route())
        status, delta, pct = classify_pair(base_r, imp_r)
        comparison[key] = {
            "base_time": base_r["time_min"],
            "imp_time": imp_r["time_min"],
            "base_dist": base_r["dist_km"],
            "imp_dist": imp_r["dist_km"],
            "delta_min": delta,
            "pct": pct,
            "status": status,
            "connected_base": base_r["connected"],
            "connected_imp": imp_r["connected"],
        }
    return comparison


# ----------------------------------------------------------------------------
# Indicadores e criticidade
# ----------------------------------------------------------------------------
def _criticality(mean_pct: float, n_disconnected: int, essential_hit: bool) -> str:
    if n_disconnected > 0 and (mean_pct >= 60 or essential_hit):
        return "crítico"
    if mean_pct >= 60 or essential_hit:
        return "crítico"
    if mean_pct >= 30 or n_disconnected > 0:
        return "alto"
    if mean_pct >= 10:
        return "moderado"
    return "baixo"


def impact_indicators(comparison: dict, events_summary: list, impacted_graph,
                      edge_usage: dict, points_by_id: dict) -> dict:
    n_blocked = sum(
        1 for _, _, d in impacted_graph.edges(data=True) if d.get("blocked"))
    n_partial = sum(
        1 for _, _, d in impacted_graph.edges(data=True)
        if d.get("status") == "parcialmente bloqueada")

    both_connected = [c for c in comparison.values()
                      if c["connected_base"] and c["connected_imp"] and c["base_time"] > 0]
    pcts = [c["pct"] for c in both_connected]
    deltas = [c["delta_min"] for c in both_connected]
    add_dist = [max(0.0, c["imp_dist"] - c["base_dist"]) for c in both_connected]

    mean_before = (sum(c["base_time"] for c in both_connected) / len(both_connected)
                   if both_connected else None)
    mean_after = (sum(c["imp_time"] for c in both_connected) / len(both_connected)
                  if both_connected else None)
    mean_pct = sum(pcts) / len(pcts) if pcts else 0.0
    mean_delta = sum(deltas) / len(deltas) if deltas else 0.0

    new_disconnected = [c for c in comparison.values()
                        if c["connected_base"] and not c["connected_imp"]]
    affected = [c for c in comparison.values()
                if c["status"] in ("afetado", "severamente afetado", "desconectado")]

    # conectividade: pares conectados depois / conectados antes
    base_conn = sum(1 for c in comparison.values() if c["connected_base"])
    imp_conn = sum(1 for c in comparison.values()
                   if c["connected_base"] and c["connected_imp"])
    connectivity_index = utils.safe_div(imp_conn, base_conn, 1.0)

    # acesso a equipamentos essenciais impactado?
    essential_hit = _essential_access_hit(comparison, points_by_id)

    # vias críticas: afetadas E entre as mais usadas na base
    critical_edges = _critical_edges(impacted_graph, edge_usage)

    # pontos mais prejudicados (por origem)
    worst_points = _worst_origins(comparison, points_by_id)

    # população potencialmente afetada
    affected_origins = {
        o for (o, d), c in comparison.items()
        if c["status"] in ("severamente afetado", "desconectado")
    }
    population_affected = sum(
        int(points_by_id.get(o, {}).get("population", 0) or 0) for o in affected_origins)

    criticality = _criticality(mean_pct, len(new_disconnected), essential_hit)

    return {
        "n_events": len(events_summary),
        "n_blocked_edges": n_blocked,
        "n_partial_edges": n_partial,
        "mean_time_before": mean_before,
        "mean_time_after": mean_after,
        "mean_delta_min": mean_delta,
        "mean_pct": mean_pct,
        "additional_dist_km": sum(add_dist) if add_dist else 0.0,
        "pairs_affected": len(affected),
        "pairs_disconnected": len(new_disconnected),
        "connectivity_index": connectivity_index,
        "essential_access_hit": essential_hit,
        "critical_edges": critical_edges,
        "worst_points": worst_points,
        "population_affected": population_affected,
        "criticality": criticality,
    }


def _essential_access_hit(comparison: dict, points_by_id: dict) -> bool:
    for (o, d), c in comparison.items():
        if points_by_id.get(d, {}).get("type") in ESSENTIAL:
            if c["status"] in ("severamente afetado", "desconectado"):
                return True
    return False


def _critical_edges(impacted_graph, edge_usage: dict, top: int = 10) -> List[dict]:
    out = []
    for u, v, d in impacted_graph.edges(data=True):
        if d.get("status") in ("bloqueada", "parcialmente bloqueada"):
            eid = d.get("edge_id")
            out.append({
                "edge_id": eid,
                "name": d.get("name", "—"),
                "highway": d.get("highway", "—"),
                "status": d.get("status"),
                "baseline_usage": int(edge_usage.get(eid, 0)),
            })
    # dedup por edge_id e ordena por uso na base
    seen, dedup = set(), []
    for e in sorted(out, key=lambda x: x["baseline_usage"], reverse=True):
        if e["edge_id"] in seen:
            continue
        seen.add(e["edge_id"])
        dedup.append(e)
    return dedup[:top]


def _worst_origins(comparison: dict, points_by_id: dict, top: int = 10) -> List[dict]:
    agg: Dict[str, list] = {}
    for (o, d), c in comparison.items():
        agg.setdefault(o, []).append(c)
    rows = []
    for o, clist in agg.items():
        disc = sum(1 for c in clist if c["status"] == "desconectado")
        finite_pcts = [c["pct"] for c in clist
                       if utils.is_finite_number(c["pct"]) and c["connected_imp"]]
        mean_pct = sum(finite_pcts) / len(finite_pcts) if finite_pcts else 0.0
        rows.append({
            "origem": points_by_id.get(o, {}).get("name", o),
            "tipo": points_by_id.get(o, {}).get("type", "—"),
            "pares_desconectados": disc,
            "aumento_medio_pct": mean_pct,
        })
    rows.sort(key=lambda r: (r["pares_desconectados"], r["aumento_medio_pct"]),
              reverse=True)
    return rows[:top]


# ----------------------------------------------------------------------------
# Orquestração da simulação
# ----------------------------------------------------------------------------
def run_simulation() -> dict:
    base_graph = st.session_state["graph_base"]
    events = st.session_state["events"]
    points = st.session_state["points"]
    points_by_id = {p["point_id"]: p for p in points}
    od_pairs = st.session_state["od_pairs"]
    base = st.session_state["baseline_results"]

    impacted, summary = apply_events(base_graph, events)
    rg = routing_graph(impacted)
    imp_routes, _ = base_mod.compute_od_routes(rg, points_by_id, od_pairs)
    comparison = compare_scenarios(base["routes"], imp_routes)
    indicators = impact_indicators(
        comparison, summary, impacted, base["edge_usage"], points_by_id)

    st.session_state["graph_impacted"] = impacted
    return {
        "comparison": comparison,
        "imp_routes": imp_routes,
        "indicators": indicators,
        "events_summary": summary,
    }


# ----------------------------------------------------------------------------
# Tela
# ----------------------------------------------------------------------------
def render() -> None:
    ui_theme.page_title("Simular impacto", kicker="Etapa 7 · Cenário impactado")

    if not validation.guard("simular"):
        return

    n_events = len(st.session_state.get("events") or [])
    st.markdown(
        f"Pronto para simular **{n_events} evento(s)** sobre a rede-base. O "
        "sistema copia a rede, aplica os eventos, recalcula as rotas e compara "
        "com o cenário-base."
    )

    if st.button("⚡ Simular impacto", type="primary"):
        with st.spinner("Aplicando eventos e recalculando rotas..."):
            results = run_simulation()
            st.session_state["impact_results"] = results
        validation.set_step_status("simular", "concluido")
        validation.set_step_status("comparacao", "pendente")
        validation.set_step_status("contingencia", "nao_iniciado")
        validation.msg_success("Simulação concluída.")

    results = st.session_state.get("impact_results")
    if results:
        _render_results(results)


def _render_results(results: dict) -> None:
    ind = results["indicators"]
    points_by_id = {p["point_id"]: p for p in st.session_state["points"]}

    st.divider()
    st.markdown(ui_theme.criticality_badge(ind["criticality"]), unsafe_allow_html=True)
    st.markdown("#### Cards principais")

    crit_color = {
        "baixo": PALETTE["improve"], "moderado": PALETTE["attention"],
        "alto": PALETTE["amber"], "crítico": PALETTE["critical"],
    }.get(ind["criticality"], PALETTE["neutral"])

    ui_theme.render_metric_cards([
        ("Vias interditadas", utils.fmt_int(ind["n_blocked_edges"]), PALETTE["critical"]),
        ("Vias parcialmente afetadas", utils.fmt_int(ind["n_partial_edges"]), PALETTE["attention"]),
        ("Pares O-D afetados", utils.fmt_int(ind["pairs_affected"]), PALETTE["attention"]),
        ("Pares sem rota", utils.fmt_int(ind["pairs_disconnected"]),
         PALETTE["critical"] if ind["pairs_disconnected"] else PALETTE["neutral"]),
    ], columns=4)
    ui_theme.render_metric_cards([
        ("Aumento médio de tempo", utils.fmt_pct(ind["mean_pct"]), PALETTE["attention"]),
        ("População afetada", utils.fmt_int(ind["population_affected"]), PALETTE["critical"]),
        ("Índice de conectividade",
         utils.fmt_number(ind["connectivity_index"] * 100, 1) + " %", PALETTE["accent"]),
        ("Nível de criticidade", ind["criticality"].upper(), crit_color),
    ], columns=4)

    if ind["essential_access_hit"]:
        validation.msg_error(
            "Acesso a equipamentos essenciais (hospital/abrigo/Defesa Civil) foi "
            "severamente afetado ou interrompido em ao menos um par O-D."
        )

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("##### Vias críticas (afetadas e mais usadas na base)")
        ce = ind.get("critical_edges", [])
        if ce:
            st.dataframe(pd.DataFrame(ce)[["name", "highway", "status", "baseline_usage"]],
                         use_container_width=True, hide_index=True, height=280)
        else:
            validation.msg_info("Nenhuma via crítica identificada.")
    with c2:
        st.markdown("##### Origens mais prejudicadas")
        wp = ind.get("worst_points", [])
        if wp:
            df = pd.DataFrame(wp)
            df["aumento_medio_pct"] = df["aumento_medio_pct"].map(lambda v: utils.fmt_pct(v))
            st.dataframe(df, use_container_width=True, hide_index=True, height=280)
        else:
            validation.msg_info("Sem dados de origens prejudicadas.")

    st.caption(
        "Veja a tela **Comparação antes/depois** para a tabela O-D completa, "
        "gráficos e mapas."
    )
