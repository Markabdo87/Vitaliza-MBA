"""Ouro -> ouro: segmentos_plano.csv (persona L × plano em 31/07/2026) +
artefatos/07_segmentos_por_plano.html.

Pergunta: como as personas L se distribuem por plano e como os dois sinais de saída se
comportam em cada grupo? A página é uma ponte entre a EDA e a segmentação, para a conversa
antes de decidir ações — ela não recomenda ação.

Lê somente `dados/3.ouro/segmentos.csv` e `dados/3.ouro/segmentos_kmeans.csv`. Não lê a
prata, não recalcula segmentos e não harmoniza as duas segmentações.

Regras (decisão X2 no decisoes.md):
  1. Base comum: assinantes pagos ativos em 31/07/2026 presentes nas duas tabelas de ouro,
     com a renovação não desligada em L (`renovacao != "desligada"`). Quem já desligou a
     renovação (segmento "Já desligou" em L) fica fora: `saiu_60d` é NaN porque a decisão já
     foi tomada. O estado "em carência" entra (não é desligado).
  2. Agrupamento: uma linha por (`segmento` L, `plano`), inclusive combinações com n = 0.
     Denominador: n = número de assinantes do grupo na base comum.
  3. Sinal de saída (L): `saiu_60d` de `segmentos.csv`, decisão de sair entre 01/08 e
     29/09/2026 (renovação desligada, cancelamento no site ou expiração).
  4. Sinal de término (N): `saiu_60d` de `segmentos_kmeans.csv`, fim da assinatura
     (`data_fim`) entre 01/08 e 29/09/2026. As duas definições não são a mesma coisa.
  5. Contagens e taxas: saída L = soma de `saiu_60d` L; término N = soma de `saiu_60d` N;
     taxa = 100 × contagem ÷ n. n = 0 fica com taxa vazia (NaN), não 0%.
  6. Nomes e datas: L e N usam nomes de segmentos diferentes; "Parados" existe nos dois com
     definições diferentes. A referência é 31/07/2026; a janela é 01/08–29/09/2026. L usa a
     data da decisão; N usa a data do fim da assinatura.
  7. L e N leem a mesma prata de treinos, sem filtro divergente: `atividades.parquet` traz um
     treino por (user_id, inicio_brt) e não marca registros no mesmo minuto (T12), então as
     duas segmentações usam a tabela inteira e a diferença entre elas fica nas variáveis e na
     definição de saída, não na base de treinos.
  8. Sem recomendação de ação: a página mede e descreve, não prioriza nem sugere oferta.

Limitações: o anual vence em data fixa (decisão antes do término); as taxas são associações,
não causalidade; a campanha de 10/08/2026 tratou parte da base; amostras pequenas (e n = 0)
têm taxas instáveis; as taxas são históricas, não previsões.

Pré-requisito: rodar `notebooks/segmentos_ouro.py` e `notebooks/segmentos_kmeans_ouro.py`.
Uso: .venv/bin/python notebooks/segmentos_plano_ouro.py  (a partir da raiz do repo)
"""
import sys

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from _artefato import CORES, Pagina, layout_padrao
from _ouro import OURO, RAIZ

SAIDA = OURO / "segmentos_plano.csv"
REF = "2026-07-31"
JANELA_INI = "2026-08-01"
JANELA_FIM = "2026-09-29"
ORDEM_L = ["Parados", "Ativos ao ar livre", "Ativos em ambiente fechado", "Veteranos"]
PLANOS = ["anual", "mensal"]


def ler_ouro(arquivo, colunas, notebook):
    """Lê uma tabela de ouro e para com mensagem clara se o arquivo ou uma coluna sumiu."""
    caminho = OURO / arquivo
    if not caminho.exists():
        sys.exit(f"falta {caminho.relative_to(RAIZ)}: rode .venv/bin/python notebooks/{notebook}")
    df = pd.read_csv(caminho)
    faltam = [c for c in colunas if c not in df.columns]
    if faltam:
        sys.exit(f"{arquivo} não tem as colunas {faltam}: rode notebooks/{notebook} de novo")
    return df


# --- 1. leitura e conferência das chaves ---------------------------------------------------
L = ler_ouro("segmentos.csv",
             ["data_ref", "user_id", "segmento", "saiu_60d", "renovacao", "plano"],
             "segmentos_ouro.py")
