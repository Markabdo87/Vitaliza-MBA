"""Ouro -> artefatos/00_historia_da_eda.html: a história da EDA numa página só.

Não gera tabela. Lê as quatro tabelas de ouro e refaz os números de cada etapa, para que a
página-resumo nunca divirja das páginas 01–04. Roda depois dos notebooks *_ouro.py.

Regras:
  1. Cada número vem da tabela de ouro da etapa, com a mesma regra da página de detalhe
     (decisões G, K, W e L do decisoes.md). O notebook para se um número-âncora não bater:
     churn médio 5,6% (2025) e 6,6% (jan–set/2026), do enunciado; soma dos tipos de saída
     = perdas do churn mensal; 14.753 pagantes ativos em 30/09/2026, do enunciado.
  2. Uma seção por achado, com o achado no título, um gráfico e o link para a página de detalhe.
  3. Hipóteses de driver e prioridades são as das páginas 03 e 04: hipóteses a testar, não causas.

Uso: .venv/bin/python notebooks/eda_historia.py  (a partir da raiz do repo, depois do ouro)
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.preprocessing import StandardScaler

from _artefato import CORES, MESES_PT, Pagina, eixo_meses, layout_padrao, linha
from pesquisa_saida_prata import tema

RAIZ = Path(__file__).resolve().parent.parent
PRATA = RAIZ / "dados" / "2.prata"
OURO = RAIZ / "dados" / "3.ouro"


def br(x, d=1):
    return f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def mes_rot(m):
    """'2026-04' -> 'abr/26'."""
    p = pd.Period(m, freq="M")
    return f"{MESES_PT[p.month - 1]}/{str(p.year)[2:]}"


def sinal(x, d=2):
    """'+0,66 p.p.' / '−0,31 p.p.' — o sentido do número não fica fixo no texto."""
    return f"{'+' if x >= 0 else '−'}{br(abs(x), d)} p.p."


def sobe(x, d=2):
    return f"{'subiu' if x > 0 else 'caiu'} {br(abs(x), d)} p.p."


cm = pd.read_csv(OURO / "churn_mensal.csv")
qs = pd.read_csv(OURO / "assinantes_30jun26.csv")
sd = pd.read_csv(OURO / "saidas.csv", parse_dates=["inicio", "data_fim"])
sg = pd.read_csv(OURO / "segmentos.csv")

# --- números de cada etapa ---------------------------------------------------------------------
tot = cm[cm.recorte == "total"].set_index("mes")
med = {ano: tot[tot.index.str.startswith(ano)].churn_pct.mean() for ano in ["2025", "2026"]}
assert round(med["2025"], 1) == 5.6 and round(med["2026"], 1) == 6.6, "churn médio difere do enunciado"


def media_rec(recorte, segmento, ano):
    d = cm[(cm.recorte == recorte) & (cm.segmento == segmento) & cm.mes.str.startswith(ano)]
    return d.churn_pct.mean()


RECORTES = [("plano", "mensal", "mensal"), ("plano", "anual", "anual"),
            ("metodo", "google_play", "Google Play"), ("metodo", "app_store", "App Store"),
            ("canal", "site", "site (cartão e Pix)")]
var = pd.DataFrame([{"recorte": rot, "2025": media_rec(r, s, "2025"), "jan–set/26": media_rec(r, s, "2026")}
                    for r, s, rot in RECORTES])
var["p.p."] = var["jan–set/26"] - var["2025"]
v = var.set_index("recorte")

TIPOS = ["voluntária", "involuntária", "devolução"]
sd["mes"] = sd.data_fim.dt.to_period("M").astype(str)
perda = sd[sd.inicio < sd.data_fim.dt.to_period("M").dt.start_time]     # regra G1: ativo no dia 1
pt = perda.groupby(["mes", "tipo_saida"]).size().unstack(fill_value=0).reindex(tot.index, fill_value=0)
assert (pt[TIPOS].sum(axis=1) == tot.perdas).all(), "tipos de saída não somam as perdas da G1"
taxa_tipo = 100 * pt[TIPOS].div(tot.ativos_inicio, axis=0)
tipo_med = {ano: taxa_tipo[taxa_tipo.index.str.startswith(ano)].mean() for ano in ["2025", "2026"]}
dv = tipo_med["2026"]["voluntária"] - tipo_med["2025"]["voluntária"]
dtot = med["2026"] - med["2025"]

vol26 = sd[(sd.tipo_saida == "voluntária") & (sd.data_fim >= "2026-01-01")]
ant = vol26.groupby("plano").antecedencia_dias.median()

men = qs[qs.plano == "mensal"].copy()
an_v = qs[(qs.plano == "anual") & (qs.vence_jul_set == 1)].copy()
men["faixa"] = pd.cut(men.tempo_casa_meses, [-0.1, 3, 6, 12, 24, np.inf],
                      labels=["até 3", "3–6", "6–12", "12–24", "mais de 24"])
an_v["faixa"] = pd.cut(an_v.dias_treino_abr_jun, [-1, 0, 10, 25, 40, np.inf],
                       labels=["nenhum", "1–10", "11–25", "26–40", "mais de 40"])
t_men = men.groupby("faixa", observed=True).saiu.mean() * 100
t_an = an_v.groupby("faixa", observed=True).saiu.mean() * 100
ESTR = {"mensal": men, "anual que vence em jul–set": an_v}
ren = pd.DataFrame([{"estrato": e, "renovação em 30/06": r, "assinantes": len(d[d.renovacao_30jun == r]),
                     "saíram (%)": 100 * d[d.renovacao_30jun == r].saiu.mean()}
                    for e, d in ESTR.items() for r in ["ligada", "desligada"]])
rn = ren.set_index(["estrato", "renovação em 30/06"])

s31 = sg[(sg.data_ref == "2026-07-31") & (sg.segmento != "Já desligou")]
s30 = sg[sg.data_ref == "2026-09-30"]
assert len(s30) == 14753, "pagantes ativos em 30/09 diferem do enunciado"

# Estabilidade e silhueta refeitas com a mesma regra da L5 (k = 4, semente 0, 10 reamostras),
# para o texto não carregar número fixo: o Rand é o ajustado entre a base e cada reamostra.
VARS = ["treinos_semana", "dias_sem_treino", "tempo_casa_dias", "pct_ar_livre"]
X = StandardScaler().fit_transform(s31[VARS])
silhueta = silhouette_score(X, s31.segmento)
rng = np.random.default_rng(0)
amostras = [rng.integers(0, len(X), len(X)) for _ in range(10)]
ref = KMeans(4, n_init=10, random_state=0).fit_predict(X)
assert adjusted_rand_score(ref, s31.segmento) == 1.0, "agrupamento da história diverge do ouro; confira a regra L5"
rand = [adjusted_rand_score(ref, KMeans(4, n_init=10, random_state=0).fit(X[i]).predict(X))
        for i in amostras]
ORDEM = ["Parados", "Ativos ao ar livre", "Ativos em ambiente fechado", "Veteranos"]
COR_SEG = dict(zip(ORDEM, [CORES[7], CORES[3], CORES[0], CORES[2]]))
seg = pd.DataFrame({"saída 60 dias (%)": s31.groupby("segmento").saiu_60d.mean() * 100,
                    "assinantes em 30/09": s30.segmento.value_counts()}).loc[ORDEM]
media_seg = 100 * s31.saiu_60d.mean()
deslig = int((s30.segmento == "Já desligou").sum())

# --- números do texto que saem das tabelas citadas (o texto não carrega valor nem sentido fixo) ---
pico = tot.churn_pct.idxmax()
mes_ini, mes_fim = mes_rot(tot.index[0]), mes_rot(tot.index[-1])
planos_pp, metodos_pp = v.loc[["mensal", "anual"], "p.p."], v.loc[["Google Play", "App Store"], "p.p."]
rec_plano, rec_metodo = planos_pp.idxmax(), metodos_pp.idxmax()
direcao = "alta" if dtot > 0 else "queda"
rot3 = ("a alta é voluntária" if dv > 0 and dv / dtot >= 0.5 else
        "a alta é só em parte voluntária" if dv > 0 else "a alta não é voluntária")

sd26 = sd[(sd.data_fim >= "2026-06-01") & (sd.data_fim <= "2026-09-30")]
loja = 100 * (sd26.canal == "loja").mean()
# Pesquisa de saída com a regra **e a população** da etapa 03 (W5): a pesquisa inteira da prata,
# não só quem já expirou (o recorte do saidas.csv); última resposta de cada conta e tema pela
# função `tema` de pesquisa_saida_prata.
ps = pd.read_csv(PRATA / "pesquisa_saida.csv", parse_dates=["respondido_em"])
ps = ps.sort_values(["user_id", "respondido_em", "resposta_id"]).groupby("user_id").tail(1).copy()
ps["tema"] = ps.comentario.map(lambda c: tema(c)[0] if isinstance(c, str) else None)
ps["tema"] = ps.tema.fillna(
    pd.Series(np.where(ps.comentario.isna(), "sem comentário", "sem tema"), index=ps.index))
comum = sd[sd.pesquisa_tema.notna()][["user_id", "pesquisa_tema"]].merge(
    ps[["user_id", "tema"]], on="user_id", how="left")
assert (comum.pesquisa_tema == comum.tema).all(), "tema da pesquisa diverge do saidas.csv"
com_tema = ps[~ps.tema.isin(["sem comentário", "sem tema"])]
tema_top = com_tema.tema.value_counts().idxmax()
pct_tema = 100 * com_tema.tema.eq(tema_top).mean()
exemplos_tema = ('; "era até a prova", "já fiz o casamento"'
                 if tema_top == "objetivo_cumprido" else "")

# GPS: a mesma regra nos dois recortes declarados (etapa 02, jul–set, mensal android; etapa 04,
# ago–set, mensal ao ar livre), com o tamanho de cada lado. O sentido sai do cálculo, não do texto;
# se um dos lados ficar vazio o notebook para, em vez de publicar diferença de NaN.
def gps(base, col, saida, rotulo):
    d = base[base[col].notna()]
    sim, nao = d[d[col] > 0], d[d[col] == 0]
    if min(len(sim), len(nao)) == 0:
        sys.exit(f"recorte GPS '{rotulo}' tem só um lado ({len(sim)} com falha, {len(nao)} sem): "
                 "ajuste o recorte antes de publicar a comparação")
    tx_sim, tx_nao = 100 * sim[saida].mean(), 100 * nao[saida].mean()
    return {"rotulo": rotulo, "sim": len(sim), "nao": len(nao), "tx_sim": tx_sim,
            "tx_nao": tx_nao, "dif": tx_sim - tx_nao}


gps_02 = gps(qs[(qs.plano == "mensal") & (qs.sistema == "android")], "pct_gps_falho", "saiu",
             "mensal android, jul–set/26")
gps_04 = gps(s31[(s31.segmento == "Ativos ao ar livre") & (s31.plano == "mensal")],
             "pct_gps_falho", "saiu_60d", "mensal ao ar livre, ago–set/26")
gps_oposto = (gps_02["dif"] > 0) != (gps_04["dif"] > 0)

# perfil de cada grupo na base de 31/07 / 30/09, para a tabela de personas
med_seg = s31.groupby("segmento")[["treinos_semana", "dias_sem_treino", "tempo_casa_dias"]].median()
anual_seg = 100 * s31.groupby("segmento").plano.apply(lambda s: (s == "anual").mean())
anual_deslig = 100 * (s30[s30.segmento == "Já desligou"].plano == "anual").mean()
cai_men = t_men.iloc[0] > t_men.iloc[-1]
cai_an = t_an.iloc[0] > t_an.iloc[-1]
titulo5 = ("5. No mensal pesa o tempo de casa; no anual que vence, o treino" if cai_men and cai_an
           else "5. Tempo de casa no mensal e treino no anual que vence, por faixa")
estavel4 = np.mean(rand) >= 0.9

# --- página -------------------------------------------------------------------------------------
p = Pagina(
    "00 · A história da EDA",
    "Por que o churn da Vitaliza subiu em 2026, quem sai, por que sai e em que grupos os "
    "assinantes se dividem. Resumo das páginas 01 a 04, com os números refeitos a partir do ouro.",
    "fonte: `dados/3.ouro/*.csv`, gerada por `notebooks/eda_historia.py` · decisões em "
    "`decisoes.md` (G, K, W, L) · método em `memorial.md`",
)
p.texto(f"""
**Base.** Dados da Vitaliza até 30/09/2026, limpos em camadas (bronze → prata → ouro) por notebooks
que rodam do zero. {br(len(s30), 0)} assinantes pagantes ativos em 30/09/2026. Churn mensal = perdas
no mês ÷ ativos no dia 1, a métrica do enunciado.

