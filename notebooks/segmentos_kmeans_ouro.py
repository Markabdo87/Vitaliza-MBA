"""Prata -> ouro: segmentos_kmeans.csv (um assinante × data de referência) +
artefatos/02_segmentos_kmeans.html.

Segmentação comportamental da base paga com k-means, para o Customer Segmentation Report.

Regras (decisões K1–K6 no decisoes.md):
  1. Base: assinaturas pagas (flag_cortesia = 0) ativas no fim da data de referência:
     inicio <= ref e (data_fim vazia ou data_fim > ref).
  2. Duas datas de referência, mesmas variáveis:
       - 31/07/2026 (treino): o k-means é ajustado aqui, e a saída nos 60 dias seguintes
         (data_fim de 01/08 a 29/09/2026) mede o churn de cada segmento;
       - 30/09/2026 (corte): a base atual recebe o segmento do centróide mais próximo,
         sem reajustar, para dimensionar cada segmento hoje.
  3. Variáveis só com informação até a data de referência (nada depois do corte):
       treinos_30d        treinos nos 30 dias até ref (atividades, sem flag_inicio_repetido)
       tendencia_treino   log((treinos_30d + 1) / (treinos dos 60 dias anteriores / 2 + 1))
       dias_sem_treino    dias desde o último treino de 2026, teto 120 (sem treino = 120)
       sessoes_app        média de sessoes_app nos 3 meses até ref (uso_mensal; todos depois
                          da mudança de escala de mar/26, M6)
       conexoes           relações recíprocas com desde <= ref (amizades, seguidor_id)
       posts_90d          posts no feed nos 90 dias até ref
       problemas_90d      chamados de suporte + treinos com GPS falho nos 90 dias até ref
       recusas_180d       cobranças recusadas nos 180 dias até ref (pagamentos)
       meses_assinatura   meses desde o início da assinatura
     Contagens entram em log1p; tudo é padronizado (z-score) com a média e o desvio da
     base de treino.
  4. Plano, canal, sistema e idade não entram no k-means: servem para descrever os
     segmentos depois. Assim o segmento descreve comportamento, e o plano (que muda o
     calendário de saída do anual) não decide o agrupamento.
  5. k escolhido entre 3 e 6 pelo silhouette (amostra de 5.000) e pela pedida do guia
     (3–4 segmentos); k-means++ com 20 inicializações, random_state = 7.
  6. Rótulo do segmento é dado pelo perfil dos centróides (ver o artefato), fixado em
     ROTULOS abaixo depois de olhar o resultado.

Limites: atividades.parquet só cobre 2026, então as variáveis de treino não existem antes de
jan/26. A campanha de ago/26 (10/08) tratou parte da base de treino; o churn de 60 dias de
cada segmento inclui esse efeito.

Uso: .venv/bin/python notebooks/segmentos_kmeans_ouro.py  (a partir da raiz do repo)
"""
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score

from _artefato import CORES, Pagina, layout_padrao

RAIZ = Path(__file__).resolve().parent.parent
PRATA = RAIZ / "dados" / "2.prata"
SAIDA = RAIZ / "dados" / "3.ouro" / "segmentos_kmeans.csv"

REF_TREINO = pd.Timestamp("2026-07-31")
REF_CORTE = pd.Timestamp("2026-09-30")
HORIZONTE = pd.Timedelta(days=60)
SEED = 7

VARS = ["treinos_30d", "tendencia_treino", "dias_sem_treino", "sessoes_app", "conexoes",
        "posts_90d", "problemas_90d", "recusas_180d", "meses_assinatura"]
LOG = ["treinos_30d", "sessoes_app", "conexoes", "posts_90d", "problemas_90d", "recusas_180d",
       "meses_assinatura"]

# --- prata -------------------------------------------------------------------------------
ass = pd.read_csv(PRATA / "assinaturas.csv", parse_dates=["inicio", "data_fim"])
ass = ass[ass.flag_cortesia == 0]
usu = pd.read_csv(PRATA / "usuarios.csv", usecols=["user_id", "sistema", "idade_corte",
                                                   "relogio_conectado", "flag_conta_teste"])
atv = pd.read_parquet(PRATA / "atividades.parquet",
                      columns=["user_id", "inicio_brt", "gps_ok", "flag_inicio_repetido"])
