"""
strategic_points.py
====================
Tela "Pontos estratégicos": cadastro manual/CSV de pontos (origem/destino) e
montagem de pares O-D.
"""

from __future__ import annotations

import csv
import io
from typing import List, Optional, Tuple

import pandas as pd
import streamlit as st

from . import maps, ui_theme, utils, validation
from .utils import POINT_TYPES

CSV_HEADER = "point_id,name,type,lat,lon,population,weight,priority,notes"

# Conjuntos de tipos para estratégias de pares O-D
ORIGIN_LIKE = {"bairro", "zona residencial", "área de risco", "polo gerador de viagens"}
ESSENTIAL = {"hospital", "abrigo", "Defesa Civil", "quartel"}


def render() -> None:
    ui_theme.page_title("Pontos estratégicos", kicker="Etapa 4 · Origens e destinos")

    if not validation.guard("pontos"):
        return

    graph = st.session_state.get("graph_base")

    tab_list, tab_od, tab_add, tab_csv = st.tabs(
        ["📋 Pontos", "🔗 Pares O-D", "➕ Cadastrar manualmente", "📥 Importar CSV"]
    )

    with tab_list:
        _ui_list(graph)
    with tab_od:
        _ui_od_pairs()
    with tab_add:
        _ui_add_manual(graph)
    with tab_csv:
        _ui_import_csv(graph)


# ----------------------------------------------------------------------------
# Cadastro
# ----------------------------------------------------------------------------
def resnap_points(graph) -> int:
    """Reassocia todos os pontos ao nó mais próximo da rede atual.

    Usado após (re)carregar a rede — por exemplo ao restaurar um estudo salvo
    ou carregar o exemplo. Retorna quantos pontos foram reassociados.
    """
    points = st.session_state.get("points") or []
    n = 0
    for p in points:
        node = utils.nearest_node(graph, float(p["lat"]), float(p["lon"]))
        if node is None:
            continue
        nlat, nlon = utils.node_coords(graph, node)
        p["node_id"] = node
        p["snap_dist_m"] = utils.haversine_m(float(p["lat"]), float(p["lon"]), nlat, nlon)
        n += 1
    return n


def _next_id() -> str:
    n = len(st.session_state.get("points") or []) + 1
    return f"P{n:03d}"


def _add_point(graph, name, ptype, lat, lon, population, weight, priority, notes,
               point_id: Optional[str] = None) -> Tuple[bool, str]:
    if not utils.normalize_text(name):
        return False, "Informe o nome do ponto."
    if not (utils.is_finite_number(lat) and utils.is_finite_number(lon)):
        return False, "Coordenadas inválidas."
    node = utils.nearest_node(graph, float(lat), float(lon))
    if node is None:
        return False, "Não foi possível associar o ponto a um nó da rede."
    nlat, nlon = utils.node_coords(graph, node)
    snap_dist = utils.haversine_m(float(lat), float(lon), nlat, nlon)
    point = {
        "point_id": point_id or _next_id(),
        "name": name.strip(),
        "type": ptype,
        "lat": float(lat),
        "lon": float(lon),
        "population": int(population) if utils.is_finite_number(population) else 0,
        "weight": float(weight) if utils.is_finite_number(weight) else 1.0,
        "priority": priority,
        "notes": utils.normalize_text(notes),
        "node_id": node,
        "snap_dist_m": snap_dist,
    }
    st.session_state["points"].append(point)
    return True, f"Ponto '{point['name']}' cadastrado (distância ao nó: {snap_dist:.0f} m)."


