"""Prata -> ouro: segmentos.csv (um assinante pagante × data de referência) +
artefatos/04_segmentos.html.

Pergunta (aula 3): entre os pagantes ativos em 31/07/2026, em quantos grupos os assinantes se
dividem, o que distingue cada grupo e o que a Vitaliza faria diferente com cada um?

Regras (decisões L1–L8 no decisoes.md; método e debate no memorial.md, etapa 04):
  1. Base do agrupamento: assinaturas pagas (flag_cortesia = 0) ativas em 31/07/2026 (regra G1
     aplicada a 01/08) com a renovação não desligada em 31/07 (situação pelos eventos, regra
     K7 aplicada a 01/08). Quem já desligou a renovação fica fora do agrupamento, porque a
     decisão já foi tomada (D02.10), e aparece como grupo à parte, "já desligou".
  2. Saída em 60 dias (descreve os grupos, não entra no agrupamento): evento
     renovacao_automatica_desligada, cancelamento_web ou assinatura_expirada entre 01/08 e
     29/09/2026. Mede a decisão de sair, não a data da perda: o anual decide meses antes de
     expirar (W4).
  3. Quatro variáveis da aula, medidas até 31/07 em atividades.parquet:
       treinos_semana   treinos nas 12 semanas de 09/05 a 31/07, divididos por 12;
       dias_sem_treino  dias entre o último treino e 31/07; sem treino no arquivo (que começa
                        em 01/01/2026), dias desde 01/01/2026 ou desde o início da assinatura,
                        o que vier depois;
       tempo_casa_dias  dias entre o início da assinatura e 31/07;
       pct_ar_livre     % dos treinos das 12 semanas em corrida, caminhada ou pedal; 0 sem treino.
  4. Padronização (StandardScaler) e k-means de k = 2 a 8, n_init = 10, random_state = 0.
  5. k escolhido pelas quatro lentes da aula: inércia (cotovelo), silhueta, estabilidade
     (índice de Rand ajustado entre o agrupamento da base e o de 10 reamostras com reposição,
     cada uma classificando a base inteira) e leitura de negócio.
  6. Variáveis do grupo testadas e deixadas de fora: % dos treinos ao ar livre com GPS falho,
     km por treino ao ar livre (mediana) e conexões recíprocas. A página mostra o teste.
  7. Nome de cada grupo por regra sobre as medianas: parados = maior mediana de dias sem treino;
     veteranos = maior mediana de tempo de casa entre os demais; dos dois restantes, ao ar
     livre = maior mediana de % ao ar livre. O notebook para se a regra não separar os quatro.
  8. Tamanho atual: o mesmo padronizador e os mesmos centros classificam os pagantes ativos em
     30/09/2026 com a renovação não desligada, com as variáveis medidas até 30/09. A saída
     desses ainda não aconteceu (fica vazia).

Uso: .venv/bin/python notebooks/segmentos_ouro.py  (a partir da raiz do repo)
"""
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.preprocessing import StandardScaler

from _artefato import CORES, GRADE, Pagina, layout_padrao

RAIZ = Path(__file__).resolve().parent.parent
PRATA = RAIZ / "dados" / "2.prata"
OURO = RAIZ / "dados" / "3.ouro"
SAIDA = OURO / "segmentos.csv"

VARS = ["treinos_semana", "dias_sem_treino", "tempo_casa_dias", "pct_ar_livre"]
EXTRAS = {"pct_gps_falho": "% de treinos ao ar livre com GPS falho",
          "km_treino": "km por treino ao ar livre", "conexoes": "conexões recíprocas"}
AR_LIVRE = ["corrida", "caminhada", "pedal"]
INICIO_ARQUIVO = pd.Timestamp("2026-01-01")
SEMENTE, N_INIT, K_FAIXA, K = 0, 10, range(2, 9), 4
MUDA_RENOVACAO = {
    "assinatura_iniciada": "ligada", "renovacao": "ligada",
    "renovacao_automatica_religada": "ligada", "renovacao_automatica_desligada": "desligada",
    "cancelamento_web": "desligada", "periodo_carencia": "em carência",
}
SAIDA_EVENTOS = ["renovacao_automatica_desligada", "cancelamento_web", "assinatura_expirada"]

# --- 1. leitura -----------------------------------------------------------------------------
a = pd.read_csv(PRATA / "assinaturas.csv", parse_dates=["inicio", "data_fim"])
a = a[a.flag_cortesia == 0].rename(columns={"plano_atual": "plano"})
u = pd.read_csv(PRATA / "usuarios.csv", usecols=["user_id", "sistema"])
ev = pd.read_csv(PRATA / "eventos_assinatura.csv", parse_dates=["data_hora_brt"],
                 usecols=["user_id", "seq_usuario", "data_hora_brt", "evento", "fase", "flag_apos_fim"])