atv = atv[atv.flag_inicio_repetido == 0]
atv["dia"] = atv.inicio_brt.dt.normalize()
uso = pd.read_csv(PRATA / "uso_mensal.csv", usecols=["user_id", "mes", "sessoes_app"])
ami = pd.read_csv(PRATA / "amizades.csv", parse_dates=["desde"])
ami = ami[(ami.reciproco == 1) & (ami.flag_id_invalido == 0)]
feed = pd.read_csv(PRATA / "feed_posts.csv", usecols=["user_id", "data_hora"],
                   parse_dates=["data_hora"])
tick = pd.read_csv(PRATA / "tickets_suporte.csv", usecols=["user_id", "aberto_em"],
                   parse_dates=["aberto_em"])
pag = pd.read_csv(PRATA / "pagamentos.csv", usecols=["user_id", "data_hora_brt", "status"],
                  parse_dates=["data_hora_brt"])
pag = pag[pag.status == "recusado"]


def conta(df, col, ini, fim):
    """Linhas por user_id com col em [ini, fim] (fim até 23:59:59)."""
    m = (df[col] >= ini) & (df[col] < fim + pd.Timedelta(days=1))
    return df[m].groupby("user_id").size()


def base(ref):
    b = ass[(ass.inicio <= ref) & (ass.data_fim.isna() | (ass.data_fim > ref))].copy()
    b = b.set_index("user_id")
    d = lambda n: ref - pd.Timedelta(days=n - 1)  # janela de n dias terminando em ref
    t30 = conta(atv, "dia", d(30), ref)
    t60ant = conta(atv, "dia", d(90), d(31))
    ult = atv[atv.dia <= ref].groupby("user_id").dia.max()
    meses = [str(p) for p in pd.period_range(ref.to_period("M") - 2, ref.to_period("M"))]
    ses = uso[uso.mes.isin(meses)].groupby("user_id").sessoes_app.sum() / 3
    gps = conta(atv[~atv.gps_ok], "dia", d(90), ref)

    f = pd.DataFrame(index=b.index)
    f["treinos_30d"] = t30.reindex(f.index).fillna(0)
    t60 = t60ant.reindex(f.index).fillna(0)
    f["tendencia_treino"] = np.log((f.treinos_30d + 1) / (t60 / 2 + 1))
    f["dias_sem_treino"] = (ref - ult.reindex(f.index)).dt.days.clip(upper=120).fillna(120)
    f["sessoes_app"] = ses.reindex(f.index).fillna(0)
    f["conexoes"] = ami[ami.desde <= ref].groupby("seguidor_id").size().reindex(f.index).fillna(0)
    f["posts_90d"] = conta(feed, "data_hora", d(90), ref).reindex(f.index).fillna(0)
    f["problemas_90d"] = (conta(tick, "aberto_em", d(90), ref).reindex(f.index).fillna(0)
                          + gps.reindex(f.index).fillna(0))
    f["recusas_180d"] = conta(pag, "data_hora_brt", d(180), ref).reindex(f.index).fillna(0)
    f["meses_assinatura"] = ((ref - b.inicio).dt.days / 30.44).round(1)

    f["data_ref"] = ref.date().isoformat()
    f["plano"] = b.plano_atual
    f["canal"] = b.canal
    f["metodo"] = b.metodo
    fim = b.data_fim
    f["saiu_60d"] = (fim.notna() & (fim <= ref + HORIZONTE)).astype(int)
    f["motivo_fim_60d"] = b.motivo_fim.where(f.saiu_60d == 1)
    f = f.join(usu.set_index("user_id")[["sistema", "idade_corte", "relogio_conectado"]])
    return f


def matriz(f):
    x = f[VARS].astype(float).copy()
    x[LOG] = np.log1p(x[LOG])
    return x


treino = base(REF_TREINO)
corte = base(REF_CORTE)
x_tr = matriz(treino)
mu, sd = x_tr.mean(), x_tr.std()
z_tr = ((x_tr - mu) / sd).values
z_co = ((matriz(corte) - mu) / sd).values

