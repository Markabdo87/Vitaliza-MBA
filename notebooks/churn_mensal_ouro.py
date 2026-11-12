"""Prata -> ouro: churn_mensal.csv (um mês × recorte × segmento) + artefatos/01_churn_mensal.html.

Regras (decisão G1 no decisoes.md):
  1. Base paga: assinaturas.csv da prata com flag_cortesia = 0 (sai a cortesia interna).
  2. Ativo no início do mês m: inicio < dia 1 de m e (data_fim vazia ou data_fim >= dia 1
     de m). Datas de assinaturas já estão em Brasília e batem 100% com os eventos (A1, E1).
  3. Perda no mês m: data_fim cai em m e a assinatura estava ativa no início de m. Quem
     assina e sai no mesmo mês não entra nem na base nem nas perdas (é a regra que reproduz
     os números do enunciado, seção 01).
  4. churn_pct = perdas / ativos_inicio × 100.
  5. Plano e canal são fixos por assinatura (ninguém troca de plano ou canal no log, E4),
     então o recorte usa plano_atual e canal da prata.
  6. Meses: ago/2024 a set/2026 (corte). Jul/2024 fica de fora: o log de fins começa em
     07/07/2024, então o mês sai incompleto (só as perdas a partir do dia 7 entram). Antes
     de jul/2024 as assinaturas encerradas não estão na base (A5).
  7. Recortes: total, plano, canal, plano_canal, metodo.

Conferência com o enunciado (o notebook para se não bater): 8.540 ativos no início de
jan/2025; abr/2026 com 1.154 perdas sobre 14.237 ativos (8,1%); 14.319 ativos no início de
set/2026; média mensal 5,6% em 2025 e 6,6% em jan–set/2026; ago/26 5,9%, set/26 5,0%.

Uso: .venv/bin/python notebooks/churn_mensal_ouro.py  (a partir da raiz do repo)
"""
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

from _artefato import CORES, Pagina, eixo_meses, layout_padrao, linha

RAIZ = Path(__file__).resolve().parent.parent
PRATA = RAIZ / "dados" / "2.prata"
SAIDA = RAIZ / "dados" / "3.ouro" / "churn_mensal.csv"

bruto = pd.read_csv(PRATA / "assinaturas.csv", parse_dates=["inicio", "data_fim"])
n_cortesia = int(bruto.flag_cortesia.sum())
a = bruto[bruto.flag_cortesia == 0].copy()
a["plano_canal"] = a.plano_atual + " · " + a.canal
a["total"] = "total"
a["mes_fim_p"] = a.data_fim.dt.to_period("M")

MESES = pd.period_range("2024-08", "2026-09", freq="M")
RECORTES = {"total": "total", "plano": "plano_atual", "canal": "canal",
            "plano_canal": "plano_canal", "metodo": "metodo"}

linhas = []
for m in MESES:
    d0 = m.start_time
    ativo = (a.inicio < d0) & (a.data_fim.isna() | (a.data_fim >= d0))
    perda = ativo & (a.mes_fim_p == m)
    entrou = (a.inicio.dt.to_period("M") == m)
    for recorte, col in RECORTES.items():
        g = pd.DataFrame({"seg": a[col], "ativo": ativo, "perda": perda, "entrou": entrou})
        agg = g.groupby("seg")[["ativo", "perda", "entrou"]].sum()
        for seg, r in agg.iterrows():
            linhas.append({"mes": str(m), "recorte": recorte, "segmento": seg,
                           "ativos_inicio": int(r.ativo), "perdas": int(r.perda),
                           "novas": int(r.entrou)})

df = pd.DataFrame(linhas)
df["churn_pct"] = (100 * df.perdas / df.ativos_inicio).round(3)
SAIDA.parent.mkdir(parents=True, exist_ok=True)
df.to_csv(SAIDA, index=False)

