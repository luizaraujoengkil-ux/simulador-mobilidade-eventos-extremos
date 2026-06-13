"""
network_processing.py
=====================
Construção e normalização do grafo viário.

Responsável por:
- imputar velocidades por tipo de via e calcular tempos de percurso;
- garantir atributos mínimos nas arestas;
- calcular estatísticas da rede;
- gerar uma rede sintética de teste (independe de internet/OSMnx).

A rede é um ``networkx.MultiDiGraph`` com:
- nós: atributos ``x`` (lon), ``y`` (lat);
- arestas: ``length`` (m), ``speed_kph``, ``travel_time`` (s), ``name``,
  ``highway``, ``status``, ``capacity``, ``edge_id``.
"""

from __future__ import annotations

from typing import Dict, Optional

import networkx as nx

from . import utils
from .utils import DEFAULT_SPEEDS_KPH


# ----------------------------------------------------------------------------
# Normalização de atributos
# ----------------------------------------------------------------------------
def _highway_value(raw) -> str:
    """OSM pode trazer 'highway' como string ou lista. Normaliza para string."""
    if isinstance(raw, (list, tuple)) and raw:
        return str(raw[0])
    if raw is None:
        return "default"
    return str(raw)


def _speed_for(highway: str, speeds: Dict[str, float]) -> float:
    return float(speeds.get(highway, speeds.get("default", 30)))


def impute_speeds_and_times(graph: nx.MultiDiGraph,
                            speeds: Optional[Dict[str, float]] = None) -> nx.MultiDiGraph:
    """Garante speed_kph e travel_time em todas as arestas."""
    speeds = speeds or dict(DEFAULT_SPEEDS_KPH)
    for u, v, k, data in graph.edges(keys=True, data=True):
        highway = _highway_value(data.get("highway"))
        data["highway"] = highway

        # comprimento
        length = data.get("length")
        if not utils.is_finite_number(length) or float(length) <= 0:
            lat1, lon1 = utils.node_coords(graph, u)
            lat2, lon2 = utils.node_coords(graph, v)
            length = max(1.0, utils.haversine_m(lat1, lon1, lat2, lon2))
        data["length"] = float(length)

        # velocidade
        speed = data.get("speed_kph")
        if not utils.is_finite_number(speed) or float(speed) <= 0:
            speed = _speed_for(highway, speeds)
        data["speed_kph"] = float(speed)

        # tempo (s)
        data["travel_time"] = float(length) / (float(speed) / 3.6)
        data["base_travel_time"] = data["travel_time"]

        # atributos de status / capacidade
        data.setdefault("status", "normal")
        data.setdefault("capacity", 1.0)
        data.setdefault("name", _edge_name(data))
    _assign_edge_ids(graph)
    return graph


def _edge_name(data: dict) -> str:
    name = data.get("name")
    if isinstance(name, (list, tuple)) and name:
        return str(name[0])
    if name:
        return str(name)
    return f"Via {data.get('highway', 'local')}"


def _assign_edge_ids(graph: nx.MultiDiGraph) -> None:
    for i, (u, v, k, data) in enumerate(graph.edges(keys=True, data=True)):
        data["edge_id"] = f"E{i:05d}"
        data["u"] = u
        data["v"] = v
        data["key"] = k


def reset_status(graph: nx.MultiDiGraph) -> None:
    """Restaura travel_time base e status normal (usado ao copiar a rede)."""
    for _, _, data in graph.edges(data=True):
        if utils.is_finite_number(data.get("base_travel_time")):
            data["travel_time"] = float(data["base_travel_time"])
        data["status"] = "normal"
        data["capacity"] = 1.0


# ----------------------------------------------------------------------------
# Estatísticas
# ----------------------------------------------------------------------------
def graph_stats(graph: nx.MultiDiGraph) -> Dict[str, float]:
    n_nodes = graph.number_of_nodes()
    n_edges = graph.number_of_edges()
    total_length_m = sum(
        float(d.get("length", 0.0)) for _, _, d in graph.edges(data=True)
    )
    # extensão "física" descontando duplicidade de mão dupla
    total_km = total_length_m / 1000.0
    try:
        und = graph.to_undirected(as_view=True)
        connected = nx.is_connected(und) if n_nodes else False
        n_components = nx.number_connected_components(und) if n_nodes else 0
    except Exception:
        connected = False
        n_components = 0
    return {
        "n_nodes": n_nodes,
        "n_edges": n_edges,
        "total_length_km": total_km,
        "is_connected": connected,
        "n_components": n_components,
    }


# ----------------------------------------------------------------------------
# Rede sintética de teste (não depende de internet/OSMnx)
# ----------------------------------------------------------------------------
def build_synthetic_grid(center_lat: float, center_lon: float,
                         radius_km: float = 3.0,
                         spacing_m: float = 350.0,
                         speeds: Optional[Dict[str, float]] = None) -> nx.MultiDiGraph:
    """Cria uma malha viária sintética em grade ao redor de um centro.

    Útil para testes offline e demonstração quando o OSMnx não está
    disponível ou a coleta real não é desejada.
    """
    speeds = speeds or dict(DEFAULT_SPEEDS_KPH)
    g = nx.MultiDiGraph()
    g.graph["crs"] = "EPSG:4326"
    g.graph["synthetic"] = True

    # número de nós por lado (limitado para manter performance)
    n = int(max(4, min(25, round(2 * radius_km * 1000 / spacing_m))))
    half = (n - 1) / 2.0

    dlat = utils.km_to_deg_lat(spacing_m / 1000.0)
    dlon = utils.km_to_deg_lon(spacing_m / 1000.0, center_lat)

    def node_id(i, j):
        return i * n + j

    for i in range(n):
        for j in range(n):
            lat = center_lat + (i - half) * dlat
            lon = center_lon + (j - half) * dlon
            g.add_node(node_id(i, j), x=lon, y=lat)

    def highway_for(i, j, axis):
        # avenidas principais a cada 5 linhas/colunas
        idx = i if axis == "row" else j
        if idx % 5 == 0:
            return "primary"
        if idx % 5 == 1:
            return "secondary"
        return "residential"

    def add_edge(a, b, highway, label):
        lat1, lon1 = g.nodes[a]["y"], g.nodes[a]["x"]
        lat2, lon2 = g.nodes[b]["y"], g.nodes[b]["x"]
        length = max(1.0, utils.haversine_m(lat1, lon1, lat2, lon2))
        speed = _speed_for(highway, speeds)
        attrs = dict(length=length, highway=highway, name=label,
                     speed_kph=speed, oneway=False)
        g.add_edge(a, b, **attrs)
        g.add_edge(b, a, **attrs)

    for i in range(n):
        for j in range(n):
            if j + 1 < n:  # horizontal
                hw = highway_for(i, j, "row")
                add_edge(node_id(i, j), node_id(i, j + 1), hw, f"Av. Linha {i+1}"
                         if hw != "residential" else f"Rua Local {i+1}-{j+1}")
            if i + 1 < n:  # vertical
                hw = highway_for(i, j, "col")
                add_edge(node_id(i, j), node_id(i + 1, j), hw, f"Av. Coluna {j+1}"
                         if hw != "residential" else f"Rua Local {i+1}-{j+1}")

    impute_speeds_and_times(g, speeds)
    return g
