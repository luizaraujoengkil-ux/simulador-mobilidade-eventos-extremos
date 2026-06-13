"""
area_selector.py
================
Tela "Área de análise": define a área de estudo por nome, ponto+raio,
coordenada ou (estrutura preparada para) polígono/arquivo geográfico.
"""

from __future__ import annotations

import streamlit as st

from . import maps, ui_theme, utils, validation

# Faixas de raio sugeridas (km)
RADIUS_HINTS = [
    ("Bairro / local", "1 a 5 km"),
    ("Área urbana parcial", "5 a 15 km"),
    ("Cidade inteira", "10 a 30 km"),
    ("Região metropolitana / ampliada", "30 a 100 km"),
]

ENTRY_TYPES = [
    "Nome da cidade/localidade",
    "Ponto + raio (coordenada)",
    "Coordenada central",
    "Polígono / arquivo geográfico (GeoJSON/KML/KMZ)",
]


def render() -> None:
    ui_theme.page_title("Área de análise", kicker="Etapa 2 · Recorte espacial")

    ok = validation.guard("area")
    if not ok:
        return

    st.markdown(
        "Defina o recorte espacial do estudo. Este recorte será usado para "
        "coletar a rede viária na etapa seguinte."
    )

    with st.expander("Faixas de raio sugeridas", expanded=False):
        for label, rng in RADIUS_HINTS:
            st.markdown(f"- **{label}:** {rng}")

    existing = st.session_state.get("area") or {}
    study = st.session_state.get("study") or {}

    entry_type = st.selectbox(
        "Tipo de entrada",
        ENTRY_TYPES,
        index=_safe_index(ENTRY_TYPES, existing.get("entry_type"), 1),
    )

    place_name = ""
    lat = existing.get("lat", -21.7642)
    lon = existing.get("lon", -43.3496)
    collect_radius = float(existing.get("collect_radius_km", 4.0))
    analysis_radius = float(existing.get("analysis_radius_km", 4.0))
    geofile = None

    if entry_type == ENTRY_TYPES[0]:
        place_name = st.text_input(
            "Nome da cidade/localidade",
            value=existing.get("place_name", study.get("city", "Juiz de Fora, Minas Gerais, Brasil")),
            help="Use um nome reconhecível pelo OpenStreetMap, ex.: 'Juiz de Fora, Minas Gerais, Brasil'.",
        )
    elif entry_type in (ENTRY_TYPES[1], ENTRY_TYPES[2]):
        c1, c2 = st.columns(2)
        lat = c1.number_input("Latitude", value=float(lat), format="%.6f")
        lon = c2.number_input("Longitude", value=float(lon), format="%.6f")
    else:  # polígono / arquivo
        geofile = st.file_uploader(
            "Arquivo geográfico (GeoJSON, KML, KMZ, ou ZIP de shapefile)",
            type=["geojson", "json", "kml", "kmz", "zip"],
        )
        validation.msg_info(
            "A importação de polígono/arquivo será usada para recorte da rede "
            "na etapa de rede viária. Para o MVP, recomenda-se iniciar por "
            "nome da cidade ou ponto + raio."
        )

    if entry_type in (ENTRY_TYPES[1], ENTRY_TYPES[2], ENTRY_TYPES[0]):
        c1, c2 = st.columns(2)
        collect_radius = c1.number_input(
            "Raio de coleta da rede (km)", min_value=0.3, max_value=100.0,
            value=float(collect_radius), step=0.5,
            help="Raio usado para baixar a rede em torno do ponto central.",
        )
        analysis_radius = c2.number_input(
            "Raio efetivo de análise (km)", min_value=0.3, max_value=100.0,
            value=float(min(analysis_radius, collect_radius)), step=0.5,
        )

    if collect_radius > 15:
        validation.msg_limitation(
            "Áreas muito extensas podem tornar a coleta da rede e os cálculos "
            "mais lentos. Recomenda-se iniciar com recorte menor para testes."
        )

    notes = st.text_area("Observações", value=existing.get("notes", ""))

    if st.button("💾 Salvar área de análise", type="primary"):
        area = {
            "entry_type": entry_type,
            "place_name": place_name.strip() if place_name else "",
            "lat": float(lat),
            "lon": float(lon),
            "collect_radius_km": float(collect_radius),
            "analysis_radius_km": float(analysis_radius),
            "geofile_name": geofile.name if geofile else None,
            "notes": notes.strip(),
        }
        # Persiste o conteúdo do arquivo (bytes) para uso posterior
        if geofile is not None:
            try:
                area["geofile_bytes"] = geofile.getvalue()
            except Exception:  # pragma: no cover - robustez de upload
                area["geofile_bytes"] = None
        st.session_state["area"] = area
        validation.set_step_status("area", "concluido")
        validation.msg_success("Área de análise salva. Avance para a rede viária.")

    if st.session_state.get("area"):
        _render_summary(st.session_state["area"])


def _render_summary(area: dict) -> None:
    st.divider()
    st.markdown("#### Resumo da área")
    c1, c2 = st.columns(2)
    c1.markdown(f"**Entrada:** {area['entry_type']}")
    if area.get("place_name"):
        c1.markdown(f"**Localidade:** {area['place_name']}")
    c1.markdown(f"**Centro:** {utils.fmt_number(area['lat'],5)}, {utils.fmt_number(area['lon'],5)}")
    c2.markdown(f"**Raio de coleta:** {utils.fmt_number(area['collect_radius_km'],1)} km")
    c2.markdown(f"**Raio de análise:** {utils.fmt_number(area['analysis_radius_km'],1)} km")
    if area.get("geofile_name"):
        c2.markdown(f"**Arquivo:** {area['geofile_name']}")

    st.markdown("#### Mapa da área")
    maps.render_area_map(
        float(area["lat"]), float(area["lon"]),
        float(area.get("collect_radius_km", 3.0)),
        float(area.get("analysis_radius_km", 3.0)),
        label=area.get("place_name") or "Centro da área",
        key="map_area_analise",
    )


def _safe_index(options: list, value, default: int) -> int:
    try:
        return options.index(value)
    except (ValueError, TypeError):
        return default
