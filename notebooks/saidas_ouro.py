"""Prata -> ouro: saidas.csv (uma assinatura paga encerrada) + artefatos/03_por_que_saem.html.

Pergunta: de que tipo são as saídas, qual tipo explica a subida de 2026, com quanta
antecedência o assinante avisa e o que ele diz quando sai?

Regras (decisões W1–W5 no decisoes.md; método e debate no memorial.md, etapa 03):
  1. Saídas: assinaturas.csv da prata com flag_cortesia = 0 e data_fim preenchida
     (07/07/2024 a 30/09/2026). Grão: uma assinatura encerrada (= um user_id).
  2. Tipo de saída pelo motivo_fim da prata: voluntária = renovacao_desligada;
     involuntária = falha_pagamento; devolução = chargeback ou reembolso.
  3. Churn por tipo: mesma regra da G1 (perda = data_fim no mês e ativa no dia 1). A soma
     dos três tipos é o churn mensal do 01_churn_mensal (o notebook para se não bater).
     Série de ago/2024 a set/2026 (G3).
  4. Antecedência do aviso (só voluntária): dias entre o último
     renovacao_automatica_desligada do eventos_assinatura e a data_fim. Desligamento que
     chega depois do fim (flag_apos_fim, loja) conta como 0 dia e fica marcado em
     flag_aviso_apos_fim.
  5. Pesquisa de saída: tema do comentário pela mesma regra de palavra-chave do diagnóstico
     de pesquisa_saida_prata.py (função tema, importada de lá), comparado ao motivo marcado.
     Quando a conta respondeu duas vezes, vale a resposta mais recente. A pesquisa só existe
     no site (cartão e Pix) e só de jun a set/2026.

Uso: .venv/bin/python notebooks/saidas_ouro.py  (a partir da raiz do repo)
"""
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from _artefato import CORES, Pagina, eixo_meses, layout_padrao
from pesquisa_saida_prata import tema

RAIZ = Path(__file__).resolve().parent.parent
PRATA = RAIZ / "dados" / "2.prata"
OURO = RAIZ / "dados" / "3.ouro"
SAIDA = OURO / "saidas.csv"

TIPO = {"renovacao_desligada": "voluntária", "falha_pagamento": "involuntária",
        "chargeback": "devolução", "reembolso": "devolução"}
TIPOS = ["voluntária", "involuntária", "devolução"]
COR_TIPO = dict(zip(TIPOS, CORES[:3]))

# --- 1. saídas ------------------------------------------------------------------------------
a = pd.read_csv(PRATA / "assinaturas.csv", parse_dates=["inicio", "data_fim"])
a = a[a.flag_cortesia == 0].rename(columns={"plano_atual": "plano"})
u = pd.read_csv(PRATA / "usuarios.csv", usecols=["user_id", "sistema"])
s = a[a.data_fim.notna()][["user_id", "plano", "canal", "metodo", "inicio", "data_fim",
                           "motivo_fim"]].copy()
s = s.merge(u, on="user_id", how="left", validate="one_to_one")
s["tipo_saida"] = s.motivo_fim.map(TIPO)
assert s.tipo_saida.notna().all(), "motivo_fim fora do mapa"
s["mes_fim"] = s.data_fim.dt.to_period("M").astype(str)
s["tempo_casa_meses"] = ((s.data_fim - s.inicio).dt.days / 30.4375).round(1)

ev = pd.read_csv(PRATA / "eventos_assinatura.csv", parse_dates=["data_hora_brt"],
                 usecols=["user_id", "seq_usuario", "data_hora_brt", "evento", "flag_apos_fim"])
des = (ev[ev.evento == "renovacao_automatica_desligada"].sort_values(["user_id", "seq_usuario"])
       .groupby("user_id").tail(1)[["user_id", "data_hora_brt", "flag_apos_fim"]]
       .rename(columns={"data_hora_brt": "desligou_em", "flag_apos_fim": "flag_aviso_apos_fim"}))
s = s.merge(des, on="user_id", how="left", validate="one_to_one")
vol = s.tipo_saida == "voluntária"
s.loc[~vol, ["desligou_em", "flag_aviso_apos_fim"]] = np.nan
s["antecedencia_dias"] = np.where(
    vol, (s.data_fim - s.desligou_em.dt.normalize()).dt.days.clip(lower=0), np.nan)
assert s.loc[vol, "antecedencia_dias"].notna().all(), "voluntária sem desligamento no log"

