"""Confere o Customer Segmentation Report contra o ouro: recalcula cada número e procura no HTML.

Não gera tabela. Lê `segmentos.csv`, `segmentos_kmeans.csv`, `churn_mensal.csv`, `saidas.csv` e
`assinantes_30jun26.csv` (ouro) e o relatório em
`artefatos/customer_segmentation_report.html` (gerado pelo `relatorio_segmentacao.py`),
recalcula os números citados
(tamanho e saída de cada persona, intervalos de Wilson, medianas, listas, cruzamento entre os
dois k-means, churn médio por tipo e plano, antecedência, tempo de casa e AUC) e confere se cada
um aparece no texto da página, no formato brasileiro.

Antes dos números, confere a ligação das duas segmentações (X1): as duas tabelas de ouro têm de
ter os mesmos pares `(user_id, data_ref)`, uma linha por par, e o cruzamento assinante por
assinante não pode mudar o tamanho da base nem a taxa de decisão de L. Números que dependem de
dizer a mesma base — decisão de L e fim da assinatura de N nos pagantes de 31/07 com a renovação
não desligada — são conferidos por âncora de texto (regex sobre o HTML sem tags), não pelo número
solto: o mesmo valor aparece noutra base (o fim da assinatura sobre a base inteira, por exemplo).
Âncora ainda ausente não reprova: sai como PENDENTE, com o valor do ouro, para quem juntar o
texto; âncora presente com outro valor reprova.

Rode depois do ouro e de `conciliacao_segmentos.py`:

    .venv/bin/python notebooks/confere_relatorio.py   (a partir da raiz do repo)

Sai com código 1 se algum número não for encontrado.
"""
import html
import re
import sys

import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score, roc_auc_score

from _ouro import OURO, PRATA, RAIZ

RELATORIO = RAIZ / "artefatos" / "customer_segmentation_report.html"
REF = "2026-07-31"
PERSONAS = ["Parados", "Ativos ao ar livre", "Ativos em ambiente fechado", "Veteranos"]
ATIVOS = PERSONAS[1:3]

for arq in ["segmentos.csv", "segmentos_kmeans.csv", "churn_mensal.csv", "saidas.csv",
            "assinantes_30jun26.csv"]:
    if not (OURO / arq).exists():
        sys.exit(f"falta dados/3.ouro/{arq}: rode os notebooks de ouro antes")
bruto = RELATORIO.read_text()
texto = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", bruto)))


def br(x, d=1):
    """Número no formato brasileiro: 14.032 · 10,5."""
    return f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def n(x):
    return br(round(x), 0)


def wilson(k, tot, z=1.96):
    p = k / tot
    c = (p + z * z / (2 * tot)) / (1 + z * z / tot)
    m = z * np.sqrt(p * (1 - p) / tot + z * z / (4 * tot * tot)) / (1 + z * z / tot)
    return c - m, c + m


achados, faltam, pendentes = 0, [], []


def confere(rotulo, trecho):
    global achados
    if trecho in texto:
        achados += 1
    else:
        faltam.append(f"{rotulo}: '{trecho}'")


def confere_contexto(rotulo, ancoras, esperado):
    """Confere `esperado` só onde ele está preso a uma âncora de texto, não em qualquer lugar.

    `ancoras` são regex com um grupo: o número. Uma frase nova que diga a mesma coisa com outras
    palavras só precisa acrescentar a regex aqui. Se o número não aparece em nenhuma âncora, a
    página pode estar ainda sendo escrita: vira PENDENTE, não reprovação.
    """
    global achados
    achou = sorted({m.group(1) for p in ancoras for m in re.finditer(p, texto)})
    if esperado in achou:
        achados += 1
    elif achou:
        faltam.append(f"{rotulo}: o texto diz {', '.join(achou)} e o ouro dá {esperado}")
    else:
        pendentes.append(f"{rotulo}: ouro {esperado} · âncoras aceitas: {' | '.join(ancoras)}")


L = pd.read_csv(OURO / "segmentos.csv")
N = pd.read_csv(OURO / "segmentos_kmeans.csv")

