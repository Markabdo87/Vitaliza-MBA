"""Prata -> ouro: segmentos_kmeans.csv (um assinante × data de referência) +
artefatos/05_segmentos_kmeans.html.

Segmentação comportamental da base paga com k-means, para o Customer Segmentation Report.

Regras (decisões N1–N7 no decisoes.md):
  1. Base: assinaturas pagas (flag_cortesia = 0) ativas no fim da data de referência:
     inicio <= ref e (data_fim vazia ou data_fim > ref).
  2. Duas datas de referência, mesmas variáveis:
       - REF_TREINO = REF_CORTE − (HORIZONTE + 1 dia) = 31/07/2026: o k-means é ajustado
         aqui, e a saída nos HORIZONTE dias seguintes mede o churn de cada segmento;
       - REF_CORTE = 30/09/2026: a base atual recebe o segmento do centróide mais próximo,
         sem reajustar, para dimensionar cada segmento hoje.
  3. Variáveis só com informação até a data de referência, definidas em VARIAVEIS (uma
     entrada por variável: como calcular, se entra em log e o texto da página). Contagens
     entram em log1p; tudo é padronizado (z-score) com a média e o desvio da base de treino.
  4. Plano, canal, sistema e idade não entram no k-means: servem para descrever os
     segmentos. O plano mudaria o agrupamento pelo calendário de saída do anual.
  5. k = o de maior silhouette (amostra de 5.000) dentro de K_FAIXA (3–4, pedida do guia);
     k-means++ com 20 inicializações, random_state = 7.
  6. Rótulos pelo centróide, na ordem de ROTULOS: maior recusa = Cobrança falhando; mais
     dias sem treino = Parados; menos meses de assinatura = Recém-chegados. Um rótulo só é
     dado se o centróide estiver a pelo menos 1 desvio da média nessa variável. Dos grupos
     que sobram, o que mais treina é Engajados; os demais viram "Grupo n".
  7. Prioridade do cartão de persona: "ação imediata" se o segmento sai em 60 dias pelo
     menos 1,5 vez a média da base; abaixo disso, "monitorar".

Feito para rodar de novo quando a prata mudar: nenhum número da página é fixo no código
(tudo sai da tabela calculada), a prata é conferida antes (existe, tem as colunas, é mais
nova que o notebook que a gera; ver `_ouro.py`), e o notebook para com mensagem clara se a
base ficar vazia ou alguma variável vier sem valor.

Para acrescentar uma variável: uma entrada em VARIAVEIS. Para usar uma tabela de ouro de um
colega (ex.: variáveis da extração com IA): uma entrada em EXTRAS com o arquivo e as colunas;
a tabela precisa ter `user_id` e, se tiver `data_ref`, é casada pela data também. Só use
colunas calculadas com informação até a data de referência.

Limites: atividades.parquet só cobre 2026, então as variáveis de treino não existem antes de
jan/26. A campanha de 10/08/2026 tratou parte da base de treino; o churn de 60 dias de cada
segmento inclui esse efeito.

Uso: .venv/bin/python notebooks/segmentos_kmeans_ouro.py  (a partir da raiz do repo)
"""
import sys

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score

from _artefato import CORES, Pagina, layout_padrao
from _ouro import OURO, RAIZ, ler_prata

SAIDA = OURO / "segmentos_kmeans.csv"

# --- configuração ---------------------------------------------------------------------------
REF_CORTE = pd.Timestamp("2026-09-30")            # corte dos dados (dicionário)
HORIZONTE = pd.Timedelta(days=60)                 # saída em 60 dias (enunciado)
REF_TREINO = REF_CORTE - HORIZONTE - pd.Timedelta(days=1)
K_FAIXA = (3, 4)                                  # segmentos pedidos pelo guia da semana 5
K_TESTE = range(2, 8)                             # k mostrados na tabela de escolha
SEED = 7
TETO_DIAS_SEM_TREINO = 120
EXTRAS = []  # ex.: [("variaveis_texto.csv", ["objetivo_cumprido", "intencao_sair"])]

# --- prata -------------------------------------------------------------------------------
ass = ler_prata("assinaturas.csv", ["user_id", "plano_atual", "canal", "metodo", "inicio",
                                    "data_fim", "motivo_fim", "flag_cortesia"],
                datas=["inicio", "data_fim"])
