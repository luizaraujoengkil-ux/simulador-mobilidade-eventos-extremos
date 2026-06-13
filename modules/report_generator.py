"""
report_generator.py
====================
Geração do relatório do estudo em HTML (com opção de PDF quando a biblioteca
estiver disponível).
"""

from __future__ import annotations

import html
from typing import Optional

import streamlit as st

from . import ui_theme, utils, validation
from .utils import PALETTE


def _esc(value) -> str:
    return html.escape(str(value if value is not None else "—"))


def _table(headers, rows) -> str:
    th = "".join(f"<th>{_esc(h)}</th>" for h in headers)
    body = ""
    for r in rows:
        body += "<tr>" + "".join(f"<td>{_esc(c)}</td>" for c in r) + "</tr>"
    return (f'<table class="rep-table"><thead><tr>{th}</tr></thead>'
            f"<tbody>{body}</tbody></table>")


def build_html(for_pdf: bool = False) -> str:
    s = st.session_state
    study = s.get("study") or {}
    area = s.get("area") or {}
    meta = s.get("network_meta") or {}
    base = s.get("baseline_results")
    impact = s.get("impact_results")
    cont = s.get("contingency_results")
    social = s.get("social_cost")
    points = s.get("points") or []
    events = s.get("events") or []
    points_by_id = {p["point_id"]: p for p in points}

    parts = [_html_head(for_pdf), _cover(study, for_pdf)]

    # 2-3. Identificação + dados do estudo
    parts.append(_section("Dados do estudo", _table(
        ["Campo", "Valor"],
        [
            ("Nome", study.get("name")),
            ("Cidade/UF", f"{study.get('city','—')} / {study.get('uf','')}"),
            ("País", study.get("country")),
            ("Responsável", study.get("responsible")),
            ("Instituição", study.get("institution")),
            ("Data", study.get("date")),
            ("Tipo de análise", study.get("study_type")),
            ("Modo", study.get("mode")),
            ("Observações", study.get("notes")),
        ])))

    # 4. Área
    if area:
        parts.append(_section("Área de análise", _table(
            ["Campo", "Valor"],
            [
                ("Tipo de entrada", area.get("entry_type")),
                ("Localidade", area.get("place_name") or "—"),
                ("Centro", f"{utils.fmt_number(area.get('lat'),5)}, {utils.fmt_number(area.get('lon'),5)}"),
                ("Raio de coleta (km)", utils.fmt_number(area.get("collect_radius_km"), 1)),
                ("Raio de análise (km)", utils.fmt_number(area.get("analysis_radius_km"), 1)),
            ])))

    # 5. Rede
    if meta:
        parts.append(_section("Rede viária utilizada", _table(
            ["Indicador", "Valor"],
            [
                ("Origem", meta.get("source")),
                ("Nós", utils.fmt_int(meta.get("n_nodes"))),
                ("Arestas", utils.fmt_int(meta.get("n_edges"))),
                ("Extensão (km)", utils.fmt_number(meta.get("total_length_km"), 1)),
                ("Componentes", utils.fmt_int(meta.get("n_components"))),
            ])))

    # 6. Pontos
    if points:
        parts.append(_section("Pontos estratégicos", _table(
            ["ID", "Nome", "Tipo", "Prioridade", "População"],
            [(p["point_id"], p["name"], p["type"], p.get("priority", "—"),
              utils.fmt_int(p.get("population"))) for p in points])))

    # 7. Cenário-base
    if base:
        ind = base["indicators"]
        parts.append(_section("Cenário-base", _table(
            ["Indicador", "Valor"],
            [
                ("Pares O-D", utils.fmt_int(ind["n_pairs"])),
                ("Pares conectados", utils.fmt_int(ind["pairs_connected"])),
                ("Pares sem rota", utils.fmt_int(ind["pairs_disconnected"])),
                ("Tempo médio O-D", utils.fmt_minutes(ind["mean_time_min"])),
                ("Distância média (km)", utils.fmt_number(ind["mean_dist_km"], 2)),
                ("Acesso médio a essenciais", utils.fmt_minutes(ind.get("essential_access_min"))),
            ])))

    # 8. Eventos
    if events:
        parts.append(_section("Eventos extremos cadastrados", _table(
            ["ID", "Nome", "Tipo", "Severidade", "Impacto", "Raio (m)"],
            [(e["event_id"], e["name"], e["type"], e["severity"],
              e["impact_type"], utils.fmt_int(e["radius_m"])) for e in events])))

    # 9-13. Impacto
    if impact:
        ind = impact["indicators"]
        parts.append(_section("Cenário impactado — indicadores", _table(
            ["Indicador", "Valor"],
            [
                ("Nível de criticidade", ind["criticality"].upper()),
                ("Vias interditadas", utils.fmt_int(ind["n_blocked_edges"])),
                ("Vias parcialmente afetadas", utils.fmt_int(ind["n_partial_edges"])),
                ("Tempo médio base", utils.fmt_minutes(ind["mean_time_before"])),
                ("Tempo médio impactado", utils.fmt_minutes(ind["mean_time_after"])),
                ("Aumento médio", utils.fmt_pct(ind["mean_pct"])),
                ("Pares afetados", utils.fmt_int(ind["pairs_affected"])),
                ("Pares desconectados", utils.fmt_int(ind["pairs_disconnected"])),
                ("Índice de conectividade", utils.fmt_number(ind["connectivity_index"] * 100, 1) + " %"),
                ("População afetada", utils.fmt_int(ind["population_affected"])),
            ])))

        crit = ind.get("critical_edges", [])
        if crit:
            parts.append(_section("Vias críticas", _table(
                ["Via", "Tipo", "Status", "Uso na base"],
                [(c["name"], c["highway"], c["status"], utils.fmt_int(c["baseline_usage"]))
                 for c in crit])))

        # pares mais afetados
        comp = impact["comparison"]
        worst = sorted(
            comp.items(),
            key=lambda kv: (kv[1]["delta_min"] if utils.is_finite_number(kv[1]["delta_min"]) else 1e9),
            reverse=True)[:15]
        parts.append(_section("Pares O-D mais afetados", _table(
            ["Origem", "Destino", "Base", "Impactado", "Aumento", "Status"],
            [(points_by_id.get(o, {}).get("name", o),
              points_by_id.get(d, {}).get("name", d),
              utils.fmt_minutes(c["base_time"]),
              utils.fmt_minutes(c["imp_time"]) if c["connected_imp"] else "sem rota",
              utils.fmt_pct(c["pct"]), c["status"])
             for (o, d), c in worst])))

    # 15. Contingência
    if cont:
        ci = cont["indicators"]
        parts.append(_section("Cenário de contingência", _table(
            ["Indicador", "Impactado → Contingência"],
            [
                ("Aumento médio",
                 f'{utils.fmt_pct(impact["indicators"]["mean_pct"])} → {utils.fmt_pct(ci["mean_pct"])}'
                 if impact else utils.fmt_pct(ci["mean_pct"])),
                ("Pares desconectados",
                 f'{utils.fmt_int(impact["indicators"]["pairs_disconnected"])} → {utils.fmt_int(ci["pairs_disconnected"])}'
                 if impact else utils.fmt_int(ci["pairs_disconnected"])),
                ("Índice de conectividade",
                 utils.fmt_number(ci["connectivity_index"] * 100, 1) + " %"),
                ("Criticidade resultante", ci["criticality"].upper()),
            ])))

    # 16. Custo social
    if social:
        parts.append(_section("Custo social preliminar", _table(
            ["Indicador", "Valor"],
            [
                ("Pessoas afetadas", utils.fmt_int(social["pessoas_afetadas"])),
                ("Atraso médio (min)", utils.fmt_number(social["atraso_min"], 1)),
                ("Horas perdidas (evento)", utils.fmt_number(social["horas_perdidas"], 1)),
                ("Custo por evento (R$)", utils.fmt_number(social["custo_evento"], 2)),
                ("Custo anual estimado (R$)", utils.fmt_number(social["custo_anual"], 2)),
            ])))
        parts.append('<p class="rep-note">O custo social é estimativo e '
                     "exploratório, não substitui estudo econômico ou EVTEA.</p>")

    # 17-19. Limitações / recomendações / aviso
    parts.append(_section("Limitações", _LIMITATIONS_HTML))
    parts.append(_section("Recomendações preliminares", _RECOMMENDATIONS_HTML))
    parts.append(f'<div class="rep-disclaimer">{_esc(utils.METHOD_DISCLAIMER)}</div>')

    parts.append("</body></html>")
    return "".join(parts)


