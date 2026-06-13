"""
baseline.py
===========
Motor de roteamento (menores caminhos) e cálculo do cenário-base.

Também expõe funções reutilizadas por ``simulation.py`` e ``contingency.py``:
- :func:`compute_od_routes` — rotas O-D por Dijkstra (peso = travel_time);
- :func:`path_metrics` — tempo/distância de um caminho;
- :func:`baseline_indicators` — indicadores agregados.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Optional, Tuple

import networkx as nx
import pandas as pd
import streamlit as st

from . import network_processing as netproc
from . import ui_theme, utils, validation
from .strategic_points import ESSENTIAL
from .utils import INF, PALETTE

WEIGHT = "travel_time"


# ----------------------------------------------------------------------------
# Núcleo de roteamento
# ----------------------------------------------------------------------------
def _best_edge(graph: nx.MultiDiGraph, u, v, weight: str = WEIGHT) -> Optional[dict]:
    data = graph.get_edge_data(u, v)
    if not data:
        return None
    return min(data.values(), key=lambda d: d.get(weight, INF))


def path_metrics(graph: nx.MultiDiGraph, path: List, weight: str = WEIGHT
                 ) -> Tuple[float, float, List[str]]:
    """Retorna (tempo_s, comprimento_m, lista de edge_id) ao longo do caminho."""
    if not path or len(path) < 2:
        return 0.0, 0.0, []
    total_t, total_l, edge_ids = 0.0, 0.0, []
    for u, v in zip(path[:-1], path[1:]):
        e = _best_edge(graph, u, v, weight)
        if e is None:
            return INF, INF, []
        total_t += float(e.get(weight, INF))
        total_l += float(e.get("length", 0.0))
        if e.get("edge_id"):
            edge_ids.append(e["edge_id"])
    return total_t, total_l, edge_ids


def compute_od_routes(graph: nx.MultiDiGraph, points_by_id: Dict[str, dict],
                      od_pairs: List[Tuple[str, str]], weight: str = WEIGHT
                      ) -> Tuple[Dict[Tuple[str, str], dict], Dict[str, int]]:
    """Calcula rotas para todos os pares O-D.

    Retorna (routes, edge_usage) onde routes[(o,d)] traz tempo, distância,
    caminho e conectividade; edge_usage conta o uso de cada aresta.
    """
    by_origin: Dict[str, List[str]] = defaultdict(list)
    for o, d in od_pairs:
        by_origin[o].append(d)

    routes: Dict[Tuple[str, str], dict] = {}
    edge_usage: Dict[str, int] = defaultdict(int)

    for o_id, dests in by_origin.items():
        o_pt = points_by_id.get(o_id)
        if not o_pt or o_pt.get("node_id") is None:
            for d_id in dests:
                routes[(o_id, d_id)] = _disconnected_route()
            continue
        o_node = o_pt["node_id"]
        try:
            dist_map, path_map = nx.single_source_dijkstra(graph, o_node, weight=weight)
        except Exception:
            dist_map, path_map = {}, {}

        for d_id in dests:
            d_pt = points_by_id.get(d_id)
            if not d_pt or d_pt.get("node_id") is None:
                routes[(o_id, d_id)] = _disconnected_route()
                continue
            d_node = d_pt["node_id"]
            if d_node == o_node:
                routes[(o_id, d_id)] = {
                    "time_s": 0.0, "time_min": 0.0, "dist_km": 0.0,
                    "path": [o_node], "edge_ids": [], "connected": True,
                    "note": "origem e destino no mesmo nó",
                }
                continue
            if d_node in dist_map:
                path = path_map.get(d_node, [])
                t_s, length_m, eids = path_metrics(graph, path, weight)
                for eid in eids:
                    edge_usage[eid] += 1
                routes[(o_id, d_id)] = {
                    "time_s": t_s, "time_min": t_s / 60.0,
                    "dist_km": length_m / 1000.0, "path": path,
                    "edge_ids": eids, "connected": True, "note": "",
                }
            else:
                routes[(o_id, d_id)] = _disconnected_route()
    return routes, dict(edge_usage)


def _disconnected_route() -> dict:
    return {"time_s": INF, "time_min": INF, "dist_km": INF, "path": [],
            "edge_ids": [], "connected": False, "note": "sem rota"}


# ----------------------------------------------------------------------------
# Indicadores
# ----------------------------------------------------------------------------
def baseline_indicators(graph, routes, edge_usage, points_by_id) -> dict:
    stats = netproc.graph_stats(graph)
    connected = [r for r in routes.values() if r["connected"] and r["time_min"] > 0]
    disconnected = [r for r in routes.values() if not r["connected"]]

    times = [r["time_min"] for r in connected]
    dists = [r["dist_km"] for r in connected]

    mean_time = sum(times) / len(times) if times else None
    mean_dist = sum(dists) / len(dists) if dists else None

    # vias mais utilizadas
    top_edges = _top_edges(graph, edge_usage, top=10)

    # acessibilidade média a equipamentos essenciais
    access = _essential_accessibility(routes, points_by_id)

    return {
        **stats,
        "n_pairs": len(routes),
        "pairs_connected": len(connected),
        "pairs_disconnected": len(disconnected),
        "mean_time_min": mean_time,
        "mean_dist_km": mean_dist,
        "top_edges": top_edges,
        "essential_access_min": access,
    }


def _top_edges(graph, edge_usage, top=10) -> List[dict]:
    by_id = {}
    for u, v, data in graph.edges(data=True):
        by_id[data.get("edge_id")] = data
    ranked = sorted(edge_usage.items(), key=lambda kv: kv[1], reverse=True)[:top]
    out = []
    for eid, count in ranked:
        d = by_id.get(eid, {})
        out.append({
            "edge_id": eid,
            "name": d.get("name", "—"),
            "highway": d.get("highway", "—"),
            "usage": count,
        })
    return out


def _essential_accessibility(routes, points_by_id) -> Optional[float]:
    """Tempo médio até o equipamento essencial mais próximo, por origem."""
    best_by_origin: Dict[str, float] = {}
    for (o, d), r in routes.items():
        d_pt = points_by_id.get(d)
        if not d_pt or d_pt.get("type") not in ESSENTIAL:
            continue
        if not r["connected"]:
            continue
        cur = best_by_origin.get(o, INF)
        best_by_origin[o] = min(cur, r["time_min"])
    vals = [v for v in best_by_origin.values() if utils.is_finite_number(v)]
    return sum(vals) / len(vals) if vals else None


# ----------------------------------------------------------------------------
# Tela
# ----------------------------------------------------------------------------
def render() -> None:
    ui_theme.page_title("Cenário-base", kicker="Etapa 5 · Linha de referência")

    if not validation.guard("base"):
        return

    graph = st.session_state["graph_base"]
    points = st.session_state["points"]
    od_pairs = st.session_state["od_pairs"]
    points_by_id = {p["point_id"]: p for p in points}

    st.markdown(
        "O cenário-base calcula as rotas normais entre os pares O-D, servindo "
        "de referência para medir o impacto dos eventos extremos."
    )

    if st.button("▶️ Calcular cenário-base", type="primary"):
        with st.spinner("Calculando menores caminhos..."):
            routes, usage = compute_od_routes(graph, points_by_id, od_pairs)
            indicators = baseline_indicators(graph, routes, usage, points_by_id)
            st.session_state["baseline_results"] = {
                "routes": routes,
                "edge_usage": usage,
                "indicators": indicators,
            }
            st.session_state["impact_results"] = None
        if indicators["pairs_connected"] == 0:
            validation.msg_error(
                "Nenhum par O-D possui rota no cenário-base. Verifique a "
                "conectividade da rede e a localização dos pontos."
            )
            validation.set_step_status("base", "erro")
        else:
            validation.set_step_status("base", "concluido")
            validation.set_step_status("eventos", "pendente")
            validation.msg_success("Cenário-base calculado.")
            if indicators["pairs_disconnected"] > 0:
                validation.msg_limitation(
                    f"{indicators['pairs_disconnected']} par(es) já estão "
                    "desconectados no cenário-base (sem evento)."
                )

    base = st.session_state.get("baseline_results")
    if base:
        _render_results(base, points_by_id)


def _render_results(base: dict, points_by_id: dict) -> None:
    ind = base["indicators"]
    st.divider()
    st.markdown("#### Indicadores do cenário-base")
    ui_theme.render_metric_cards([
        ("Nós", utils.fmt_int(ind["n_nodes"]), PALETTE["accent"]),
        ("Arestas", utils.fmt_int(ind["n_edges"]), PALETTE["accent"]),
        ("Extensão da rede", f'{utils.fmt_number(ind["total_length_km"],1)} km', PALETTE["base"]),
        ("Pares O-D", utils.fmt_int(ind["n_pairs"]), PALETTE["base"]),
    ], columns=4)
    ui_theme.render_metric_cards([
        ("Tempo médio O-D", utils.fmt_minutes(ind["mean_time_min"]), PALETTE["accent"]),
        ("Distância média", f'{utils.fmt_number(ind["mean_dist_km"],2)} km', PALETTE["accent"]),
        ("Pares conectados", utils.fmt_int(ind["pairs_connected"]), PALETTE["improve"]),
        ("Pares sem rota", utils.fmt_int(ind["pairs_disconnected"]),
         PALETTE["critical"] if ind["pairs_disconnected"] else PALETTE["neutral"]),
    ], columns=4)

    if ind.get("essential_access_min") is not None:
        st.markdown(
            f"**Acessibilidade média a equipamentos essenciais:** "
            f"{utils.fmt_minutes(ind['essential_access_min'])}"
        )

    c1, c2 = st.columns([3, 2])
    with c1:
        st.markdown("##### Rotas O-D (cenário-base)")
        st.dataframe(_routes_table(base["routes"], points_by_id),
                     use_container_width=True, hide_index=True, height=320)
    with c2:
        st.markdown("##### Vias mais utilizadas")
        top = ind.get("top_edges", [])
        if top:
            st.dataframe(pd.DataFrame(top)[["name", "highway", "usage"]],
                         use_container_width=True, hide_index=True, height=320)
        else:
            validation.msg_info("Sem dados de uso de vias.")


def _routes_table(routes: dict, points_by_id: dict) -> pd.DataFrame:
    rows = []
    for (o, d), r in routes.items():
        rows.append({
            "origem": points_by_id.get(o, {}).get("name", o),
            "destino": points_by_id.get(d, {}).get("name", d),
            "tempo": utils.fmt_minutes(r["time_min"]),
            "distância (km)": utils.fmt_number(r["dist_km"], 2) if r["connected"] else "—",
            "status": "conectado" if r["connected"] else "sem rota",
        })
    return pd.DataFrame(rows)
