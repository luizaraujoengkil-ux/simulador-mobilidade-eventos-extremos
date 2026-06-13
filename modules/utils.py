"""
utils.py
========
Funções utilitárias, constantes, paleta de cores e inicialização do
``st.session_state`` para o SIMCIV-Mob.

Este módulo NÃO depende de bibliotecas pesadas (osmnx, geopandas). Tudo aqui
deve funcionar apenas com a biblioteca padrão + numpy quando disponível.
"""

from __future__ import annotations

import math
from datetime import date
from typing import Any, Dict, Iterable, List, Optional, Tuple

# ----------------------------------------------------------------------------
# Identidade do produto
# ----------------------------------------------------------------------------
APP_NAME = "SIMCIV-Mob"
APP_SUBTITLE = (
    "Simulador de Impactos Climáticos e Interdições Viárias na Mobilidade Urbana"
)
APP_DESCRIPTION = (
    "Ferramenta exploratória para análise dos impactos de chuvas extremas, "
    "alagamentos, deslizamentos e bloqueios viários sobre a acessibilidade, "
    "conectividade e tempos de deslocamento em redes urbanas."
)

DISCIPLINE = (
    "PROBLEMAS ESPECIAIS - CIÊNCIA DE DADOS E APRENDIZADO PROFUNDO "
    "APLICADOS AOS TRANSPORTES"
)
AUTHOR = "Pedro Paulo Ferreira Peron"
AUTHOR_EMAIL = "pedro.ferreira@ime.eb.br"
INSTITUTION = "Instituto Militar de Engenharia - IME"

METHOD_DISCLAIMER = (
    "Esta ferramenta possui caráter exploratório e preliminar. Os resultados "
    "não substituem levantamento de campo, contagem volumétrica, estudos "
    "hidrológicos/hidráulicos, microssimulação de tráfego, plano oficial de "
    "contingência, projeto executivo ou análise oficial da Defesa Civil."
)

# ----------------------------------------------------------------------------
# Paleta institucional (inspiração Defesa Civil, sem marcas oficiais)
# ----------------------------------------------------------------------------
PALETTE = {
    "base": "#0F2C44",        # azul petróleo / institucional
    "base_light": "#1B4A6B",
    "accent": "#1E88E5",      # azul sistema/normal
    "attention": "#F39C12",   # laranja - atenção / evento monitorado
    "amber": "#F5B041",
    "critical": "#C0392B",    # vermelho - crítico / interdição grave
    "improve": "#2E9E5B",     # verde - alternativa / contingência / melhoria
    "neutral": "#9AA5B1",     # cinza - dado neutro / sem alteração
    "bg": "#F4F6F8",          # cinza claro / off-white - fundo
    "card": "#FFFFFF",        # branco - cards
    "text": "#1A2733",
    "text_soft": "#52606D",
}

# Mapeamento semântico de status -> cor
STATUS_COLORS = {
    "normal": PALETTE["accent"],
    "atencao": PALETTE["attention"],
    "parcial": PALETTE["attention"],
    "parcialmente bloqueada": PALETTE["attention"],
    "bloqueada": PALETTE["critical"],
    "critica": PALETTE["critical"],
    "alternativa": PALETTE["improve"],
    "rota alternativa": PALETTE["improve"],
}

# ----------------------------------------------------------------------------
# Trilha de progresso / etapas do fluxo
# ----------------------------------------------------------------------------
# (chave, rótulo) — a ordem define o fluxo de trabalho
STEPS: List[Tuple[str, str]] = [
    ("inicio", "Início"),
    ("estudo", "Novo estudo"),
    ("area", "Área de análise"),
    ("rede", "Rede viária"),
    ("pontos", "Pontos estratégicos"),
    ("base", "Cenário-base"),
    ("eventos", "Eventos extremos"),
    ("simular", "Simular impacto"),
    ("comparacao", "Comparação antes/depois"),
    ("contingencia", "Cenários de contingência"),
    ("relatorio", "Relatório"),
    ("metodologia", "Metodologia e limitações"),
]