ps = pd.read_csv(PRATA / "pesquisa_saida.csv", parse_dates=["respondido_em"])
ps = ps.sort_values(["user_id", "respondido_em", "resposta_id"]).groupby("user_id").tail(1).copy()
ps["tema_comentario"] = ps.comentario.map(lambda c: tema(c)[0] if isinstance(c, str) else None)
ps["tema_comentario"] = ps.tema_comentario.fillna(
    pd.Series(np.where(ps.comentario.isna(), "sem comentário", "sem tema"), index=ps.index))
s = s.merge(ps[["user_id", "motivo_principal", "tema_comentario"]].rename(
    columns={"motivo_principal": "pesquisa_motivo", "tema_comentario": "pesquisa_tema"}),
    on="user_id", how="left", validate="one_to_one")

OURO.mkdir(parents=True, exist_ok=True)
s.to_csv(SAIDA, index=False)
print(f"{SAIDA.relative_to(RAIZ)}: {len(s)} saídas · {s.tipo_saida.value_counts().to_dict()}")

# --- 2. churn por tipo (regra G1) -----------------------------------------------------------
MESES = pd.period_range("2024-08", "2026-09", freq="M")
linhas = []
for m in MESES:
    d0 = m.start_time
    ativo = (a.inicio < d0) & (a.data_fim.isna() | (a.data_fim >= d0))
    perda = ativo & (a.data_fim.dt.to_period("M") == m)
    for plano in ["total", "mensal", "anual"]:
        sel = ativo if plano == "total" else ativo & (a.plano == plano)
        pp = perda & sel
        linha = {"mes": str(m), "plano": plano, "ativos": int(sel.sum())}
        for t in TIPOS:
            linha[t] = int((pp & a.motivo_fim.map(TIPO).eq(t)).sum())
        linhas.append(linha)
ct = pd.DataFrame(linhas)
for t in TIPOS:
    ct[f"churn_{t}"] = 100 * ct[t] / ct.ativos

cm = pd.read_csv(OURO / "churn_mensal.csv")
ref = cm[cm.recorte == "total"].set_index("mes")
tot = ct[ct.plano == "total"].set_index("mes")
assert (tot[TIPOS].sum(axis=1) == ref.loc[tot.index, "perdas"]).all(), "tipos não somam as perdas da G1"
print("conferência: voluntária + involuntária + devolução = perdas do churn_mensal em todos os meses")


def media(plano, ano, t):
    d = ct[(ct.plano == plano) & ct.mes.str.startswith(ano)]
    return d[f"churn_{t}"].mean()


res = pd.DataFrame([
    {"plano": pl, "tipo": t, "churn 2025 (%)": media(pl, "2025", t),
     "churn jan–set/26 (%)": media(pl, "2026", t)}
    for pl in ["total", "mensal", "anual"] for t in TIPOS])
res["variação (p.p.)"] = res["churn jan–set/26 (%)"] - res["churn 2025 (%)"]
print(res.round(2).to_string(index=False))

# --- 3. artefato ------------------------------------------------------------------------------
def br(x, d=1):
    return f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


r = res.set_index(["plano", "tipo"])

# valores citados no texto, derivados de `r`, `ct` e `s`
dev_max = ct.loc[ct.plano == "total", "churn_devolução"].max()
var_tipo = r.loc["total"]["variação (p.p.)"]
lider = var_tipo.idxmax()
titulo_lider = (f"**A subida é de saída {lider}** ({br(var_tipo[lider], 2)} p.p. na média mensal)"
                if var_tipo[lider] > 0 else
                "**Nenhum tipo de saída sobe na média mensal de 2026**")


def variacao(plano, tipo):
    """Formato "de X% para Y% (Z p.p.)" do tipo no plano, tudo vindo de `r`."""
    a25 = r.loc[(plano, tipo), "churn 2025 (%)"]
    a26 = r.loc[(plano, tipo), "churn jan–set/26 (%)"]
    return f"de {br(a25, 2)}% para {br(a26, 2)}% ({br(a26 - a25, 2)} p.p.)"


de, ate = s.data_fim.min(), s.data_fim.max()
periodo = f"{de:%d/%m/%Y} e {ate:%d/%m/%Y}"
js = s[(s.data_fim >= "2026-06-01") & (s.data_fim <= "2026-09-30")]
loja_pct = 100 * js.canal.eq("loja").mean()
recem = s[(s.tipo_saida == "voluntária") & (s.plano == "mensal")
          & (s.tempo_casa_meses <= 6) & (s.data_fim >= "2026-01-01")]