**Páginas de detalhe:** [01 · Churn mensal](01_churn_mensal.html) · [02 · Quem saiu](02_quem_saiu.html) ·
[03 · Por que saem](03_por_que_saem.html) · [04 · Segmentos](04_segmentos.html).
""")

p.secao(f"1. O churn subiu de {br(med['2025'])}% para {br(med['2026'])}% ao mês")
f = go.Figure()
x = pd.PeriodIndex(tot.index, freq="M").to_timestamp()
linha(f, x, tot.churn_pct, "churn mensal", CORES[0], hovertemplate="%{y:.2f}%<extra></extra>")
for ano, ini, fim in [("2025", "2025-01-01", "2025-12-01"), ("2026", "2026-01-01", "2026-09-01")]:
    f.add_shape(type="line", x0=ini, x1=fim, y0=med[ano], y1=med[ano],
                line=dict(color="#52514e", width=1.5, dash="dot"))
    f.add_annotation(x=fim, y=med[ano], text=f"média {ano}: {br(med[ano], 2)}%", showarrow=False,
                     yshift=12, xanchor="right", font=dict(size=11))
layout_padrao(f, "churn no mês (%)", altura=320)
eixo_meses(f, "2024-08-01", "2026-09-01")
f.update_layout(showlegend=False)
p.figura(f, f"Churn mensal da base paga, {mes_ini}–{mes_fim} (ago–dez/24 com viés de sobrevivência, G3). "
            f"Pico em {mes_rot(pico)}: {br(tot.loc[pico, 'churn_pct'])}%.")
p.texto(f"""
- Os dois números do enunciado (5,6% e 6,6%) saem da regra G1: {br(med['2025'], 2)}% e
  {br(med['2026'], 2)}% de média mensal; o notebook para se não baterem. Detalhe em [01 · Churn mensal](01_churn_mensal.html).