N = ler_ouro("segmentos_kmeans.csv",
             ["data_ref", "user_id", "segmento", "saiu_60d", "plano"],
             "segmentos_kmeans_ouro.py")

for nome, df in [("segmentos.csv", L), ("segmentos_kmeans.csv", N)]:
    dup = int(df.duplicated(["data_ref", "user_id"]).sum())
    if dup:
        sys.exit(f"{nome}: {dup} chaves (data_ref, user_id) duplicadas")

for ref in sorted(set(L.data_ref) | set(N.data_ref)):
    u_l = set(L.loc[L.data_ref == ref, "user_id"])
    u_n = set(N.loc[N.data_ref == ref, "user_id"])
    if u_l != u_n:
        sys.exit(f"{ref}: as duas tabelas não cobrem os mesmos user_id "
                 f"(L {len(u_l)}, N {len(u_n)})")

# --- 2. base comum e grupo ----------------------------------------------------------------
t = L[L.data_ref == REF].copy()
tn = N[N.data_ref == REF].copy()
if t.renovacao.isna().any():
    sys.exit(f"{REF}: renovacao com NaN em {int(t.renovacao.isna().sum())} linhas de L")
if not set(t.plano.unique()) <= set(PLANOS):
    sys.exit(f"{REF}: plano inesperado em L: {sorted(set(t.plano.unique()))}")

j = t[t.renovacao == "desligada"].copy()
if not j.segmento.eq("Já desligou").all():
    sys.exit("renovação desligada em L não está no segmento 'Já desligou'")
if j.saiu_60d.notna().any():
    sys.exit(f"'Já desligou' tem {int(j.saiu_60d.notna().sum())} saiu_60d não nulo; "
             "não é possível calcular a saída L desse grupo")

b = t[t.renovacao != "desligada"].merge(
    tn[["data_ref", "user_id", "segmento", "saiu_60d", "plano"]],
    on=["data_ref", "user_id"], how="inner", validate="one_to_one",
    suffixes=("_l", "_n"))
if b.empty:
    sys.exit("base comum vazia: confira segmentos.csv e segmentos_kmeans.csv")
if not (b.plano_l == b.plano_n).all():
    sys.exit("plano diverge entre L e N para os mesmos user_id")
for c in ["saiu_60d_l", "saiu_60d_n"]:
    if b[c].isna().any():
        sys.exit(f"base comum tem {int(b[c].isna().sum())} valores NaN em {c}")
if not b[["saiu_60d_l", "saiu_60d_n"]].isin([0, 1]).all().all():
    sys.exit("saiu_60d fora de 0/1 na base comum")

extras = sorted(set(b.segmento_l) - set(ORDEM_L))
if extras:
    sys.exit(f"segmento L fora da ordem conhecida: {extras}")

grade = pd.MultiIndex.from_product([ORDEM_L, PLANOS], names=["segmento_l", "plano_l"])
g = (b.groupby(["segmento_l", "plano_l"], dropna=False)
      .agg(n_assinantes=("user_id", "size"),
           saida_l=("saiu_60d_l", "sum"),
           termino_n=("saiu_60d_n", "sum"))
      .reindex(grade, fill_value=0)
      .reset_index()
      .rename(columns={"plano_l": "plano"}))
g.insert(0, "data_ref", REF)

# n = 0: taxa não é 0%, é indefinida. Evita a divisão por zero.
den = g.n_assinantes.replace(0, np.nan)
g["saida_l_pct"] = 100 * g.saida_l / den
g["termino_n_pct"] = 100 * g.termino_n / den
g = g[["data_ref", "segmento_l", "plano", "n_assinantes",
       "saida_l", "saida_l_pct", "termino_n", "termino_n_pct"]]

# --- 3. conferências de cruzamento --------------------------------------------------------
n0 = g[g.n_assinantes == 0].copy()
assert int(g.n_assinantes.sum()) == len(b)
assert int(g.saida_l.sum()) == int(b.saiu_60d_l.sum())
assert int(g.termino_n.sum()) == int(b.saiu_60d_n.sum())
assert bool((g.saida_l <= g.n_assinantes).all())
assert bool((g.termino_n <= g.n_assinantes).all())
assert bool(g.loc[g.n_assinantes == 0, "saida_l_pct"].isna().all())
assert bool(g.loc[g.n_assinantes == 0, "termino_n_pct"].isna().all())
assert bool(g.saida_l_pct.dropna().between(0, 100).all())
assert bool(g.termino_n_pct.dropna().between(0, 100).all())