n_recem = len(recem)
med_recem = recem.antecedencia_dias.median()
assert n_recem > 0, "recorte 'mensal até 6 meses' vazio: a hipótese do recém-chegado não se sustenta"
assert pd.notna(med_recem), "mediana do aviso vazia no recorte de recém-chegados"

p = Pagina(
    "03 · Por que saem",
    "De que tipo são as saídas, qual tipo explica a subida de 2026, com quanta antecedência o "
    "assinante avisa e o que ele diz quando sai.",
    "fonte: `dados/3.ouro/saidas.csv`, gerada por `notebooks/saidas_ouro.py` (decisões W1–W5) · "
    "método em `memorial.md`, etapa 03",
)
p.texto(f"""
**Regra.** {br(len(s), 0)} assinaturas pagas encerradas entre {periodo}, pelo
`motivo_fim` da prata: **voluntária** (desligou a renovação), **involuntária** (falha de
pagamento) e **devolução** (chargeback ou reembolso). O churn por tipo usa a regra G1; somados,
os três tipos dão o churn mensal do `01_churn_mensal` em todos os meses.
""")

p.secao("Qual tipo de saída subiu em 2026")
f = go.Figure()
x = pd.PeriodIndex(tot.index, freq="M").to_timestamp()
for t in TIPOS:
    f.add_trace(go.Bar(x=x, y=tot[f"churn_{t}"], name=t, marker_color=COR_TIPO[t],
                       hovertemplate=f"{t}: %{{y:.2f}}%<extra></extra>"))
layout_padrao(f, "churn no mês (%)")
eixo_meses(f, "2024-08-01", "2026-09-01")
f.update_layout(barmode="stack", margin=dict(t=48))
f.add_vline(x="2026-03-01", line=dict(color="#52514e", width=1, dash="dot"))
p.figura(f, "Churn mensal da base paga decomposto por tipo de saída (a soma é o churn total do "
            "01). Linha pontilhada: reajuste do mensal em 01/03/26.")
p.tabela(res, "Média mensal por tipo de saída, 2025 × jan–set/2026",
         {c: "{:.2f}" for c in ["churn 2025 (%)", "churn jan–set/26 (%)", "variação (p.p.)"]})
p.texto(f"""
- {titulo_lider}. Na base total, a voluntária vai {variacao('total', 'voluntária')}, a
  involuntária {variacao('total', 'involuntária')} e a devolução {variacao('total', 'devolução')};
  no mês, a devolução nunca passou de {br(dev_max, 2)}% do total.
- Por plano, a voluntária vai {variacao('mensal', 'voluntária')} no mensal e
  {variacao('anual', 'voluntária')} no anual; a involuntária, {variacao('mensal', 'involuntária')}
  no mensal e {variacao('anual', 'involuntária')} no anual.
""")

p.secao("Involuntária: onde a cobrança falha")
inv = s[(s.tipo_saida == "involuntária") & (s.data_fim >= "2026-01-01")]
a26 = a[(a.inicio < "2026-09-30") & (a.data_fim.isna() | (a.data_fim >= "2026-01-01"))]
tab = (inv.groupby(["plano", "metodo"]).size().rename("saídas involuntárias")
       .to_frame().join(a26.groupby(["plano", "metodo"]).size().rename("assinaturas ativas em 2026"))
       .reset_index())
tab["por 100 assinaturas"] = 100 * tab["saídas involuntárias"] / tab["assinaturas ativas em 2026"]
p.tabela(tab, "Saídas por falha de pagamento em jan–set/2026, por plano e método",
         {"saídas involuntárias": "{:,.0f}", "assinaturas ativas em 2026": "{:,.0f}",
          "por 100 assinaturas": "{:.2f}"})
t_inv = tab.set_index(["plano", "metodo"])["por 100 assinaturas"]
outros = t_inv.loc["mensal"].drop("cartao")
p.texto(f"""
- **O cartão concentra a falha de pagamento**: no mensal, {br(t_inv.loc[('mensal', 'cartao')], 1)}
  saídas involuntárias por 100 assinaturas no cartão, contra {br(outros.min(), 1)} a
  {br(outros.max(), 1)} nos outros métodos. No anual, o cartão também é o pior
  ({br(t_inv.loc[('anual', 'cartao')], 1)}).
- Denominador: assinaturas pagas ativas em algum dia de jan–set/2026. É uma taxa do período,
  não mensal: serve para comparar métodos entre si.
""")

