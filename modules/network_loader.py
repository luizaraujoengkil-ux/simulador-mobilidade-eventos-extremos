"""
network_loader.py
=================
Tela "Rede viária": obtenção da rede por OpenStreetMap (OSMnx), importação de
GeoJSON ou geração de rede sintética de teste.

Todas as bibliotecas pesadas (osmnx) são importadas com proteção (try/except)
e fallback. O app nunca quebra caso o OSMnx não esteja instalado.
"""

from __future__ import annotations

import json
from typing import Optional

import networkx as nx
import streamlit as st

from . import maps
from . import network_processing as netproc
from . import ui_theme, utils, validation


# ----------------------------------------------------------------------------
# Disponibilidade do OSMnx
# ----------------------------------------------------------------------------
def osmnx_available() -> bool:
    try:
        import osmnx  # noqa: F401
        return True
    except Exception:
        return False


# ----------------------------------------------------------------------------
# Carregadores via OSMnx (com cache)
# ----------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def _download_by_place(place: str, network_type: str) -> Optional[bytes]:
    """Baixa por nome de lugar. Retorna grafo serializado (pickle bytes)."""
    import pickle
    import osmnx as ox
    g = ox.graph_from_place(place, network_type=network_type, simplify=True)
    return pickle.dumps(g)


@st.cache_data(show_spinner=False)
def _download_by_point(lat: float, lon: float, dist_m: int,
                       network_type: str) -> Optional[bytes]:
    import pickle
    import osmnx as ox
    g = ox.graph_from_point((lat, lon), dist=dist_m,
                            network_type=network_type, simplify=True)
    return pickle.dumps(g)


def _load_graph_bytes(raw: bytes) -> nx.MultiDiGraph:
    import pickle
    return pickle.loads(raw)


def load_point_network(lat: float, lon: float, radius_km: float,
                       network_type: str = "drive",
                       speeds: Optional[dict] = None) -> nx.MultiDiGraph:
    """Baixa e normaliza a rede real do OSM por ponto + raio (reutilizável)."""
    raw = _download_by_point(lat, lon, int(radius_km * 1000), network_type)
    g = _load_graph_bytes(raw)
    netproc.impute_speeds_and_times(g, speeds)
    return g


# ----------------------------------------------------------------------------
# Importação de GeoJSON (sem geopandas)
# ----------------------------------------------------------------------------
def graph_from_geojson(text: str,
                       speeds: Optional[dict] = None) -> nx.MultiDiGraph:
    """Constrói grafo a partir de FeatureCollection com LineString/MultiLineString."""
    data = json.loads(text)
    g = nx.MultiDiGraph()
    g.graph["crs"] = "EPSG:4326"
    node_index: dict = {}

    def get_node(lon, lat):
        key = (round(lon, 6), round(lat, 6))
        if key not in node_index:
            nid = len(node_index)
            node_index[key] = nid
            g.add_node(nid, x=float(lon), y=float(lat))
        return node_index[key]

    def add_line(coords, props):
        highway = props.get("highway", "default")
        name = props.get("name", "Via importada")
        for a, b in zip(coords[:-1], coords[1:]):
            na = get_node(a[0], a[1])
            nb = get_node(b[0], b[1])
            g.add_edge(na, nb, highway=highway, name=name, oneway=False)
            g.add_edge(nb, na, highway=highway, name=name, oneway=False)

    features = data.get("features", []) if isinstance(data, dict) else []
    if not features and data.get("type") == "Feature":
        features = [data]
    for feat in features:
        geom = feat.get("geometry") or {}
        props = feat.get("properties") or {}
        gtype = geom.get("type")
        if gtype == "LineString":
            add_line(geom.get("coordinates", []), props)
        elif gtype == "MultiLineString":
            for part in geom.get("coordinates", []):
                add_line(part, props)

    if g.number_of_edges() == 0:
        raise ValueError(
            "Nenhuma geometria de linha (LineString) encontrada no GeoJSON."
        )
    netproc.impute_speeds_and_times(g, speeds)
    return g