print(f"{REF}: {len(t):,} linhas em L e {len(tn):,} em N · base comum {len(b):,}")
print(f"'Já desligou' (L, fora da base): {len(j):,} · saiu_60d L todo nulo: "
      f"{bool(j.saiu_60d.isna().all())}")
print("\nL × plano (base comum):")
print(pd.crosstab(b.segmento_l, b.plano_l, margins=True))
print("\nL × N (base comum):")
print(pd.crosstab(b.segmento_l, b.segmento_n, margins=True))
print("\nSaída L × término N (base comum):")
print(pd.crosstab(b.saiu_60d_l, b.saiu_60d_n, margins=True))
print("\nTaxas por persona L e plano:")
print(g.to_string(index=False))
if len(n0):
    print(f"\nn = 0: {len(n0)} grupo(s) — taxa fica vazia, não 0%:")
    print(n0[["segmento_l", "plano"]].to_string(index=False))

# --- 4. saídas ----------------------------------------------------------------------------
OURO.mkdir(parents=True, exist_ok=True)
g.to_csv(SAIDA, index=False, na_rep="")
print(f"\n{SAIDA.relative_to(RAIZ)}: {len(g)} linhas")


def br(x, d=1):
    return f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


nomes_l = ", ".join(sorted(set(t.segmento)))
nomes_n = ", ".join(sorted(set(tn.segmento)))
n_grupos = len(g)
n_com_n = int((g.n_assinantes > 0).sum())

p = Pagina(
    "07 · Persona L × plano",
    "Distribuição das personas L por plano em 31/07/2026 e os dois sinais de saída nos 60 dias "
    "seguintes. Ponte entre a EDA e a segmentação, sem recomendação de ação.",
    "fonte: `dados/3.ouro/segmentos.csv` e `dados/3.ouro/segmentos_kmeans.csv` · "
    "gerado por `notebooks/segmentos_plano_ouro.py`",
)

p.texto(f"""
**Regra e denominador.** Base comum de {br(len(b), 0)} assinantes pagos ativos em 31/07/2026 que
estão nas duas segmentações e ainda não tinham desligado a renovação. Cada linha é um
`segmento` L × `plano`; `n` é o denominador e a taxa é `100 × contagem ÷ n`. Combinações sem
assinantes aparecem com `n = 0` e taxa vazia — não é 0%. A janela dos dois sinais é
{JANELA_INI} a {JANELA_FIM} (60 dias).

A saída (L) é a **decisão** de sair; o término (N) é o **fim** da assinatura. As duas medidas
não são a mesma coisa.
""")

p.secao("Nomes e datas: as duas segmentações não são a mesma")
p.texto(f"""
- **L** (`segmentos.csv`): {nomes_l}. O grupo "Já desligou" fica à parte.
- **N** (`segmentos_kmeans.csv`): {nomes_n}.
- **"Parados" nos dois nomes**: em L, o grupo é o de maior mediana de dias sem treino; em N,
  é o grupo com mais dias sem treino entre as nove variáveis. Não são o mesmo grupo.
- **Data**: a referência é 31/07/2026. A saída L usa a data da decisão (desligamento da
  renovação, cancelamento ou expiração); a saída N usa a data do fim da assinatura. No anual,
  o vencimento é fixo e a decisão pode vir meses antes do término.
""")

p.secao("Mesma base de treinos nas duas segmentações")
p.texto("""
L e N usam a mesma base de treinos: `atividades.parquet` entrega um treino por
(`user_id`, `inicio_brt`) e não marca registros no mesmo minuto (T12). A diferença entre as duas
segmentações está nas variáveis e na definição de saída (decisão × término), não no filtro de
treinos.
""")

p.secao("Resultados por persona L e plano")
tab = g.rename(columns={
    "segmento_l": "Segmento L",
    "plano": "Plano",
    "n_assinantes": "n",
    "saida_l": "Saída L (n)",
    "saida_l_pct": "Saída L (%)",
    "termino_n": "Término N (n)",
    "termino_n_pct": "Término N (%)",
})
p.tabela(
    tab,
    "Base de 31/07/2026",
    formatos={
        "n": "{:,.0f}",
        "Saída L (n)": "{:,.0f}",
        "Saída L (%)": "{:.1f}",
        "Término N (n)": "{:,.0f}",
        "Término N (%)": "{:.1f}",
    },
)
p.texto(f"""
A tabela tem {br(n_grupos, 0)} linhas; {br(n_com_n, 0)} combinações têm assinantes. O `n` de
cada linha é o denominador das duas taxas. As taxas vazias são grupos com `n = 0`; elas não
entram em nenhuma média e não devem ser lidas como 0%.
""")