# --- conferência com o enunciado -------------------------------------------------------
tot = df[df.recorte == "total"].set_index("mes")
media = lambda ano: tot[tot.index.str.startswith(ano)].churn_pct.mean()
confere = [
    ("ativos início jan/25", 8540, tot.loc["2025-01", "ativos_inicio"]),
    ("ativos início abr/26", 14237, tot.loc["2026-04", "ativos_inicio"]),
    ("perdas abr/26", 1154, tot.loc["2026-04", "perdas"]),
    ("churn abr/26 (%)", 8.1, round(tot.loc["2026-04", "churn_pct"], 1)),
    ("ativos início set/26", 14319, tot.loc["2026-09", "ativos_inicio"]),
    ("churn ago/26 (%)", 5.9, round(tot.loc["2026-08", "churn_pct"], 1)),
    ("churn set/26 (%)", 5.0, round(tot.loc["2026-09", "churn_pct"], 1)),
    ("média mensal 2025 (%)", 5.6, round(media("2025"), 1)),
    ("média mensal jan–set/26 (%)", 6.6, round(media("2026"), 1)),
]
for nome, esperado, obtido in confere:
    assert esperado == obtido, f"{nome}: esperado {esperado}, obtido {obtido}"
print(f"{SAIDA.relative_to(RAIZ)}: {len(df)} linhas · conferência com o enunciado OK")

# --- resumo por ano ---------------------------------------------------------------------
def resumo(recorte):
    d = df[df.recorte == recorte].copy()
    d["periodo"] = d.mes.str[:4].map({"2025": "2025", "2026": "jan–set/26"})
    d = d.dropna(subset=["periodo"])
    r = d.groupby(["segmento", "periodo"]).agg(churn=("churn_pct", "mean"),
                                               ativos=("ativos_inicio", "mean")).unstack()
    out = pd.DataFrame({
        "segmento": r.index,
        "ativos médios 2025": r[("ativos", "2025")].round(0).values,
        "ativos médios 2026": r[("ativos", "jan–set/26")].round(0).values,
        "churn 2025 (%)": r[("churn", "2025")].values,
        "churn 2026 (%)": r[("churn", "jan–set/26")].values,
    })
    out["variação (p.p.)"] = out["churn 2026 (%)"] - out["churn 2025 (%)"]
    return out

for rc in ["plano", "canal", "plano_canal", "metodo"]:
    print(resumo(rc).round(2).to_string(index=False))

# --- artefato HTML ------------------------------------------------------------------------
def br(x, d=1):
    return f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


# valores citados no texto, todos derivados de `tot` / `pl`
plano = df[df.recorte == "plano"]
pm = plano[plano.segmento == "mensal"].set_index("mes")
pa = plano[plano.segmento == "anual"].set_index("mes")

abr26 = tot.loc["2026-04"]
jan_mai = tot.loc["2026-01":"2026-05", "churn_pct"]
ago_set = tot.loc["2026-08":"2026-09", "churn_pct"]
jun_set = tot.loc["2026-06":"2026-09", "churn_pct"]
ano26 = tot.loc["2026-01":"2026-09", "churn_pct"]
base24 = tot.loc["2024-08":"2024-12", "churn_pct"]
sobe_jan = (tot.loc["2025-01", "churn_pct"] > tot.loc["2024-12", "churn_pct"]
            and tot.loc["2026-01", "churn_pct"] > tot.loc["2025-12", "churn_pct"])
MES_ABREV = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out",
             "nov", "dez"]
rotulo_mes = lambda m: f"{MES_ABREV[int(m[5:7]) - 1]}/{m[2:4]}"
pico26 = rotulo_mes(ano26.idxmax())
jan_mai_mais_alto = jan_mai.mean() > jun_set.mean()
# o mensal cai nos dois últimos meses? o anual muda de patamar em jul/25?
caiu_fim = (pm.loc["2026-08", "churn_pct"] < pm.loc["2026-07", "churn_pct"]
            and pm.loc["2026-09", "churn_pct"] < pm.loc["2026-08", "churn_pct"])