t = pd.read_parquet(PRATA / "atividades.parquet",
                    columns=["user_id", "inicio_brt", "tipo", "gps_ok", "distancia_km"])
am = pd.read_csv(PRATA / "amizades.csv", parse_dates=["desde"])
am = am[(am.reciproco == 1) & (am.flag_id_invalido == 0)]


def monta(ref):
    """Pagantes ativos no dia ref (data, inclusive) com as variáveis medidas até ref."""
    d = ref + pd.Timedelta(days=1)                         # dia 1 da janela (01/08 ou 01/10)
    b = a[(a.inicio < d) & (a.data_fim.isna() | (a.data_fim >= d))][
        ["user_id", "plano", "canal", "metodo", "inicio"]].copy()
    b = b.merge(u, on="user_id", how="left", validate="one_to_one")

    e = ev[(ev.fase == "assinatura") & (ev.data_hora_brt < d) & (ev.flag_apos_fim == 0)
           & ev.evento.isin(list(MUDA_RENOVACAO))]
    ult = e.sort_values(["user_id", "seq_usuario"]).groupby("user_id").tail(1)
    b = b.merge(pd.DataFrame({"user_id": ult.user_id, "renovacao": ult.evento.map(MUDA_RENOVACAO)}),
                on="user_id", how="left", validate="one_to_one")
    assert b.renovacao.notna().all(), "assinante sem evento de renovação"

    tt = t[t.inicio_brt < d]
    j = tt[tt.inicio_brt >= d - pd.Timedelta(days=84)]
    fora = j[j.tipo.isin(AR_LIVRE)]
    g = j.groupby("user_id").agg(treinos_12s=("tipo", "size"),
                                 ar_livre_12s=("tipo", lambda s: int(s.isin(AR_LIVRE).sum())))
    gf = fora.groupby("user_id").agg(gps_falho_12s=("gps_ok", lambda s: int((~s).sum())),
                                     km_treino=("distancia_km", "median"))
    ult_treino = tt.groupby("user_id").inicio_brt.max().dt.normalize().rename("ultimo_treino")
    con = am[am.desde <= ref].groupby("seguidor_id").size().rename("conexoes")
    for novo in [g, gf, ult_treino, con]:
        b = b.merge(novo, left_on="user_id", right_index=True, how="left", validate="one_to_one")
    for c in ["treinos_12s", "ar_livre_12s", "gps_falho_12s", "km_treino", "conexoes"]:
        b[c] = b[c].fillna(0)

    b["treinos_semana"] = b.treinos_12s / 12
    desde = np.maximum(b.inicio, INICIO_ARQUIVO)
    b["dias_sem_treino"] = np.where(b.ultimo_treino.notna(), (ref - b.ultimo_treino).dt.days,
                                    (ref - desde).dt.days).astype(int)
    b["tempo_casa_dias"] = (ref - b.inicio).dt.days
    b["pct_ar_livre"] = np.where(b.treinos_12s > 0, 100 * b.ar_livre_12s / b.treinos_12s, 0.0)
    b["pct_gps_falho"] = np.where(b.ar_livre_12s > 0, 100 * b.gps_falho_12s / b.ar_livre_12s, 0.0)
    b.insert(0, "data_ref", ref.date().isoformat())
    return b.drop(columns=["ar_livre_12s", "gps_falho_12s", "ultimo_treino"])


REF, REF_ATUAL = pd.Timestamp("2026-07-31"), pd.Timestamp("2026-09-30")
b = monta(REF)
JAN_INI = REF + pd.Timedelta(days=1)                       # 01/08
JAN_FIM = JAN_INI + pd.Timedelta(days=60)                  # 30/09, exclusive: até 29/09
w = ev[(ev.data_hora_brt >= JAN_INI) & (ev.data_hora_brt < JAN_FIM) & ev.evento.isin(SAIDA_EVENTOS)]
b["saiu_60d"] = b.user_id.isin(w.user_id).astype(int)
atual = monta(REF_ATUAL)
assert len(atual) == 14753, "pagantes ativos em 30/09 diferem do enunciado (14.753)"

ag = b[b.renovacao != "desligada"].reset_index(drop=True)   # base do agrupamento (L1)
ag_atual = atual[atual.renovacao != "desligada"].reset_index(drop=True)
print(f"31/07: {len(b)} ativos · {len(ag)} com renovação não desligada · "
      f"saída 60d {100 * ag.saiu_60d.mean():.1f}% · 30/09: {len(atual)} ativos, {len(ag_atual)} no agrupamento")

# --- 2. k-means -----------------------------------------------------------------------------
esc = StandardScaler().fit(ag[VARS])
X = esc.transform(ag[VARS])
curvas = []
for k in K_FAIXA:
    km = KMeans(k, n_init=N_INIT, random_state=SEMENTE).fit(X)
    curvas.append({"k": k, "inércia": km.inertia_, "silhueta": silhouette_score(X, km.labels_)})
