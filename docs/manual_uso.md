# Manual de uso — SIMCIV-Mob

## Fluxo recomendado
1. **Início** — leia a apresentação e, se quiser, carregue o exemplo de
   Juiz de Fora/MG.
2. **Novo estudo** — preencha nome, cidade, responsável e tipo de análise.
3. **Área de análise** — defina o recorte (nome do lugar, ponto + raio etc.).
4. **Rede viária** — baixe do OpenStreetMap, importe GeoJSON ou gere a rede
   sintética de teste.
5. **Pontos estratégicos** — cadastre origens/destinos (bairros, hospitais,
   abrigos, Defesa Civil...) e monte os pares O-D.
6. **Cenário-base** — calcule as rotas de referência.
7. **Eventos extremos** — cadastre alagamentos, deslizamentos, interdições.
8. **Simular impacto** — recalcule e veja os indicadores e a criticidade.
9. **Comparação antes/depois** — tabela O-D, gráficos e mapas.
10. **Contingência** — teste ações de resposta e meça a recuperação.
11. **Relatório** — gere o documento HTML/PDF do estudo.
12. **Metodologia e limitações** — consulte os fundamentos e ressalvas.

## Dicas
- Comece com um **recorte pequeno** (1–5 km) para testes rápidos.
- Se o OSMnx não estiver instalado ou a coleta falhar, use a **rede sintética
  de teste** para percorrer todo o fluxo.
- Mantenha os pontos a poucas centenas de metros de vias da rede para um bom
  encaixe (*snap*) nos nós.
- A trilha de progresso na barra lateral indica o estado de cada etapa.

## Formato CSV de pontos
```
point_id,name,type,lat,lon,population,weight,priority,notes
P001,Centro,centro,-21.7615,-43.3500,5000,1,alta,
```

## Salvar / carregar estudo
Use os botões na tela inicial. O pacote salvo (JSON) guarda estudo, área,
pontos, pares O-D, eventos e parâmetros. **A rede viária deve ser recarregada/
regenerada** após o carregamento.
