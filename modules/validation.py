"""
validation.py
=============
Validações obrigatórias do fluxo e mensagens padronizadas.

Garante que o usuário não avance sem pré-requisitos e que nunca apareça
NaN/erro silencioso na interface.
"""

from __future__ import annotations

from typing import List, Tuple

import streamlit as st


# ----------------------------------------------------------------------------
# Mensagens padronizadas
# ----------------------------------------------------------------------------
def msg_success(text: str) -> None:
    st.success(f"✓ {text}")


def msg_pending(text: str) -> None:
    st.warning(f"⏳ Pendência: {text}")


def msg_error(text: str) -> None:
    st.error(f"✕ {text}")


def msg_info(text: str) -> None:
    st.info(f"ℹ️ {text}")


def msg_limitation(text: str) -> None:
    st.warning(f"⚠️ Limitação metodológica: {text}")


def msg_processing(text: str) -> None:
    st.info(f"⚙️ {text}")


# ----------------------------------------------------------------------------
# Checagens de pré-requisitos (retornam (ok, mensagem))
# ----------------------------------------------------------------------------
def has_study() -> Tuple[bool, str]:
    ok = bool(st.session_state.get("study"))
    return ok, "É necessário criar um estudo antes de prosseguir."


def has_area() -> Tuple[bool, str]:
    ok = bool(st.session_state.get("area"))
    return ok, "Defina a área de análise antes de prosseguir."


def has_network() -> Tuple[bool, str]:
    g = st.session_state.get("graph_base")
    ok = g is not None and g.number_of_nodes() > 0
    return ok, "Carregue ou gere a rede viária antes de prosseguir."


def has_points() -> Tuple[bool, str]:
    pts = st.session_state.get("points") or []
    ok = len(pts) >= 2
    return ok, "Cadastre ao menos dois pontos estratégicos (origem/destino)."


def has_od_pairs() -> Tuple[bool, str]:
    ok = len(st.session_state.get("od_pairs") or []) >= 1
    return ok, "Monte ao menos um par origem-destino."


def has_baseline() -> Tuple[bool, str]:
    ok = bool(st.session_state.get("baseline_results"))
    return ok, "Calcule o cenário-base antes de prosseguir."


def has_events() -> Tuple[bool, str]:
    ok = len(st.session_state.get("events") or []) >= 1
    return ok, "Cadastre ao menos um evento extremo para simular."


def has_impact() -> Tuple[bool, str]:
    ok = bool(st.session_state.get("impact_results"))
    return ok, "Execute a simulação de impacto antes de prosseguir."


# Pré-requisitos por etapa (chave da etapa -> lista de checagens)
PREREQUISITES = {
    "rede": [has_study, has_area],
    "pontos": [has_network],
    "base": [has_network, has_points, has_od_pairs],
    "eventos": [has_baseline],
    "simular": [has_baseline, has_events],
    "comparacao": [has_impact],
    "contingencia": [has_impact],
    "relatorio": [has_baseline],
}


def guard(step_key: str) -> bool:
    """Verifica os pré-requisitos de uma etapa. Mostra pendências e retorna
    True se a etapa pode prosseguir."""
    checks = PREREQUISITES.get(step_key, [])
    pending: List[str] = []
    for check in checks:
        ok, message = check()
        if not ok:
            pending.append(message)
    if pending:
        for p in pending:
            msg_pending(p)
        return False
    return True


def set_step_status(step_key: str, status: str) -> None:
    ws = st.session_state.setdefault("workflow_status", {})
    ws[step_key] = status