curvas = pd.DataFrame(curvas)

rng = np.random.default_rng(SEMENTE)
amostras = [rng.integers(0, len(X), len(X)) for _ in range(10)]
estab = []
for k in range(3, 7):
    ref_lab = KMeans(k, n_init=N_INIT, random_state=SEMENTE).fit_predict(X)
    aris = [adjusted_rand_score(ref_lab, KMeans(k, n_init=N_INIT, random_state=SEMENTE)
                                .fit(X[i]).predict(X)) for i in amostras]
    outra = adjusted_rand_score(ref_lab, KMeans(k, n_init=N_INIT, random_state=1).fit_predict(X))
    estab.append({"k": k, "Rand médio": np.mean(aris), "Rand mínimo": np.min(aris),
                  "outra semente": outra})
estab = pd.DataFrame(estab)
print(curvas.round(3).to_string(index=False)); print(estab.round(3).to_string(index=False))

km = KMeans(K, n_init=N_INIT, random_state=SEMENTE).fit(X)
ag["grupo"] = km.labels_
med = ag.groupby("grupo")[VARS].median()
nomes = {}
nomes[med.dias_sem_treino.idxmax()] = "Parados"
resto = med.drop(index=list(nomes))
nomes[resto.tempo_casa_dias.idxmax()] = "Veteranos"
resto = med.drop(index=list(nomes))
nomes[resto.pct_ar_livre.idxmax()] = "Ativos ao ar livre"
nomes[resto.pct_ar_livre.idxmin()] = "Ativos em ambiente fechado"
assert len(set(nomes.values())) == K, "regra de nomes não separou os quatro grupos"
ORDEM = ["Parados", "Ativos ao ar livre", "Ativos em ambiente fechado", "Veteranos"]
COR_SEG = dict(zip(ORDEM, [CORES[7], CORES[3], CORES[0], CORES[2]]))
ag["segmento"] = ag.grupo.map(nomes)
ag_atual["segmento"] = pd.Series(km.predict(esc.transform(ag_atual[VARS]))).map(nomes)

teste = []
for col, nome in EXTRAS.items():
    cols = VARS + [col]
    Xe = StandardScaler().fit_transform(ag[cols])
    lab = KMeans(K, n_init=N_INIT, random_state=SEMENTE).fit_predict(Xe)
    teste.append({"variável somada": nome, "silhueta em k = 4": silhouette_score(Xe, lab),
                  "Rand com os 4 grupos da aula": adjusted_rand_score(ag.grupo, lab)})
teste = pd.DataFrame(teste)
print(teste.round(3).to_string(index=False))

# --- 3. tabela de ouro ----------------------------------------------------------------------
fora_b = b[b.renovacao == "desligada"].assign(segmento="Já desligou", saiu_60d=np.nan)
jan = ev[(ev.data_hora_brt >= JAN_INI) & (ev.data_hora_brt < JAN_FIM)]
fora_b["expirou_60d"] = fora_b.user_id.isin(jan[jan.evento == "assinatura_expirada"].user_id)
fora_b["religou_60d"] = fora_b.user_id.isin(jan[jan.evento == "renovacao_automatica_religada"].user_id)
fora_a = atual[atual.renovacao == "desligada"].assign(segmento="Já desligou")
ouro = pd.concat([ag.drop(columns="grupo"), fora_b.drop(columns=["expirou_60d", "religou_60d"]),
                  ag_atual, fora_a], ignore_index=True)
assert ouro.groupby("data_ref").size().to_dict() == {"2026-07-31": len(b), "2026-09-30": len(atual)}
assert not ouro.duplicated(["data_ref", "user_id"]).any()
OURO.mkdir(parents=True, exist_ok=True)
ouro.to_csv(SAIDA, index=False)
print(f"{SAIDA.relative_to(RAIZ)}: {len(ouro)} linhas · "
      f"{ouro.groupby(['data_ref', 'segmento']).size().to_dict()}")

# --- 4. artefato ------------------------------------------------------------------------------
from plotly.subplots import make_subplots  # noqa: E402


def br(x, d=1):
    return f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def wilson(k, n, z=1.96):
    p = k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    m = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return c - m, c + m


media = ag.saiu_60d.mean()
n_atual = ag_atual.segmento.value_counts()
linhas = []
for sg in ORDEM:
    d = ag[ag.segmento == sg]
    lo, hi = wilson(d.saiu_60d.sum(), len(d))
    linhas.append({"segmento": sg, "assinantes": len(d), "% da base": 100 * len(d) / len(ag),
                   "treinos/semana": d.treinos_semana.median(), "dias sem treino": d.dias_sem_treino.median(),
                   "tempo de casa (dias)": d.tempo_casa_dias.median(), "% ao ar livre": d.pct_ar_livre.median(),
                   "saída 60 dias (%)": 100 * d.saiu_60d.mean(), "IC 95%": f"{br(100 * lo)}–{br(100 * hi)}",
                   "% anual": 100 * (d.plano == "anual").mean(), "assinantes em 30/09": n_atual[sg]})