""")

p.secao(f"2. A {direcao} veio do {rec_plano} ({sinal(v.loc[rec_plano, 'p.p.'])}) e do {rec_metodo}")
f = go.Figure()
for i, col in enumerate(["2025", "jan–set/26"]):
    f.add_trace(go.Bar(x=var.recorte, y=var[col], name=col, marker_color=CORES[i],
                       text=[f"{br(y, 2)}%" for y in var[col]], textposition="outside",
                       hovertemplate=f"{col}: %{{y:.2f}}%<extra></extra>"))
layout_padrao(f, "churn médio no mês (%)", altura=340)
f.update_layout(barmode="group", margin=dict(t=48))
p.figura(f, "Média mensal do churn por recorte, 2025 × jan–set/2026.")
p.texto(f"""
- O mensal {sobe(v.loc['mensal', 'p.p.'])} e o anual {sobe(v.loc['anual', 'p.p.'])} O reajuste do
  mensal (R$ 34,90 → R$ 39,90 em 01/03/26) coincide com a alta, mas não foi testado como causa.
- Google Play {sinal(v.loc['Google Play', 'p.p.'])} contra App Store {sinal(v.loc['App Store', 'p.p.'])}:
  o android é onde apareceu a falha de GPS de mai–jun/26.
""")

p.secao(f"3. Quem sai decide sair: {rot3} ({sinal(dv)})")
f = go.Figure()
for i, t in enumerate(TIPOS):
    f.add_trace(go.Bar(x=x, y=taxa_tipo[t], name=t, marker_color=CORES[i],
                       hovertemplate=f"{t}: %{{y:.2f}}%<extra></extra>"))
layout_padrao(f, "churn no mês (%)", altura=320)
eixo_meses(f, "2024-08-01", "2026-09-01")
f.update_layout(barmode="stack", margin=dict(t=48))
p.figura(f, "Churn mensal decomposto pelo tipo de saída; a soma é o churn do gráfico 1.")
p.texto(f"""
- Voluntária (desligou a renovação): {br(tipo_med['2025']['voluntária'], 2)}% → {br(tipo_med['2026']['voluntária'], 2)}%
  ao mês. Involuntária (falha de pagamento): {br(tipo_med['2025']['involuntária'], 2)}% →
  {br(tipo_med['2026']['involuntária'], 2)}%, pequena, estável e concentrada no mensal no cartão.