ass = ass[ass.flag_cortesia == 0]
usu = ler_prata("usuarios.csv", ["user_id", "sistema", "idade_corte", "relogio_conectado"])
atv = ler_prata("atividades.parquet", ["user_id", "inicio_brt", "gps_ok", "flag_inicio_repetido"])
atv = atv[atv.flag_inicio_repetido == 0].copy()
atv["dia"] = atv.inicio_brt.dt.normalize()
uso = ler_prata("uso_mensal.csv", ["user_id", "mes", "sessoes_app"])
ami = ler_prata("amizades.csv", ["seguidor_id", "desde", "reciproco", "flag_id_invalido"],
                datas=["desde"])
ami = ami[(ami.reciproco == 1) & (ami.flag_id_invalido == 0)]
feed = ler_prata("feed_posts.csv", ["user_id", "data_hora"], datas=["data_hora"])
tick = ler_prata("tickets_suporte.csv", ["user_id", "aberto_em"], datas=["aberto_em"])
pag = ler_prata("pagamentos.csv", ["user_id", "data_hora_brt", "status"], datas=["data_hora_brt"])
pag = pag[pag.status == "recusado"]

if atv.dia.min() > REF_TREINO - pd.Timedelta(days=89):
    print(f"aviso: atividades começa em {atv.dia.min():%d/%m/%Y}; as janelas de 90 dias de "
          f"{REF_TREINO:%d/%m/%Y} ficam incompletas")


def conta(df, col, ini, fim):
    """Linhas por user_id com col em [ini, fim] (fim até 23:59:59)."""
    m = (df[col] >= ini) & (df[col] < fim + pd.Timedelta(days=1))
    return df[m].groupby("user_id").size()


def janela(ref, n):
    """Primeiro dia da janela de n dias que termina em ref."""
    return ref - pd.Timedelta(days=n - 1)


def sessoes(ref, b):
    meses = [str(m) for m in pd.period_range(ref.to_period("M") - 2, ref.to_period("M"))]
    return uso[uso.mes.isin(meses)].groupby("user_id").sessoes_app.sum() / 3


def tendencia(ref, b):
    t30 = conta(atv, "dia", janela(ref, 30), ref).reindex(b.index).fillna(0)
    t60 = conta(atv, "dia", janela(ref, 90), janela(ref, 31)).reindex(b.index).fillna(0)
    return np.log((t30 + 1) / (t60 / 2 + 1))


def dias_sem_treino(ref, b):
    ult = atv[atv.dia <= ref].groupby("user_id").dia.max().reindex(b.index)
    return (ref - ult).dt.days.clip(upper=TETO_DIAS_SEM_TREINO).fillna(TETO_DIAS_SEM_TREINO)


def problemas(ref, b):
    tickets = conta(tick, "aberto_em", janela(ref, 90), ref).reindex(b.index).fillna(0)
    gps = conta(atv[~atv.gps_ok], "dia", janela(ref, 90), ref).reindex(b.index).fillna(0)
    return tickets + gps


# Uma entrada por variável do k-means. calc(ref, b) devolve uma série por user_id (b é a
# base da data, indexada por user_id); quem não aparece na série fica com 0.
VARIAVEIS = {
    "treinos_30d": dict(log=True, nome="treinos em 30 dias", resumo="median",
                        calc=lambda ref, b: conta(atv, "dia", janela(ref, 30), ref)),
    "tendencia_treino": dict(log=False, nome="tendência de treino", resumo="median",
                             calc=tendencia),
    "dias_sem_treino": dict(log=False, nome="dias sem treinar", resumo="median",
                            calc=dias_sem_treino),
    "sessoes_app": dict(log=True, nome="sessões no app/mês", resumo="median", calc=sessoes),
    "conexoes": dict(log=True, nome="conexões", resumo="median",
                     calc=lambda ref, b: ami[ami.desde <= ref].groupby("seguidor_id").size()),
    "posts_90d": dict(log=True, nome="posts em 90 dias", resumo="median",
                      calc=lambda ref, b: conta(feed, "data_hora", janela(ref, 90), ref)),
    "problemas_90d": dict(log=True, nome="chamados + GPS falho em 90 dias", resumo="mean",
                          calc=problemas),
    "recusas_180d": dict(log=True, nome="recusas em 180 dias", resumo="mean",
                         calc=lambda ref, b: conta(pag, "data_hora_brt", janela(ref, 180), ref)),
    "meses_assinatura": dict(log=True, nome="meses de assinatura", resumo="median",
                             calc=lambda ref, b: ((ref - b.inicio).dt.days / 30.44).round(1)),
}

