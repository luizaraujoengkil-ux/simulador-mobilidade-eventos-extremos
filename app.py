"""
SIMCIV-Mob — Simulador de Impactos Climáticos e Interdições Viárias
na Mobilidade Urbana.

Aplicação Streamlit. Ponto de entrada e roteamento das telas.

Execução:
    streamlit run app.py
"""

from __future__ import annotations

import json
import os

import streamlit as st

from modules import (
    area_selector,
    baseline,
    comparison,
    contingency,
    events,
    manual,
    network_loader,
    network_processing as netproc,
    report_generator,
    simulation,
    social_cost,
    strategic_points,
    study_setup,
    ui_theme,
    utils,
    validation,
)
from modules.utils import STEPS

DOCS_DIR = os.path.join(os.path.dirname(__file__), "docs")
EXAMPLE_PATH = os.path.join(os.path.dirname(__file__), "data", "examples",
                            "juiz_de_fora.json")


# ----------------------------------------------------------------------------
# Inicialização
# ----------------------------------------------------------------------------
ui_theme.set_page_config()
ui_theme.load_css()
utils.init_session_state(st.session_state)


def goto(page_key: str) -> None:
    st.session_state["page"] = page_key


# ----------------------------------------------------------------------------
# Barra lateral — navegação + trilha de progresso
# ----------------------------------------------------------------------------
def render_sidebar() -> str:
    with st.sidebar:
        st.markdown(
            f"<div style='font-weight:800;font-size:20px;color:{utils.PALETTE['base']}'>"
            f"SIMCIV<span style='color:{utils.PALETTE['amber']}'>-Mob</span></div>"
            "<div style='font-size:11px;color:#52606D;margin-bottom:8px'>"
            "Mobilidade Urbana &amp; Eventos Extremos</div>",
            unsafe_allow_html=True,
        )
        st.divider()

        labels = [label for _, label in STEPS]
        keys = [key for key, _ in STEPS]
        current = st.session_state.get("page", "inicio")
        idx = keys.index(current) if current in keys else 0

        choice = st.radio("Navegação", labels, index=idx, label_visibility="collapsed")
        selected_key = keys[labels.index(choice)]
        st.session_state["page"] = selected_key

        st.divider()
        st.caption("Trilha de progresso")
        ui_theme.render_progress_trail(st.session_state["workflow_status"], selected_key)
        ui_theme.legend_trail()

        st.divider()
        if st.button("🔄 Reiniciar estudo", use_container_width=True):
            _reset_state()
            st.rerun()

    return selected_key


def _reset_state() -> None:
    for key in list(utils.SESSION_DEFAULTS):
        st.session_state.pop(key, None)
    st.session_state.pop("_report_html", None)
    st.session_state.pop("_report_pdf", None)
    utils.init_session_state(st.session_state)


