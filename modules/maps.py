"""
maps.py
=======
Mapas interativos (Folium) da rede, pontos, eventos e cenários.

Folium e streamlit-folium são importados com proteção. Sem eles, o app
oferece um mapa simples (st.map) e orientação de instalação.
"""

from __future__ import annotations

from typing import List, Optional

import streamlit as st

from . import utils, validation
from .utils import PALETTE

try:
    import folium
    from streamlit_folium import st_folium
    FOLIUM_OK = True
except Exception:  # pragma: no cover
    FOLIUM_OK = False

# Limite de arestas desenhadas (proteção de performance)
MAX_EDGES_DRAW = 6000

STATUS_EDGE_COLOR = {
    "normal": PALETTE["accent"],
    "atencao": PALETTE["attention"],
    "parcialmente bloqueada": PALETTE["attention"],
    "bloqueada": PALETTE["critical"],
    "rota alternativa": PALETTE["improve"],
    "critica": PALETTE["critical"],
}

POINT_TYPE_COLOR = {
    "hospital": "red", "abrigo": "green", "Defesa Civil": "orange",
    "quartel": "darkblue", "centro": "blue", "área de risco": "darkred",
}


def _folium_missing_notice() -> None:
    validation.msg_info(
        "Folium não está instalado. Instale com "
        "`pip install folium streamlit-folium` para mapas interativos."
    )


def _simple_map_fallback(graph) -> None:
    """Fallback com st.map exibindo os nós."""
    try:
        import pandas as pd
        rows = [{"lat": d["y"], "lon": d["x"]}
                for _, d in graph.nodes(data=True) if "x" in d and "y" in d]
        if rows:
            st.map(pd.DataFrame(rows))
    except Exception:
        validation.msg_info("Não foi possível gerar o mapa simples.")


# ----------------------------------------------------------------------------
# Construção do mapa Folium
# ----------------------------------------------------------------------------
def build_map(graph, points: Optional[List[dict]] = None,
              events: Optional[List[dict]] = None,
              draw_edges: bool = True):
    center = utils.graph_center(graph)
    fmap = folium.Map(location=list(center), zoom_start=14,
                      tiles="cartodbpositron", control_scale=True)

    if draw_edges:
        _draw_edges(fmap, graph)
    if points:
        _draw_points(fmap, points)
    if events:
        _draw_events(fmap, events)

    _add_legend(fmap)
    return fmap


def _draw_edges(fmap, graph) -> None:
    drawn = set()
    count = 0
    truncated = False
    for u, v, data in graph.edges(data=True):
        key = frozenset((u, v))
        # desenha bloqueadas/parciais sempre; normais respeitam dedup e limite
        status = data.get("status", "normal")
        is_special = status in ("bloqueada", "parcialmente bloqueada")
        if not is_special:
            if key in drawn:
                continue
            drawn.add(key)
            if count >= MAX_EDGES_DRAW:
                truncated = True
                continue
        # usa a geometria real da via (LineString do OSM) quando disponível;
        # caso contrário, traça reta entre os nós (rede sintética)
        coords = _edge_coords(graph, u, v, data)
        if coords is None:
            continue
        color = STATUS_EDGE_COLOR.get(status, PALETTE["neutral"])
        weight = 5 if is_special else 2
        opacity = 0.95 if is_special else 0.65
        folium.PolyLine(
            coords, color=color, weight=weight, opacity=opacity,
            tooltip=f"{data.get('name','via')} · {status}",
        ).add_to(fmap)
        count += 1
    if truncated:
        st.caption(
            f"⚠️ Exibindo {MAX_EDGES_DRAW} vias (rede grande). Vias bloqueadas e "
            "parciais são sempre mostradas."
        )


def _edge_coords(graph, u, v, data):
    """Lista de (lat, lon) da via: usa geometria real do OSM se houver."""
    geom = data.get("geometry")
    if geom is not None and hasattr(geom, "coords"):
        try:
            return [(y, x) for x, y in geom.coords]  # shapely dá (lon, lat)
        except Exception:
            pass
    try:
        lat1, lon1 = utils.node_coords(graph, u)
        lat2, lon2 = utils.node_coords(graph, v)
        return [(lat1, lon1), (lat2, lon2)]
    except Exception:
        return None


def _draw_points(fmap, points) -> None:
    for p in points:
        color = POINT_TYPE_COLOR.get(p.get("type"), "cadetblue")
        folium.Marker(
            location=[p["lat"], p["lon"]],
            tooltip=f"{p['name']} ({p['type']})",
            icon=folium.Icon(color=color, icon="info-sign"),
        ).add_to(fmap)