# --- a ligação das duas segmentações (decisão X1) ----------------------------------------
# O cruzamento é assinante por assinante: exige os mesmos pares (user_id, data_ref) nas duas
# tabelas e uma linha por par. Sem isso o merge inflaria ou perderia linhas em silêncio.
for nome, tab in [("segmentos.csv (L)", L), ("segmentos_kmeans.csv (N)", N)]:
    rep = tab.duplicated(["user_id", "data_ref"])
    if rep.any():
        sys.exit(f"{nome}: {rep.sum()} pares (user_id, data_ref) repetidos")
pares = {nome: {(u, r) for u, r in tab[["user_id", "data_ref"]].to_numpy()}
         for nome, tab in [("L", L), ("N", N)]}
por_ref = {}
for ref in sorted(L.data_ref.unique()):
    l = {p for p in pares["L"] if p[1] == ref}
    nn = {p for p in pares["N"] if p[1] == ref}
    if l != nn:
        sys.exit(f"{ref}: {len(l - nn)} assinantes só em L e {len(nn - l)} só em N — o "
                 f"cruzamento X1 exige os mesmos pares nas duas tabelas (veja L1/N1 e o merge de "
                 f"conciliacao_segmentos.py)")
    por_ref[ref] = len(l)
print("pares (user_id, data_ref) iguais em L e N: "
      + " · ".join(f"{ref} {n(k)}" for ref, k in por_ref.items()))

a, b = L[L.data_ref == REF], L[L.data_ref == "2026-09-30"]
ag = a[a.segmento != "Já desligou"]
media = ag.saiu_60d.mean()

# --- personas (decisões L1–L8) ----------------------------------------------------------
confere("pagantes em 31/07", n(len(a)))
confere("renovação ligada em 31/07", n(len(ag)))
confere("já desligou em 31/07", n((a.segmento == "Já desligou").sum()))
confere("pagantes em 30/09", n(len(b)))
confere("renovação ligada em 30/09", n((b.segmento != "Já desligou").sum()))
confere("média de saída", br(100 * media) + "%")
confere("limiar de ação imediata (1,5 × média)", br(150 * media) + "%")
for s in PERSONAS:
    g, gb = ag[ag.segmento == s], b[b.segmento == s]
    taxa = g.saiu_60d.mean()
    lo, hi = wilson(g.saiu_60d.sum(), len(g))
    confere(f"{s}: assinantes 30/09", n(len(gb)))
    confere(f"{s}: % da base", br(100 * len(g) / len(ag)) + "%")
    confere(f"{s}: saída", br(100 * taxa) + "%")
    confere(f"{s}: IC 95%", f"IC {br(100 * lo)}–{br(100 * hi)}")
    confere(f"{s}: saídas esperadas", n(taxa * len(gb)))
    confere(f"{s}: treinos por semana", br(g.treinos_semana.median()))
    if s in ATIVOS:
        m = g[(g.plano == "mensal") & (g.tempo_casa_dias <= 90)]
        confere(f"{s}: % mensal", f"{100 * (g.plano == 'mensal').mean():.0f}%")
        confere(f"{s}: mensal com até 90 dias", br(100 * m.saiu_60d.mean()) + "%")
        confere(f"{s}: meses de casa", f"{g.tempo_casa_dias.median() / 30.4:.0f} meses de casa")
    else:
        confere(f"{s}: % anual", f"{100 * (g.plano == 'anual').mean():.0f}%")
p = ag[ag.segmento == "Parados"]
confere("Parados: dias sem treino", f"{p.dias_sem_treino.median():.0f} dias sem treino")
confere("Parados: vezes a média", br(p.saiu_60d.mean() / media) + " vezes")
v = ag[ag.segmento == "Veteranos"]
confere("Veteranos: anos de casa", br(v.tempo_casa_dias.median() / 365.25) + " anos de casa")
confere_contexto("Parados em 31/07 (grupo pequeno)",
                 [r"Grupo pequeno \((\d[\d.]*)"], n((ag.segmento == "Parados").sum()))
jd, jb = a[a.segmento == "Já desligou"], b[b.segmento == "Já desligou"]
confere("Já desligou: % anual em 30/09", f"{100 * (jb.plano == 'anual').mean():.0f}%")
confere("Já desligou: treino no anual", br(jd[jd.plano == "anual"].treinos_semana.median(), 2) + " treino")
livre_m = ag[(ag.segmento == "Ativos ao ar livre") & (ag.plano == "mensal")
             & (ag.pct_ar_livre > 0)]