# --- escolha de k ---------------------------------------------------------------------
rng = np.random.default_rng(SEED)
amostra = rng.choice(len(z_tr), size=min(5000, len(z_tr)), replace=False)
escolha = []
for k in range(2, 8):
    km = KMeans(n_clusters=k, n_init=20, random_state=SEED).fit(z_tr)
    sil = silhouette_score(z_tr[amostra], km.labels_[amostra])
    escolha.append({"k": k, "inercia": km.inertia_, "silhouette": sil})
escolha = pd.DataFrame(escolha)
print(escolha.round(3).to_string(index=False))

K = 4
km = KMeans(n_clusters=K, n_init=20, random_state=SEED).fit(z_tr)
centros = pd.DataFrame(km.cluster_centers_, columns=VARS)

# Rótulos pelo perfil dos centróides (regra 6): cada segmento pelo traço que o separa.
rot = {}
rot[centros.recusas_180d.idxmax()] = "Cobrança falhando"
rot[centros.drop(index=list(rot)).dias_sem_treino.idxmax()] = "Parados"
rot[centros.drop(index=list(rot)).meses_assinatura.idxmin()] = "Recém-chegados"
rot[centros.drop(index=list(rot)).index[0]] = "Engajados"
ORDEM = ["Engajados", "Recém-chegados", "Parados", "Cobrança falhando"]
COR = dict(zip(ORDEM, CORES))

treino["segmento"] = pd.Series(km.labels_, index=treino.index).map(rot)
corte["segmento"] = pd.Series(km.predict(z_co), index=corte.index).map(rot)
corte["saiu_60d"] = np.nan  # o horizonte de 60 dias depois de 30/09 ainda não aconteceu
corte["motivo_fim_60d"] = np.nan

saida = pd.concat([treino, corte]).reset_index()
saida[["user_id", "data_ref", "segmento"] + VARS + [
    "plano", "canal", "metodo", "sistema", "idade_corte", "relogio_conectado",
    "saiu_60d", "motivo_fim_60d"]].to_csv(SAIDA, index=False)

# --- conferência ------------------------------------------------------------------------
n_ativos_set = ((ass.inicio < "2026-09-01") & (ass.data_fim.isna() | (ass.data_fim >= "2026-09-01"))).sum()
assert n_ativos_set == 14319, n_ativos_set  # mesma base do churn_mensal (G1)
assert len(saida) == len(treino) + len(corte) and saida.segmento.notna().all()
print(f"{SAIDA.relative_to(RAIZ)}: {len(saida)} linhas · base 31/07 {len(treino):,} · "
      f"base 30/09 {len(corte):,} · saída em 60 dias {treino.saiu_60d.mean():.1%}")

# --- perfil ------------------------------------------------------------------------------
def pct(s, valor):
    return 100 * (s == valor).mean()


g = treino.groupby("segmento")
perfil = pd.DataFrame({
    "assinantes 31/07": g.size(),
    "% da base": 100 * g.size() / len(treino),
    "saída em 60 dias (%)": 100 * g.saiu_60d.mean(),
    "treinos em 30 dias": g.treinos_30d.median(),
    "dias sem treinar": g.dias_sem_treino.median(),
    "sessões no app/mês": g.sessoes_app.median(),
    "conexões": g.conexoes.median(),
    "posts em 90 dias": g.posts_90d.median(),
    "recusas em 180 dias": g.recusas_180d.mean(),
    "meses de assinatura": g.meses_assinatura.median(),
    "% mensal": g.plano.apply(pct, valor="mensal"),
    "% loja": g.canal.apply(pct, valor="loja"),
    "% android": g.sistema.apply(pct, valor="android"),
}).reindex(ORDEM)
perfil["assinantes 30/09"] = corte.segmento.value_counts().reindex(ORDEM)
perfil["% em 30/09"] = 100 * perfil["assinantes 30/09"] / len(corte)
saidas = treino[treino.saiu_60d == 1]
motivos = pd.crosstab(saidas.segmento, saidas.motivo_fim_60d, normalize="index").reindex(ORDEM) * 100
por_plano = treino.pivot_table(index="segmento", columns="plano", values="saiu_60d",
                               aggfunc="mean").reindex(ORDEM) * 100
print(perfil.round(1).T.to_string())
print(motivos.round(1).to_string())
print(por_plano.round(1).to_string())

def br(v, casas=1):
    """Número no formato brasileiro: 14.032 · 10,5."""
    return f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