degrau_jul25 = (pa.loc["2025-07", "churn_pct"]
                > pa.loc["2025-01":"2025-06", "churn_pct"].max())

m25 = pm.loc["2025-01":"2025-12", "churn_pct"]
NOMES = {"2026-03": "mar", "2026-04": "abr", "2026-05": "mai", "2026-06": "jun",
         "2026-07": "jul"}
pico_mensal = ", ".join(f"{br(pm.loc[m, 'churn_pct'])}% em {n}" for m, n in NOMES.items())
a25 = pa.loc["2025-01":"2025-12", "churn_pct"]
a_desde_jul25 = pa.loc["2025-07":, "churn_pct"]
menor_serie = pm.churn_pct.idxmin() == "2026-09"
r25_mensal, r25_anual = m25.mean(), a25.mean()
r26_mensal = pm.loc["2026-01":"2026-09", "churn_pct"].mean()
r26_anual = pa.loc["2026-01":"2026-09", "churn_pct"].mean()
delta_plano = {"mensal": r26_mensal - r25_mensal, "anual": r26_anual - r25_anual}
plano_que_mais_sobe = max(delta_plano, key=delta_plano.get)
frase_sobe_plano = (f"**O plano que mais sobe é o {plano_que_mais_sobe}**"
                   if delta_plano[plano_que_mais_sobe] > 0 else
                   "**Nenhum plano sobe na média de 2026**")

p = Pagina(
    "01 · Churn mensal",
    "Quantos assinantes pagantes a Vitaliza perde por mês, e como isso muda por plano e canal.",
    "fonte: `dados/3.ouro/churn_mensal.csv`, gerada por `notebooks/churn_mensal_ouro.py` "
    "(decisão G1)",
)
p.texto(f"""
**Regra.** Churn do mês = assinaturas pagas que terminaram no mês ÷ assinantes pagantes
ativos no dia 1 do mês. Quem assina e sai dentro do mesmo mês não entra na conta. Fora as
{br(n_cortesia, 0)} cortesias internas. Com essa regra os números batem com o enunciado:
{br(tot.loc['2025-01', 'ativos_inicio'], 0)} ativos em jan/25, {br(abr26.churn_pct)}% em abr/26
({br(abr26.perdas, 0)} ÷ {br(abr26.ativos_inicio, 0)}), média de {br(media('2025'))}% em 2025 e
{br(media('2026'))}% em jan–set/26.
""")

meses_dt = pd.PeriodIndex(tot.index, freq="M").to_timestamp()

def marcos(fig):
    fig.add_vrect(x0="2026-05-01", x1="2026-06-30", fillcolor="#e34948", opacity=0.07, line_width=0)
    fig.add_vline(x="2026-03-01", line=dict(color="#52514e", width=1, dash="dot"))
    fig.add_vline(x="2026-08-10", line=dict(color="#52514e", width=1, dash="dot"))
    for x, txt in [("2026-03-01", "reajuste<br>mensal"), ("2026-05-25", "pico tickets<br>GPS"),
                   ("2026-08-10", "campanha")]:
        fig.add_annotation(x=x, y=1, yref="paper", text=txt, showarrow=False,
                           font=dict(size=11, color="#52514e"), yanchor="bottom")

p.secao("A série total")
f = go.Figure()
linha(f, meses_dt, tot.churn_pct, "churn total", CORES[0],
      hovertemplate="%{y:.2f}%<extra></extra>")
for ano, x0, x1 in [("2025", "2025-01-01", "2025-12-01"), ("2026", "2026-01-01", "2026-09-01")]:
    f.add_shape(type="line", x0=x0, x1=x1, y0=media(ano), y1=media(ano),
                line=dict(color="#52514e", width=1, dash="dash"))
    f.add_annotation(x=x1, y=media(ano), text=f"média {ano}: {media(ano):.1f}%",
                     showarrow=False, xanchor="right", yanchor="bottom", font=dict(size=11))