# Rótulos (regra 6): (rótulo, variável, "max" ou "min"), na ordem em que são aplicados.
ROTULOS = [("Cobrança falhando", "recusas_180d", "max"),
           ("Parados", "dias_sem_treino", "max"),
           ("Recém-chegados", "meses_assinatura", "min")]
ORDEM_PREFERIDA = ["Engajados", "Recém-chegados", "Parados", "Cobrança falhando"]


def ler_extras():
    tabelas = []
    for arquivo, colunas in EXTRAS:
        caminho = OURO / arquivo
        if not caminho.exists():
            sys.exit(f"EXTRAS: falta {caminho.relative_to(RAIZ)}; gere a tabela ou tire a entrada")
        df = pd.read_csv(caminho)
        faltam = [c for c in ["user_id", *colunas] if c not in df.columns]
        if faltam:
            sys.exit(f"EXTRAS: {arquivo} não tem as colunas {faltam}")
        chave = ["user_id", "data_ref"] if "data_ref" in df.columns else ["user_id"]
        tabelas.append((df[chave + colunas], chave, colunas))
        for c in colunas:
            VARIAVEIS[c] = dict(log=False, nome=c, resumo="median", calc=None)
    return tabelas


EXTRAS_TAB = ler_extras()
VARS = list(VARIAVEIS)


def base(ref):
    b = ass[(ass.inicio <= ref) & (ass.data_fim.isna() | (ass.data_fim > ref))].set_index("user_id")
    if b.empty:
        sys.exit(f"nenhuma assinatura paga ativa em {ref:%d/%m/%Y}: confira assinaturas.csv")
    f = pd.DataFrame(index=b.index)
    f["data_ref"] = ref.date().isoformat()
    for nome, v in VARIAVEIS.items():
        if v["calc"] is not None:
            f[nome] = v["calc"](ref, b).reindex(f.index).fillna(0).astype(float)
    for df, chave, colunas in EXTRAS_TAB:
        f = f.reset_index().merge(df, on=chave, how="left").set_index("user_id")
    f["plano"] = b.plano_atual
    f["canal"] = b.canal
    f["metodo"] = b.metodo
    fim = b.data_fim
    f["saiu_60d"] = (fim.notna() & (fim <= ref + HORIZONTE)).astype(int)
    f["motivo_fim_60d"] = b.motivo_fim.where(f.saiu_60d == 1)
    f = f.join(usu.set_index("user_id")[["sistema", "idade_corte", "relogio_conectado"]])
    vazias = [c for c in VARS if f[c].isna().any()]
    if vazias:
        sys.exit(f"variáveis sem valor em {ref:%d/%m/%Y}: {vazias} (EXTRAS sem a conta toda?)")
    return f


def matriz(f):
    x = f[VARS].astype(float).copy()
    log = [c for c in VARS if VARIAVEIS[c]["log"]]
    x[log] = np.log1p(x[log].clip(lower=0))
    return x


treino = base(REF_TREINO)
corte = base(REF_CORTE)
x_tr = matriz(treino)
mu, sd = x_tr.mean(), x_tr.std().replace(0, 1)  # variável constante não divide por zero
z_tr = ((x_tr - mu) / sd).values
z_co = ((matriz(corte) - mu) / sd).values

# --- escolha de k (regra 5) ---------------------------------------------------------------
rng = np.random.default_rng(SEED)
amostra = rng.choice(len(z_tr), size=min(5000, len(z_tr)), replace=False)
modelos, escolha = {}, []
for k in sorted(set(K_TESTE) | set(range(K_FAIXA[0], K_FAIXA[1] + 1))):
    modelos[k] = KMeans(n_clusters=k, n_init=20, random_state=SEED).fit(z_tr)
    sil = silhouette_score(z_tr[amostra], modelos[k].labels_[amostra])
    escolha.append({"k": k, "inercia": modelos[k].inertia_, "silhouette": sil})