p.secao("Os dois sinais por persona e plano")
fig = make_subplots(rows=1, cols=2, horizontal_spacing=0.12,
                    subplot_titles=("Saída (L) — decisão", "Término (N) — fim da assinatura"))
for plano, cor in zip(PLANOS, [CORES[0], CORES[1]]):
    d = g[(g.plano == plano) & (g.n_assinantes > 0)]
    fig.add_trace(go.Bar(x=d.segmento_l, y=d.saida_l_pct, name=plano, marker_color=cor,
                         hovertemplate="%{x} · " + plano + ": %{y:.1f}%<extra></extra>"),
                  1, 1)
    fig.add_trace(go.Bar(x=d.segmento_l, y=d.termino_n_pct, name=plano, marker_color=cor,
                         showlegend=False,
                         hovertemplate="%{x} · " + plano + ": %{y:.1f}%<extra></extra>"),
                  1, 2)
layout_padrao(fig, "taxa (%)", formato_y=".1f", altura=420)
fig.update_layout(barmode="group", legend_title_text="plano", margin=dict(t=48))
fig.update_xaxes(tickangle=-20)
fig.update_yaxes(range=[0, 1.1 * float(g[["saida_l_pct", "termino_n_pct"]].max().max())])
p.figura(fig, "Taxas por persona L e plano. Barras ausentes são grupos com n = 0. "
              "A escala é a mesma nos dois painéis; compare dentro de cada sinal e entre sinais "
              "com cautela, porque as definições de saída e término são diferentes.")

p.secao("Conferências")
p.texto(f"""
- As duas tabelas têm a mesma chave (`data_ref`, `user_id`) e não têm duplicatas.
- Em 31/07, L e N cobrem os mesmos {br(len(t), 0)} `user_id`; o plano de cada pessoa é o mesmo
  nas duas.
- A base comum é {br(len(b), 0)}; a soma dos `n` dos grupos é {br(int(g.n_assinantes.sum()), 0)}.
- As somas de saída L ({br(int(g.saida_l.sum()), 0)}) e término N ({br(int(g.termino_n.sum()), 0)})
  batem com as colunas da base. Das pessoas com sinal L, {br(int(((b.saiu_60d_l == 1) & (b.saiu_60d_n == 1)).sum()), 0)}
  também tiveram término N; {br(int(((b.saiu_60d_l == 1) & (b.saiu_60d_n == 0)).sum()), 0)} não tiveram término na janela.
- Nenhum grupo com `n = 0` tem taxa calculada; são {br(len(n0), 0)} grupo(s) com n = 0.
- O grupo "Já desligou" de L tem {br(len(j), 0)} pessoas em 31/07 e fica fora: `saiu_60d` é
  NaN porque a decisão já foi tomada. Não calculamos a taxa L desse grupo.
""")

p.secao("Limitações")
p.texto("""
- **Anual e vencimento.** O plano anual vence em data fixa. A decisão (L) pode ocorrer meses
  antes do término (N); no anual, as duas taxas não medem a mesma coisa. Não trate a taxa L
  como perda imediata nem a taxa N como intenção.
- **Não causal.** As diferenças entre grupos são associações descritivas. Não há desenho
  causal; não se pode atribuir a saída ao segmento nem ao plano.
- **Campanha.** A campanha de 10/08/2026 tratou parte da base; as taxas de 60 dias podem
  incluir o efeito da campanha e não separam tratado de controle.
- **Amostras.** Os `n` estão na tabela; grupos com `n = 0` ficam sem taxa (não é 0%) e grupos
  com `n` pequeno têm taxas instáveis. Não é possível comparar planos dentro de uma persona
  sem assinantes nos dois planos. Leia a contagem junto com a taxa.
- **Taxas históricas.** As taxas são de ago–set/2026, não previsões nem taxas esperadas no
  futuro. Para prever, use um modelo e valide.
- **Sem ação.** Esta página não recomenda ação, prioridade ou oferta: ela só mede os dois
  sinais para a conversa entre EDA e segmentação.
""")

destino = p.salvar("07_segmentos_por_plano.html")
print(f"artefato: {destino.relative_to(RAIZ)}")
