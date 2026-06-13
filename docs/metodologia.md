# Metodologia — SIMCIV-Mob

## Representação da rede como grafo
A rede viária é representada como um **grafo direcionado com múltiplas arestas**
(`networkx.MultiDiGraph`), no qual:

- **nós** representam interseções ou pontos de conexão da rede;
- **arestas** representam trechos viários (ruas, avenidas, rodovias, pontes,
  túneis).

Cada aresta possui atributos como **comprimento** (m), **velocidade estimada**
(km/h), **tempo de percurso** (s), **tipo de via** (`highway`), **status** e
**capacidade relativa**.

## Origem dos dados
A rede pode ser obtida de três formas:

1. **OpenStreetMap via OSMnx** — por nome de cidade ou por ponto + raio;
2. **Importação de GeoJSON** com geometrias de linha (`LineString`);
3. **Rede sintética de teste** — malha em grade gerada localmente, útil para
   demonstração e testes offline (não depende de internet).

Quando a rede não traz velocidade, esta é **estimada por tipo de via** a partir
de valores padrão editáveis na interface (ex.: *primary* = 50 km/h,
*residential* = 25 km/h). O **tempo de percurso** é então calculado por
`tempo = comprimento / velocidade`.

## Cenário-base
No cenário-base, calculam-se os **menores caminhos** entre os pares
origem-destino (O-D) selecionados, usando o **tempo de percurso** como peso
(algoritmo de Dijkstra). São registrados tempo, distância, caminho e a
conectividade de cada par, além de indicadores agregados (tempo médio,
distância média, vias mais utilizadas, acessibilidade a equipamentos
essenciais).

## Aplicação de bloqueios e penalizações
Os eventos extremos alteram a rede de três formas:

- **Bloqueio total** — a aresta é removida do grafo de roteamento;
- **Bloqueio parcial** — a velocidade é reduzida por um fator, aumentando o
  tempo de percurso (`tempo_novo = tempo_base / fator`);
- **Atraso** — adiciona-se um tempo fixo (minutos) ao trecho.

As **arestas afetadas** por um evento são aquelas cujo ponto médio está dentro
do **raio de afetação** definido para o evento.

## Comparação antes/depois
Para cada par O-D comparam-se os tempos:

```
ΔT_ij = T_evento_ij − T_base_ij
G_ij  = (ΔT_ij / T_base_ij) × 100
```

Se não há caminho no cenário impactado, o par é marcado como **desconectado**
(perda de conectividade / possível isolamento). O sistema nunca exibe `NaN`:
ausência de rota e infinito são tratados com mensagens claras.

## Acessibilidade e conectividade
- **Acessibilidade** a equipamentos essenciais: tempo até o hospital/abrigo/
  Defesa Civil mais próximo, por origem.
- **Índice de conectividade**: razão entre pares conectados depois e antes do
  evento.

## Custo social preliminar
```
pessoas_afetadas = fluxo_afetado × ocupacao_media
horas_perdidas   = pessoas_afetadas × atraso_min / 60
custo_evento     = horas_perdidas × valor_hora
custo_anual      = custo_evento × frequencia_anual
```
Na ausência de fluxo, admite-se aproximação por população/peso (com aviso).

## Limitações
Ver [limitacoes.md](limitacoes.md).