- Na pesquisa de saída inteira (regra e população da etapa 03: {br(len(ps), 0)} contas, só site,
  jun–set/26), o tema dominante dos comentários é "{tema_top.replace('_', ' ')}" ({br(pct_tema)}% dos
  {br(len(com_tema), 0)} com tema{exemplos_tema}), que não existe na lista de motivos. Detalhe em
  [03 · Por que saem](03_por_que_saem.html).
""")

p.secao(f"4. E avisa antes: {br(ant['mensal'], 0)} dias no mensal, {br(ant['anual'] / 30.4375, 0)} meses no anual")
f = go.Figure()
for i, pl in enumerate(["mensal", "anual"]):
    d = vol26[vol26.plano == pl].antecedencia_dias
    f.add_trace(go.Box(x=d, name=pl, marker_color=CORES[i], boxpoints=False, orientation="h",
                       hovertemplate=f"{pl}<extra></extra>"))
layout_padrao(f, altura=260)
f.update_layout(showlegend=False, hovermode="closest")
f.update_xaxes(title_text="dias entre desligar a renovação e a assinatura expirar")
p.figura(f, "Saídas voluntárias de jan–set/2026: caixa = do 1º ao 3º quartil; traço = mediana.")
p.texto(f"""
- Entre desligar a renovação e expirar, a pessoa segue assinante e usando o app (enunciado). No
  anual são meses: a maior janela para tentar reverter. No mensal, a ação tem de chegar antes.