def _section(title: str, body_html: str) -> str:
    return f'<section><h2>{_esc(title)}</h2>{body_html}</section>'


def _cover(study: dict, for_pdf: bool = False) -> str:
    if for_pdf:
        # Capa enxuta para PDF: faixa sólida + tabela de identificação legível
        banner = (
            f'<div class="rep-cover">'
            f'<div class="rep-mark">SIMCIV-Mob</div>'
            f'<h1>{_esc(utils.APP_NAME)}</h1>'
            f'<div class="rep-sub">{_esc(utils.APP_SUBTITLE)}</div>'
            f"</div>"
        )
        id_table = _table(
            ["Campo", "Valor"],
            [
                ("Estudo", study.get("name")),
                ("Local", f"{study.get('city', '—')} / {study.get('uf', '')}"),
                ("Data", study.get("date")),
                ("Disciplina", utils.DISCIPLINE),
                ("Autoria", f"{utils.AUTHOR} — {utils.AUTHOR_EMAIL}"),
                ("Instituição", utils.INSTITUTION),
            ])
        return (banner + _section("Identificação", id_table)
                + '<div style="page-break-after: always;"></div>')

    return f"""
    <div class="rep-cover">
        <div class="rep-mark">SIMCIV-Mob</div>
        <h1>{_esc(utils.APP_NAME)}</h1>
        <p class="rep-sub">{_esc(utils.APP_SUBTITLE)}</p>
        <div class="rep-cover-block">
            <p><b>Estudo:</b> {_esc(study.get('name'))}</p>
            <p><b>Local:</b> {_esc(study.get('city'))} / {_esc(study.get('uf'))}</p>
            <p><b>Data:</b> {_esc(study.get('date'))}</p>
        </div>
        <div class="rep-cover-block">
            <p><b>Disciplina:</b> {_esc(utils.DISCIPLINE)}</p>
            <p><b>Autoria:</b> {_esc(utils.AUTHOR)} ({_esc(utils.AUTHOR_EMAIL)})</p>
            <p><b>Instituição:</b> {_esc(utils.INSTITUTION)}</p>
        </div>
    </div>
    """