# ----------------------------------------------------------------------------
# Tela
# ----------------------------------------------------------------------------
def render() -> None:
    ui_theme.page_title("Rede viária", kicker="Etapa 3 · Grafo da rede")

    if not validation.guard("rede"):
        return

    area = st.session_state.get("area")
    speeds = st.session_state.get("speeds")

    osm_ok = osmnx_available()
    if not osm_ok:
        validation.msg_info(
            "OSMnx não está instalado neste ambiente. Você pode importar um "
            "GeoJSON ou usar a **rede sintética de teste**. Para baixar dados "
            "reais do OpenStreetMap, instale: `pip install osmnx`."
        )

    options = []
    if osm_ok:
        options += [
            "Baixar do OpenStreetMap por nome da cidade",
            "Baixar do OpenStreetMap por ponto + raio",
        ]
    options += [
        "Importar GeoJSON",
        "Rede sintética de teste (offline)",
    ]
    choice = st.radio("Origem da rede", options, index=0)

    network_type = "drive"
    if osm_ok and choice.startswith("Baixar"):
        network_type = st.selectbox(
            "Tipo de rede",
            ["drive", "drive_service", "all"],
            help="'drive': vias para automóveis. 'all': inclui mais vias (mais pesado).",
        )

    _render_speed_editor(speeds)

    st.divider()

    if choice == "Baixar do OpenStreetMap por nome da cidade":
        _ui_download_place(area, network_type, speeds)
    elif choice == "Baixar do OpenStreetMap por ponto + raio":
        _ui_download_point(area, network_type, speeds)
    elif choice == "Importar GeoJSON":
        _ui_import_geojson(speeds)
    else:
        _ui_synthetic(area, speeds)

    _render_current_network()


def _render_speed_editor(speeds: dict) -> None:
    with st.expander("Velocidades padrão por tipo de via (km/h) — editável"):
        st.caption(
            "Usadas quando a rede não traz velocidade. Ajuste conforme a "
            "realidade local."
        )
        cols = st.columns(3)
        keys = ["motorway", "trunk", "primary", "secondary", "tertiary",
                "residential", "service", "unclassified", "default"]
        for i, key in enumerate(keys):
            with cols[i % 3]:
                speeds[key] = st.number_input(
                    key, min_value=5, max_value=130,
                    value=int(speeds.get(key, 30)), step=5, key=f"speed_{key}")
        st.session_state["speeds"] = speeds


def _ui_download_place(area, network_type, speeds) -> None:
    default_place = (area or {}).get("place_name") or "Juiz de Fora, Minas Gerais, Brasil"
    place = st.text_input("Nome do lugar (OSM)", value=default_place)
    if st.button("⬇️ Baixar rede por nome", type="primary"):
        with st.spinner("Baixando rede do OpenStreetMap..."):
            try:
                raw = _download_by_place(place, network_type)
                g = _load_graph_bytes(raw)
                netproc.impute_speeds_and_times(g, speeds)
                _store_network(g, source=f"OSM · {place}", network_type=network_type)
            except Exception as exc:  # pragma: no cover - rede externa
                validation.msg_error(f"Falha ao baixar a rede: {exc}")
                validation.msg_info(
                    "Verifique o nome do lugar ou a conexão. Você pode usar a "
                    "rede sintética de teste como alternativa."
                )


def _ui_download_point(area, network_type, speeds) -> None:
    c1, c2, c3 = st.columns(3)
    lat = c1.number_input("Latitude", value=float((area or {}).get("lat", -21.7642)),
                          format="%.6f")
    lon = c2.number_input("Longitude", value=float((area or {}).get("lon", -43.3496)),
                          format="%.6f")
    radius = c3.number_input("Raio (km)", min_value=0.3, max_value=30.0,
                             value=float((area or {}).get("collect_radius_km", 3.0)),
                             step=0.5)
    if st.button("⬇️ Baixar rede por ponto + raio", type="primary"):
        with st.spinner("Baixando rede do OpenStreetMap..."):
            try:
                g = load_point_network(lat, lon, radius, network_type, speeds)
                _store_network(g, source=f"OSM · ponto ({lat:.4f},{lon:.4f}) r={radius}km",
                               network_type=network_type)
            except Exception as exc:  # pragma: no cover - rede externa
                validation.msg_error(f"Falha ao baixar a rede: {exc}")