def _ui_add_manual(graph) -> None:
    with st.form("form_point"):
        c1, c2 = st.columns(2)
        name = c1.text_input("Nome *")
        ptype = c2.selectbox("Tipo", POINT_TYPES, index=0)
        c3, c4 = st.columns(2)
        lat = c3.number_input("Latitude *", value=float((st.session_state.get("area") or {}).get("lat", -21.7642)),
                              format="%.6f")
        lon = c4.number_input("Longitude *", value=float((st.session_state.get("area") or {}).get("lon", -43.3496)),
                              format="%.6f")
        c5, c6, c7 = st.columns(3)
        population = c5.number_input("População associada", min_value=0, step=100, value=0)
        weight = c6.number_input("Peso de demanda", min_value=0.0, value=1.0, step=0.5)
        priority = c7.selectbox("Prioridade", ["baixa", "média", "alta", "crítica"], index=1)
        notes = st.text_input("Observações")
        ok = st.form_submit_button("➕ Adicionar ponto", type="primary")
    if ok:
        success, message = _add_point(graph, name, ptype, lat, lon, population,
                                      weight, priority, notes)
        if success:
            _refresh_points_status()
            validation.msg_success(message)
        else:
            validation.msg_error(message)


def _ui_import_csv(graph) -> None:
    st.caption(f"Formato esperado: `{CSV_HEADER}`")
    st.download_button(
        "Baixar modelo CSV",
        data=CSV_HEADER + "\nP001,Centro,centro,-21.7615,-43.3500,5000,1,alta,",
        file_name="modelo_pontos.csv",
        mime="text/csv",
    )
    up = st.file_uploader("Arquivo CSV de pontos", type=["csv"])
    if up is not None and st.button("📥 Importar pontos do CSV", type="primary"):
        try:
            text = up.getvalue().decode("utf-8-sig")
            reader = csv.DictReader(io.StringIO(text))
            added, errors = 0, 0
            for row in reader:
                success, _ = _add_point(
                    graph,
                    row.get("name", ""),
                    row.get("type", "outro") if row.get("type") in POINT_TYPES else "outro",
                    _to_float(row.get("lat")),
                    _to_float(row.get("lon")),
                    _to_float(row.get("population"), 0),
                    _to_float(row.get("weight"), 1.0),
                    row.get("priority", "média"),
                    row.get("notes", ""),
                    point_id=row.get("point_id") or None,
                )
                added += int(success)
                errors += int(not success)
            _refresh_points_status()
            validation.msg_success(f"{added} pontos importados.")
            if errors:
                validation.msg_pending(f"{errors} linhas ignoradas por dados inválidos.")
        except Exception as exc:
            validation.msg_error(f"Falha ao importar CSV: {exc}")


def _ui_list(graph) -> None:
    points = st.session_state.get("points") or []
    if not points:
        validation.msg_info("Nenhum ponto cadastrado ainda.")
        return
    df = pd.DataFrame(points)[
        ["point_id", "name", "type", "lat", "lon", "population", "weight",
         "priority", "snap_dist_m"]
    ].rename(columns={"snap_dist_m": "dist_no_m"})
    st.dataframe(df, use_container_width=True, hide_index=True)

    far = [p for p in points if p.get("snap_dist_m", 0) > 500]
    if far:
        validation.msg_limitation(
            f"{len(far)} ponto(s) estão a mais de 500 m do nó mais próximo da "
            "rede. Verifique as coordenadas ou amplie a área de coleta."
        )

    st.markdown("#### Mapa dos pontos sobre a malha viária")
    st.caption(
        "Hospital (vermelho), abrigo (verde), Defesa Civil (laranja), "
        "centro (azul), área de risco (vinho), demais (azul-acinzentado)."
    )
    maps.render_graph_map(
        st.session_state.get("graph_base"),
        title="Pontos estratégicos",
        with_points=True,
        with_events=False,
        key="map_pontos",
    )

    c1, c2 = st.columns(2)
    to_remove = c1.selectbox(
        "Remover ponto", ["—"] + [f"{p['point_id']} · {p['name']}" for p in points])
    if c1.button("🗑️ Remover selecionado") and to_remove != "—":
        pid = to_remove.split(" · ")[0]
        st.session_state["points"] = [p for p in points if p["point_id"] != pid]
        st.session_state["od_pairs"] = [
            (o, d) for (o, d) in st.session_state.get("od_pairs", [])
            if o != pid and d != pid
        ]
        _refresh_points_status()
        st.rerun()
    if c2.button("🧹 Limpar todos os pontos"):
        st.session_state["points"] = []
        st.session_state["od_pairs"] = []
        _refresh_points_status()
        st.rerun()