confere_contexto("GPS com falha", [r"GPS falho não se confirmou como driver \((\d+,\d+)% com falha"],
                 br(100 * livre_m[livre_m.pct_gps_falho > 0].saiu_60d.mean()))
confere_contexto("GPS sem falha", [r"GPS falho não se confirmou como driver \(\d+,\d+% com falha × (\d+,\d+)% sem"],
                 br(100 * livre_m[livre_m.pct_gps_falho == 0].saiu_60d.mean()))

# --- EDA descritiva (seção 02 do relatório) ----------------------------------------------
# Churn por tipo e plano: perdas do mês ÷ ativos no dia 1 (G1), tipo pelo motivo_fim (W1).
cm = pd.read_csv(OURO / "churn_mensal.csv")
sd = pd.read_csv(OURO / "saidas.csv", parse_dates=["inicio", "data_fim"])
qs = pd.read_csv(OURO / "assinantes_30jun26.csv")

# Falha de pagamento por método: involuntárias de jan–set/26 ÷ assinaturas pagas ativas em algum
# dia do período (prata `assinaturas`), por plano × método — o mesmo denominador do gerador.
ass = pd.read_csv(PRATA / "assinaturas.csv", parse_dates=["inicio", "data_fim"],
                  usecols=["plano_atual", "metodo", "inicio", "data_fim", "flag_cortesia"])
pago = ass[ass.flag_cortesia == 0]
ativo_periodo = pago[(pago.inicio < "2026-09-30")
                     & (pago.data_fim.isna() | (pago.data_fim >= "2026-01-01"))]
inv = sd[(sd.tipo_saida == "involuntária") & (sd.data_fim >= "2026-01-01")
         & (sd.data_fim <= "2026-09-30")]
tx_inv = (100 * inv.groupby(["plano", "metodo"]).size()
          / ativo_periodo.groupby(["plano_atual", "metodo"]).size()).dropna()
mm = tx_inv.loc["mensal"]
confere_contexto("involuntárias por 100 no cartão, no mensal",
                 [r"No mensal,\s*(\d+,\d)\s*saídas involuntárias"], br(mm["cartao"]))
confere_contexto("involuntárias nos outros métodos do mensal, mínima",
                 [r"contra\s+(\d+,\d)\s*a\s+\d+,\d\s*nos outros métodos"],
                 br(mm.drop("cartao").min()))
confere_contexto("involuntárias nos outros métodos do mensal, máxima",
                 [r"contra\s+\d+,\d\s*a\s+(\d+,\d)\s*nos outros métodos"],
                 br(mm.drop("cartao").max()))
confere("loja nas saídas de 2026",
        br(100 * (sd[sd.data_fim >= "2026-01-01"].canal == "loja").mean()) + "%")
tot = cm[cm.recorte == "total"].set_index("mes")
med = {ano: tot[tot.index.str.startswith(ano)].churn_pct.mean() for ano in ["2025", "2026"]}
confere("churn total 2025", br(med["2025"], 2) + "%")
confere("churn total jan–set/26", br(med["2026"], 2) + "%")

sd["mes"] = sd.data_fim.dt.to_period("M").astype(str)
perda = sd[sd.inicio < sd.data_fim.dt.to_period("M").dt.start_time]
TIPOS = ["voluntária", "involuntária", "devolução"]
pt = perda.groupby(["mes", "tipo_saida"]).size().unstack(fill_value=0).reindex(tot.index, fill_value=0)
taxa = 100 * pt[TIPOS].div(tot.ativos_inicio, axis=0)
tipo_med = {ano: taxa[taxa.index.str.startswith(ano)].mean() for ano in ["2025", "2026"]}
for tipo in ["voluntária", "involuntária"]:
    confere(f"churn {tipo} 2025", br(tipo_med["2025"][tipo], 2) + "%")
    confere(f"churn {tipo} jan–set/26", br(tipo_med["2026"][tipo], 2) + "%")