perfil = pd.DataFrame(linhas)
pf = perfil.set_index("segmento")
sx = ag.groupby(["segmento", "plano"]).saiu_60d.agg(["size", "mean"])
mens = ag[ag.plano == "mensal"].assign(novo=lambda x: np.where(x.tempo_casa_dias <= 90, "até 90 dias", "mais de 90 dias"))
nov = mens.groupby(["segmento", "novo"]).saiu_60d.agg(["size", "mean"])
livre_m = ag[(ag.segmento == "Ativos ao ar livre") & (ag.plano == "mensal")]
gps_sim = livre_m[livre_m.pct_gps_falho > 0].saiu_60d.mean()
gps_nao = livre_m[livre_m.pct_gps_falho == 0].saiu_60d.mean()
met = ag[ag.plano == "mensal"].groupby("metodo").saiu_60d.mean()
sil4 = curvas.set_index("k").loc[K, "silhueta"]
e4 = estab.set_index("k").loc[K]

p = Pagina(
    "04 · Segmentos de assinantes",
    "Em quantos grupos os pagantes ativos em 31/07/2026 se dividem, o que distingue cada grupo e o "
    "que a Vitaliza faria diferente com cada um.",
    "fonte: `dados/3.ouro/segmentos.csv`, gerada por `notebooks/segmentos_ouro.py` (decisões L1–L8) · "
    "método em `memorial.md`, etapa 04",
)
p.texto(f"""
**Regra.** {br(len(ag), 0)} assinantes pagos ativos em 31/07/2026 que ainda não tinham desligado a
renovação. Quatro variáveis medidas até 31/07, padronizadas: treinos por semana (12 semanas), dias
sem treino, tempo de casa e % dos treinos ao ar livre. K-means com `n_init = 10` e
`random_state = 0`. A saída em 60 dias (desligou a renovação, cancelou no site ou expirou entre
01/08 e 29/09) **não entra no agrupamento**: só descreve os grupos depois. Média da base:
{br(100 * media)}%.

Outros {br(len(fora_b), 0)} ativos em 31/07 já tinham desligado a renovação. Ficam fora do
agrupamento, porque a decisão já foi tomada, e aparecem no fim como grupo à parte.
""")

p.secao("Quantos grupos: as quatro lentes")
f = make_subplots(rows=1, cols=2, horizontal_spacing=0.12,
                  subplot_titles=("Inércia: cai sempre; procurar a dobra", "Silhueta: −1 a 1, maior é melhor"))
f.add_trace(go.Scatter(x=curvas.k, y=curvas["inércia"], mode="lines+markers", marker_color=CORES[0],
                       hovertemplate="k = %{x}: %{y:,.0f}<extra></extra>"), 1, 1)
f.add_trace(go.Scatter(x=curvas.k, y=curvas.silhueta, mode="lines+markers", marker_color=CORES[0],
                       hovertemplate="k = %{x}: %{y:.3f}<extra></extra>"), 1, 2)
for col, y in [(1, curvas.set_index("k").loc[K, "inércia"]), (2, sil4)]:
    f.add_trace(go.Scatter(x=[K], y=[y], mode="markers", marker=dict(size=13, color=CORES[7]),
                           hoverinfo="skip"), 1, col)
for y0, rot in [(0.25, "fraca acima de 0,25"), (0.5, "razoável acima de 0,50")]:
    f.add_hline(y=y0, line=dict(color="#9a9893", width=1, dash="dot"), row=1, col=2,
                annotation_text=rot, annotation_position="top right", annotation_font_size=11)
layout_padrao(f)
f.update_layout(showlegend=False, hovermode="closest", margin=dict(t=48))
f.update_xaxes(title_text="número de grupos (k)", dtick=1)
p.figura(f, f"De k = 2 a 8 na base de {br(len(ag), 0)} assinantes. Ponto vermelho: o k escolhido. "
            "Faixas da silhueta de Kaufman e Rousseeuw.")
f = go.Figure(go.Bar(x=[f"k = {k}" for k in estab.k], y=estab["Rand médio"],
                     marker_color=[CORES[7] if k == K else CORES[0] for k in estab.k],
                     text=[f"mín. {br(v, 3)}" for v in estab["Rand mínimo"]], textposition="outside",
                     hovertemplate="%{x}: Rand médio %{y:.3f}<extra></extra>"))
layout_padrao(f, "índice de Rand ajustado", altura=300)
f.update_yaxes(range=[0, 1.12])
p.figura(f, "Estabilidade: 10 reamostras com reposição, cada uma classificando a base inteira, "
            "comparadas com o agrupamento original (1 = mesmos grupos; 0 = acaso).")