# Estados possíveis de cada etapa e suas cores
STEP_STATE_COLORS = {
    "nao_iniciado": PALETTE["neutral"],   # cinza
    "atual": PALETTE["accent"],           # azul
    "concluido": PALETTE["improve"],      # verde
    "pendente": PALETTE["attention"],     # laranja
    "erro": PALETTE["critical"],          # vermelho
    "bloqueado": PALETTE["neutral"],
}

STEP_STATE_ICON = {
    "nao_iniciado": "○",
    "atual": "◉",
    "concluido": "✓",
    "pendente": "!",
    "erro": "✕",
    "bloqueado": "🔒",
}

# ----------------------------------------------------------------------------
# Listas de domínio (tipos)
# ----------------------------------------------------------------------------
STUDY_TYPES = [
    "Chuva extrema",
    "Alagamento urbano",
    "Deslizamento",
    "Interdição viária",
    "Evento múltiplo",
    "Contingência",
    "Melhoria de rede",
    "Outro",
]

POINT_TYPES = [
    "bairro", "centro", "hospital", "escola", "abrigo", "terminal",
    "área de risco", "Defesa Civil", "quartel", "rodoviária",
    "zona residencial", "zona comercial", "polo gerador de viagens", "outro",
]

EVENT_TYPES = [
    "alagamento", "deslizamento", "queda de barreira", "via bloqueada",
    "avenida interditada", "ponte interditada", "túnel interditado",
    "erosão", "árvore caída", "obra emergencial", "acidente",
    "bloqueio preventivo", "outro",
]

SEVERITY_LEVELS = ["baixa", "média", "alta", "crítica"]

# Tipo de impacto na rede
IMPACT_TYPES = {
    "total": "Bloqueio total (remove a via)",
    "parcial": "Bloqueio parcial (reduz velocidade / penaliza)",
    "atraso": "Atraso (adiciona minutos)",
}

CONTINGENCY_TYPES = [
    "rota alternativa liberada", "via reversível", "desbloqueio parcial",
    "prioridade operacional", "abertura de acesso temporário",
    "obra de drenagem", "nova ligação viária", "reforço de ponte",
    "sinalização de desvio", "restrição de tráfego pesado",
    "atendimento emergencial prioritário",
]

# Velocidades padrão por tipo de via (km/h) — editáveis na interface
DEFAULT_SPEEDS_KPH = {
    "motorway": 60, "motorway_link": 50,
    "trunk": 60, "trunk_link": 50,
    "primary": 50, "primary_link": 40,
    "secondary": 40, "secondary_link": 35,
    "tertiary": 35, "tertiary_link": 30,
    "residential": 25, "living_street": 15,
    "unclassified": 30, "service": 15,
    "road": 30, "default": 30,
}

# ----------------------------------------------------------------------------
# session_state
# ----------------------------------------------------------------------------
SESSION_DEFAULTS: Dict[str, Any] = {
    "page": "inicio",
    "study": None,            # dict com metadados do estudo
    "area": None,             # dict com definição da área de análise
    "graph_base": None,       # networkx.MultiDiGraph (cenário-base)
    "graph_impacted": None,   # networkx.MultiDiGraph (cenário impactado)
    "graph_contingency": None,
    "network_meta": None,     # dict com origem/estatísticas da rede
    "speeds": None,           # dict de velocidades por tipo de via
    "points": [],             # list[dict] de pontos estratégicos
    "od_pairs": [],           # list[tuple(point_id_o, point_id_d)]
    "baseline_results": None, # dict com rotas e indicadores do cenário-base
    "events": [],             # list[dict] de eventos extremos
    "impact_results": None,   # dict com comparação base x impactado
    "contingency_actions": [],# list[dict] de ações de contingência
    "contingency_results": None,
    "social_cost": None,      # dict com parâmetros e resultado de custo social
    "scenarios": {},          # cenários salvos
    "workflow_status": {},    # status por etapa
}


def init_session_state(st_state) -> None:
    """Garante que todas as chaves esperadas existam no session_state."""
    for key, default in SESSION_DEFAULTS.items():
        if key not in st_state:
            # cópia rasa para mutáveis
            if isinstance(default, (list, dict)):
                st_state[key] = type(default)()
            else:
                st_state[key] = default
    if not st_state.get("speeds"):
        st_state["speeds"] = dict(DEFAULT_SPEEDS_KPH)
    if not st_state.get("workflow_status"):
        st_state["workflow_status"] = {k: "nao_iniciado" for k, _ in STEPS}
        st_state["workflow_status"]["inicio"] = "concluido"


