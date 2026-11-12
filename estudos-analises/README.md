# Estudos e análises + o template do relatório de segmentação

Esta pasta guarda o que não é tabela de dados: o **texto-fonte** do Customer Segmentation Report
e o memorial técnico. O relatório gerado **não fica aqui**: sai em
`artefatos/customer_segmentation_report.html`, junto das páginas do ouro.

| Arquivo | O que é |
|---|---|
| `customer_segmentation_report.template.html` | texto do relatório, com os `{{placeholders}}` |
| `memorial_tecnico.html` | memorial técnico, gerado por `notebooks/memorial_tecnico.py` |

O produto do relatório é `artefatos/customer_segmentation_report.html` (sem número, porque a
numeração de `artefatos/` é das páginas de análise do ouro), gerado por
`notebooks/relatorio_segmentacao.py`. Por isso os links do template são para as páginas **irmãs**
desse diretório (`00_historia_da_eda.html`, `04_segmentos.html`), não `../artefatos/`.

## Customer Segmentation Report: como atualizar

O relatório é gerado, não escrito à mão. São três peças:

| Peça | Papel |
|---|---|
| `estudos-analises/customer_segmentation_report.template.html` | **fonte do texto**: a redação, os cartões de persona, as hipóteses e as ofertas moram aqui, com `{{placeholders}}` onde entra número |
| `notebooks/relatorio_segmentacao.py` | calcula os números do ouro, monta as barras, os eixos e a matriz do cruzamento, confere as conclusões e escreve o HTML |
| `artefatos/customer_segmentation_report.html` | **produto**: o que se abre e se envia. Não editar à mão — a próxima execução sobrescreve |

Ciclo, a partir da raiz do repo (depois da prata, do ouro e de `conciliacao_segmentos.py`):

```bash
.venv/bin/python notebooks/relatorio_segmentacao.py     # template + ouro -> artefatos/customer_segmentation_report.html
.venv/bin/python notebooks/confere_relatorio.py         # recalcula e procura cada número no HTML
```

Para mudar texto, tom ou uma oferta: edite o **template** e rode o gerador. Para mudar um número
que vem de regra nova: mude o notebook de ouro (e registre no `decisoes.md`); o relatório acompanha.

### O que é dinâmico

Todos os números de base, persona, churn, conciliação, pesquisa e cobrança; as larguras das
barras, os rótulos `aria-label`, as marcas dos eixos e as escalas (com conferência de que os
valores cabem); a matriz do cruzamento L × N (contagens, taxas, totais, células em destaque);
o destaque de ação imediata, calculado pelo critério declarado na seção 06 (1,5 × a média de
saída em 60 dias ou o maior volume esperado), não escolhido no código.

Também saem do ouro, com a população escrita no texto: os números que antes estavam fixos no
template — Parados em 31/07 (560), "2 vezes por semana" dos Ativos ao ar livre e dos de
ambiente fechado (mediana de treinos), anos de casa dos Veteranos (4,8) e a fatia da loja nas
saídas de 2026 (66,6%). A falha de pagamento por método usa o denominador de **período** (pagantes
ativas em algum dia de jan–set/26, na prata `assinaturas`), por plano × método — não o estoque de
30/09: no mensal, cartão 10,7 e os outros métodos 2,1 a 3,6. O GPS usa a população de 31/07,
segmento Ativos ao ar livre, plano mensal e `pct_ar_livre > 0` (quem treinou ao ar livre): 11,8%
com falha × 16,6% sem.

### O que continua fixo

**Decisão editorial** (não é número de dado): a redação, a ordem das personas, as hipóteses de
driver, as ofertas, o critério de 1,5 × a média e as constantes de negócio declaradas em
`CONSTANTES` no notebook, cada uma com a fonte (prazos do guia, datas do enunciado). Preços e
datas citados na prosa (R$ 34,90 → R$ 39,90 em 01/03/26; ago–set/2026; jan–set/2026;
01/08–29/09) são texto: se o corte ou a política mudar, a redação precisa ser revista à mão.

Nenhuma pendência de número: os dois casos que ficavam fixos no texto (falha de pagamento por
método e GPS) passaram a sair do ouro com a população e o denominador declarados na prosa. O
gerador não imprime mais pendências; imprime os valores que calculou.

### Quando o gerador se recusa a rodar

Ele para, sem escrever o HTML, com a instrução de revisão, em oito casos:

1. **conclusão qualitativa obsoleta** — 27 frases do texto são conferidas contra o ouro (maior
   taxa, maior volume, 100% anual em Parados, involuntária estável, mensal acima do anual,
   prioridade igual ao critério da seção 06…). O erro diz qual frase do template rever;
2. **placeholder sem métrica** — texto novo que usa um `{{nome}}` que o notebook não calcula;
3. **cruzamento L × N que deixou de ser um para um** (decisão X1);
4. **valor de gráfico fora da escala do eixo** (as barras ficariam cortadas);
5. **corte dos dados diferente** do que o texto descreve (datas de referência ou janela do churn);
6. **direção do AUC do treino trocada** — a narrativa "quem treina pouco não renova" depende de
   AUC < 0,5 na base do anual que vence e entre quem estava com a renovação ligada;
7. **população de GPS vazia** — sem o grupo com falha ou sem o grupo sem falha na base de 31/07
   (Ativos ao ar livre, mensal, com treino ao ar livre);
8. **fim da assinatura sem evento de decisão** — se algum fim do período não tiver decisão em L,
   a frase "a decisão antecipa o fim" deixa de valer.

Silhuetas e Rand em reamostras **não são constantes**: saem de `notebooks/_metricas_segmentacao.py`,
helper que os dois notebooks de ouro e o relatório chamam, para o número publicado ser o mesmo que
o ouro calculou (regra em L5/N5: z-score — com `log1p` nas contagens do k-means de 9 —, k-means com
`n_init` e semente declarados, silhueta na base inteira no de 4 variáveis e em amostra de 5.000 no
de 9, Rand ajustado em 10 reamostras com reposição). Na última execução: 0,43 e 0,24 de silhueta e
Rand médio 0,999 (mínimo 0,998). O helper guarda a reprodução — o k-means refeito tem de devolver
exatamente a coluna `segmento` do ouro (Rand = 1) — e o texto depende de dois limiares: o gerador
para se a silhueta deixar de ser "estrutura fraca" (≥ 0,50) ou se o Rand médio cair abaixo de 0,90.
