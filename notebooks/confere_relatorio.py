"""Confere o Customer Segmentation Report contra o ouro: recalcula cada número e procura no HTML.

Não gera tabela. Lê `segmentos.csv` e `segmentos_kmeans.csv` (ouro) e o relatório em
`estudos-analises/rascunho_customer_segmentation_report.html`, recalcula os números citados
(tamanho e saída de cada persona, intervalos de Wilson, medianas, listas, cruzamento entre os
dois k-means) e confere se cada um aparece no texto da página, no formato brasileiro.

Rode depois do ouro e de `conciliacao_segmentos.py`:

    .venv/bin/python notebooks/confere_relatorio.py   (a partir da raiz do repo)

Sai com código 1 se algum número não for encontrado.
"""
import html
import re
import sys

import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score

from _ouro import OURO, RAIZ

RELATORIO = RAIZ / "estudos-analises" / "rascunho_customer_segmentation_report.html"
REF = "2026-07-31"
PERSONAS = ["Parados", "Ativos ao ar livre", "Ativos em ambiente fechado", "Veteranos"]
ATIVOS = PERSONAS[1:3]

for arq in ["segmentos.csv", "segmentos_kmeans.csv"]:
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


achados, faltam = 0, []


def confere(rotulo, trecho):
    global achados
    if trecho in texto:
        achados += 1
    else:
        faltam.append(f"{rotulo}: '{trecho}'")


L = pd.read_csv(OURO / "segmentos.csv")
N = pd.read_csv(OURO / "segmentos_kmeans.csv")
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
jd, jb = a[a.segmento == "Já desligou"], b[b.segmento == "Já desligou"]
confere("Já desligou: % anual em 30/09", f"{100 * (jb.plano == 'anual').mean():.0f}%")
confere("Já desligou: treino no anual", br(jd[jd.plano == "anual"].treinos_semana.median(), 2) + " treino")

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
j = a.merge(na, on="user_id", suffixes=("_l", "_n"))
ct = pd.crosstab(j.segmento_l, j.segmento_n)
for (l, c), v in ct.stack().items():
    if v >= 3:
        confere(f"célula {l} × {c}", n(v))
taxa_cel = j[j.segmento_l != "Já desligou"].groupby(["segmento_l", "segmento_n"]).saiu_60d_l.mean()
for (l, c), v in taxa_cel.items():
    if ct.loc[l, c] >= 10:
        confere(f"saída {l} × {c}", f"({br(100 * v)}%)")
sem_jd = j[j.segmento_l != "Já desligou"]
confere("Rand ajustado", br(adjusted_rand_score(sem_jd.segmento_l, sem_jd.segmento_n), 2))
pn = j[j.segmento_n == "Parados"]
confere("Parados (N) já desligados", f"{n((pn.renovacao == 'desligada').sum())} ({100 * (pn.renovacao == 'desligada').mean():.0f}%)")
lig = pn[pn.renovacao == "ligada"]
confere("Parados (N) com renovação ligada", f"({n(len(lig))}) saem {br(100 * lig.saiu_60d_l.mean())}%")
confere("Já desligou em Parados (N)", f"{100 * (j[j.segmento_l == 'Já desligou'].segmento_n == 'Parados').mean():.0f}%")
confere("decidiram sair", n(sem_jd.saiu_60d_l.sum()))
confere("decidiram e já tinham fim", n((sem_jd.saiu_60d_l.astype(bool) & sem_jd.saiu_60d_n.astype(bool)).sum()))
mn = j[j.segmento_l.isin(ATIVOS) & (j.plano_l == "mensal") & (j.tempo_casa_dias <= 90)]
confere("mensais ativos com até 90 dias", n(len(mn)))
confere("deles em Recém-chegados", n((mn.segmento_n == "Recém-chegados").sum()))

for f in faltam:
    print("NÃO ACHEI", f)
print(f"\n{achados} números do relatório conferidos com o ouro · {len(faltam)} não encontrados")
sys.exit(1 if faltam else 0)