ganho = curvas.set_index("k")["inércia"].diff()
p.texto(f"""
- **Inércia.** De 3 para 4 grupos a inércia cai {br(-ganho[4], 0)}; de 4 para 5, {br(-ganho[5], 0)}; de
  5 para 6, {br(-ganho[6], 0)}. A dobra fica entre 4 e 5.
- **Silhueta.** A maior é a de k = 2 ({br(curvas.silhueta.iloc[0], 2)}): quem treina e quem parou. Em
  k = 4 é {br(sil4, 2)}, estrutura fraca: os grupos são regiões de um contínuo, não ilhas.
- **Estabilidade.** Até k = 4 os grupos se repetem nas reamostras (Rand médio {br(e4['Rand médio'], 3)},
  mínimo {br(e4['Rand mínimo'], 3)}; outra semente, {br(e4['outra semente'], 3)}). Em k = 6 o mínimo cai
  para {br(estab.set_index('k').loc[6, 'Rand mínimo'], 2)}.
- **Leitura de negócio.** k = 4 dá quatro grupos que se descrevem numa frase e pedem ações
  diferentes; k = 5 parte um deles em dois com a mesma saída. **Escolha: k = 4.**
""")

p.secao("O que distingue cada grupo")
am_ = ag.sample(4000, random_state=SEMENTE)
f = make_subplots(rows=1, cols=2, horizontal_spacing=0.1)
for sg in ORDEM:
    d = am_[am_.segmento == sg]
    f.add_trace(go.Scattergl(x=d.treinos_semana, y=d.pct_ar_livre, mode="markers", name=sg,
                             legendgroup=sg, marker=dict(size=4, color=COR_SEG[sg], opacity=0.55),
                             hovertemplate=f"{sg}<br>%{{x:.1f}} treinos/semana · %{{y:.0f}}% ao ar livre<extra></extra>"), 1, 1)
    f.add_trace(go.Scattergl(x=d.tempo_casa_dias / 365.25, y=d.dias_sem_treino, mode="markers", name=sg,
                             legendgroup=sg, showlegend=False,
                             marker=dict(size=4, color=COR_SEG[sg], opacity=0.55),
                             hovertemplate=f"{sg}<br>%{{x:.1f}} anos de casa · %{{y}} dias sem treino<extra></extra>"), 1, 2)
layout_padrao(f, altura=420)
f.update_layout(hovermode="closest", margin=dict(t=48))
f.update_xaxes(title_text="treinos por semana (12 semanas)", row=1, col=1)
f.update_yaxes(title_text="% dos treinos ao ar livre", row=1, col=1)
f.update_xaxes(title_text="tempo de casa (anos)", row=1, col=2)
f.update_yaxes(title_text="dias sem treino em 31/07", row=1, col=2)
p.figura(f, "As quatro variáveis na unidade original, 4.000 assinantes sorteados. À esquerda, o eixo "
            "que separa ar livre de ambiente fechado; à direita, os que isolam parados e veteranos.")
p.tabela(perfil, "Perfil de cada grupo em 31/07/2026 (medianas) e saída nos 60 dias seguintes",
         {"assinantes": "{:,.0f}", "% da base": "{:.1f}", "treinos/semana": "{:.1f}",
          "dias sem treino": "{:.0f}", "tempo de casa (dias)": "{:,.0f}", "% ao ar livre": "{:.0f}",
          "saída 60 dias (%)": "{:.1f}", "% anual": "{:.0f}", "assinantes em 30/09": "{:,.0f}"})

f = go.Figure()
taxas = perfil.set_index("segmento")["saída 60 dias (%)"]
ics = [tuple(float(v.replace(",", ".")) for v in pf.loc[sg, "IC 95%"].split("–")) for sg in ORDEM]
f.add_trace(go.Bar(y=ORDEM[::-1], x=taxas[ORDEM[::-1]], orientation="h",
                   marker_color=[COR_SEG[sg] for sg in ORDEM[::-1]],
                   error_x=dict(type="data", symmetric=False, color="#52514e",
                                array=[hi - taxas[sg] for sg, (lo, hi) in zip(ORDEM, ics)][::-1],
                                arrayminus=[taxas[sg] - lo for sg, (lo, hi) in zip(ORDEM, ics)][::-1]),
                   text=[f"{br(v)}%" for v in taxas[ORDEM[::-1]]], textposition="outside", cliponaxis=False,
                   hovertemplate="%{y}: %{x:.1f}%<extra></extra>"))
f.add_vline(x=100 * media, line=dict(color="#52514e", width=1, dash="dot"),
            annotation_text=f"média {br(100 * media)}%", annotation_position="top")