p.secao("Antecedência: quanto tempo antes o assinante avisa")
v26 = s[vol & (s.data_fim >= "2026-01-01")]
f = go.Figure()
for i, pl in enumerate(["mensal", "anual"]):
    d = v26[v26.plano == pl].antecedencia_dias
    f.add_trace(go.Histogram(x=d, name=pl, marker_color=CORES[i], opacity=0.75,
                             xbins=dict(start=0, end=370, size=7 if pl == "mensal" else 14),
                             histnorm="percent",
                             hovertemplate=f"{pl}: %{{x}} dias · %{{y:.1f}}%<extra></extra>"))
layout_padrao(f, "% das saídas voluntárias do plano")
f.update_layout(barmode="overlay", hovermode="closest", margin=dict(t=48))
f.update_xaxes(title_text="dias entre desligar a renovação e a assinatura expirar")
p.figura(f, "Saídas voluntárias de jan–set/2026. Antecedência = data do fim − data do último "
            "desligamento da renovação.")
ant = (v26.groupby(["plano", "canal"]).antecedencia_dias
       .describe(percentiles=[.25, .5, .75])[["count", "25%", "50%", "75%"]].reset_index()
       .rename(columns={"count": "saídas", "25%": "Q1 (dias)", "50%": "mediana (dias)", "75%": "Q3 (dias)"}))
p.tabela(ant, "Antecedência do aviso por plano e canal (voluntárias, jan–set/2026)",
         {"saídas": "{:,.0f}", "Q1 (dias)": "{:.0f}", "mediana (dias)": "{:.0f}", "Q3 (dias)": "{:.0f}"})
med = v26.groupby("plano").antecedencia_dias.median()
apos = v26[v26.flag_aviso_apos_fim.eq(1)]
apos_loja = int(apos.canal.eq("loja").sum())
apos_site = int(apos.canal.eq("site").sum())
an_ant = v26[v26.plano == "anual"].antecedencia_dias
moda, n_moda = an_ant.mode().iloc[0], int((an_ant == an_ant.mode().iloc[0]).sum())
viz = max(int((an_ant == moda + d).sum()) for d in (-14, -7, 7, 14))
p.texto(f"""
- **O anual avisa com meses de antecedência**: mediana de {br(med['anual'], 0)} dias entre desligar a
  renovação e o fim. Quem desliga no anual segue pagando (e usando) até o vencimento: é uma janela
  longa para tentar reverter.
- No anual há um pico isolado: {n_moda} desligamentos ({br(100 * n_moda / len(an_ant))}%)
  exatamente {moda:.0f} dias antes do fim, na loja e no site, com os dias vizinhos (uma e duas
  semanas antes e depois) em no máximo {br(viz, 0)}. Coincide com algum lembrete de renovação?
  O enunciado não descreve um; fica como pergunta.
- **O mensal avisa em semanas**: mediana de {br(med['mensal'], 0)} dias. A intervenção no mensal
  tem de chegar antes de ele desligar.
- {br(len(apos), 0)} saídas voluntárias ({br(apos_loja, 0)} na loja e {br(apos_site, 0)} no site)
  têm o desligamento registrado depois do fim (`flag_aviso_apos_fim`, E8) e contam como 0 dia.
""")

p.secao("O que dizem na pesquisa de saída")
ps["expirou_ate_corte"] = ps.user_id.isin(s.user_id).map({True: "já expirou", False: "ainda ativo em 30/09"})
ps = ps.merge(a[["user_id", "plano", "metodo"]], on="user_id", how="left")
cruz = pd.crosstab(ps.tema_comentario, ps.motivo_principal, margins=True, margins_name="total")
ordem = cruz["total"].drop("total").sort_values(ascending=False).index.tolist() + ["total"]
cruz.columns.name = None
cruz = cruz.loc[ordem].reset_index().rename(columns={"tema_comentario": "tema do comentário"})
p.tabela(cruz, f"Tema do comentário × motivo marcado ({br(len(ps), 0)} contas, última resposta)")
tema_pl = (pd.crosstab(ps.tema_comentario, ps.plano, normalize="columns") * 100).round(1)
tema_pl.columns.name = None
tema_pl = tema_pl.loc[[t for t in ordem if t in tema_pl.index]].reset_index().rename(
    columns={"tema_comentario": "tema do comentário"})
p.tabela(tema_pl, "Tema do comentário por plano (% das respostas do plano)",
         {c: "{:.1f}" for c in tema_pl.columns if c != "tema do comentário"})