def _ui_import_geojson(speeds) -> None:
    up = st.file_uploader("Arquivo GeoJSON com vias (LineString)",
                          type=["geojson", "json"])
    if up is not None and st.button("📥 Importar GeoJSON", type="primary"):
        try:
            text = up.getvalue().decode("utf-8")
            g = graph_from_geojson(text, speeds)
            _store_network(g, source=f"GeoJSON · {up.name}", network_type="import")
        except Exception as exc:
            validation.msg_error(f"Falha ao importar GeoJSON: {exc}")


def _ui_synthetic(area, speeds) -> None:
    st.caption(
        "Gera uma malha em grade ao redor do centro da área. Ideal para testes "
        "offline e demonstração do fluxo completo."
    )
    c1, c2, c3 = st.columns(3)
    lat = c1.number_input("Latitude central",
                          value=float((area or {}).get("lat", -21.7642)), format="%.6f")
    lon = c2.number_input("Longitude central",
                          value=float((area or {}).get("lon", -43.3496)), format="%.6f")
    radius = c3.number_input("Raio (km)", min_value=0.5, max_value=10.0,
                             value=float(min(3.0, (area or {}).get("analysis_radius_km", 3.0))),
                             step=0.5)
    if st.button("⚙️ Gerar rede sintética", type="primary"):
        with st.spinner("Gerando rede sintética..."):
            g = netproc.build_synthetic_grid(lat, lon, radius_km=radius, speeds=speeds)
            _store_network(g, source=f"Sintética · r={radius}km", network_type="synthetic")


def _store_network(g: nx.MultiDiGraph, source: str, network_type: str) -> None:
    stats = netproc.graph_stats(g)
    if stats["n_nodes"] == 0 or stats["n_edges"] == 0:
        validation.msg_error("A rede obtida está vazia. Tente outra origem.")
        validation.set_step_status("rede", "erro")
        return
    st.session_state["graph_base"] = g
    st.session_state["graph_impacted"] = None
    st.session_state["baseline_results"] = None
    st.session_state["impact_results"] = None
    st.session_state["network_meta"] = {
        "source": source,
        "network_type": network_type,
        **stats,
    }
    validation.set_step_status("rede", "concluido")
    # invalida etapas seguintes
    for k in ("base", "simular", "comparacao", "contingencia"):
        validation.set_step_status(k, "nao_iniciado")
    # reassocia pontos já cadastrados (ex.: estudo salvo / exemplo)
    from . import strategic_points
    if st.session_state.get("points"):
        strategic_points.resnap_points(g)
    validation.msg_success(
        f"Rede carregada: {stats['n_nodes']} nós, {stats['n_edges']} arestas, "
        f"{utils.fmt_number(stats['total_length_km'],1)} km."
    )
    if not stats["is_connected"]:
        validation.msg_limitation(
            f"A rede possui {stats['n_components']} componentes desconectados. "
            "Alguns pares O-D podem não ter rota mesmo no cenário-base."
        )


def _render_current_network() -> None:
    meta = st.session_state.get("network_meta")
    if not meta:
        return
    st.divider()
    st.markdown("#### Rede carregada")
    ui_theme.render_metric_cards([
        ("Nós", utils.fmt_int(meta["n_nodes"]), utils.PALETTE["accent"]),
        ("Arestas", utils.fmt_int(meta["n_edges"]), utils.PALETTE["accent"]),
        ("Extensão", f'{utils.fmt_number(meta["total_length_km"],1)} km',
         utils.PALETTE["base"]),
        ("Componentes", utils.fmt_int(meta["n_components"]),
         utils.PALETTE["improve"] if meta["is_connected"] else utils.PALETTE["attention"]),
    ], columns=4)
    st.caption(f"Origem: {meta['source']}")

    st.markdown("#### Mapa da cidade e malha viária")
    if meta.get("network_type") == "synthetic":
        validation.msg_info(
            "Rede sintética de teste (grade) sobre o mapa real da cidade. Para a "
            "malha viária real, use 'Baixar do OpenStreetMap'."
        )
    maps.render_graph_map(
        st.session_state.get("graph_base"),
        title="Rede viária carregada",
        with_points=bool(st.session_state.get("points")),
        with_events=False,
        key="map_rede_viaria",
    )