layout_padrao(f, altura=300)
f.update_layout(hovermode="closest", margin=dict(t=40, l=190))
f.update_xaxes(title_text="% que decidiu sair entre 01/08 e 29/09/2026", range=[0, 38])
p.figura(f, "Saída em 60 dias por grupo, com intervalo de Wilson 95%. É taxa histórica (descrição), "
            "não previsão: o modelo de risco é a entrega da semana 10.")

p.secao("Plano, tempo de casa e método dentro de cada grupo")
f = go.Figure()
for i, pl in enumerate(["mensal", "anual"]):
    ys = [100 * sx.loc[(sg, pl), "mean"] if (sg, pl) in sx.index else None for sg in ORDEM]
    ns = [int(sx.loc[(sg, pl), "size"]) if (sg, pl) in sx.index else 0 for sg in ORDEM]
    f.add_trace(go.Bar(x=ORDEM, y=ys, name=pl, marker_color=CORES[i], customdata=ns,
                       hovertemplate=f"{pl}: %{{y:.1f}}% de %{{customdata:,}}<extra></extra>"))
layout_padrao(f, "saída em 60 dias (%)", altura=320)
f.update_layout(barmode="group", margin=dict(t=48))
p.figura(f, "Saída em 60 dias por grupo e plano. Os parados são todos anuais: nenhum mensal com a "
            "renovação ligada estava sem treinar.")
nov_t = nov.reset_index().rename(columns={"novo": "tempo de casa", "size": "mensais", "mean": "saída 60 dias (%)"})
nov_t["saída 60 dias (%)"] *= 100
p.tabela(nov_t, "Mensal: saída em 60 dias por tempo de casa dentro de cada grupo",
         {"mensais": "{:,.0f}", "saída 60 dias (%)": "{:.1f}"})
p.texto(f"""
- **O plano não é eixo do agrupamento, mas muda a taxa dentro dele.** O mensal sai mais que o anual
  nos dois grupos ativos ({br(100 * sx.loc[('Ativos ao ar livre', 'mensal'), 'mean'])}% × {br(100 * sx.loc[('Ativos ao ar livre', 'anual'), 'mean'])}%
  ao ar livre; {br(100 * sx.loc[('Ativos em ambiente fechado', 'mensal'), 'mean'])}% × {br(100 * sx.loc[('Ativos em ambiente fechado', 'anual'), 'mean'])}% em ambiente fechado).
  As ofertas do CRM são por plano, então o plano entra na escolha da ação, depois do grupo.
- **O mensal recém-chegado sai mais em todo grupo**: {br(100 * nov.loc[('Ativos ao ar livre', 'até 90 dias'), 'mean'])}%
  ao ar livre com até 90 dias de casa, contra {br(100 * nov.loc[('Ativos ao ar livre', 'mais de 90 dias'), 'mean'])}% depois
  disso. É o achado da etapa 02 (tempo de casa, AUC 0,60 no mensal) visto dentro dos grupos.
- **Cartão no mensal**: {br(100 * met['cartao'])}% de saída, contra {br(100 * met.drop('cartao').min())}% a
  {br(100 * met.drop('cartao').max())}% nos outros métodos. É a falha de pagamento da etapa 03 (a
  expiração por falha de cobrança conta como saída).
- **GPS falho não se confirma aqui.** Entre os mensais ao ar livre, quem teve treino com GPS falho
  saiu **menos** ({br(100 * gps_sim)}% × {br(100 * gps_nao)}%), o contrário da etapa 02. Seleção
  provável: quem teve a falha em mai–jun e saiu em julho já não está na base de 31/07.
""")

p.secao("Variáveis que o grupo testou e deixou de fora")
p.tabela(teste, "Cada variável somada às quatro da aula, k = 4",
         {"silhueta em k = 4": "{:.3f}", "Rand com os 4 grupos da aula": "{:.3f}"})
p.texto(f"""
Nenhuma das três muda os grupos (Rand de {br(teste['Rand com os 4 grupos da aula'].min(), 3)} a
{br(teste['Rand com os 4 grupos da aula'].max(), 3)} com o agrupamento das quatro) e todas baixam a silhueta
({br(sil4, 2)} → {br(teste['silhueta em k = 4'].min(), 2)}–{br(teste['silhueta em k = 4'].max(), 2)}). Ficam fora do
agrupamento e entram no perfil e no modelo. Plano, canal e método também ficam fora: variável 0/1
padronizada pesa demais na distância e o grupo passa a ser a própria categoria (aula 3).
""")