com = ps[~ps.tema_comentario.isin(["sem comentário", "sem tema"])]
preco = ps[(ps.motivo_principal == "preco") & ps.comentario.notna()]
top_tema = com.tema_comentario.value_counts()
tema_top, n_top = top_tema.index[0], int(top_tema.iloc[0])
pct_top = 100 * n_top / len(com)
lista_fechada = set(ps.motivo_principal.dropna().unique())
# o texto do comentário tem de descrever o tema que de fato lidera; não fixar exemplo de outro tema
tema_txt = (f'**"Objetivo cumprido" é o tema dominante**: {br(pct_top)}% dos comentários com tema'
            if tema_top == "objetivo_cumprido" else
            f'**O tema dominante é `{tema_top}`**: {br(pct_top)}% dos comentários com tema'
            f' ({br(n_top, 0)} de {br(len(com), 0)})')
exemplos = (f' ("era só até a prova", "já fiz o casamento")'
            if tema_top == "objetivo_cumprido" else "")
fora_da_lista = ("Esse motivo não existe na lista fechada da pesquisa."
                 if tema_top not in lista_fechada else
                 f'Esse motivo existe na lista fechada da pesquisa (opção `{tema_top}`).')
tp = tema_pl.set_index("tema do comentário")
obj_anual = (tp["anual"].get("objetivo_cumprido", float("nan"))
             if "anual" in tp.columns else float("nan"))
obj_mensal = (tp["mensal"].get("objetivo_cumprido", float("nan"))
              if "mensal" in tp.columns else float("nan"))
dif_obj = abs(obj_anual - obj_mensal)
mesma_fatia = bool(dif_obj <= 5)
mistura = ('A fatia de "objetivo cumprido" é quase a mesma no anual e no mensal'
           if mesma_fatia else
           'A fatia de "objetivo cumprido" difere entre anual e mensal')
conclusao_mistura = (": o plano muda quando a pessoa sai, não tanto por quê." if mesma_fatia else ".")
p.texto(f"""
- {tema_txt}{exemplos}. {fora_da_lista}
- {mistura} ("objetivo cumprido" em {br(obj_anual)}% das respostas do anual e
  {br(obj_mensal)}% do mensal){conclusao_mistura}
- **O motivo marcado engana**: dos {len(preco)} que marcaram `preco` e comentaram, só
  {int((preco.tema_comentario == 'cobranca').sum())} falam de cobrança (Q7). `preco` parece a
  primeira opção da lista, não a razão.
- Limite: a pesquisa só existe no site (cartão e Pix) e em jun–set/2026; a loja, que é
  {br(loja_pct)}% das saídas de jun–set/2026, não responde. Amostra autosselecionada: indica
  temas, não proporções da base.
""")

p.secao("Hipóteses de driver por grupo (para o Segmentation Report)")
p.texto(f"""
Cruzamento das etapas 02 e 03. São hipóteses a testar, não causas.

- **Mensal recém-chegado** (até 6 meses de casa): saída voluntária alta, aviso de
  {br(med_recem, 0)} dias na mediana do próprio grupo ({br(n_recem, 0)} saídas; no mensal
  inteiro, {br(med['mensal'], 0)} dias).
  Driver suspeito: a primeira experiência não vira hábito; o reajuste de mar/26 coincide com a
  alta do voluntário no mensal.
- **Anual desengajado perto do vencimento**: para de treinar e desliga a renovação meses antes.
  Driver suspeito: objetivo cumprido (prova, evento) ou perda de rotina.
- **Android com GPS falho** (mai–jun/26): saída mais alta no mensal android com falha. Driver
  suspeito: experiência técnica ruim na versão nova do app.
- **Mensal no cartão com falha de pagamento**: problema estável e concentrado no cartão; driver
  operacional (cobrança), não de produto.
""")

p.secao("Três frases")
p.texto(f"""
- **O que o dado diz.** {titulo_lider.replace('**', '')}, e quem sai avisa:
  {br(med['mensal'], 0)} dias no mensal, cerca de {br(med['anual'] / 30.4375, 0)} meses no anual.
- **O que ele não diz.** Por que desligam: a pesquisa só cobre o site e o motivo marcado diverge
  do texto; o tema `{tema_top}` aparece no texto, mas não sabemos o quanto pesa na loja.
- **A próxima pergunta.** Os grupos das hipóteses acima existem como segmentos distintos quando
  agrupamos os assinantes ativos, e quanto da base atual cai em cada um?
""")

p.secao("Limites")
p.texto("""
- `motivo_fim` diz como a assinatura terminou, não por quê.
- Antecedência só para voluntárias e pelo último desligamento; quem religou e desligou de novo
  conta a partir do último.
- Taxa involuntária por método usa um denominador de período, não mensal.
""")

destino = p.salvar("03_por_que_saem.html")
print(f"artefato: {destino.relative_to(RAIZ)}")
