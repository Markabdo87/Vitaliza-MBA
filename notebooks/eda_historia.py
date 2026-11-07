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
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from _artefato import CORES, Pagina, eixo_meses, layout_padrao, linha

RAIZ = Path(__file__).resolve().parent.parent
OURO = RAIZ / "dados" / "3.ouro"


def br(x, d=1):
    return f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


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
ORDEM = ["Parados", "Ativos ao ar livre", "Ativos em ambiente fechado", "Veteranos"]
COR_SEG = dict(zip(ORDEM, [CORES[7], CORES[3], CORES[0], CORES[2]]))
seg = pd.DataFrame({"saída 60 dias (%)": s31.groupby("segmento").saiu_60d.mean() * 100,
                    "assinantes em 30/09": s30.segmento.value_counts()}).loc[ORDEM]
media_seg = 100 * s31.saiu_60d.mean()
deslig = int((s30.segmento == "Já desligou").sum())

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
p.figura(f, "Churn mensal da base paga, ago/24–set/26 (ago–dez/24 com viés de sobrevivência, G3). "
            f"Pico de abr/26: {br(tot.loc['2026-04', 'churn_pct'])}%.")
p.texto(f"""
- Os dois números do enunciado (5,6% e 6,6%) saem da regra G1: {br(med['2025'], 2)}% e
  {br(med['2026'], 2)}% de média mensal; o notebook para se não baterem. Detalhe em [01 · Churn mensal](01_churn_mensal.html).
""")

p.secao(f"2. A alta veio do mensal ({'+' + br(v.loc['mensal', 'p.p.'], 2)} p.p.) e do Google Play")
f = go.Figure()
for i, col in enumerate(["2025", "jan–set/26"]):
    f.add_trace(go.Bar(x=var.recorte, y=var[col], name=col, marker_color=CORES[i],
                       text=[f"{br(y, 2)}%" for y in var[col]], textposition="outside",
                       hovertemplate=f"{col}: %{{y:.2f}}%<extra></extra>"))
layout_padrao(f, "churn médio no mês (%)", altura=340)
f.update_layout(barmode="group", margin=dict(t=48))
p.figura(f, "Média mensal do churn por recorte, 2025 × jan–set/2026.")
p.texto(f"""
- O mensal subiu {br(v.loc['mensal', 'p.p.'], 2)} p.p. e o anual {br(v.loc['anual', 'p.p.'], 2)} p.p. O
  reajuste do mensal (R$ 34,90 → R$ 39,90 em 01/03/26) coincide com a alta, mas não foi testado como causa.
- Google Play {br(v.loc['Google Play', 'p.p.'], 2)} p.p. contra App Store {br(v.loc['App Store', 'p.p.'], 2)} p.p.:
  o android é onde apareceu a falha de GPS de mai–jun/26.
""")

p.secao(f"3. Quem sai decide sair: a alta é voluntária "
        f"(+{br(tipo_med['2026']['voluntária'] - tipo_med['2025']['voluntária'], 2)} p.p.)")
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
- Na pesquisa de saída (só site, jun–set/26), o tema dominante dos comentários é "objetivo cumprido"
  (era até a prova, até o casamento), que não existe na lista de motivos. Detalhe em
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

p.secao("5. No mensal pesa o tempo de casa; no anual que vence, o treino")
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
f.update_yaxes(range=[0, 92])
f.update_yaxes(title_text="", row=1, col=2)
p.figura(f, f"Assinantes pagantes em 30/06/2026 ({br(len(qs), 0)}) e quem saiu até 30/09. O anual só "
            "pode sair no aniversário, por isso só entra o anual que vencia na janela (K6).")
p.texto(f"""
- **Mensal:** {br(t_men.iloc[0])}% de saída com até 3 meses de casa, {br(t_men.iloc[-1])}% acima de 24 meses.
  A primeira experiência é o ponto fraco.
- **Anual que vence:** até 10 dias de treino no trimestre, a maioria não renova; acima de 25 dias,
  menos de 1 em 4. O engajamento antes do aniversário decide a renovação. Detalhe em
  [02 · Quem saiu](02_quem_saiu.html).
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
f.update_yaxes(range=[0, 112])
p.figura(f, "Situação da renovação em 30/06 reconstruída pelos eventos (K7).")
p.texto(f"""
- {br(rn.loc[('anual que vence em jul–set', 'desligada'), 'assinantes'], 0)} anuais que venciam já tinham
  desligado a renovação em 30/06; {br(rn.loc[('anual que vence em jul–set', 'desligada'), 'saíram (%)'])}% saíram.
  Parte do "parou de treinar, então saiu" é o contrário: decidiu sair, então parou (causalidade reversa).
- Por isso a segmentação e o modelo olham quem **ainda** está com a renovação ligada; quem já desligou
  é uma lista de reversão à parte ({br(deslig, 0)} assinantes em 30/09).
""")

p.secao("7. Os assinantes se dividem em quatro grupos estáveis")
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
f.update_xaxes(title_text="% que decidiu sair em 60 dias (01/08–29/09/2026)", range=[0, 48])
p.figura(f, "K-means (k = 4) nos pagantes de 31/07/2026 com a renovação ligada, em quatro variáveis: "
            "treinos por semana, dias sem treino, tempo de casa e % ao ar livre. Tamanho em 30/09.")
p.texto("""
- A saída não entra no agrupamento; só descreve os grupos depois. Os grupos se repetem em
  reamostras (índice de Rand 0,999), mas a separação é fraca (silhueta 0,43): são regiões de um
  contínuo. Detalhe em [04 · Segmentos](04_segmentos.html).
""")

p.secao("8. Personas e priorização preliminar")
prio = pd.DataFrame([
    {"segmento": "Parados", "quem é": "anual que paga e não treina há ~6 meses",
     "hipótese de driver": "perda de rotina ou objetivo cumprido", "prioridade": "ação imediata (maior taxa)"},
    {"segmento": "Ativos ao ar livre", "quem é": "corre, caminha ou pedala 2× por semana; metade mensal",
     "hipótese de driver": "treino com data marcada (prova); mensal recém-chegado",
     "prioridade": "ação imediata (maior volume)"},
    {"segmento": "Ativos em ambiente fechado", "quem é": "força, funcional ou yoga 2× por semana",
     "hipótese de driver": "rotina estável; risco no mensal novo e no cartão",
     "prioridade": "monitoramento"},
    {"segmento": "Veteranos", "quem é": "quase 5 anos de casa, treina 2× por semana",
     "hipótese de driver": "hábito formado", "prioridade": "monitoramento (oferta seria custo)"},
    {"segmento": "Já desligou", "quem é": "desligou a renovação e ainda paga (93% anual)",
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
p.texto("""
- **Causa.** Cruzamento aponta suspeitos (reajuste, GPS falho, objetivo cumprido); só experimento
  sorteado, como a campanha de ago/26, chega perto de causa.
- **Risco individual.** A taxa do grupo é histórica; quem, dentro do grupo, vai sair até 29/11/2026 é
  a pergunta do modelo da semana 10.
- **Motivo na loja.** A pesquisa de saída só existe no site; a loja, dois terços das saídas, não diz por quê.
- **GPS falho.** Separa no mensal android em jul–set, mas vai no sentido contrário em ago–set: precisa
  de controle por tipo de treino antes de virar driver.
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