p.secao("Personas e priorização preliminar")
f = go.Figure()
for sg in ORDEM:
    n, tx = n_atual[sg], pf.loc[sg, "saída 60 dias (%)"]
    f.add_trace(go.Scatter(x=[n], y=[tx], mode="markers+text", name=sg, text=[sg], textposition="top center",
                           marker=dict(size=np.sqrt(n * tx / 100) * 1.6, color=COR_SEG[sg], opacity=0.8,
                                       line=dict(color="white", width=1)),
                           hovertemplate=f"{sg}<br>%{{x:,}} assinantes em 30/09 · %{{y:.1f}}% de saída"
                                         f"<br>≈ {br(n * tx / 100, 0)} saídas se a taxa se repetir<extra></extra>"))
f.add_hline(y=100 * media, line=dict(color="#52514e", width=1, dash="dot"),
            annotation_text=f"média {br(100 * media)}%", annotation_position="bottom right")
layout_padrao(f, "saída em 60 dias, ago–set/26 (%)", altura=380)
f.update_layout(showlegend=False, hovermode="closest", margin=dict(t=24))
f.update_xaxes(title_text="assinantes no grupo em 30/09/2026", range=[0, 7600])
f.update_yaxes(range=[0, 36])
p.figura(f, "Taxa × tamanho atual. A área da bolha é o número de saídas se a taxa de ago–set se "
            "repetisse no grupo de 30/09 (ordem de grandeza, não previsão).")


def esperado(sg):
    return n_atual[sg] * pf.loc[sg, "saída 60 dias (%)"] / 100


p.cartoes([
    {"titulo": "Parados", "cor": COR_SEG["Parados"],
     "destaque": f"{br(pf.loc['Parados', 'assinantes'], 0)} em 31/07 · {br(n_atual['Parados'], 0)} em 30/09 · todos anuais",
     "linhas": [
         ("Perfil", f"Pagam o anual e não treinam: {br(pf.loc['Parados', 'dias sem treino'], 0)} dias sem treino "
                    f"(mediana), {br(pf.loc['Parados', 'tempo de casa (dias)'] / 30.4375, 0)} meses de casa."),
         ("Saída em 60 dias", f"**{br(pf.loc['Parados', 'saída 60 dias (%)'])}%**, "
                              f"{br(pf.loc['Parados', 'saída 60 dias (%)'] / (100 * media))} vezes a média."),
         ("Hipótese de driver", "Perda de rotina ou objetivo cumprido (\"era só até a prova\", tema de 55% "
                                "dos comentários da pesquisa, etapa 03). No anual, quem não treina não "
                                "renova (AUC 0,78, etapa 02)."),
         ("Prioridade", "**Ação imediata**: a maior taxa da base."),
         ("Direção da ação", "Reativar antes da renovação: plano de treino personalizado (sem custo "
                             "direto); 1 mês grátis só perto do aniversário. Grupo de controle sorteado "
                             "para medir o efeito."),
     ]},
    {"titulo": "Ativos ao ar livre", "cor": COR_SEG["Ativos ao ar livre"],
     "destaque": f"{br(pf.loc['Ativos ao ar livre', 'assinantes'], 0)} em 31/07 · {br(n_atual['Ativos ao ar livre'], 0)} em 30/09 · "
                 f"{br(100 - pf.loc['Ativos ao ar livre', '% anual'], 0)}% mensais",
     "linhas": [
         ("Perfil", f"{br(pf.loc['Ativos ao ar livre', 'treinos/semana'])} treinos por semana, "
                    f"{br(pf.loc['Ativos ao ar livre', '% ao ar livre'], 0)}% em corrida, caminhada ou pedal, "
                    f"{br(pf.loc['Ativos ao ar livre', 'tempo de casa (dias)'] / 30.4375, 0)} meses de casa."),
         ("Saída em 60 dias", f"**{br(pf.loc['Ativos ao ar livre', 'saída 60 dias (%)'])}%**, acima da média; "
                              f"o maior volume (≈ {br(esperado('Ativos ao ar livre'), 0)} saídas em 60 dias "
                              f"se a taxa se repetir na base de 30/09)."),
         ("Hipótese de driver", f"Treino com data marcada (prova, evento): cumprido o objetivo, sai. O mensal "
                                f"recém-chegado sai {br(100 * nov.loc[('Ativos ao ar livre', 'até 90 dias'), 'mean'])}%."),
         ("Prioridade", "**Ação imediata**, pelo volume, a começar pelo mensal com até 90 dias de casa."),
         ("Direção da ação", "Próximo objetivo antes do fim do atual (novo desafio, plano para a próxima "
                             "prova); desconto de 3 meses no mensal só se o teste mostrar efeito."),
     ]},
    {"titulo": "Ativos em ambiente fechado", "cor": COR_SEG["Ativos em ambiente fechado"],
     "destaque": f"{br(pf.loc['Ativos em ambiente fechado', 'assinantes'], 0)} em 31/07 · "
                 f"{br(n_atual['Ativos em ambiente fechado'], 0)} em 30/09 · "
                 f"{br(100 - pf.loc['Ativos em ambiente fechado', '% anual'], 0)}% mensais",
     "linhas": [
         ("Perfil", f"{br(pf.loc['Ativos em ambiente fechado', 'treinos/semana'])} treinos por semana, "
                    f"{br(100 - pf.loc['Ativos em ambiente fechado', '% ao ar livre'], 0)}% em força, funcional ou yoga."),
         ("Saída em 60 dias", f"**{br(pf.loc['Ativos em ambiente fechado', 'saída 60 dias (%)'])}%**, abaixo da média."),
         ("Hipótese de driver", f"Rotina estável; o risco está no mensal recém-chegado "
                                f"({br(100 * nov.loc[('Ativos em ambiente fechado', 'até 90 dias'), 'mean'])}%) e no "
                                f"cartão (falha de cobrança)."),
         ("Prioridade", "**Monitoramento**, com ação só no mensal novo e no cartão."),
         ("Direção da ação", "Conteúdo e progressão de treino (sem custo); aviso de cartão e troca de "
                             "método para quem paga no cartão."),
     ]},
    {"titulo": "Veteranos", "cor": COR_SEG["Veteranos"],
     "destaque": f"{br(pf.loc['Veteranos', 'assinantes'], 0)} em 31/07 · {br(n_atual['Veteranos'], 0)} em 30/09",
     "linhas": [
         ("Perfil", f"{br(pf.loc['Veteranos', 'tempo de casa (dias)'] / 365.25)} anos de casa (mediana), "
                    f"{br(pf.loc['Veteranos', 'treinos/semana'])} treinos por semana."),
         ("Saída em 60 dias", f"**{br(pf.loc['Veteranos', 'saída 60 dias (%)'])}%**, menos da metade da média."),
         ("Hipótese de driver", "Hábito formado; parte é sobrevivência (só ficou quem gosta)."),
         ("Prioridade", "**Monitoramento.** Oferta para quem ficaria de qualquer jeito é custo sem retorno."),
         ("Direção da ação", "Reconhecimento e indicação de amigos, sem desconto."),
     ]},
])
exp = fora_b.groupby("plano")[["expirou_60d", "religou_60d"]].mean()
p.secao("À parte: quem já desligou a renovação")
p.texto(f"""
- **{br(len(fora_b), 0)} assinantes ativos em 31/07** ({br(100 * (fora_b.plano == 'anual').mean(), 0)}% anuais;
  {br(len(fora_a), 0)} em 30/09) já tinham desligado a renovação e seguem pagando até o fim do período.
  Treinavam pouco: mediana de {br(fora_b[fora_b.plano == 'anual'].treinos_semana.median(), 2)} treino por semana no anual.
- Em 60 dias, {br(100 * fora_b.expirou_60d.mean())}% expiraram (mensal {br(100 * exp.loc['mensal', 'expirou_60d'], 0)}%,
  anual {br(100 * exp.loc['anual', 'expirou_60d'], 0)}%) e só {br(100 * fora_b.religou_60d.mean())}% religaram sozinhos.
- O anual que desligou ainda tem meses até expirar (mediana de 157 dias de aviso, etapa 03): é a maior
  janela para tentar reverter. Não é segmento de comportamento, é uma **lista operacional**.
""")