marcos(f)
layout_padrao(f, "churn no mês (%)"); eixo_meses(f, "2024-08-01", "2026-09-01")
f.update_layout(showlegend=False, margin=dict(t=40))
p.figura(f, "Churn mensal da base paga, ago/24–set/26. Tracejado: média do ano. "
            "Faixa vermelha: pico de chamados de GPS (mai–jun/26).")

p.texto(f"""
- Em 2026 o churn total vai de {br(ano26.min())}% a {br(ano26.max())}%, com o mês mais alto em
  {pico26}; os meses de jan–mai ficam entre {br(jan_mai.min())}% e {br(jan_mai.max())}% (média
  {br(jan_mai.mean())}%) e os de jun–set entre {br(jun_set.min())}% e {br(jun_set.max())}% (média
  {br(jun_set.mean())}%){', ou seja, o churn de jan–mai é o mais alto do ano' if jan_mai_mais_alto else ''}.
  Ago e set/26 ficam em {br(ago_set.iloc[0])}% e {br(ago_set.iloc[1])}%, perto da média de 2025
  ({br(media('2025'))}%).
- {('**Janeiro sobe nos dois anos**' if sobe_jan else '**Janeiro**')}: {br(tot.loc['2025-01', 'churn_pct'])}%
  em jan/25 ({br(tot.loc['2024-12', 'churn_pct'])}% em dez/24) e {br(tot.loc['2026-01', 'churn_pct'])}%
  em jan/26 ({br(tot.loc['2025-12', 'churn_pct'])}% em dez/25). No mês, o mensal é o plano com o
  churn mais alto ({br(pm.loc['2026-01', 'churn_pct'])}% contra {br(pa.loc['2026-01', 'churn_pct'])}%
  do anual em jan/26).
- Ago/24 a dez/24 ficam entre {br(base24.min())}% e {br(base24.max())}%, mas a base de 2024 só
  contém quem estava vivo em jul/24 (A5): não usar como referência de "normal".
""")


p.secao("Por plano")
pl = df[df.recorte == "plano"]
f = go.Figure()
for i, seg in enumerate(["mensal", "anual"]):
    s = pl[pl.segmento == seg]
    linha(f, pd.PeriodIndex(s.mes, freq="M").to_timestamp(), s.churn_pct, seg, CORES[i],
          hovertemplate=f"{seg}: %{{y:.2f}}%<extra></extra>")
marcos(f)
layout_padrao(f, "churn no mês (%)"); eixo_meses(f, "2024-08-01", "2026-09-01")
f.update_layout(margin=dict(t=48))
p.figura(f, "Churn mensal por plano. O anual só perde na renovação (ou por devolução), então "
            "a taxa mensal do anual depende de quantos vencem no mês.")
p.texto(f"""
- {frase_sobe_plano}: a média mensal do plano foi de {br(r25_mensal)}% em 2025 para
  {br(r26_mensal)}% em jan–set/26 ({br(r26_mensal - r25_mensal, 2)} p.p.), e a do anual de
  {br(r25_anual)}% para {br(r26_anual)}% ({br(r26_anual - r25_anual, 2)} p.p.). Em 2025 o mensal
  ficou entre {br(m25.min())}% e {br(m25.max())}%; mês a mês, de mar a jul/26: {pico_mensal}.
- {('O mensal recua em ago e set/26: ' if caiu_fim else 'Fechando 2026, o mensal fica em ')}
  {br(pm.loc['2026-08', 'churn_pct'])}% em ago e {br(pm.loc['2026-09', 'churn_pct'])}% em
  set{', o menor valor da série' if menor_serie else ''}.
- **Janeiro é do mensal**: {br(pm.loc['2025-01', 'churn_pct'])}% em jan/25 e
  {br(pm.loc['2026-01', 'churn_pct'])}% em jan/26, contra {br(a25.min())}% a {br(a25.max())}%
  no anual em 2025.
- {('**Em jul/25 o anual muda de patamar** (' + br(pa.loc['2025-06', 'churn_pct']) + '% → ' + br(pa.loc['2025-07', 'churn_pct']) + '%)' if degrau_jul25 else '**O anual não tem degrau claro** (de ' + br(pa.loc['2025-06', 'churn_pct']) + '% em jun/25 para ' + br(pa.loc['2025-07', 'churn_pct']) + '% em jul/25)')}
  e fica entre {br(a_desde_jul25.min())}% e {br(a_desde_jul25.max())}% desde então. Jul/25 é
  quando começam a vencer as anuais que entraram a partir de jul/24, com a base em expansão:
  descrição do calendário de renovações, não medida de piora.
""")
p.tabela(resumo("plano"), "Média mensal por plano",
         {c: "{:.2f}" for c in ["churn 2025 (%)", "churn 2026 (%)", "variação (p.p.)"]} |
         {c: "{:,.0f}" for c in ["ativos médios 2025", "ativos médios 2026"]})