for plano, rot in [("mensal", "Mensal"), ("anual", "Anual")]:
    pl = cm[(cm.recorte == "plano") & (cm.segmento == plano)].set_index("mes")
    p = (perda[perda.plano == plano].groupby(["mes", "tipo_saida"]).size()
         .unstack(fill_value=0).reindex(pl.index, fill_value=0))
    tx = 100 * p[TIPOS].div(pl.ativos_inicio, axis=0)
    for ano in ["2025", "2026"]:
        confere(f"{rot}, voluntária {ano}",
                br(tx[tx.index.str.startswith(ano)]["voluntária"].mean(), 2) + "%")
    d = cm[(cm.recorte == "plano") & (cm.segmento == plano)]
    v = {ano: d[d.mes.str.startswith(ano)].churn_pct.mean() for ano in ["2025", "2026"]}
    confere(f"{plano} + p.p.", br(v["2026"] - v["2025"], 2) + " p.p.")

vol26 = sd[(sd.tipo_saida == "voluntária") & (sd.data_fim >= "2026-01-01")]
ant = vol26.groupby("plano").antecedencia_dias.median()
for plano, rot in [("mensal", "mensal"), ("anual", "anual")]:
    confere(f"antecedência {rot}", f"{br(ant[plano], 0)} dias")

men = qs[qs.plano == "mensal"].copy()
men["faixa"] = pd.cut(men.tempo_casa_meses, [-0.1, 3, 6, 12, 24, np.inf],
                      labels=["até 3", "3–6", "6–12", "12–24", "mais de 24"])
t_men = men.groupby("faixa", observed=True).saiu.mean() * 100
confere("saída até 3 meses", br(t_men.loc["até 3"]) + "%")
confere("saída acima de 24 meses", br(t_men.loc["mais de 24"]) + "%")

an = qs[(qs.plano == "anual") & (qs.vence_jul_set == 1)]
d = an[["saiu", "dias_treino_abr_jun"]].dropna()
auc = roc_auc_score(d.saiu, d.dias_treino_abr_jun)
lig = an[an.renovacao_30jun == "ligada"][["saiu", "dias_treino_abr_jun"]].dropna()
auc_l = roc_auc_score(lig.saiu, lig.dias_treino_abr_jun)
if auc >= 0.5 or auc_l >= 0.5:
    sys.exit(f"a direção do treino mudou: AUC {auc:.2f} na base do anual que vence e {auc_l:.2f} "
             f"com a renovação ligada; o relatório diz que quem treina pouco não renova. Revise a "
             f"seção 02, achado 4, e a seção 05, e gere de novo.")
confere("AUC do treino no anual", "AUC " + br(max(auc, 1 - auc), 2))
confere("AUC do treino com renovação ligada",
        br(max(auc_l, 1 - auc_l), 2) + " só entre quem estava com a renovação ligada")

# --- k-means de nove variáveis (N1–N7) --------------------------------------------------
na, nb = N[N.data_ref == REF], N[N.data_ref == "2026-09-30"]
cf = na[na.segmento == "Cobrança falhando"]
confere("Cobrança falhando: 31/07", n(len(cf)))
confere("Cobrança falhando: 30/09", n((nb.segmento == "Cobrança falhando").sum()))
confere("Cobrança falhando: saída", br(100 * cf.saiu_60d.mean()) + "%")
confere("Cobrança falhando: % mensal", f"{100 * (cf.plano == 'mensal').mean():.0f}%")
confere("Cobrança falhando: % cartão", f"{100 * (cf.metodo == 'cartao').mean():.0f}%")
confere("Cobrança falhando: continuaram", f"{100 * (1 - cf.saiu_60d.mean()):.0f}%")
sai = cf[cf.saiu_60d == 1]
confere("Cobrança falhando: % falha de pagamento",
        f"{100 * (sai.motivo_fim_60d == 'falha_pagamento').mean():.0f}%")
confere("média de saída (fim da assinatura)", br(100 * na.saiu_60d.mean()) + "%")

# --- cruzamento (X1) ----------------------------------------------------------------------
j = a.merge(na, on=["user_id", "data_ref"], suffixes=("_l", "_n"))
if len(j) != len(a):
    sys.exit(f"o cruzamento L × N em {REF} não ficou um para um: {len(a)} linhas em L, {len(j)} "
             f"no merge")

# --- as duas réguas na mesma base (seção 04 do relatório) ---------------------------------
# Mesma base = os pagantes de 31/07 com a renovação não desligada: é nela que o relatório compara
# o que L chama de decisão de sair com o que N chama de fim da assinatura (`data_fim`).
base = j[j.segmento_l != "Já desligou"]
if len(base) != len(ag) or not np.isclose(base.saiu_60d_l.mean(), media):
    sys.exit("o merge com N mudou o tamanho ou a taxa de decisão da base de L: o cruzamento não "
             "ficou um para um")