def _draw_events(fmap, events) -> None:
    for e in events:
        color = {"total": PALETTE["critical"], "parcial": PALETTE["attention"],
                 "atraso": PALETTE["amber"]}.get(e.get("impact_type"), PALETTE["critical"])
        folium.Circle(
            location=[e["lat"], e["lon"]],
            radius=float(e.get("radius_m", 100)),
            color=color, fill=True, fill_opacity=0.25,
            tooltip=f"{e['name']} ({e['type']}, {e['severity']})",
        ).add_to(fmap)


def _add_legend(fmap) -> None:
    legend_html = f"""
    <div style="position: fixed; bottom: 24px; left: 24px; z-index: 9999;
         background: white; padding: 10px 12px; border-radius: 8px;
         box-shadow: 0 2px 8px rgba(0,0,0,0.2); font-size: 12px;">
      <b>Legenda</b><br>
      <span style="color:{PALETTE['accent']}">━</span> via normal<br>
      <span style="color:{PALETTE['attention']}">━</span> parcial / atenção<br>
      <span style="color:{PALETTE['critical']}">━</span> bloqueada / crítica<br>
      <span style="color:{PALETTE['improve']}">━</span> alternativa
    </div>
    """
    fmap.get_root().html.add_child(folium.Element(legend_html))


# ----------------------------------------------------------------------------
# Funções de tela
# ----------------------------------------------------------------------------
def render_graph_map(graph, title: str = "Rede viária",
                     with_points: bool = True, with_events: bool = True,
                     key: Optional[str] = None) -> None:
    if graph is None or graph.number_of_nodes() == 0:
        validation.msg_info("Sem rede para exibir.")
        return
    if not FOLIUM_OK:
        _folium_missing_notice()
        _simple_map_fallback(graph)
        return
    points = st.session_state.get("points") if with_points else None
    events = st.session_state.get("events") if with_events else None
    fmap = build_map(graph, points=points, events=events)
    st_folium(fmap, use_container_width=True, height=560,
              key=key or f"map_{title}", returned_objects=[])


def render_area_map(lat: float, lon: float, collect_km: float,
                    analysis_km: float, label: str = "Centro da área",
                    key: str = "map_area") -> None:
    """Mapa de localização da área: marcador + círculos de coleta/análise."""
    if not FOLIUM_OK:
        _folium_missing_notice()
        try:
            import pandas as pd
            st.map(pd.DataFrame([{"lat": lat, "lon": lon}]))
        except Exception:
            pass
        return
    fmap = folium.Map(location=[lat, lon], zoom_start=13,
                      tiles="cartodbpositron", control_scale=True)
    folium.Marker([lat, lon], tooltip=label,
                  icon=folium.Icon(color="darkblue", icon="map-marker")).add_to(fmap)
    folium.Circle([lat, lon], radius=collect_km * 1000, color=PALETTE["accent"],
                  fill=False, weight=2, dash_array="6",
                  tooltip=f"Raio de coleta: {collect_km:g} km").add_to(fmap)
    folium.Circle([lat, lon], radius=analysis_km * 1000, color=PALETTE["improve"],
                  fill=True, fill_opacity=0.08, weight=2,
                  tooltip=f"Raio de análise: {analysis_km:g} km").add_to(fmap)
    st_folium(fmap, use_container_width=True, height=420, key=key,
              returned_objects=[])


def render_comparison_map() -> None:
    """Mapa lado a lado: rede-base x rede impactada."""
    base = st.session_state.get("graph_base")
    impacted = st.session_state.get("graph_impacted")
    if not FOLIUM_OK:
        _folium_missing_notice()
        if base is not None:
            _simple_map_fallback(base)
        return

    view = st.radio("Visualização", ["Rede impactada", "Rede-base", "Lado a lado"],
                    horizontal=True, key="cmp_map_view")
    points = st.session_state.get("points")
    events = st.session_state.get("events")

    if view == "Lado a lado":
        c1, c2 = st.columns(2)
        with c1:
            st.caption("Cenário-base")
            if base is not None:
                st_folium(build_map(base, points=points), height=460,
                          use_container_width=True, key="map_base_side",
                          returned_objects=[])
        with c2:
            st.caption("Cenário impactado")
            if impacted is not None:
                st_folium(build_map(impacted, points=points, events=events),
                          height=460, use_container_width=True,
                          key="map_imp_side", returned_objects=[])
    elif view == "Rede-base":
        if base is not None:
            st_folium(build_map(base, points=points), height=560,
                      use_container_width=True, key="map_base_full",
                      returned_objects=[])
    else:
        if impacted is not None:
            st_folium(build_map(impacted, points=points, events=events),
                      height=560, use_container_width=True, key="map_imp_full",
                      returned_objects=[])
        else:
            validation.msg_info("Execute a simulação para ver a rede impactada.")