""")

p.secao(titulo5)
f = make_subplots(rows=1, cols=2, horizontal_spacing=0.12,
                  subplot_titles=("Mensal · por tempo de casa (meses)",
                                  "Anual que vence · por dias com treino (abr–jun)"))
f.add_trace(go.Bar(x=t_men.index.astype(str), y=t_men, marker_color=CORES[0],
                   text=[f"{br(y)}%" for y in t_men], textposition="outside",
                   hovertemplate="%{x} meses: %{y:.1f}%<extra></extra>"), 1, 1)
f.add_trace(go.Bar(x=t_an.index.astype(str), y=t_an, marker_color=CORES[1],
                   text=[f"{br(y)}%" for y in t_an], textposition="outside",
                   hovertemplate="%{x} dias: %{y:.1f}%<extra></extra>"), 1, 2)
layout_padrao(f, "saíram em jul–set/26 (%)", altura=340)
f.update_layout(showlegend=False, hovermode="closest", margin=dict(t=56))
f.update_yaxes(range=[0, float(max(t_men.max(), t_an.max())) * 1.25])
f.update_yaxes(title_text="", row=1, col=2)
p.figura(f, f"Assinantes pagantes em 30/06/2026 ({br(len(qs), 0)}) e quem saiu até 30/09. O anual só "
            "pode sair no aniversário, por isso só entra o anual que vencia na janela (K6).")
p.texto(f"""
- **Mensal:** {br(t_men.iloc[0])}% de saída na faixa de {t_men.index[0]} meses de casa,
  {br(t_men.iloc[-1])}% na de {t_men.index[-1]} meses. A primeira experiência é o ponto fraco.