# ----------------------------------------------------------------------------
# Helpers numéricos e de formatação (evitam NaN / inf na interface)
# ----------------------------------------------------------------------------
INF = float("inf")


def is_finite_number(value: Any) -> bool:
    try:
        return value is not None and math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def fmt_number(value: Any, decimals: int = 1, dash: str = "—") -> str:
    """Formata número evitando exibir NaN/inf. Usa separador de milhar pt-BR."""
    if not is_finite_number(value):
        return dash
    s = f"{float(value):,.{decimals}f}"
    # converte 1,234.5 -> 1.234,5
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return s


def fmt_int(value: Any, dash: str = "—") -> str:
    if not is_finite_number(value):
        return dash
    return f"{int(round(float(value))):,}".replace(",", ".")


def fmt_minutes(value: Any) -> str:
    """Formata minutos; trata infinito como 'sem rota'."""
    if value == INF or value is None:
        return "sem rota"
    if not is_finite_number(value):
        return "—"
    return f"{fmt_number(value, 1)} min"


def fmt_pct(value: Any) -> str:
    if value == INF:
        return "∞"
    if not is_finite_number(value):
        return "—"
    return f"{fmt_number(value, 1)} %"


def safe_div(numerator: float, denominator: float, default: float = 0.0) -> float:
    try:
        if denominator == 0:
            return default
        return numerator / denominator
    except (TypeError, ZeroDivisionError):
        return default


# ----------------------------------------------------------------------------
# Geometria
# ----------------------------------------------------------------------------
EARTH_RADIUS_M = 6_371_000.0


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distância em metros entre dois pontos (graus decimais)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(a)))


def km_to_deg_lat(km: float) -> float:
    return km / 111.32


def km_to_deg_lon(km: float, lat: float) -> float:
    denom = 111.32 * math.cos(math.radians(lat))
    return km / denom if abs(denom) > 1e-9 else km / 111.32


# ----------------------------------------------------------------------------
# Helpers de grafo (independentes de osmnx)
# ----------------------------------------------------------------------------
def node_coords(graph, node) -> Tuple[float, float]:
    """Retorna (lat, lon) de um nó usando atributos y/x."""
    data = graph.nodes[node]
    return float(data.get("y")), float(data.get("x"))


def nearest_node(graph, lat: float, lon: float) -> Optional[Any]:
    """Nó mais próximo de (lat, lon) por distância haversine.

    Funciona tanto para grafos OSMnx quanto para a rede sintética de teste.
    """
    best = None
    best_d = INF
    for n, d in graph.nodes(data=True):
        if "x" not in d or "y" not in d:
            continue
        dist = haversine_m(lat, lon, float(d["y"]), float(d["x"]))
        if dist < best_d:
            best_d = dist
            best = n
    return best


def edge_midpoint(graph, u, v) -> Tuple[float, float]:
    lat1, lon1 = node_coords(graph, u)
    lat2, lon2 = node_coords(graph, v)
    return (lat1 + lat2) / 2.0, (lon1 + lon2) / 2.0


def graph_bounds(graph) -> Optional[Tuple[float, float, float, float]]:
    """Retorna (min_lat, min_lon, max_lat, max_lon) ou None."""
    lats, lons = [], []
    for _, d in graph.nodes(data=True):
        if "x" in d and "y" in d:
            lats.append(float(d["y"]))
            lons.append(float(d["x"]))
    if not lats:
        return None
    return min(lats), min(lons), max(lats), max(lons)


def graph_center(graph) -> Tuple[float, float]:
    b = graph_bounds(graph)
    if not b:
        return (-21.7642, -43.3496)  # Juiz de Fora como fallback
    return (b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0


def normalize_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def today_iso() -> str:
    return date.today().isoformat()


def first_finite(values: Iterable[Any]) -> Optional[float]:
    for v in values:
        if is_finite_number(v):
            return float(v)
    return None