_LIMITATIONS_HTML = """
<ul>
  <li>Levantamentos de campo e contagens volumétricas não realizados.</li>
  <li>Sem pesquisa origem-destino, estudos hidrológicos/hidráulicos ou
      mapeamento oficial de áreas de risco.</li>
  <li>Sem plano municipal de contingência, modelagem microscópica de tráfego,
      EVTEA, projeto executivo ou análise oficial da Defesa Civil.</li>
  <li>Resultados dependem da qualidade dos dados, da cobertura do OpenStreetMap,
      dos parâmetros adotados e das hipóteses de bloqueio/penalização.</li>
</ul>
"""

_RECOMMENDATIONS_HTML = """
<ul>
  <li>Validar as vias críticas identificadas com inspeção de campo.</li>
  <li>Priorizar intervenções nos pares O-D que perdem acesso a equipamentos
      essenciais (hospitais, abrigos, Defesa Civil).</li>
  <li>Refinar parâmetros de velocidade e penalização com dados locais.</li>
  <li>Considerar cenários de contingência para os bloqueios de maior impacto.</li>
</ul>
"""


def _html_head(for_pdf: bool = False) -> str:
    if for_pdf:
        # Estilo conservador e legível para xhtml2pdf: sem gradiente, sem rgba,
        # cores sólidas em hex, fontes em pt, espaçamento compacto.
        return f"""<!DOCTYPE html><html lang="pt-br"><head><meta charset="utf-8">
    <title>Relatório SIMCIV-Mob</title><style>
    @page {{ size: A4; margin: 1.6cm; }}
    body {{ font-family: Helvetica, Arial, sans-serif; color: {PALETTE['text']};
            font-size: 10pt; line-height: 1.4; }}
    .rep-cover {{ background-color: {PALETTE['base']}; color: #ffffff;
            padding: 22px 22px; margin-bottom: 16px; }}
    .rep-mark {{ font-size: 12pt; font-weight: bold; color: {PALETTE['amber']}; }}
    .rep-cover h1 {{ margin: 6px 0 2px 0; font-size: 22pt; color: #ffffff; }}
    .rep-sub {{ font-size: 10.5pt; color: #ffffff; }}
    section {{ margin: 12px 0; }}
    h2 {{ color: {PALETTE['base']}; font-size: 13pt;
          border-bottom: 2px solid {PALETTE['amber']}; padding-bottom: 2px; }}
    .rep-table {{ border-collapse: collapse; width: 100%; font-size: 9pt;
          margin-top: 6px; }}
    .rep-table th {{ background-color: {PALETTE['base']}; color: #ffffff;
          text-align: left; padding: 5px 8px; }}
    .rep-table td {{ border-bottom: 1px solid #D9DEE3; padding: 5px 8px; }}
    .rep-disclaimer {{ background-color: #FFF6E6; padding: 10px 12px;
          font-size: 9pt; color: #7A5300; }}
    .rep-note {{ font-size: 8.5pt; color: {PALETTE['text_soft']}; }}
    ul {{ font-size: 9pt; margin: 4px 0; }}
    </style></head><body>"""

    # versão para navegador (pré-visualização e download HTML): visual rico
    return f"""<!DOCTYPE html><html lang="pt-br"><head><meta charset="utf-8">
    <title>Relatório SIMCIV-Mob</title><style>
    body {{ font-family: 'Segoe UI', Arial, sans-serif; color: {PALETTE['text']};
            margin: 0; padding: 0 32px 40px; background: #fff; }}
    .rep-cover {{ background: linear-gradient(120deg, {PALETTE['base']}, {PALETTE['base_light']});
            color: #fff; padding: 48px 32px; border-radius: 0 0 14px 14px;
            margin: 0 -32px 28px; }}
    .rep-mark {{ font-size: 22px; font-weight: 800; opacity: .85; }}
    .rep-cover h1 {{ margin: 8px 0 2px; font-size: 34px; }}
    .rep-sub {{ font-size: 15px; opacity: .9; }}
    .rep-cover-block {{ background: rgba(255,255,255,.1); padding: 12px 16px;
            border-radius: 8px; margin-top: 14px; font-size: 13px; }}
    section {{ margin: 22px 0; }}
    h2 {{ color: {PALETTE['base']}; border-bottom: 3px solid {PALETTE['amber']};
          display: inline-block; padding-bottom: 3px; }}
    .rep-table {{ border-collapse: collapse; width: 100%; font-size: 13px;
          margin-top: 8px; }}
    .rep-table th {{ background: {PALETTE['base']}; color: #fff; text-align: left;
          padding: 6px 10px; }}
    .rep-table td {{ border-bottom: 1px solid #E1E7ED; padding: 6px 10px; }}
    .rep-disclaimer {{ background: #FFF6E6; border-left: 5px solid {PALETTE['attention']};
          padding: 12px 16px; border-radius: 8px; font-size: 13px; color: #7A5300; }}
    .rep-note {{ font-size: 12px; color: {PALETTE['text_soft']}; }}
    ul {{ font-size: 13px; }}
    </style></head><body>"""