- **Anual que vence:** com {t_an.index[0]} dia de treino no trimestre, {br(t_an.iloc[0])}% não
  renovaram; com {t_an.index[-1]} dias, {br(t_an.iloc[-1])}%. O engajamento antes do aniversário decide
  a renovação. Detalhe em [02 · Quem saiu](02_quem_saiu.html).
""")

p.secao("6. Para muitos, a decisão já está tomada antes do sinal de uso")
f = go.Figure()
for i, r in enumerate(["ligada", "desligada"]):
    d = ren[ren["renovação em 30/06"] == r]
    f.add_trace(go.Bar(x=d.estrato, y=d["saíram (%)"], name=f"renovação {r} em 30/06",
                       marker_color=CORES[[2, 7][i]], customdata=d.assinantes,
                       text=[f"{br(y)}%" for y in d["saíram (%)"]], textposition="outside",
                       hovertemplate="%{y:.1f}% de %{customdata:,} assinantes<extra></extra>"))
layout_padrao(f, "saíram em jul–set/26 (%)", altura=320)
f.update_layout(barmode="group", margin=dict(t=48))
f.update_yaxes(range=[0, float(ren["saíram (%)"].max()) * 1.2])
p.figura(f, "Situação da renovação em 30/06 reconstruída pelos eventos (K7).")
p.texto(f"""
- {br(rn.loc[('anual que vence em jul–set', 'desligada'), 'assinantes'], 0)} anuais que venciam já tinham
  desligado a renovação em 30/06; {br(rn.loc[('anual que vence em jul–set', 'desligada'), 'saíram (%)'])}% saíram.
  Parte do "parou de treinar, então saiu" é o contrário: decidiu sair, então parou (causalidade reversa).
- Por isso a segmentação e o modelo olham quem **ainda** está com a renovação ligada; quem já desligou
  é uma lista de reversão à parte ({br(deslig, 0)} assinantes em 30/09).
""")

p.secao(f"7. Os assinantes se dividem em {len(ORDEM)} grupos "
        f"{'estáveis' if estavel4 else 'que só se repetem em parte'}")
f = go.Figure(go.Bar(
    y=ORDEM[::-1], x=seg["saída 60 dias (%)"][ORDEM[::-1]], orientation="h",
    marker_color=[COR_SEG[s] for s in ORDEM[::-1]],
    text=[f"{br(seg.loc[s, 'saída 60 dias (%)'])}% · {br(seg.loc[s, 'assinantes em 30/09'], 0)} assinantes"
          for s in ORDEM[::-1]], textposition="outside", cliponaxis=False,
    hovertemplate="%{y}: %{x:.1f}%<extra></extra>"))
f.add_vline(x=media_seg, line=dict(color="#52514e", width=1, dash="dot"),
            annotation_text=f"média {br(media_seg)}%", annotation_position="top")
layout_padrao(f, altura=300)
f.update_layout(hovermode="closest", margin=dict(t=40, l=190, r=40))
f.update_xaxes(title_text="% que decidiu sair em 60 dias (01/08–29/09/2026)",
               range=[0, float(seg["saída 60 dias (%)"].max()) * 1.6])
p.figura(f, "K-means (k = 4) nos pagantes de 31/07/2026 com a renovação ligada, em quatro variáveis: "
            "treinos por semana, dias sem treino, tempo de casa e % ao ar livre. Tamanho em 30/09.")
p.texto(f"""
- A saída não entra no agrupamento; só descreve os grupos depois. Os grupos se repetem em
  reamostras (índice de Rand {br(np.mean(rand), 3)}), mas a separação é fraca (silhueta
  {br(silhueta, 2)}): são regiões de um contínuo. Detalhe em [04 · Segmentos](04_segmentos.html).