# ----------------------------------------------------------------------------
# Tela inicial
# ----------------------------------------------------------------------------
def render_home() -> None:
    ui_theme.page_title("Início", kicker="Painel institucional")

    st.markdown(
        f"""
        <div class="simciv-block">
            <p style="font-size:15px">{utils.APP_DESCRIPTION}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f'<div class="simciv-disclaimer"><b>Aviso metodológico:</b> '
        f"{utils.METHOD_DISCLAIMER}</div>",
        unsafe_allow_html=True,
    )

    st.markdown("### ")
    b1, b2, b3, b4 = st.columns(4)
    if b1.button("🧪 Exemplo de Juiz de Fora", use_container_width=True, type="primary"):
        _load_example()
    if b2.button("📖 Abrir metodologia", use_container_width=True):
        goto("metodologia"); st.rerun()
    if b3.button("➕ Criar novo estudo", use_container_width=True):
        goto("estudo"); st.rerun()
    if b4.button("📂 Carregar estudo salvo", use_container_width=True):
        st.session_state["_show_load"] = True

    _render_save_load()


def _render_save_load() -> None:
    st.divider()
    with st.expander("💾 Salvar / carregar estudo (sem a rede viária)",
                     expanded=st.session_state.pop("_show_load", False)):
        st.caption(
            "O pacote salvo guarda estudo, área, pontos, pares O-D, eventos e "
            "parâmetros. A rede viária deve ser recarregada/regenerada depois."
        )
        # salvar
        bundle = _export_bundle()
        st.download_button(
            "⬇️ Baixar pacote do estudo (JSON)",
            data=json.dumps(bundle, ensure_ascii=False, indent=2).encode("utf-8"),
            file_name="estudo_simciv_mob.json", mime="application/json")

        # carregar
        up = st.file_uploader("Carregar pacote (JSON)", type=["json"], key="load_bundle")
        if up is not None and st.button("📥 Restaurar estudo"):
            try:
                data = json.loads(up.getvalue().decode("utf-8"))
                _import_bundle(data)
                validation.msg_success(
                    "Estudo restaurado. Recarregue/gere a rede viária para "
                    "recalcular as rotas."
                )
            except Exception as exc:
                validation.msg_error(f"Falha ao carregar: {exc}")


def _export_bundle() -> dict:
    s = st.session_state
    return {
        "study": s.get("study"),
        "area": s.get("area"),
        "points": [{k: v for k, v in p.items() if k != "node_id"}
                   for p in (s.get("points") or [])],
        "od_pairs": [list(t) for t in (s.get("od_pairs") or [])],
        "events": s.get("events"),
        "speeds": s.get("speeds"),
        "social_cost": s.get("social_cost"),
    }


def _import_bundle(data: dict) -> None:
    _reset_state()
    st.session_state["study"] = data.get("study")
    st.session_state["area"] = data.get("area")
    st.session_state["points"] = data.get("points") or []
    st.session_state["od_pairs"] = [tuple(t) for t in (data.get("od_pairs") or [])]
    st.session_state["events"] = data.get("events") or []
    if data.get("speeds"):
        st.session_state["speeds"] = data["speeds"]
    st.session_state["social_cost"] = data.get("social_cost")
    ws = st.session_state["workflow_status"]
    if st.session_state["study"]:
        ws["estudo"] = "concluido"
    if st.session_state["area"]:
        ws["area"] = "concluido"
    if len(st.session_state["points"]) >= 2:
        ws["pontos"] = "concluido"
    if st.session_state["events"]:
        ws["eventos"] = "pendente"


def _load_example() -> None:
    try:
        with open(EXAMPLE_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as exc:
        validation.msg_error(f"Não foi possível carregar o exemplo: {exc}")
        return

    _reset_state()
    st.session_state["study"] = data["study"]
    st.session_state["area"] = data["area"]
    st.session_state["points"] = data["points"]
    st.session_state["events"] = data["events"]

    # carrega a malha viária: tenta a rede REAL do OSM; se falhar, usa sintética
    area = data["area"]
    speeds = st.session_state["speeds"]
    radius = float(area.get("analysis_radius_km", 2.0))
    g, source, ntype = None, "", "synthetic"
    if network_loader.osmnx_available():
        try:
            with st.spinner("Baixando a malha viária real de Juiz de Fora "
                            "(OpenStreetMap)..."):
                g = network_loader.load_point_network(
                    area["lat"], area["lon"], radius, "drive", speeds)
            source = f"OSM · Juiz de Fora (ponto, r={radius:g} km)"
            ntype = "drive"
        except Exception:
            g = None
    if g is None:
        g = netproc.build_synthetic_grid(
            area["lat"], area["lon"], radius_km=radius, speeds=speeds)
        source = "Sintética (exemplo Juiz de Fora)"
        ntype = "synthetic"
    st.session_state["graph_base"] = g
    st.session_state["network_meta"] = {
        "source": source, "network_type": ntype, **netproc.graph_stats(g)}

    # encaixa pontos e monta pares O-D (origens -> equipamentos essenciais)
    strategic_points.resnap_points(g)
    origins = [p["point_id"] for p in data["points"]
               if p["type"] in strategic_points.ORIGIN_LIKE or p["type"] == "centro"]
    dests = [p["point_id"] for p in data["points"]
             if p["type"] in strategic_points.ESSENTIAL]
    st.session_state["od_pairs"] = [(o, d) for o in origins for d in dests if o != d]

    ws = st.session_state["workflow_status"]
    for k in ("estudo", "area", "rede", "pontos"):
        ws[k] = "concluido"
    ws["base"] = "pendente"

    validation.msg_success(
        "Exemplo de Juiz de Fora carregado. Veja os dados da área abaixo; em "
        "**Rede viária** você pode visualizar o mapa da cidade e a malha viária."
    )
    goto("area")
    st.rerun()


# ----------------------------------------------------------------------------
# Metodologia
# ----------------------------------------------------------------------------
def render_methodology() -> None:
    ui_theme.page_title("Metodologia e limitações", kicker="Fundamentos")
    tab_met, tab_lim, tab_man = st.tabs(["Metodologia", "Limitações", "Manual de uso"])
    with tab_met:
        _render_markdown_file("metodologia.md")
    with tab_lim:
        _render_markdown_file("limitacoes.md")
    with tab_man:
        pdf = _manual_pdf_bytes()
        if pdf:
            st.download_button(
                "⬇️ Baixar manual completo (PDF)", data=pdf,
                file_name="Manual_SIMCIV-Mob.pdf", mime="application/pdf",
                type="primary")
        else:
            validation.msg_info(
                "Para o manual em PDF, instale `xhtml2pdf` (`pip install xhtml2pdf`)."
            )
        st.divider()
        _render_markdown_file("manual_uso.md")


@st.cache_data(show_spinner=False)
def _manual_pdf_bytes():
    return manual.build_manual_pdf()


def _render_markdown_file(filename: str) -> None:
    path = os.path.join(DOCS_DIR, filename)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            st.markdown(fh.read())
    except OSError:
        validation.msg_info(f"Documento '{filename}' não encontrado.")


# ----------------------------------------------------------------------------
# Roteamento
# ----------------------------------------------------------------------------
ROUTES = {
    "inicio": render_home,
    "estudo": study_setup.render,
    "area": area_selector.render,
    "rede": network_loader.render,
    "pontos": strategic_points.render,
    "base": baseline.render,
    "eventos": events.render,
    "simular": simulation.render,
    "comparacao": comparison.render,
    "contingencia": contingency.render,
    "relatorio": report_generator.render,
    "metodologia": render_methodology,
}


def main() -> None:
    page = render_sidebar()
    if page == "inicio":
        ui_theme.render_home_header()
    else:
        ui_theme.render_header()
    renderer = ROUTES.get(page, render_home)
    try:
        renderer()
    except Exception as exc:  # rede de segurança contra telas quebradas
        validation.msg_error(f"Ocorreu um erro ao renderizar a tela: {exc}")
        st.exception(exc)

    # módulos opcionais acessíveis fora da trilha principal
    if page == "comparacao":
        with st.expander("💰 Custo social preliminar"):
            social_cost.render()


if __name__ == "__main__":
    main()