p.secao("Por canal de cobrança")
cn = df[df.recorte == "canal"]
f = go.Figure()
for i, seg in enumerate(["loja", "site"]):
    s = cn[cn.segmento == seg]
    linha(f, pd.PeriodIndex(s.mes, freq="M").to_timestamp(), s.churn_pct, seg, CORES[i + 2],
          hovertemplate=f"{seg}: %{{y:.2f}}%<extra></extra>")
marcos(f)
layout_padrao(f, "churn no mês (%)"); eixo_meses(f, "2024-08-01", "2026-09-01")
f.update_layout(margin=dict(t=48))
p.figura(f, "Churn mensal por canal: loja (App Store e Google Play) e site (cartão e Pix).")
p.tabela(resumo("plano_canal"), "Média mensal por plano e canal",
         {c: "{:.2f}" for c in ["churn 2025 (%)", "churn 2026 (%)", "variação (p.p.)"]} |
         {c: "{:,.0f}" for c in ["ativos médios 2025", "ativos médios 2026"]})
p.tabela(resumo("metodo"), "Média mensal por método de pagamento",
         {c: "{:.2f}" for c in ["churn 2025 (%)", "churn 2026 (%)", "variação (p.p.)"]} |
         {c: "{:,.0f}" for c in ["ativos médios 2025", "ativos médios 2026"]})

p.secao("A base: quantos ativos e de que plano")
f = go.Figure()
for i, seg in enumerate(["mensal", "anual"]):
    s = pl[pl.segmento == seg]
    f.add_trace(go.Bar(x=pd.PeriodIndex(s.mes, freq="M").to_timestamp(), y=s.ativos_inicio,
                       name=seg, marker=dict(color=CORES[i], line=dict(color="#fcfcfb", width=1)),
                       hovertemplate=f"{seg}: %{{y:,.0f}}<extra></extra>"))
layout_padrao(f, "ativos no dia 1 do mês"); eixo_meses(f, "2024-08-01", "2026-09-01")
f.update_layout(barmode="stack", margin=dict(t=48))
p.figura(f, "Assinantes pagantes ativos no início de cada mês, por plano. Se a mistura de "
            "planos muda, o churn total muda mesmo sem nenhum plano piorar.")

p.secao("Perguntas para a próxima etapa")
p.texto("""
- Separar a perda **voluntária** (desligou a renovação, cancelou) da **involuntária** (falha
  de pagamento, carência que expira) e de **devolução** (chargeback, reembolso). A subida de
  2026 pode estar numa só dessas.
- No anual, medir a **taxa de não renovação** (quem venceu no mês e não renovou), que é a
  taxa que de fato muda; a taxa mensal sobre toda a base anual dilui esse efeito.
- Abrir o pico de jan–mai/26 por plano × canal × sistema (android/ios), cruzando com o
  reajuste (mensal) e o GPS (android).
""")

destino = p.salvar("01_churn_mensal.html")
print(f"artefato: {destino.relative_to(RAIZ)}")
