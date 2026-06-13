"""
manual.py
=========
Gera o Manual de Utilização do SIMCIV-Mob em HTML/PDF.

Reaproveita o conversor de PDF do report_generator (xhtml2pdf) e usa um
estilo conservador e legível para impressão.
"""

from __future__ import annotations

import html

from . import report_generator, utils

PAGEBREAK = '<div style="page-break-after: always;"></div>'


def _esc(v) -> str:
    return html.escape(str(v if v is not None else ""))


def _head() -> str:
    # CSS conservador (compatível com xhtml2pdf): cores sólidas, fontes em pt.
    return """<!DOCTYPE html><html lang="pt-br"><head><meta charset="utf-8">
<title>Manual SIMCIV-Mob</title><style>
@page { size: A4; margin: 1.6cm; }
body { font-family: Helvetica, Arial, sans-serif; color: #1A2733; font-size: 10pt; line-height: 1.45; }
.cover { background-color: #0F2C44; color: #ffffff; padding: 30px 24px; margin-bottom: 18px; }
.cover .mark { font-size: 12pt; font-weight: bold; color: #F5B041; }
.cover h1 { font-size: 24pt; margin: 10px 0 2px 0; color: #ffffff; }
.cover .sub { font-size: 11pt; color: #ffffff; }
.cover .meta { font-size: 9.5pt; color: #ffffff; margin-top: 14px; }
h2 { color: #0F2C44; font-size: 14pt; border-bottom: 2px solid #F5B041; padding-bottom: 2px; margin-top: 20px; }
h3 { color: #1B4A6B; font-size: 11.5pt; margin: 14px 0 2px 0; }
p { margin: 5px 0; }
ul, ol { margin: 5px 0; padding-left: 18px; }
li { margin: 2px 0; }
.lead { font-size: 10.5pt; color: #1A2733; }
.note { background-color: #FFF6E6; padding: 10px 12px; font-size: 9pt; color: #7A5300; margin: 8px 0; }
.tip { background-color: #EAF4EC; padding: 8px 12px; font-size: 9pt; color: #1E5631; margin: 8px 0; }
table { border-collapse: collapse; width: 100%; font-size: 9pt; margin-top: 6px; }
th { background-color: #0F2C44; color: #ffffff; text-align: left; padding: 5px 8px; }
td { border-bottom: 1px solid #D9DEE3; padding: 5px 8px; vertical-align: top; }
.kicker { color: #52606D; font-size: 8.5pt; letter-spacing: 1px; text-transform: uppercase; font-weight: bold; }
</style></head><body>"""


def _table(headers, rows) -> str:
    th = "".join(f"<th>{_esc(h)}</th>" for h in headers)
    body = ""
    for r in rows:
        body += "<tr>" + "".join(f"<td>{_esc(c)}</td>" for c in r) + "</tr>"
    return f"<table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>"


def _cover() -> str:
    return f"""
    <div class="cover">
        <div class="mark">SIMCIV-Mob</div>
        <h1>Manual de Utilização</h1>
        <div class="sub">{_esc(utils.APP_SUBTITLE)}</div>
        <div class="meta">
            Disciplina: {_esc(utils.DISCIPLINE)}<br>
            Autoria: {_esc(utils.AUTHOR)} — {_esc(utils.AUTHOR_EMAIL)}<br>
            Instituição: {_esc(utils.INSTITUTION)}<br>
            Aplicação inicial: Juiz de Fora/MG
        </div>
    </div>
    """