escolha = pd.DataFrame(escolha).set_index("k")
K = escolha.loc[K_FAIXA[0]:K_FAIXA[1], "silhouette"].idxmax()
km = modelos[K]
print(escolha.round(3).to_string(), f"\nk escolhido: {K}")
centros = pd.DataFrame(km.cluster_centers_, columns=VARS)

# --- rótulos (regra 6) ----------------------------------------------------------------------
rot = {}
for rotulo, var, lado in ROTULOS:
    livres = centros.drop(index=list(rot))
    if var not in VARS or len(livres) < 2:
        continue
    i = livres[var].idxmax() if lado == "max" else livres[var].idxmin()
    if abs(livres.loc[i, var]) >= 1:
        rot[i] = rotulo
livres = centros.drop(index=list(rot))
if len(livres):
    rot[livres.treinos_30d.idxmax() if "treinos_30d" in VARS else livres.index[0]] = "Engajados"
for n, i in enumerate(centros.drop(index=list(rot)).index, start=1):
    rot[i] = f"Grupo {n}"
ORDEM = [s for s in ORDEM_PREFERIDA if s in rot.values()] + \
        sorted(s for s in rot.values() if s not in ORDEM_PREFERIDA)
COR = dict(zip(ORDEM, CORES))

treino["segmento"] = pd.Series(km.labels_, index=treino.index).map(rot)
corte["segmento"] = pd.Series(km.predict(z_co), index=corte.index).map(rot)
corte["saiu_60d"] = np.nan  # o horizonte depois do corte ainda não aconteceu
corte["motivo_fim_60d"] = np.nan

saida = pd.concat([treino, corte]).reset_index()
saida = saida[["user_id", "data_ref", "segmento"] + VARS + [
    "plano", "canal", "metodo", "sistema", "idade_corte", "relogio_conectado",
    "saiu_60d", "motivo_fim_60d"]]
SAIDA.parent.mkdir(parents=True, exist_ok=True)
saida.to_csv(SAIDA, index=False)

# --- conferência ------------------------------------------------------------------------
assert saida.segmento.notna().all() and len(saida) == len(treino) + len(corte)
assert not saida.duplicated(["user_id", "data_ref"]).any(), "assinante repetido numa data"
pequenos = treino.segmento.value_counts(normalize=True).loc[lambda s: s < 0.01]
if len(pequenos):
    print(f"aviso: segmentos com menos de 1% da base: {pequenos.round(4).to_dict()}")
print(f"{SAIDA.relative_to(RAIZ)}: {len(saida)} linhas · base {REF_TREINO:%d/%m} {len(treino):,} · "
      f"base {REF_CORTE:%d/%m} {len(corte):,} · saída em 60 dias {treino.saiu_60d.mean():.1%}")

# --- perfil ------------------------------------------------------------------------------
def br(v, casas=1):
    """Número no formato brasileiro: 14.032 · 10,5."""
    return f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def pct(s, valor):
    return 100 * (s == valor).mean()


D_TR, D_CO = f"{REF_TREINO:%d/%m}", f"{REF_CORTE:%d/%m}"
FIM_JANELA = REF_TREINO + HORIZONTE
g = treino.groupby("segmento")
perfil = pd.DataFrame({f"assinantes {D_TR}": g.size(),
                       "% da base": 100 * g.size() / len(treino),
                       "saída em 60 dias (%)": 100 * g.saiu_60d.mean()})
for c in VARS:
    perfil[VARIAVEIS[c]["nome"]] = g[c].agg(VARIAVEIS[c]["resumo"])
perfil["% mensal"] = g.plano.apply(pct, valor="mensal")
perfil["% loja"] = g.canal.apply(pct, valor="loja")
perfil["% android"] = g.sistema.apply(pct, valor="android")
perfil = perfil.reindex(ORDEM)
perfil[f"assinantes {D_CO}"] = corte.segmento.value_counts().reindex(ORDEM).fillna(0)
perfil[f"% em {D_CO}"] = 100 * perfil[f"assinantes {D_CO}"] / len(corte)
saidas = treino[treino.saiu_60d == 1]
motivos = (pd.crosstab(saidas.segmento, saidas.motivo_fim_60d, normalize="index") * 100) \
    .reindex(ORDEM).fillna(0)
por_plano = (treino.pivot_table(index="segmento", columns="plano", values="saiu_60d",
                                aggfunc="mean") * 100).reindex(ORDEM)