""")

p.secao("8. Personas e priorização preliminar")
def m(sg, col):
    return med_seg.loc[sg, col]


prio = pd.DataFrame([
    {"segmento": "Parados",
     "quem é": f"{br(anual_seg['Parados'], 0)}% anual; paga e não treina há "
               f"{br(m('Parados', 'dias_sem_treino') / 30.4375, 0)} meses (mediana)",
     "hipótese de driver": "perda de rotina ou objetivo cumprido",
     "prioridade": "ação imediata (maior taxa)" if seg["saída 60 dias (%)"].idxmax() == "Parados"
                   else "ação imediata (taxa alta)"},
    {"segmento": "Ativos ao ar livre",
     "quem é": f"corre, caminha ou pedala {br(m('Ativos ao ar livre', 'treinos_semana'))}× por semana; "
               f"{br(100 - anual_seg['Ativos ao ar livre'], 0)}% mensal",
     "hipótese de driver": "treino com data marcada (prova); mensal recém-chegado",
     "prioridade": "ação imediata (maior volume)"},
    {"segmento": "Ativos em ambiente fechado",
     "quem é": f"força, funcional ou yoga {br(m('Ativos em ambiente fechado', 'treinos_semana'))}× por semana",
     "hipótese de driver": "rotina estável; risco no mensal novo e no cartão",
     "prioridade": "monitoramento"},
    {"segmento": "Veteranos",
     "quem é": f"{br(m('Veteranos', 'tempo_casa_dias') / 365.25)} anos de casa (mediana), treina "
               f"{br(m('Veteranos', 'treinos_semana'))}× por semana",
     "hipótese de driver": "hábito formado", "prioridade": "monitoramento (oferta seria custo)"},
    {"segmento": "Já desligou",
     "quem é": f"desligou a renovação e ainda paga ({br(anual_deslig, 0)}% anual)",
     "hipótese de driver": "decisão tomada; meses até expirar no anual",
     "prioridade": "lista de reversão"},
])
prio.insert(1, "assinantes em 30/09", [int((s30.segmento == s).sum()) for s in prio.segmento])
prio.insert(2, "saída 60 dias (%)", [seg.loc[s, "saída 60 dias (%)"] if s in seg.index else np.nan
                                     for s in prio.segmento])
p.tabela(prio, "Segmentos para o Customer Segmentation Report",
         {"assinantes em 30/09": "{:,.0f}", "saída 60 dias (%)": "{:.1f}"})
p.texto("""
- As hipóteses vêm do cruzamento das etapas 02 a 04 e são para testar, não causas. Toda ação sugerida
  leva um grupo de controle sorteado, para medir o efeito (uplift) antes de escalar.
""")

p.secao("9. O que a EDA não responde")
p.texto(f"""
- **Causa.** Cruzamento aponta suspeitos (reajuste, GPS falho, objetivo cumprido); só experimento
  sorteado, como a campanha de ago/26, chega perto de causa.
- **Risco individual.** A taxa do grupo é histórica; quem, dentro do grupo, vai sair até 29/11/2026 é
  a pergunta do modelo da semana 10.
- **Motivo na loja.** A pesquisa de saída só existe no site; a loja, {br(loja, 0)}% das saídas de
  jun–set/26, não diz por quê.
- **GPS falho.** No mensal android em jul–set, quem teve treino com GPS falho saiu
  {br(abs(gps_02['dif']))} p.p. {'mais' if gps_02['dif'] > 0 else 'menos'} que quem não teve
  ({br(gps_02['sim'], 0)} com falha × {br(gps_02['nao'], 0)} sem);
  no mensal ao ar livre em ago–set, {br(abs(gps_04['dif']))} p.p. {'mais' if gps_04['dif'] > 0 else 'menos'}
  ({br(gps_04['sim'], 0)} × {br(gps_04['nao'], 0)}) —
  {'sentidos opostos' if gps_oposto else 'mesmo sentido'}. Precisa de controle por tipo de treino
  antes de virar driver.
""")

p.secao("Como refazer cada número")
p.texto("""
- Rodar a prata e o ouro (`notebooks/*_prata.py`, depois `notebooks/*_ouro.py`) e então
  `notebooks/eda_historia.py`, a partir da raiz do repo, com o `.venv`.
- Cada regra tem ID no `decisoes.md` (G churn mensal, K quem saiu, W por que saem, L segmentação) e o
  porquê do método está no `memorial.md`.
""")

destino = p.salvar("00_historia_da_eda.html")
print(f"artefato: {destino.relative_to(RAIZ)}")