p.secao("Três frases")
p.texto(f"""
- **O que o dado diz.** Os pagantes se dividem em quatro grupos estáveis por engajamento e tempo de
  casa; a saída vai de {br(pf['saída 60 dias (%)'].min())}% (veteranos) a {br(pf['saída 60 dias (%)'].max())}% (parados),
  e o maior volume de saídas está nos ativos ao ar livre.
- **O que ele não diz.** Que o grupo causa a saída, nem quanto uma ação reduziria cada taxa: a
  separação é fraca (silhueta {br(sil4, 2)}) e a taxa é histórica.
- **A próxima pergunta.** Dentro de cada grupo, quem tem o maior risco individual (modelo da semana
  10), e qual ação muda a decisão (uplift da campanha de ago/26)?
""")

p.secao("Limites")
p.texto("""
- Estrutura fraca (silhueta abaixo de 0,50): os grupos cortam um contínuo; assinantes na fronteira
  mudam de grupo com pouca mudança de comportamento.
- Taxa de saída histórica (ago–set/26), não previsão. A saída inclui a expiração por falha de
  pagamento, que não é decisão do cliente.
- Seleção: a base de 31/07 não tem quem saiu antes. Viés de sobrevivência no tempo de casa (D02.4).
- O k-means procura grupos redondos em torno de médias, com distância euclidiana; outra régua forma
  outros grupos (aula 3).
- Diferença para a referência da aula (12,5% de saída média; parados 472): a regra de borda de cada
  variável (sem treino, janela) muda dezenas de assinantes; os quatro grupos e as taxas se mantêm.
""")

destino = p.salvar("04_segmentos.html")
print(f"artefato: {destino.relative_to(RAIZ)}")