print(perfil.round(1).T.to_string())
print(motivos.round(1).to_string())
print(por_plano.round(1).to_string())

# --- artefato HTML -------------------------------------------------------------------------
P = perfil.round(1)
churn_base = 100 * treino.saiu_60d.mean()
z_seg = centros.rename(index=rot).reindex(ORDEM)
nomes = [VARIAVEIS[c]["nome"] for c in VARS]
POR_EXTENSO = {2: "Dois", 3: "Três", 4: "Quatro", 5: "Cinco", 6: "Seis", 7: "Sete"}
sil_k = escolha.loc[K, "silhouette"]

p = Pagina(
    "02 · Segmentos (k-means)",
    f"{POR_EXTENSO.get(K, K)} grupos de assinantes pelo comportamento no app, e quanto cada um "
    "sai em 60 dias.",
    "fonte: `dados/3.ouro/segmentos_kmeans.csv`, gerada por `notebooks/segmentos_kmeans_ouro.py` "
    "(decisões N1–N7)",
)
p.texto(f"""
**Regra.** Base: assinantes pagantes ativos em {REF_TREINO:%d/%m/%Y} ({br(len(treino), 0)}
assinaturas, sem as cortesias internas). Cada um é descrito por {len(VARS)} variáveis
calculadas só com dados até {D_TR}: {", ".join(nomes)}. Contagens em log, tudo padronizado;
k-means com k = {K}. Plano, canal e sistema ficam fora do agrupamento e servem para descrever
os grupos. **Saída em 60 dias** = assinatura terminada entre
{REF_TREINO + pd.Timedelta(days=1):%d/%m} e {FIM_JANELA:%d/%m/%Y} (média da base:
{br(churn_base)}%).
""")

p.secao("Os segmentos")
f = go.Figure()
for s in ORDEM:
    v = perfil.loc[s, "saída em 60 dias (%)"]
    f.add_trace(go.Bar(x=[s], y=[v], name=s, marker=dict(color=COR[s]), text=[f"{br(v)}%"],
                       textposition="outside",
                       hovertemplate=f"{s}: {br(v)}% · "
                                     f"{br(perfil.loc[s, f'assinantes {D_TR}'], 0)} assinantes<extra></extra>"))
f.add_hline(y=churn_base, line=dict(color="#52514e", width=1, dash="dash"),
            annotation_text=f"base: {br(churn_base)}%", annotation_position="top right")
layout_padrao(f, "saíram em 60 dias (%)", altura=340)
f.update_layout(showlegend=False, hovermode="closest")
p.figura(f, f"Parcela de cada segmento (base de {REF_TREINO:%d/%m/%Y}) cuja assinatura terminou "
            f"até {FIM_JANELA:%d/%m/%Y}.")

f = go.Figure(go.Heatmap(
    z=z_seg.values.T, x=ORDEM, y=nomes, zmid=0, zmin=-2, zmax=2,
    colorscale=[[0, "#2a78d6"], [0.5, "#fcfcfb"], [1, "#eb6834"]],
    text=z_seg.values.T.round(1), texttemplate="%{text}",
    hovertemplate="%{y} · %{x}: %{z:.2f} desvios<extra></extra>", colorbar=dict(title="z")))
layout_padrao(f, altura=120 + 34 * len(VARS))
f.update_layout(hovermode="closest", margin=dict(l=230))
f.update_yaxes(autorange="reversed", gridcolor="rgba(0,0,0,0)")
fora = [f"{VARIAVEIS[c]['nome']} em {s} ({br(z_seg.loc[s, c])})"
        for s in ORDEM for c in VARS if abs(z_seg.loc[s, c]) > 2]
p.figura(f, "Centróides em desvios-padrão da média da base (laranja = acima, azul = abaixo). "
            "A cor satura em ±2" + (f"; passam disso: {'; '.join(fora)}." if fora else "."))