# --- artefato HTML -------------------------------------------------------------------------
P = perfil.round(1)
churn_base = 100 * treino.saiu_60d.mean()
p = Pagina(
    "02 · Segmentos (k-means)",
    "Quatro grupos de assinantes pelo comportamento no app, e quanto cada um sai em 60 dias.",
    "fonte: `dados/3.ouro/segmentos_kmeans.csv`, gerada por `notebooks/segmentos_kmeans_ouro.py` "
    "(decisões K1–K6)",
)
p.texto(f"""
**Regra.** Base: assinantes pagantes ativos em 31/07/2026 ({br(len(treino), 0)} assinaturas, sem as
cortesias internas). Cada um é descrito por nove variáveis calculadas só com dados até 31/07:
treinos nos últimos 30 dias, tendência de treino (30 dias contra os 60 anteriores), dias sem
treinar, sessões no app, conexões recíprocas, posts no feed, chamados e treinos com GPS falho,
cobranças recusadas e meses de assinatura. Contagens em log, tudo padronizado; k-means com
k = 4. Plano, canal e sistema ficam fora do agrupamento e servem para descrever os grupos.
**Saída em 60 dias** = assinatura terminada entre 01/08 e 29/09/2026 (média da base:
{br(churn_base, 1)}%).
""")

p.secao("Os quatro segmentos")
f = go.Figure()
for s in ORDEM:
    f.add_trace(go.Bar(x=[s], y=[perfil.loc[s, "saída em 60 dias (%)"]], name=s,
                       marker=dict(color=COR[s]), text=[f"{br(perfil.loc[s, 'saída em 60 dias (%)'], 1)}%"],
                       textposition="outside",
                       hovertemplate=f"{s}: %{{y:.1f}}% · {br(perfil.loc[s, 'assinantes 31/07'], 0)} assinantes<extra></extra>"))
f.add_hline(y=churn_base, line=dict(color="#52514e", width=1, dash="dash"),
            annotation_text=f"base: {br(churn_base, 1)}%", annotation_position="top right")
layout_padrao(f, "saíram em 60 dias (%)", altura=340)
f.update_layout(showlegend=False, hovermode="closest")
p.figura(f, "Parcela de cada segmento (base de 31/07/2026) cuja assinatura terminou até 29/09/2026.")

f = go.Figure(go.Heatmap(
    z=centros.rename(index=rot).reindex(ORDEM).values.T, x=ORDEM, y=VARS,
    colorscale=[[0, "#2a78d6"], [0.5, "#fcfcfb"], [1, "#eb6834"]], zmid=0, zmin=-2, zmax=2,
    text=centros.rename(index=rot).reindex(ORDEM).values.T.round(1), texttemplate="%{text}",
    hovertemplate="%{y} · %{x}: %{z:.2f} desvios<extra></extra>", colorbar=dict(title="z")))
layout_padrao(f, altura=420)
f.update_layout(hovermode="closest", margin=dict(l=140))
f.update_yaxes(autorange="reversed", gridcolor="rgba(0,0,0,0)")
p.figura(f, "Centróides em desvios-padrão da média da base (laranja = acima, azul = abaixo). "
            "A escala corta em ±2; recusas do segmento Cobrança falhando ficam em +5,5.")

# Dispersão em 2D: os 9 eixos padronizados projetados nos 2 componentes principais (PCA),
# amostra de assinantes por segmento e os 4 centróides do k-means projetados no mesmo plano.
pca = PCA(n_components=2, random_state=SEED).fit(z_tr)
pts = pca.transform(z_tr[amostra])
cen = pca.transform(km.cluster_centers_)
seg_amostra = treino.segmento.values[amostra]
var = pca.explained_variance_ratio_ * 100
f = go.Figure()
for s in ORDEM:
    m = seg_amostra == s
    f.add_trace(go.Scattergl(x=pts[m, 0], y=pts[m, 1], mode="markers", name=s,
                             marker=dict(color=COR[s], size=4, opacity=0.35),
                             hovertemplate=f"{s}<extra></extra>"))
