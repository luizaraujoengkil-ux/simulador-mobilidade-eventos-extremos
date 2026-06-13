"""
study_setup.py
==============
Tela "Novo estudo": metadados do estudo de mobilidade/evento extremo.
"""

from __future__ import annotations

import streamlit as st

from . import ui_theme, utils, validation
from .utils import STUDY_TYPES


def render() -> None:
    ui_theme.page_title("Novo estudo", kicker="Etapa 1 · Identificação")

    st.markdown(
        "Defina os metadados do estudo. Estes dados aparecerão no relatório "
        "final e identificam o cenário analisado."
    )

    existing = st.session_state.get("study") or {}

    with st.form("form_estudo"):
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input(
                "Nome do estudo *",
                value=existing.get("name", ""),
                placeholder="Impactos de chuvas extremas na mobilidade urbana de Juiz de Fora",
            )
            city = st.text_input("Cidade / localidade *",
                                 value=existing.get("city", ""))
            uf = st.text_input("UF", value=existing.get("uf", ""), max_chars=2)
            country = st.text_input("País", value=existing.get("country", "Brasil"))
            population = st.number_input(
                "População aproximada (opcional)",
                min_value=0, step=1000,
                value=int(existing.get("population", 0) or 0),
            )
        with c2:
            responsible = st.text_input(
                "Responsável", value=existing.get("responsible", utils.AUTHOR))
            institution = st.text_input(
                "Instituição", value=existing.get("institution", utils.INSTITUTION))
            study_date = st.date_input("Data do estudo")
            study_type = st.selectbox(
                "Tipo de análise",
                STUDY_TYPES,
                index=_safe_index(STUDY_TYPES, existing.get("study_type"), 3),
            )
            mode = st.radio(
                "Modo de operação",
                ["básico", "avançado"],
                index=0 if existing.get("mode", "básico") == "básico" else 1,
                horizontal=True,
                help="O modo avançado expõe parâmetros adicionais ao longo do fluxo.",
            )

        notes = st.text_area("Observações", value=existing.get("notes", ""))
        submitted = st.form_submit_button("💾 Salvar estudo", type="primary")

    if submitted:
        if not utils.normalize_text(name):
            validation.msg_error("Informe o nome do estudo.")
            return
        if not utils.normalize_text(city):
            validation.msg_error("Informe a cidade/localidade.")
            return

        st.session_state["study"] = {
            "name": name.strip(),
            "city": city.strip(),
            "uf": uf.strip().upper(),
            "country": country.strip() or "Brasil",
            "population": int(population) if population else None,
            "responsible": responsible.strip(),
            "institution": institution.strip(),
            "date": study_date.isoformat(),
            "study_type": study_type,
            "mode": mode,
            "notes": notes.strip(),
        }
        validation.set_step_status("estudo", "concluido")
        validation.msg_success("Estudo salvo com sucesso. Avance para a área de análise.")

    if st.session_state.get("study"):
        _render_summary(st.session_state["study"])


def _render_summary(study: dict) -> None:
    st.divider()
    st.markdown("#### Resumo do estudo")
    c1, c2, c3 = st.columns(3)
    c1.markdown(f"**Estudo:** {study['name']}")
    c1.markdown(f"**Local:** {study['city']} / {study.get('uf','')} · {study.get('country','')}")
    c2.markdown(f"**Tipo:** {study['study_type']}")
    c2.markdown(f"**Modo:** {study['mode']}")
    c3.markdown(f"**Responsável:** {study['responsible']}")
    c3.markdown(f"**Data:** {study['date']}")


def _safe_index(options: list, value, default: int) -> int:
    try:
        return options.index(value)
    except (ValueError, TypeError):
        return default
