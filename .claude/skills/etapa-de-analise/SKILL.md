---
name: etapa-de-analise
description: Ciclo de uma etapa de análise do case Vitaliza na camada ouro - definir a métrica conferindo o glossário oficial, gerar a tabela de ouro e a página em artefatos/, conferir com os números do enunciado, apresentar ao grupo e registrar. Use ao fazer qualquer análise, gráfico, EDA, segmentação, AUC/correlação, modelo, ROI ou artefato de entrega, e sempre que alguém pedir "a próxima análise", "um gráfico", "o que está correlacionado com churn" ou algo para a entrega da semana 5 ou 10.
---

# Etapa de análise

A análise anda **uma etapa por vez**: gera, mostra, discute com a pessoa, registra, e só
então parte para a próxima. Não emende três análises seguidas para mostrar no fim: a
discussão de uma etapa muda a seguinte.

Cada etapa produz três coisas, no mesmo commit:

| Peça | Onde | Vai pro git? |
|---|---|---|
| Tabela de ouro | `dados/3.ouro/<tabela>.csv`, gerada por `notebooks/<tabela>_ouro.py` | não (recria rodando) |
| Página com os gráficos | `artefatos/NN_<tabela>.html`, gerada pelo mesmo notebook | **sim**: o grupo abre sem rodar nada |
| Definições e números de referência | seção própria no `decisoes.md` | sim |

`NN` é a ordem da etapa (`01_churn_mensal`, `02_...`). Páginas de apoio que não são ouro
(ex.: visão da bronze) usam `00x_`.

## 1. Defina a métrica antes de calcular

- **Confira a definição oficial primeiro**: o glossário e o texto do enunciado (ver
  "Fontes oficiais" no `AGENTS.md`) e as definições já registradas no `decisoes.md`. Se a
  métrica tem definição oficial, use exatamente ela, com o mesmo nome. Se o grupo precisa
  de uma variação (ex.: taxa de não renovação do anual), dê **outro nome** e registre por que
  difere, para não haver dois "churn" com números diferentes.
- Se o enunciado dá números para a métrica, eles viram **conferência no notebook**
  (`assert`): o notebook para se a regra deixar de reproduzi-los. Exemplo:
  `churn_mensal_ouro.py` confere 8.540 ativos em jan/25, 8,1% em abr/26 e as médias de 5,6% e
  6,6%.
- Toda conta de R$ parte da seção 03 do enunciado. Premissa que o enunciado não dá é
  premissa **do grupo** e entra em "Premissas gerais" do `decisoes.md` dizendo isso.
- Variável de modelo só usa informação até a data de referência (nunca depois do corte,
  30/09/2026); use os `flag_*` de corte da prata.

## 2. Gere tabela e página

- O notebook segue a skill `camadas-de-dados` (docstring com as regras, roda do zero,
  lê só da prata). Rode com `.venv/bin/python notebooks/<tabela>_ouro.py`.
- A página sai de `notebooks/_artefato.py`:

  ```python
  from _artefato import CORES, Pagina, eixo_meses, layout_padrao, linha
  p = Pagina("02 · Título", "A pergunta que a página responde.", "fonte: `dados/3.ouro/x.csv` (decisão Gn)")
  p.texto("**Regra.** ...")          # parágrafos; linhas com "- " viram lista
  p.figura(fig, "legenda")           # figura plotly com layout_padrao(fig, ...)
  p.tabela(df, "título", {"col": "{:.2f}"})
  p.salvar("02_x.html")
  ```

- Gráfico: uma pergunta por gráfico; um eixo y só (nada de eixo duplo); cores de `CORES`
  na ordem, a mesma cor para o mesmo segmento em toda a página; meses em português com
  `eixo_meses`; marcos do negócio (reajuste 01/03/26, pico de GPS mai–jun/26, campanha
  10/08/26) como linha ou faixa quando a série passa por eles.
- Antes de mostrar, **abra a página e olhe** (`browsin check artefatos/NN_x.html`): erro de
  console, rótulo sobreposto, mês incompleto puxando a série.

## 3. Escreva o texto da página

- **A regra vem antes do número**: qual tabela, filtro, corte e definição.
- Achado em frase com número ("o mensal foi de 8,97% para 10,83%"), não adjetivo.
- **Cruzamento aponta suspeito, não prova causa.** Escreva "coincide com", "concentra-se
  em", nunca "causou", até haver teste (ex.: comparação com controle sorteado).
- Diga o limite de cada achado (viés de sobrevivência antes de jul/24, amostra só do site
  na pesquisa de saída…).
- Termine com "Perguntas para a próxima etapa": é a pauta da discussão.
- O texto descreve o produto, não o processo ("a série começa em ago/24 porque…", não
  "primeiro tentamos…").

## 4. Apresente e espere

Mostre à pessoa: o que foi gerado, a conferência com o enunciado, três a cinco achados com
número, e as opções de próxima etapa com uma recomendação. **Pare e espere a discussão.**

## 5. Registre o que a discussão decidiu

- Definições, filtros e números de referência no `decisoes.md` (skill `registrar-decisao`),
  numa seção por etapa: `## <Nome> (ouro)`, prefixo de ID livre anotado no topo.
- Perguntas que ficaram abertas em "Em aberto".
- Tabela nova em "Tabelas prontas" do `AGENTS.md` e no `README.md`.
- Achado que muda a leitura de outros dados vira "Armadilha conhecida" no `AGENTS.md`.
- Suba com a skill `git-do-grupo`: notebook + página + `decisoes.md` + READMEs juntos.

## Para onde cada etapa vai

As etapas alimentam as entregas do guia do Módulo 2 (resumo e rubrica no `AGENTS.md`):

| Entrega | O que precisa sair das etapas |
|---|---|
| Semana 5, EDA (tecnologia) | código + gráficos de churn, padrões e correlações com a saída, base empírica da segmentação, mini deck |
| Semana 5, Segmentation Report (negócios) | 3–4 segmentos com persona, hipótese de driver de churn por segmento, prioridade (imediata × monitorar), gráficos da EDA, limitações |
| Semana 10, modelo (tecnologia) | base de modelagem sem vazamento, métricas (AUC, matriz de confusão), importância de variáveis, escolha entre precisão e recall |
| Semana 10, plano e ROI (negócios) | segmento → risco → oferta → mensagem na mesma linha; ROI com premissas da seção 03 + custo de tokens; KPIs (retenção, uplift, payback) |

Ao propor a próxima etapa, diga qual linha desta tabela ela alimenta.