taxa_dec, taxa_fim = base.saiu_60d_l.mean(), base.saiu_60d_n.mean()
# Fim da assinatura (N) e decisão (L) são conjuntos: contagem de fim e interseção são calculadas
# à parte, com operação de conjuntos (o mesmo que o gerador faz).
dec_users = set(base.loc[base.saiu_60d_l == 1, "user_id"])
fim_users = set(base.loc[base.saiu_60d_n == 1, "user_id"])
print(f"mesma base ({n(len(base))} com a renovação não desligada em {REF}): decisão L "
      f"{br(100 * taxa_dec)}% ({n(base.saiu_60d_l.sum())}) · fim da assinatura N "
      f"{br(100 * taxa_fim)}% ({n(base.saiu_60d_n.sum())})")
confere_contexto("taxa de decisão de L, em %, na base com a renovação ligada",
                 [r"Decis[ãa]o[^.]{0,80}?(\d+,\d)\s*%",
                  r"(?:renova[çc][ãa]o ligada|base)[^.]{0,80}?(\d+,\d)\s*%[^.]{0,40}decis"],
                 br(100 * taxa_dec))
confere_contexto("taxa de fim da assinatura de N, em %, na mesma base",
                 [r"(?:fim da assinatura|data_fim)[^.]{0,60}?é\s*(\d+,\d)\s*%",
                  r"mesma base[^.]{0,80}?[é:]\s*(\d+,\d)\s*%",
                  r"fim da assinatura[^.]{0,60}n(?:a|essa) mesma base[^.]{0,40}?(\d+,\d)\s*%"],
                 br(100 * taxa_fim))
confere_contexto("saídas pela decisão na mesma base (contagem)",
                 [r"(\d[\d.]*)\s+que decidiram sair"], n(base.saiu_60d_l.sum()))
confere_contexto("saídas pelo fim da assinatura na mesma base (contagem)",
                 [r"[sS][óo]\s+(\d[\d.]*)\s+j[áa]\s+tinham a assinatura encerrada",
                  rf"(\d[\d.]*)\s+de\s+{re.escape(n(len(base)))} "],
                 n(len(fim_users)))

ct = pd.crosstab(j.segmento_l, j.segmento_n)
for (l, c), v in ct.stack().items():
    if v >= 3:
        confere(f"célula {l} × {c}", n(v))
taxa_cel = base.groupby(["segmento_l", "segmento_n"]).saiu_60d_l.mean()
for (l, c), v in taxa_cel.items():
    if ct.loc[l, c] >= 10:
        confere(f"saída {l} × {c}", f"({br(100 * v)}%)")
confere("Rand ajustado", br(adjusted_rand_score(base.segmento_l, base.segmento_n), 2))
pn = j[j.segmento_n == "Parados"]
confere("Parados (N) já desligados", f"{n((pn.renovacao == 'desligada').sum())} ({100 * (pn.renovacao == 'desligada').mean():.0f}%)")
lig = pn[pn.renovacao == "ligada"]
confere("Parados (N) com renovação ligada", f"({n(len(lig))}) saem {br(100 * lig.saiu_60d_l.mean())}%")
confere("Já desligou em Parados (N)", f"{100 * (j[j.segmento_l == 'Já desligou'].segmento_n == 'Parados').mean():.0f}%")
confere("decidiram sair", n(base.saiu_60d_l.sum()))
confere("fim da assinatura na mesma base (contagem)", n(len(fim_users)))
confere("interseção de decisão e fim", n(len(dec_users & fim_users)))
mn = j[j.segmento_l.isin(ATIVOS) & (j.plano_l == "mensal") & (j.tempo_casa_dias <= 90)]
confere("mensais ativos com até 90 dias", n(len(mn)))
confere("deles em Recém-chegados", n((mn.segmento_n == "Recém-chegados").sum()))

for f in faltam:
    print("NÃO ACHEI", f)
for f in pendentes:
    print("PENDENTE (texto a juntar)", f)
print(f"\n{achados} números do relatório conferidos com o ouro · {len(faltam)} não encontrados · "
      f"{len(pendentes)} pendentes de texto")
sys.exit(1 if faltam else 0)