# Dispersão em 2D: as variáveis padronizadas projetadas nos 2 componentes principais (PCA),
# amostra de assinantes por segmento e os centróides do k-means no mesmo plano.
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
# Rótulos de centróides vizinhos vão um para cima-esquerda, outro para baixo-direita.
dist = np.linalg.norm(cen[:, None] - cen[None], axis=2) + np.eye(len(cen)) * 99
for i, s in rot.items():
    j = dist[i].argmin()
    pos = "top center" if dist[i, j] > 1 else ("top left" if cen[i, 0] <= cen[j, 0] else "bottom right")
    f.add_trace(go.Scatter(x=[cen[i, 0]], y=[cen[i, 1]], mode="markers+text", showlegend=False,
                           marker=dict(symbol="x", size=18, color=COR[s],
                                       line=dict(width=2, color="#0b0b0b")),
                           text=[f"<b>{s}</b>"], textposition=pos,
                           textfont=dict(color="#0b0b0b", size=12),
                           hovertemplate=f"centróide · {s}<extra></extra>"))
layout_padrao(f, f"componente 2 ({br(var[1], 0)}% da variância)", altura=480)
f.update_xaxes(title_text=f"componente 1 ({br(var[0], 0)}% da variância)", showgrid=True,
               gridcolor="#e6e5e0", zeroline=False)
f.update_layout(hovermode="closest")
p.figura(f, f"Assinantes (amostra de {br(len(amostra), 0)}) e centróides (×) projetados nos dois "
            f"componentes principais das {len(VARS)} variáveis padronizadas, que juntos explicam "
            f"{br(var.sum(), 0)}% da variação. O k-means agrupa em todas as dimensões; na projeção "
            "em 2D, centróides próximos podem estar separados por uma variável que o plano não "
            "mostra (ver o mapa de calor acima).")

fmt = {c: "{:,.1f}" for c in P.columns} | \
      {c: "{:,.0f}" for c in [f"assinantes {D_TR}", f"assinantes {D_CO}"]}
p.tabela(P.reset_index(), "Perfil (medianas; % e médias onde indicado)", fmt)

p.secao("Cartões de persona")
HIPOTESE = {
    "Engajados": "quando saem, é por fim de objetivo (prova, evento) ou preço no mensal depois "
                 "do reajuste",
    "Recém-chegados": "hábito ainda não formado e pouco laço social no app; o primeiro "
                      "vencimento é o momento de risco",
    "Parados": "perda de hábito ou objetivo cumprido; no anual, a saída espera o vencimento",
    "Cobrança falhando": "churn involuntário: cartão vencido ou sem limite",
}
ACAO = {
    "Engajados": "programa de fidelidade e conteúdo de nova meta",
    "Recém-chegados": "onboarding social (conectar amigos, desafios em grupo)",
    "Parados": "reativação antes da renovação",
    "Cobrança falhando": "régua de cobrança e troca de meio de pagamento, sem desconto",
}


def tracos(s, n=3):
    z = z_seg.loc[s]
    top = z.abs().sort_values(ascending=False).index[:n]
    return "; ".join(f"{'mais' if z[c] > 0 else 'menos'} {VARIAVEIS[c]['nome']} "
                     f"({br(perfil.loc[s, VARIAVEIS[c]['nome']])}, {br(z[c])} desvios)" for c in top)


for s in ORDEM:
    r = P.loc[s]
    risco = r["saída em 60 dias (%)"] >= 1.5 * churn_base
    prioridade = "ação imediata" if risco else "monitorar"
    hip = HIPOTESE.get(s, "a definir pelo grupo a partir dos traços")
    acao = f" ({ACAO[s]})" if s in ACAO else ""
    p.texto(f"""
**{s} · {br(r['% da base'], 0)}% da base · saem {br(r['saída em 60 dias (%)'])}% em 60 dias.**
Traços que mais separam o grupo: {tracos(s)}. {br(r['% mensal'], 0)}% no mensal,
{br(r['% loja'], 0)}% na loja, {br(r['% android'], 0)}% Android. **Hipótese de driver**: {hip}.
**Prioridade: {prioridade}{acao}.**
""")
p.texto(f"Prioridade: **ação imediata** quando o segmento sai pelo menos 1,5 vez a média da base "
        f"({br(1.5 * churn_base)}% em 60 dias); abaixo disso, **monitorar**.")

p.secao("Como cada segmento sai")
f = go.Figure()
for i, m in enumerate(motivos.columns):
    f.add_trace(go.Bar(y=ORDEM, x=motivos[m], name=m, orientation="h",
                       marker=dict(color=CORES[(i + 4) % len(CORES)], line=dict(color="#fcfcfb", width=1)),
                       hovertemplate=f"{m}: %{{x:.0f}}%<extra></extra>"))