# ----------------------------------------------------------------------------
# Pares O-D
# ----------------------------------------------------------------------------
def _ui_od_pairs() -> None:
    points = st.session_state.get("points") or []
    if len(points) < 2:
        validation.msg_pending("Cadastre ao menos dois pontos para montar pares O-D.")
        return

    labels = {p["point_id"]: f"{p['point_id']} · {p['name']} ({p['type']})" for p in points}

    strategy = st.selectbox(
        "Estratégia de geração de pares",
        [
            "Todos contra todos",
            "Origens (bairros/risco) → equipamentos essenciais",
            "Origens (bairros/risco) → destino específico",
            "Seleção manual",
        ],
    )

    generated: List[Tuple[str, str]] = []

    if strategy == "Todos contra todos":
        ids = [p["point_id"] for p in points]
        generated = [(o, d) for o in ids for d in ids if o != d]
    elif strategy.startswith("Origens (bairros/risco) → equipamentos"):
        origins = [p["point_id"] for p in points if p["type"] in ORIGIN_LIKE] or \
                  [p["point_id"] for p in points]
        dests = [p["point_id"] for p in points if p["type"] in ESSENTIAL]
        if not dests:
            validation.msg_pending("Nenhum equipamento essencial (hospital/abrigo/Defesa Civil) cadastrado.")
        generated = [(o, d) for o in origins for d in dests if o != d]
    elif strategy.startswith("Origens (bairros/risco) → destino"):
        dest = st.selectbox("Destino", list(labels), format_func=lambda x: labels[x])
        origins = [p["point_id"] for p in points if p["point_id"] != dest]
        generated = [(o, dest) for o in origins]
    else:  # manual
        c1, c2 = st.columns(2)
        o = c1.selectbox("Origem", list(labels), format_func=lambda x: labels[x], key="man_o")
        d = c2.selectbox("Destino", list(labels), format_func=lambda x: labels[x], key="man_d")
        if st.button("➕ Adicionar par"):
            if o == d:
                validation.msg_error("Origem e destino devem ser diferentes.")
            elif (o, d) in st.session_state["od_pairs"]:
                validation.msg_info("Par já existe.")
            else:
                st.session_state["od_pairs"].append((o, d))
                _invalidate_baseline()
                validation.msg_success("Par adicionado.")

    if strategy != "Seleção manual":
        st.caption(f"{len(generated)} pares serão gerados.")
        if len(generated) > 400:
            validation.msg_limitation(
                f"{len(generated)} pares O-D podem deixar o cálculo lento. "
                "Considere reduzir os pontos ou usar uma estratégia mais focada."
            )
        if st.button("🔗 Gerar pares O-D", type="primary"):
            st.session_state["od_pairs"] = generated
            _invalidate_baseline()
            validation.msg_success(f"{len(generated)} pares O-D definidos.")

    pairs = st.session_state.get("od_pairs") or []
    if pairs:
        st.divider()
        st.markdown(f"**Pares O-D definidos:** {len(pairs)}")
        df = pd.DataFrame(
            [{"origem": labels.get(o, o), "destino": labels.get(d, d)} for o, d in pairs]
        )
        st.dataframe(df, use_container_width=True, hide_index=True)
        if st.button("🧹 Limpar pares O-D"):
            st.session_state["od_pairs"] = []
            _invalidate_baseline()
            st.rerun()


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def _refresh_points_status() -> None:
    pts = st.session_state.get("points") or []
    status = "concluido" if len(pts) >= 2 else ("pendente" if pts else "nao_iniciado")
    validation.set_step_status("pontos", status)
    _invalidate_baseline()


def _invalidate_baseline() -> None:
    st.session_state["baseline_results"] = None
    st.session_state["impact_results"] = None
    if st.session_state.get("workflow_status", {}).get("base") == "concluido":
        validation.set_step_status("base", "pendente")


def _to_float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