def build_manual_html() -> str:
    p = [_head(), _cover()]

    # 1. Apresentação
    p.append("<h2>1. Apresentação</h2>")
    p.append(f'<p class="lead">{_esc(utils.APP_DESCRIPTION)}</p>')
    p.append(
        "<p>O SIMCIV-Mob permite avaliar como chuvas extremas, alagamentos, "
        "deslizamentos e interdições viárias afetam a <b>acessibilidade</b>, os "
        "<b>tempos de deslocamento</b> e a <b>conectividade</b> da rede urbana. "
        "A lógica é semelhante a uma análise de resiliência de rede, aplicada à "
        "mobilidade sob eventos extremos.</p>")
    p.append(
        '<div class="note"><b>Caráter exploratório:</b> os resultados não '
        "substituem levantamento de campo, estudos hidrológicos/hidráulicos, "
        "microssimulação de tráfego, plano oficial de contingência ou análise "
        "oficial da Defesa Civil.</div>")

    # 2. Conceito central
    p.append("<h2>2. Como o simulador funciona</h2>")
    p.append(
        "<p>A rede viária é representada como um <b>grafo</b>: os <b>nós</b> são "
        "interseções/pontos da rede e as <b>arestas</b> são trechos de via, com "
        "atributos de comprimento, velocidade estimada e tempo de percurso.</p>")
    p.append("<ol>"
             "<li><b>Cenário-base:</b> calcula as rotas de menor tempo entre os "
             "pares origem-destino (O-D) na rede normal.</li>"
             "<li><b>Eventos:</b> alagamentos/deslizamentos/interdições removem ou "
             "penalizam trechos atingidos.</li>"
             "<li><b>Cenário impactado:</b> recalcula as rotas e compara com o "
             "cenário-base (variação de tempo, pares sem rota, vias críticas).</li>"
             "<li><b>Contingência:</b> testa ações de resposta e mede a "
             "recuperação.</li></ol>")

    # 3. Como abrir
    p.append("<h2>3. Como abrir o simulador</h2>")
    p.append(_table(["Passo", "Ação"], [
        ("1", "Instalar dependências: pip install -r requirements.txt"),
        ("2", "No terminal, na pasta do projeto: streamlit run app.py"),
        ("3", "Abrir o navegador em http://localhost:8501"),
    ]))
    p.append('<div class="tip"><b>Dica:</b> se o OpenStreetMap (OSMnx) não estiver '
             "disponível, o simulador funciona offline com a rede sintética de "
             "teste e com importação de GeoJSON.</div>")

    # 4. Visão geral da interface
    p.append("<h2>4. Visão geral da interface</h2>")
    p.append(
        "<p>À esquerda há a <b>navegação</b> entre as 12 telas e a <b>trilha de "
        "progresso</b>, que indica o estado de cada etapa por cor:</p>")
    p.append(_table(["Cor", "Significado"], [
        ("Cinza", "Etapa não iniciada"),
        ("Azul", "Etapa atual"),
        ("Verde", "Etapa concluída"),
        ("Laranja", "Etapa pendente / atenção"),
        ("Vermelho", "Etapa com erro"),
    ]))
    p.append(
        "<p>As cores também guiam a leitura dos resultados: <b>azul</b> = normal/"
        "sistema; <b>laranja</b> = atenção/parcial; <b>vermelho</b> = crítico/"
        "bloqueio; <b>verde</b> = alternativa/melhoria; <b>cinza</b> = neutro.</p>")
    p.append(PAGEBREAK)

    # 5. Guia passo a passo
    p.append("<h2>5. Guia passo a passo</h2>")

    p.append("<h3>5.1 Início</h3>")
    p.append("<p>Tela institucional. Botões principais:</p>")
    p.append("<ul>"
             "<li><b>Exemplo de Juiz de Fora</b> — carrega um estudo pronto (rede "
             "real do OSM, 6 pontos e 4 eventos) e leva à Área de análise.</li>"
             "<li><b>Abrir metodologia</b> — fundamentos e limitações.</li>"
             "<li><b>Criar novo estudo</b> — inicia um estudo do zero.</li>"
             "<li><b>Carregar estudo salvo</b> — restaura um pacote .json salvo.</li>"
             "</ul>")

    p.append("<h3>5.2 Novo estudo</h3>")
    p.append("<p>Preencha os metadados que identificam o estudo (aparecem no "
             "relatório):</p>")
    p.append(_table(["Campo", "Descrição"], [
        ("Nome do estudo", "Título do cenário analisado."),
        ("Cidade / UF / País", "Localização do estudo."),
        ("Responsável / Instituição", "Autoria."),
        ("Tipo de análise", "Chuva extrema, alagamento, interdição, evento múltiplo…"),
        ("Modo de operação", "Básico ou avançado."),
    ]))

    p.append("<h3>5.3 Área de análise</h3>")
    p.append("<p>Define o recorte espacial usado para coletar a rede. Pode ser por "
             "nome da cidade, ponto + raio ou coordenada. Um <b>mapa</b> mostra o "
             "centro e os raios de coleta e de análise.</p>")
    p.append('<div class="tip"><b>Dica:</b> comece com um raio pequeno (1–5 km). '
             "Áreas muito grandes deixam a coleta e os cálculos mais lentos.</div>")

    p.append("<h3>5.4 Rede viária</h3>")
    p.append("<p>Obtém o grafo da rede. Opções: baixar do <b>OpenStreetMap</b> "
             "(por cidade ou ponto+raio), <b>importar GeoJSON</b> ou gerar a "
             "<b>rede sintética de teste</b>. Um <b>mapa</b> exibe a cidade com a "
             "malha viária. As velocidades por tipo de via são editáveis.</p>")

    p.append("<h3>5.5 Pontos estratégicos</h3>")
    p.append("<p>Origens e destinos da análise (bairros, hospital, abrigo, Defesa "
             "Civil, área de risco…). Abas:</p>")
    p.append("<ul>"
             "<li><b>Pontos</b> — tabela e <b>mapa</b> dos pontos cadastrados.</li>"
             "<li><b>Pares O-D</b> — monta as duplas origem→destino (todos contra "
             "todos, origens→equipamentos essenciais, ou manual).</li>"
             "<li><b>Cadastrar manualmente / Importar CSV</b> — para estudos "
             "próprios.</li></ul>")
    p.append('<div class="note">É preciso pelo menos <b>2 pontos</b> e <b>1 par '
             "O-D</b> para calcular o cenário-base.</div>")

    p.append("<h3>5.6 Cenário-base</h3>")
    p.append("<p>Clique em <b>Calcular cenário-base</b>. Ele computa as rotas "
             "normais e indicadores de referência: nº de nós/arestas, extensão da "
             "rede, tempo e distância médios, pares conectados e acessibilidade a "
             "equipamentos essenciais.</p>")
    p.append(PAGEBREAK)

    p.append("<h3>5.7 Eventos extremos</h3>")
    p.append("<p>Cadastre os eventos que afetam a rede. Cada evento tem um ponto, "
             "um <b>raio de afetação</b> e um <b>tipo de impacto</b>:</p>")
    p.append(_table(["Impacto", "Efeito na rede"], [
        ("Bloqueio total", "Remove a via do roteamento (não é mais transitável)."),
        ("Bloqueio parcial", "Reduz a velocidade/capacidade (aumenta o tempo)."),
        ("Atraso", "Adiciona minutos ao tempo do trecho."),
    ]))
    p.append("<p>A aba <b>Eventos cadastrados</b> mostra a tabela e um <b>mapa</b> "
             "com cada evento (círculo colorido pelo tipo; tamanho = raio).</p>")

    p.append("<h3>5.8 Simular impacto</h3>")
    p.append("<p>Clique em <b>Simular impacto</b>. O sistema copia a rede, aplica "
             "os eventos, recalcula as rotas e compara com o cenário-base. Os "
             "cards mostram vias interditadas, pares afetados/sem rota, aumento "
             "médio de tempo, população afetada e o <b>nível de criticidade</b>:</p>")
    p.append(_table(["Nível", "Critério preliminar"], [
        ("Baixo", "Poucos pares afetados e aumento médio < 10%."),
        ("Moderado", "Aumento médio entre 10% e 30%."),
        ("Alto", "Aumento médio entre 30% e 60% ou pares desconectados."),
        ("Crítico", "Aumento > 60%, isolamento ou acesso essencial prejudicado."),
    ]))

    p.append("<h3>5.9 Comparação antes/depois</h3>")
    p.append("<p>Tabela O-D (tempo base, tempo impactado, diferença, aumento %, "
             "status), <b>gráficos</b> (antes/depois, distribuição dos atrasos, "
             "ranking, classes de impacto) e <b>mapa</b> da rede impactada. A "
             "tabela pode ser exportada em CSV. Inclui também a estimativa de "
             "<b>custo social preliminar</b>.</p>")

    p.append("<h3>5.10 Cenários de contingência</h3>")
    p.append("<p>Para cada evento escolha uma ação (manter, mitigar/remover, ou "
             "desbloqueio parcial) e recalcule. Compara <b>base × impactado × "
             "contingência</b> e mostra quantos pares foram recuperados, a redução "
             "do aumento médio e o ganho de conectividade.</p>")

    p.append("<h3>5.11 Relatório</h3>")
    p.append("<p>Gera o relatório do estudo em <b>PDF</b> e HTML, com "
             "identificação, indicadores, vias críticas, pares mais afetados, "
             "contingência, custo social, limitações e recomendações.</p>")

    p.append("<h3>5.12 Metodologia e limitações</h3>")
    p.append("<p>Fundamentos do método, manual de uso e as limitações da "
             "ferramenta.</p>")
    p.append(PAGEBREAK)

    # 6. Roteiro rápido
    p.append("<h2>6. Roteiro rápido (exemplo de Juiz de Fora)</h2>")
    p.append("<ol>"
             "<li>Início → <b>Exemplo de Juiz de Fora</b>.</li>"
             "<li>Confira a <b>Área de análise</b> (mapa) e a <b>Rede viária</b> "
             "(malha real).</li>"
             "<li>Em <b>Pontos estratégicos</b>, veja os pontos no mapa e os pares "
             "O-D.</li>"
             "<li><b>Cenário-base</b> → <i>Calcular cenário-base</i>.</li>"
             "<li><b>Eventos extremos</b> → veja os 4 eventos no mapa.</li>"
             "<li><b>Simular impacto</b> → <i>Simular impacto</i>.</li>"
             "<li><b>Comparação antes/depois</b> → analise tabela, gráficos e mapa.</li>"
             "<li>(Opcional) <b>Contingência</b> e <b>Relatório (PDF)</b>.</li></ol>")

    # 7. Dicas e solução de problemas
    p.append("<h2>7. Dicas e solução de problemas</h2>")
    p.append(_table(["Situação", "O que fazer"], [
        ("Download do OSM falhou", "Use a rede sintética de teste ou tente um raio menor / outro nome de lugar."),
        ("Pares sem rota no cenário-base", "A rede pode ter trechos desconectados; verifique o recorte e os pontos."),
        ("Ponto longe da rede", "Verifique as coordenadas ou amplie o raio de coleta (aviso aparece > 500 m)."),
        ("Mapa pesado/lento", "Reduza o raio da rede; vias muito numerosas tornam o mapa lento."),
        ("Não aparece NaN", "Ausência de rota é mostrada como 'sem rota'; nunca como NaN."),
    ]))

    # 8. Glossário
    p.append("<h2>8. Glossário</h2>")
    p.append(_table(["Termo", "Definição"], [
        ("Grafo", "Estrutura de nós e arestas que representa a rede viária."),
        ("Par O-D", "Dupla origem-destino entre a qual se calcula a rota."),
        ("Cenário-base", "Situação normal de referência, sem eventos."),
        ("Cenário impactado", "Rede após aplicar os eventos extremos."),
        ("Conectividade", "Capacidade de alcançar destinos pela rede."),
        ("Via crítica", "Trecho muito usado nas rotas e afetado por evento."),
        ("Custo social", "Estimativa do valor do tempo perdido pelos usuários."),
    ]))

    p.append('<div class="note"><b>Limitações:</b> ferramenta exploratória e '
             "preliminar; depende da qualidade dos dados, da cobertura do "
             "OpenStreetMap, dos parâmetros adotados e das hipóteses de bloqueio. "
             "Não substitui estudos técnicos oficiais.</div>")

    p.append("</body></html>")
    return "".join(p)


def build_manual_pdf():
    """Retorna os bytes do PDF do manual (ou None se a conversão falhar)."""
    return report_generator._html_to_pdf(build_manual_html())