layout_padrao(f, altura=120 + 45 * len(ORDEM))
f.update_layout(barmode="stack", hovermode="closest", margin=dict(l=130))
f.update_xaxes(title_text="% das saídas do segmento em 60 dias", ticksuffix="%")
f.update_yaxes(autorange="reversed", gridcolor="rgba(0,0,0,0)")
p.figura(f, "Motivo do fim (`motivo_fim` de assinaturas) entre quem saiu em 60 dias.")
p.tabela(por_plano.round(1).reset_index(), "Saída em 60 dias por segmento e plano (%)",
         {c: "{:.1f}" for c in por_plano.columns})
achados = []
for plano in por_plano.columns:
    col = por_plano[plano].dropna()
    if len(col) >= 2:
        alto, baixo = col.idxmax(), col.idxmin()
        achados.append(f"- **{plano}**: {alto} sai {br(col[alto])}% em 60 dias, contra "
                       f"{br(col[baixo])}% de {baixo}.")
if "falha_pagamento" in motivos.columns:
    inv = motivos["falha_pagamento"]
    achados.append(f"- **Perda involuntária**: {inv.idxmax()} tem {br(inv.max(), 0)}% das saídas "
                   f"por falha de pagamento; nos demais fica entre {br(inv.drop(inv.idxmax()).min(), 0)}% "
                   f"e {br(inv.drop(inv.idxmax()).max(), 0)}%.")
p.texto("\n".join(achados))

p.secao("Escolha de k")
melhor = escolha.silhouette.idxmax()
p.texto(f"""
O silhouette (amostra de {br(len(amostra), 0)}) vai de {br(escolha.silhouette.min(), 2)} a
{br(escolha.silhouette.max(), 2)} para k de {escolha.index.min()} a {escolha.index.max()}: abaixo de
0,5, os grupos se sobrepõem, o que é comum em dados de comportamento. Entre {K_FAIXA[0]} e
{K_FAIXA[1]} segmentos (pedida do guia), k = {K} tem o maior silhouette ({br(sil_k, 3)}).
""" + (f"Fora dessa faixa, o maior é k = {melhor} ({br(escolha.loc[melhor, 'silhouette'], 3)})."
       if melhor != K else ""))
p.tabela(escolha.reset_index(), "Inércia e silhouette por k",
         {"inercia": "{:,.0f}", "silhouette": "{:.3f}"})

p.secao(f"A base hoje ({REF_CORTE:%d/%m/%Y})")
p.texto(f"""
Os {br(len(corte), 0)} assinantes ativos em {D_CO} recebem o segmento do centróide mais
próximo, com a mesma padronização de {D_TR} (sem reajustar o modelo).
""")
p.tabela(P[[f"assinantes {D_CO}", f"% em {D_CO}"]].reset_index(), f"Tamanho dos segmentos em {D_CO}",
         {f"assinantes {D_CO}": "{:,.0f}", f"% em {D_CO}": "{:.1f}"})

p.secao("Limitações")
p.texto(f"""
- Os segmentos são descritivos: a saída em 60 dias **coincide** com o perfil, não prova causa.
- A campanha de 10/08/2026 tratou parte da base de {D_TR}; a saída de 60 dias inclui esse efeito.
- Treinos vêm de `atividades.parquet`, que começa em {atv.dia.min():%m/%Y}; variáveis de
  engajamento não existem para datas anteriores.
- Silhouette de {br(sil_k, 2)}: as fronteiras entre segmentos são difusas.
- No anual, sair em 60 dias depende de a renovação cair na janela; compare segmentos dentro
  do mesmo plano (tabela acima).
""")

p.secao("Perguntas para a próxima etapa")
p.texto("""
- Os segmentos devem entrar no modelo de churn como variável, ou o modelo usa as mesmas
  variáveis e o segmento fica só para a comunicação?
- Acrescentar as variáveis de texto (objetivo do onboarding, intenção de sair no feed) quando
  a extração com IA estiver pronta (entrada em `EXTRAS`).
- Cruzar os segmentos com o resultado da campanha de ago/26 (uplift por segmento).
""")
destino = p.salvar("05_segmentos_kmeans.html")
print(f"artefato: {destino.relative_to(RAIZ)}")