# ----------------------------------------------------------------------------
# PDF opcional
# ----------------------------------------------------------------------------
def _html_to_pdf(html_str: str) -> Optional[bytes]:
    try:
        from xhtml2pdf import pisa
        import io
        out = io.BytesIO()
        result = pisa.CreatePDF(src=html_str, dest=out, encoding="utf-8")
        if result.err:
            return None
        return out.getvalue()
    except Exception:
        return None


# ----------------------------------------------------------------------------
# Tela
# ----------------------------------------------------------------------------
def render() -> None:
    ui_theme.page_title("Relatório", kicker="Etapa 10 · Documentação")

    if not validation.guard("relatorio"):
        return

    st.markdown(
        "Gere o relatório do estudo com identificação acadêmica, indicadores, "
        "vias críticas, pares mais afetados, limitações e recomendações."
    )

    if not st.session_state.get("impact_results"):
        validation.msg_info(
            "Sem simulação de impacto: o relatório incluirá apenas o "
            "cenário-base. Execute a simulação para um relatório completo."
        )

    if st.button("📄 Gerar relatório", type="primary"):
        with st.spinner("Gerando relatório (PDF e HTML)..."):
            st.session_state["_report_html"] = build_html(for_pdf=False)
            st.session_state["_report_pdf"] = _html_to_pdf(build_html(for_pdf=True))
        if st.session_state["_report_pdf"]:
            validation.msg_success("Relatório gerado. Baixe o PDF abaixo.")
        else:
            validation.msg_pending(
                "PDF não pôde ser gerado neste ambiente; o HTML está disponível "
                "(use Imprimir → Salvar como PDF)."
            )

    html_str = st.session_state.get("_report_html")
    pdf = st.session_state.get("_report_pdf")
    if html_str:
        fname = _report_filename()
        c1, c2 = st.columns(2)
        if pdf:
            c1.download_button(
                "⬇️ Baixar relatório (PDF)", data=pdf,
                file_name=f"{fname}.pdf", mime="application/pdf",
                type="primary", use_container_width=True)
        else:
            c1.button("PDF indisponível", disabled=True, use_container_width=True)
        c2.download_button(
            "⬇️ Baixar relatório (HTML)", data=html_str.encode("utf-8"),
            file_name=f"{fname}.html", mime="text/html",
            use_container_width=True)

        with st.expander("Pré-visualizar relatório", expanded=True):
            st.components.v1.html(html_str, height=700, scrolling=True)


def _report_filename() -> str:
    study = st.session_state.get("study") or {}
    city = (study.get("city") or "estudo").lower()
    safe = "".join(c if c.isalnum() else "_" for c in city).strip("_")
    return f"relatorio_simciv_mob_{safe or 'estudo'}"