for i, s in rot.items():
    f.add_trace(go.Scatter(x=[cen[i, 0]], y=[cen[i, 1]], mode="markers+text", showlegend=False,
                           marker=dict(symbol="x", size=18, color=COR[s],
                                       line=dict(width=2, color="#0b0b0b")),
                           text=[f"<b>{s}</b>"],
                           textposition={"Engajados": "top left",
                                         "Cobrança falhando": "bottom right"}.get(s, "top center"),
                           textfont=dict(color="#0b0b0b", size=12),
                           hovertemplate=f"centróide · {s}<extra></extra>"))
layout_padrao(f, f"componente 2 ({br(var[1], 0)}% da variância)", altura=480)
f.update_xaxes(title_text=f"componente 1 ({br(var[0], 0)}% da variância)", showgrid=True,
               gridcolor="#e6e5e0", zeroline=False)
f.update_layout(hovermode="closest")
p.figura(f, f"Assinantes (amostra de {br(len(amostra), 0)}) e centróides (×) projetados nos dois "
            f"componentes principais das nove variáveis padronizadas, que juntos explicam "
            f"{br(var.sum(), 0)}% da variação. O k-means agrupa nas nove dimensões; a projeção "
            "em 2D sobrepõe grupos que lá estão separados: Cobrança falhando fica sobre "
            "Engajados porque se separa só pelas recusas (ver o mapa de calor acima).")

fmt = {c: "{:,.1f}" for c in P.columns} | {c: "{:,.0f}" for c in ["assinantes 31/07", "assinantes 30/09"]}
p.tabela(P.reset_index().rename(columns={"segmento": "segmento"}), "Perfil (medianas, exceto %, e recusas em média)", fmt)

p.secao("Cartões de persona")
for s in ORDEM:
    r = P.loc[s]
    texto = {
        "Engajados": f"""
**Engajados · {br(r['% da base'], 0)}% da base · saem {br(r['saída em 60 dias (%)'], 1)}% em 60 dias.**
Treinam ~{br(r['treinos em 30 dias'], 0)} vezes por mês, abrem o app ~{br(r['sessões no app/mês'], 0)}
vezes por mês, postam no feed e têm conexões. Assinam há ~{br(r['meses de assinatura'], 0)} meses;
{br(r['% mensal'], 0)}% no mensal. **Hipótese de driver**: quando saem, é por fim de objetivo (prova,
evento) ou preço no mensal depois do reajuste. **Prioridade: monitorar.**""",
        "Recém-chegados": f"""
**Recém-chegados · {br(r['% da base'], 0)}% da base · saem {br(r['saída em 60 dias (%)'], 1)}% em 60 dias.**
Até ~{br(r['meses de assinatura'], 0)} meses de casa, treinam bem (~{br(r['treinos em 30 dias'], 0)} por mês,
em alta), mas usam pouco o lado social: mediana de {br(r['conexões'], 0)} conexões e
{br(r['posts em 90 dias'], 0)} posts. {br(r['% mensal'], 0)}% no mensal. **Hipótese de driver**: hábito
ainda não formado e app sem laço social; o primeiro vencimento é o momento de risco.
**Prioridade: ação imediata (onboarding social).**""",
        "Parados": f"""
**Parados · {br(r['% da base'], 0)}% da base · saem {br(r['saída em 60 dias (%)'], 1)}% em 60 dias.**
Não treinam há ~{br(r['dias sem treinar'], 0)} dias e quase não abrem o app
(~{br(r['sessões no app/mês'], 1)} sessões/mês). São {br(100 - r['% mensal'], 0)}% anuais: pagam sem usar
e decidem na renovação. **Hipótese de driver**: perda de hábito ou objetivo cumprido; o anual
adia a saída até o vencimento. **Prioridade: ação imediata antes da renovação.**""",
        "Cobrança falhando": f"""
**Cobrança falhando · {br(r['% da base'], 0)}% da base · saem {br(r['saída em 60 dias (%)'], 1)}% em 60 dias.**
Usam o app como os engajados, mas têm ~{br(r['recusas em 180 dias'], 1)} cobranças recusadas em 180
dias. {br(r['% mensal'], 0)}% mensal e {br(100 - r['% loja'], 0)}% no site (cartão/Pix). **Hipótese de
driver**: churn involuntário, cartão vencido ou sem limite. **Prioridade: ação imediata
(régua de cobrança, troca de meio de pagamento), barata e sem desconto.**""",
    }[s]
    p.texto(texto)

