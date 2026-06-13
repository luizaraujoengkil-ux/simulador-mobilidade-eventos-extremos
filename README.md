# SIMCIV-Mob
**Simulador de Impactos Climáticos e Interdições Viárias na Mobilidade Urbana**

Ferramenta exploratória para análise de **acessibilidade, conectividade e
tempos de deslocamento** diante de chuvas extremas, alagamentos, deslizamentos
e bloqueios viários em redes urbanas.

> Disciplina: *Problemas Especiais — Ciência de Dados e Aprendizado Profundo
> Aplicados aos Transportes*
> Autoria: **Pedro Paulo Ferreira Peron** — pedro.ferreira@ime.eb.br
> Instituição: **Instituto Militar de Engenharia – IME**
> Aplicação inicial: **Juiz de Fora/MG** (a ferramenta é genérica).

---

## 1. Como instalar

Requer **Python 3.10+** (testado em 3.12).

```bash
# 1. (recomendado) criar e ativar um ambiente virtual
python -m venv .venv
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Linux/macOS:
# source .venv/bin/activate

# 2. instalar dependências
pip install -r requirements.txt
```

### Instalação mínima (sem OSMnx)
Se a instalação do `osmnx`/`geopandas` falhar no seu ambiente, instale apenas
o núcleo — o app funciona com a **rede sintética de teste** e **importação de
GeoJSON**:

```bash
pip install streamlit pandas numpy networkx folium streamlit-folium plotly branca
```

## 2. Como rodar localmente

```bash
streamlit run app.py
```

O navegador abrirá em `http://localhost:8501`.

## 3. Como testar com Juiz de Fora

Na **tela inicial**, clique em **"🧪 Exemplo de Juiz de Fora"**. Isso carrega:
- um estudo pré-configurado;
- uma **rede sintética** ao redor do centro (funciona offline);
- 6 pontos estratégicos (centro, hospital, bairro, área de risco, abrigo,
  Defesa Civil);
- 4 eventos (alagamento, deslizamento, ponte interditada, bloqueio parcial).

Depois:
1. vá em **Cenário-base** → *Calcular cenário-base*;
2. vá em **Simular impacto** → *Simular impacto*;
3. veja **Comparação antes/depois** (tabela, gráficos, mapa);
4. teste **Contingência** e gere o **Relatório**.

Para usar **dados reais do OpenStreetMap**, vá em **Rede viária** e escolha
"Baixar do OpenStreetMap por nome da cidade" (ex.: *Juiz de Fora, Minas Gerais,
Brasil*) — requer `osmnx` instalado e conexão à internet.

## 4. Estrutura do projeto

```
simciv_mob/
├── app.py                 # ponto de entrada (navegação + roteamento)
├── requirements.txt
├── README.md
├── assets/styles.css      # tema institucional
├── data/
│   ├── examples/          # exemplo de Juiz de Fora
│   ├── uploads/ exports/ cache/
├── docs/                  # metodologia, limitações, manual
├── modules/
│   ├── utils.py           # constantes, paleta, helpers, session_state
│   ├── ui_theme.py        # tema, cabeçalho, trilha de progresso, cards
│   ├── validation.py      # validações obrigatórias e mensagens
│   ├── study_setup.py     # novo estudo
│   ├── area_selector.py   # área de análise
│   ├── network_loader.py  # OSMnx / GeoJSON / rede sintética
│   ├── network_processing.py  # grafo, velocidades, tempos
│   ├── strategic_points.py    # pontos e pares O-D
│   ├── baseline.py        # roteamento + cenário-base
│   ├── events.py          # eventos extremos
│   ├── simulation.py      # cenário impactado
│   ├── comparison.py      # antes/depois
│   ├── contingency.py     # cenários de contingência
│   ├── social_cost.py     # custo social preliminar
│   ├── maps.py            # mapas Folium
│   └── report_generator.py    # relatório HTML/PDF
└── outputs/               # mapas, relatórios, cenários
```

## 5. Limitações
Ferramenta **exploratória e preliminar**. Os resultados não substituem
levantamentos de campo, contagens volumétricas, pesquisas O-D, estudos
hidrológicos/hidráulicos, mapeamento oficial de risco, planos de contingência,
microssimulação de tráfego, EVTEA, projeto executivo ou análise oficial da
Defesa Civil. Veja [docs/limitacoes.md](docs/limitacoes.md).

## 6. Próximos passos sugeridos
- Análise de centralidade da rede (betweenness) para vias críticas.
- Acessibilidade por isócronas a hospitais/abrigos.
- Importação de KML/KMZ e shapefile (zip) com `geopandas`/`fiona`.
- Comparação multicenários salvos e dashboard avançado.
- Inserção de eventos por clique no mapa (captura de coordenadas).
