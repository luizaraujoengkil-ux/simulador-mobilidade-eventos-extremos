"""
ui_theme.py
===========
Tema visual institucional, cabeçalho, trilha de progresso, cards de métricas
e mensagens padronizadas do SIMCIV-Mob.
"""

from __future__ import annotations

import os
from typing import Optional

import streamlit as st

from . import utils
from .utils import PALETTE, STEPS, STEP_STATE_COLORS, STEP_STATE_ICON

ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")


def set_page_config() -> None:
    st.set_page_config(
        page_title=f"{utils.APP_NAME} | Mobilidade Urbana e Eventos Extremos",
        page_icon="🛰️",
        layout="wide",
        initial_sidebar_state="expanded",
    )


def load_css() -> None:
    """Injeta o CSS institucional (arquivo externo + ajustes inline)."""
    css_path = os.path.join(ASSETS_DIR, "styles.css")
    css = ""
    if os.path.exists(css_path):
        try:
            with open(css_path, "r", encoding="utf-8") as fh:
                css = fh.read()
        except OSError:
            css = ""
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


# ----------------------------------------------------------------------------
# Cabeçalho
# ----------------------------------------------------------------------------
def render_header(subtitle: Optional[str] = None) -> None:
    sub = subtitle or utils.APP_SUBTITLE
    st.markdown(
        f"""
        <div class="simciv-header">
            <div class="simciv-header-mark">SIMCIV<span>-Mob</span></div>
            <div class="simciv-header-text">
                <div class="simciv-header-title">{utils.APP_NAME}</div>
                <div class="simciv-header-sub">{sub}</div>
            </div>
            <div class="simciv-header-badge">IME · Mobilidade & Eventos Extremos</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_home_header() -> None:
    """Cabeçalho expandido (hero) da tela Início: preenche o banner com a
    identificação acadêmica e aplicada."""
    st.markdown(
        f"""
        <div class="simciv-hero">
            <div class="simciv-hero-top">
                <div class="simciv-header-mark">SIMCIV<span>-Mob</span></div>
                <div class="simciv-header-text">
                    <div class="simciv-header-title">{utils.APP_NAME}</div>
                    <div class="simciv-header-sub">{utils.APP_SUBTITLE}</div>
                </div>
                <div class="simciv-header-badge">IME · Mobilidade &amp; Eventos Extremos</div>
            </div>
            <div class="simciv-hero-info">
                <div class="simciv-hero-cell">
                    <span class="lbl">Disciplina</span>
                    <span class="val">{utils.DISCIPLINE}</span>
                </div>
                <div class="simciv-hero-cell">
                    <span class="lbl">Autoria</span>
                    <span class="val">{utils.AUTHOR} — {utils.AUTHOR_EMAIL}</span>
                </div>
                <div class="simciv-hero-cell">
                    <span class="lbl">Instituição</span>
                    <span class="val">{utils.INSTITUTION}</span>
                </div>
                <div class="simciv-hero-cell">
                    <span class="lbl">Aplicação inicial</span>
                    <span class="val">Juiz de Fora/MG · apoio preliminar ao
                    planejamento de contingência e gestão de trânsito</span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def page_title(title: str, kicker: str = "") -> None:
    kick = f'<div class="simciv-kicker">{kicker}</div>' if kicker else ""
    st.markdown(
        f'<div class="simciv-pagehead">{kick}<h2>{title}</h2></div>',
        unsafe_allow_html=True,
    )


# ----------------------------------------------------------------------------
# Trilha de progresso
# ----------------------------------------------------------------------------
def render_progress_trail(workflow_status: dict, current: str) -> None:
    """Renderiza a trilha de etapas na barra lateral."""
    st.markdown('<div class="simciv-trail">', unsafe_allow_html=True)
    for key, label in STEPS:
        state = workflow_status.get(key, "nao_iniciado")
        if key == current:
            state = "atual"
        color = STEP_STATE_COLORS.get(state, PALETTE["neutral"])
        icon = STEP_STATE_ICON.get(state, "○")
        weight = "700" if key == current else "500"
        st.markdown(
            f"""
            <div class="simciv-trail-item">
                <span class="simciv-trail-dot" style="background:{color}">{icon}</span>
                <span class="simciv-trail-label" style="font-weight:{weight}">{label}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)


def legend_trail() -> None:
    items = [
        ("Concluído", STEP_STATE_COLORS["concluido"]),
        ("Etapa atual", STEP_STATE_COLORS["atual"]),
        ("Pendente", STEP_STATE_COLORS["pendente"]),
        ("Erro", STEP_STATE_COLORS["erro"]),
        ("Não iniciado", STEP_STATE_COLORS["nao_iniciado"]),
    ]
    html = "".join(
        f'<span class="simciv-legend-item"><span class="simciv-legend-dot" '
        f'style="background:{c}"></span>{lbl}</span>'
        for lbl, c in items
    )
    st.markdown(f'<div class="simciv-legend">{html}</div>', unsafe_allow_html=True)


# ----------------------------------------------------------------------------
# Cards de métricas
# ----------------------------------------------------------------------------
def metric_card(label: str, value: str, color: str = PALETTE["accent"],
                help_text: str = "") -> str:
    sub = f'<div class="simciv-card-sub">{help_text}</div>' if help_text else ""
    return (
        f'<div class="simciv-card" style="border-left:5px solid {color}">'
        f'<div class="simciv-card-label">{label}</div>'
        f'<div class="simciv-card-value" style="color:{color}">{value}</div>'
        f"{sub}</div>"
    )


def render_metric_cards(cards: list, columns: int = 4) -> None:
    """cards: lista de tuplas (label, value, color, help_text)."""
    cols = st.columns(columns)
    for i, card in enumerate(cards):
        label, value = card[0], card[1]
        color = card[2] if len(card) > 2 else PALETTE["accent"]
        help_text = card[3] if len(card) > 3 else ""
        with cols[i % columns]:
            st.markdown(metric_card(label, value, color, help_text),
                        unsafe_allow_html=True)


def criticality_badge(level: str) -> str:
    mapping = {
        "baixo": PALETTE["improve"],
        "moderado": PALETTE["attention"],
        "alto": PALETTE["amber"],
        "crítico": PALETTE["critical"],
    }
    color = mapping.get(level, PALETTE["neutral"])
    return (
        f'<span class="simciv-badge" style="background:{color}">'
        f"Criticidade: {level.upper()}</span>"
    )


def status_pill(text: str, color: str) -> str:
    return f'<span class="simciv-pill" style="background:{color}">{text}</span>'