p.secao("Como cada segmento sai")
f = go.Figure()
for i, m in enumerate(motivos.columns):
    f.add_trace(go.Bar(y=ORDEM, x=motivos[m], name=m, orientation="h",
                       marker=dict(color=CORES[i + 4], line=dict(color="#fcfcfb", width=1)),
                       hovertemplate=f"{m}: %{{x:.0f}}%<extra></extra>"))
layout_padrao(f, altura=300)
f.update_layout(barmode="stack", hovermode="closest", margin=dict(l=130))
f.update_xaxes(title_text="% das saídas do segmento em 60 dias", ticksuffix="%")
f.update_yaxes(autorange="reversed", gridcolor="rgba(0,0,0,0)")
p.figura(f, "Motivo do fim (`motivo_fim` de assinaturas) entre quem saiu em 60 dias.")
p.tabela(por_plano.round(1).reset_index(), "Saída em 60 dias por segmento e plano (%)",
         {c: "{:.1f}" for c in por_plano.columns})
p.texto(f"""
- **Dentro do mesmo plano a ordem se mantém**: no mensal, Parados saem
  {br(por_plano.loc['Parados', 'mensal'])}% em 60 dias contra {br(por_plano.loc['Engajados', 'mensal'])}%
  dos Engajados; no anual, {br(por_plano.loc['Parados', 'anual'])}% contra
  {br(por_plano.loc['Engajados', 'anual'])}%.
- **Cobrança falhando é o único segmento com perda involuntária relevante**:
  {br(motivos.loc['Cobrança falhando', 'falha_pagamento'], 0)}% das saídas por falha de pagamento,
  contra {br(motivos.loc['Engajados', 'falha_pagamento'], 0)}% nos Engajados.
""")

p.secao("Escolha de k")
p.texto(f"""
O silhouette (amostra de 5.000) fica entre 0,20 e 0,25 para k de 2 a 7: os grupos se
sobrepõem, como é comum em dados de comportamento. Entre os 3 ou 4 segmentos que o guia
pede, k = 4 tem o maior silhouette ({br(escolha.set_index('k').loc[4, 'silhouette'], 3)}). Com k = 5 o
quinto grupo separa usuários Android com muitos chamados e GPS falho, e a saída desse grupo
em 60 dias (7,6%) fica abaixo da média: não pede ação própria.
""")
p.tabela(escolha, "Inércia e silhouette por k", {"inercia": "{:,.0f}", "silhouette": "{:.3f}"})

p.secao("A base hoje (30/09/2026)")
p.texto(f"""
Os {br(len(corte), 0)} assinantes ativos em 30/09 recebem o segmento do centróide mais próximo, com a
mesma padronização de 31/07 (sem reajustar o modelo).
""")
p.tabela(P[["assinantes 30/09", "% em 30/09"]].reset_index(), "Tamanho dos segmentos em 30/09",
         {"assinantes 30/09": "{:,.0f}", "% em 30/09": "{:.1f}"})

p.secao("Limitações")
p.texto("""
- Os segmentos são descritivos: a saída em 60 dias **coincide** com o perfil, não prova causa.
- A campanha de 10/08/2026 tratou parte da base de 31/07; a saída de 60 dias inclui esse efeito.
- Treinos vêm de `atividades.parquet`, que só cobre 2026; variáveis de engajamento não
  existem para datas anteriores.
- Silhouette baixo (~0,24): as fronteiras entre segmentos são difusas, principalmente entre
  Engajados e Recém-chegados.
- No anual, sair em 60 dias depende de a renovação cair na janela; compare segmentos dentro
  do mesmo plano (tabela acima).
""")

p.secao("Perguntas para a próxima etapa")
p.texto("""
- Os segmentos devem entrar no modelo de churn como variável, ou o modelo usa as mesmas
  variáveis e o segmento fica só para a comunicação?
- Acrescentar as variáveis de texto (objetivo do onboarding, intenção de sair no feed) quando
  a extração com IA estiver pronta: "objetivo cumprido" pode separar parte dos Parados.
- Cruzar os segmentos com o resultado da campanha de ago/26 (uplift por segmento).
""")
destino = p.salvar("02_segmentos_kmeans.html")
print(f"artefato: {destino.relative_to(RAIZ)}")
