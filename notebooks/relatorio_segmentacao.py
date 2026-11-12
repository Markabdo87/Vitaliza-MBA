"""Gera o Customer Segmentation Report (HTML) a partir das tabelas de ouro.

O texto do relatório mora em `estudos-analises/customer_segmentation_report.template.html`:
é lá que se escreve, se revisa e se discute a redação. Este notebook não escreve texto novo —
ele preenche os `{{placeholders}}` do template com números calculados do ouro, monta os blocos
repetidos (barras, eixos e a matriz do cruzamento) e falha se uma conclusão qualitativa do texto
deixar de ser verdadeira nos dados.

Uso (da raiz do repo, depois do ouro e de `conciliacao_segmentos.py`):

    .venv/bin/python notebooks/relatorio_segmentacao.py

Lê (ouro e uma tabela de prata):
    dados/3.ouro/segmentos.csv            L1–L8 (personas)
    dados/3.ouro/segmentos_kmeans.csv     N1–N7 (k-means de 9 variáveis)
    dados/3.ouro/churn_mensal.csv         G (churn mensal)
    dados/3.ouro/saidas.csv               W (tipo de saída, antecedência, pesquisa)
    dados/3.ouro/assinantes_30jun26.csv   K (tempo de casa, AUC do treino)
    dados/2.prata/pesquisa_saida.csv      Q7 (tema do comentário, pela função `tema`)
    dados/2.prata/assinaturas.csv         pagantes ativos no período (denominador de cobrança)
    dados/2.prata/eventos_assinatura.csv  religou sozinho nos 60 dias (lista "Já desligou")
Escreve:
    artefatos/customer_segmentation_report.html

O produto vai para `artefatos/`, ao lado das páginas numeradas do ouro (`00`–`06`), e não para
`estudos-analises/`: é entrega da semana 5, não rascunho. Fica sem número para não disputar a
numeração com as páginas de análise. Por isso os links do template são para as páginas irmãs
(`00_historia_da_eda.html`, `04_segmentos.html`), relativos a `artefatos/`.

O que é dinâmico e o que é fixo
-------------------------------
Dinâmico (sai do ouro a cada execução): todos os números de base, persona, churn, conciliação,
pesquisa e cobrança; as larguras das barras, os rótulos `aria-label` e as escalas dos eixos; a
matriz do cruzamento (contagens, taxas, totais, células em destaque); os destaques de prioridade
que dependem do critério declarado na seção 06; os números do texto que antes ficavam fixos
(Parados em 31/07, 2 vezes por semana, anos de casa dos Veteranos, fatia da loja nas saídas);
GPS na população do mensal com treino ao ar livre; falha de pagamento por método com
denominador de período, por plano × método; o fator do critério de priorização da seção 06, que
sai da constante `FATOR_ACAO` e entra no texto pelo placeholder `{{fator_acao}}`, para o template
não repetir o número; e a qualidade das duas segmentações — silhueta de cada uma e Rand ajustado
em reamostras —, recalculada a cada execução com a regra de `_metricas_segmentacao` (a de L5/N5)
sobre as variáveis publicadas no ouro. Nenhum desses números fica escrito no código.

A métrica de qualidade tem guarda de reprodução: o k-means refeito aqui tem de devolver
exatamente a coluna `segmento` das tabelas de ouro (Rand ajustado = 1). Se a regra ou o parâmetro
mudar num notebook e não no helper, o relatório para em vez de publicar a silhueta de um
agrupamento que não é o que está nas tabelas. Também para se a silhueta deixar de ser "estrutura
fraca" (< 0,50) ou se o Rand médio cair abaixo de 0,90 — as duas afirmações do texto.

Fixo, por decisão editorial (não é número de dado): a redação, a ordem das personas, as ofertas e
as hipóteses de driver; o próprio `FATOR_ACAO` (critério da seção 06, escolha do grupo); as
variáveis e os parâmetros do k-means (`VARS_L`, `VARS_N`, `LOG_N`, k, `n_init`, sementes), que
moram em `notebooks/_metricas_segmentacao.py` e são usados pelos dois notebooks de ouro; e as
constantes de negócio declaradas em `CONSTANTES` (prazos e datas do enunciado), cada uma com a
fonte ao lado.

Se uma conclusão qualitativa deixar de valer, o notebook para com a instrução de revisão (qual
frase do template rever e por quê) em vez de gerar uma página que diz uma coisa e mostra outra.
"""
import re
import sys
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score, roc_auc_score

from _metricas_segmentacao import (LIMIAR_FRACA, LIMIAR_RAND, REAMOSTRAS, metricas_l,
                                   metricas_n)
from _ouro import OURO, PRATA, RAIZ, ler_prata
from pesquisa_saida_prata import tema

TEMPLATE = RAIZ / "estudos-analises" / "customer_segmentation_report.template.html"
SAIDA = RAIZ / "artefatos" / "customer_segmentation_report.html"

REF = "2026-07-31"
REF_FIM = "2026-09-30"
PERSONAS = ["Parados", "Ativos ao ar livre", "Ativos em ambiente fechado", "Veteranos"]
ATIVOS = PERSONAS[1:3]
CHAVE = {"Parados": "parados", "Ativos ao ar livre": "ar_livre",
         "Ativos em ambiente fechado": "fechado", "Veteranos": "veteranos"}
# Ordem editorial das colunas do k-means de 9 variáveis (a mesma da página 05).
ORDEM_N = ["Engajados", "Recém-chegados", "Parados", "Cobrança falhando"]

# Constantes de negócio: não saem do ouro, vêm do enunciado e do guia de entregas.
CONSTANTES = {
    "data_corte": ("30/09/2026", "enunciado, corte dos dados"),
    "prazo_semana5": ("15/11/2026, 23h59", "guia de entregas, semana 5"),
    "prazo_semana10": ("20/12/2026", "guia de entregas, semana 10"),
    "data_limite_modelo": ("29/11/2026", "enunciado, seção 02 (prever quem sai em 60 dias)"),
}

# Escalas dos gráficos: escolha de layout (teto do eixo), não de dado. O gerador confere que
# todos os valores cabem e avisa se ficarem pequenos demais para a escala.
ESCALAS = {"churn": (20, 5), "personas": (35, 7), "volume": (1000, 250)}

# Campos de perfil que o template usa em cada persona (evita cálculo morto).
CAMPOS = {
    "parados": ["anual", "treinos", "meses"],
    "ar_livre": ["anual", "mensal", "treinos", "pct_ar", "meses", "saidas"],
    "fechado": ["anual", "mensal", "treinos", "pct_ar", "meses"],
    "veteranos": ["anual", "treinos"],
}

# Critério de priorização declarado na seção 06 do relatório.
FATOR_ACAO = 1.5


# ---------------------------------------------------------------------------------------------
# formatação
# ---------------------------------------------------------------------------------------------
def br(x, d=1):
    """Número no formato brasileiro: 14.032 · 10,5."""
    return f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def n(x):
    return br(round(x), 0)


def pct(x, d=1):
    return br(x, d)


def treinos(x):
    """Mediana de treinos por semana: 0 sem casa decimal, o resto com uma (2,0)."""
    return "0" if float(x) == 0 else br(x, 1)


def largura(valor, escala):
    """Largura da barra em % da escala, a partir do valor já arredondado que aparece no rótulo.

    Arredonda meio para cima (2,51 de 20 vira 12,6) e tira o zero à toa (40, não 40.0).
    """
    d = (Decimal(100) * Decimal(str(valor)) / Decimal(str(escala))).quantize(
        Decimal("0.1"), rounding=ROUND_HALF_UP)
    return f"{d:.1f}".rstrip("0").rstrip(".")


def wilson(k, tot, z=1.96):
    p = k / tot
    c = (p + z * z / (2 * tot)) / (1 + z * z / tot)
    m = z * np.sqrt(p * (1 - p) / tot + z * z / (4 * tot * tot)) / (1 + z * z / tot)
    return c - m, c + m


# ---------------------------------------------------------------------------------------------
# leitura
# ---------------------------------------------------------------------------------------------
for arq in ["segmentos.csv", "segmentos_kmeans.csv", "churn_mensal.csv", "saidas.csv",
            "assinantes_30jun26.csv", "conciliacao_segmentos.csv"]:
    if not (OURO / arq).exists():
        sys.exit(f"falta dados/3.ouro/{arq}: rode os notebooks de ouro e conciliacao_segmentos.py")

L = pd.read_csv(OURO / "segmentos.csv")
N = pd.read_csv(OURO / "segmentos_kmeans.csv")
cm = pd.read_csv(OURO / "churn_mensal.csv")
sd = pd.read_csv(OURO / "saidas.csv", parse_dates=["inicio", "data_fim"])
qs = pd.read_csv(OURO / "assinantes_30jun26.csv")
ps = pd.read_csv(PRATA / "pesquisa_saida.csv", parse_dates=["respondido_em"])

a, b = L[L.data_ref == REF], L[L.data_ref == REF_FIM]
ag = a[a.segmento != "Já desligou"]
na, nb = N[N.data_ref == REF], N[N.data_ref == REF_FIM]
jd = a[a.segmento == "Já desligou"]
jb = b[b.segmento == "Já desligou"]

# O cruzamento é assinante por assinante (X1): sem um para um, nada abaixo vale.
j = a.merge(na, on=["user_id", "data_ref"], suffixes=("_l", "_n"))
if len(j) != len(a):
    sys.exit(f"o cruzamento L × N em {REF} não ficou um para um: {len(a)} em L, {len(j)} no merge")
base = j[j.segmento_l != "Já desligou"]
if len(base) != len(ag):
    sys.exit("o merge com N mudou o tamanho da base de L: o cruzamento não ficou um para um")

# ---------------------------------------------------------------------------------------------
# métricas
# ---------------------------------------------------------------------------------------------
M = {k: v for k, (v, _) in CONSTANTES.items()}
M["data_geracao"] = date.today().strftime("%d/%m/%Y")

# As datas do texto são literais: se o corte mudar, a redação precisa ser revista antes.
if set(L.data_ref) != {REF, REF_FIM} or set(N.data_ref) != {REF, REF_FIM}:
    sys.exit(f"o ouro tem datas de referência {sorted(set(L.data_ref))}, e o texto do template "
             f"fala de {REF} e {REF_FIM} (mês a mês, 60 dias, janela de 90 dias). Confira o "
             f"corte em decisoes.md e atualize as datas da redação antes de gerar.")
if (cm.mes.min(), cm.mes.max()) != ("2024-08", "2026-09"):
    sys.exit(f"churn_mensal vai de {cm.mes.min()} a {cm.mes.max()}, e o texto compara 2025 com "
             f"jan–set/2026: revise as janelas citadas no template antes de gerar.")

# --- qualidade das duas segmentações (silhueta e Rand em reamostras) -------------------------
# Não são constantes: o k-means é refeito aqui, com a regra de `_metricas_segmentacao` (a mesma de
# L5 e N5) sobre as variáveis publicadas nas tabelas de ouro, e o resultado tem de reproduzir a
# partição que o ouro gravou. Se a regra divergir do notebook, o Rand ajustado cai abaixo de 1 e o
# relatório para: publicar a métrica de outro agrupamento seria pior que não publicar.
SL, SN = metricas_l(ag), metricas_n(na)
for nome, met in [("4 variáveis (L)", SL), ("9 variáveis (N)", SN)]:
    ari = adjusted_rand_score(ag.segmento if met is SL else na.segmento, met["rotulos"])
    if ari < 1:
        sys.exit(f"o k-means de {nome} recalculado não reproduz a partição das tabelas de ouro "
                 f"(Rand ajustado {br(ari, 3)} com a coluna `segmento`, n = {n(met['n'])}). "
                 f"VARS, LOG_N, k, n_init ou semente de notebooks/_metricas_segmentacao.py "
                 f"divergiram de segmentos_ouro.py / segmentos_kmeans_ouro.py: alinhe a regra ou "
                 f"rode os notebooks de ouro. O relatório NÃO foi escrito.")
if not (0 < SL["silhueta"] < 1 and 0 < SN["silhueta"] < 1):
    sys.exit(f"silhueta fora de (0, 1): {SL['silhueta']:.3f} em L, {SN['silhueta']:.3f} em N")
if SL["silhueta"] >= LIMIAR_FRACA:
    sys.exit(f"silhueta de {br(SL['silhueta'], 2)} em k = {SL['k']} não é 'estrutura fraca' "
             f"(abaixo de {br(LIMIAR_FRACA, 2)}): revise as três frases do template que dizem que "
             f"os grupos cortam um contínuo (resumo, seção 04 e limitações). O relatório NÃO foi "
             f"escrito.")
if SL["rand_medio"] < LIMIAR_RAND:
    sys.exit(f"Rand ajustado médio de {br(SL['rand_medio'], 3)} em {REAMOSTRAS} reamostras está "
             f"abaixo de {br(LIMIAR_RAND, 2)}: o texto cita o agrupamento como estável na mesma "
             f"base. Revise a frase da seção 04 antes de gerar. O relatório NÃO foi escrito.")
M["silhueta_l"] = pct(SL["silhueta"], 2)
M["silhueta_n"] = pct(SN["silhueta"], 2)
M["rand_reamostras"] = br(SL["rand_medio"], 3)

# --- base ------------------------------------------------------------------------------------
M["pagantes_3107"], M["pagantes_3009"] = n(len(a)), n(len(b))
M["base_renov"], M["jd_3107"] = n(len(ag)), n(len(jd))
M["renov_ligada_3009"] = n((b.segmento != "Já desligou").sum())
M["ja_desligou_3009"] = n(len(jb))
M["n_personas"], M["n_listas"] = str(len(PERSONAS)), "2"

media = ag.saiu_60d.mean()
taxa_dec, taxa_fim = base.saiu_60d_l.mean(), base.saiu_60d_n.mean()
M["media_taxa"] = pct(100 * media)
# O fator do critério entra no texto pelo template: a frase da seção 06 não repete o número fixo.
M["fator_acao"] = pct(FATOR_ACAO)
M["limiar_acao"] = pct(100 * FATOR_ACAO * media)
M["taxa_fim_1c"] = pct(100 * taxa_fim)
M["taxa_fim_n"] = pct(100 * na.saiu_60d.mean())
M["n_decisao"] = n(base.saiu_60d_l.sum())
# Fim da assinatura (N) e decisão (L) são conjuntos: a contagem de fim sai do conjunto de N e a
# interseção é calculada à parte, com a operação de conjuntos, não derivada da contagem de fim.
dec_users = set(base.loc[base.saiu_60d_l == 1, "user_id"])
fim_users = set(base.loc[base.saiu_60d_n == 1, "user_id"])
M["fim_contagem"], M["fim_intersecao"] = n(len(fim_users)), n(len(dec_users & fim_users))
if not fim_users <= dec_users:
    sys.exit(f"h\u00e1 {len(fim_users - dec_users)} assinaturas com fim da assinatura no per\u00edodo e "
             f"sem evento de decis\u00e3o em L. A narrativa da se\u00e7\u00e3o 04 ('a decis\u00e3o antecipa o fim') "
             f"n\u00e3o vale mais: revise a frase em "
             f"estudos-analises/customer_segmentation_report.template.html e decida como tratar "
             f"esses casos antes de gerar. O relatório N\u00c3O foi escrito.")

# --- personas --------------------------------------------------------------------------------
taxas, volumes, ics = {}, {}, {}
for s in PERSONAS:
    g, gb = ag[ag.segmento == s], b[b.segmento == s]
    taxa = g.saiu_60d.mean()
    taxas[s], volumes[s] = taxa, taxa * len(gb)
    ics[s] = wilson(g.saiu_60d.sum(), len(g))
    c = CHAVE[s]
    M[f"{c}_3009"] = n(len(gb))
    M[f"{c}_pct_3107"] = pct(100 * len(g) / len(ag))
    M[f"{c}_taxa"] = pct(100 * taxa)
    for campo in CAMPOS[c]:                      # só o que o texto/cartão usa
        if campo == "anual":
            M[f"{c}_anual"] = f"{100 * (g.plano == 'anual').mean():.0f}"
        elif campo == "mensal":
            M[f"{c}_mensal"] = f"{100 * (g.plano == 'mensal').mean():.0f}"
        elif campo == "treinos":
            M[f"{c}_treinos"] = treinos(g.treinos_semana.median())
        elif campo == "pct_ar":
            M[f"{c}_pct_ar"] = f"{g.pct_ar_livre.median():.0f}"
        elif campo == "meses":
            M[f"{c}_meses"] = f"{g.tempo_casa_dias.median() / 30.4:.0f}"
        elif campo == "saidas":
            M[f"{c}_saidas"] = n(taxa * len(gb))

M["taxa_min"], M["taxa_max"] = pct(100 * min(taxas.values())), pct(100 * max(taxas.values()))
M["parados_vezes"] = pct(taxas["Parados"] / media)
M["parados_dias"] = f"{ag[ag.segmento == 'Parados'].dias_sem_treino.median():.0f}"
M["veteranos_anos"] = pct(ag[ag.segmento == "Veteranos"].tempo_casa_dias.median() / 365.25)
M["parados_3107"] = n((ag.segmento == "Parados").sum())

mensal90 = {s: ag[(ag.segmento == s) & (ag.plano == "mensal") & (ag.tempo_casa_dias <= 90)]
            for s in ATIVOS}
M["ar_livre_mensal90"] = pct(100 * mensal90["Ativos ao ar livre"].saiu_60d.mean())
M["fechado_mensal90"] = pct(100 * mensal90["Ativos em ambiente fechado"].saiu_60d.mean())

# --- listas e cruzamento ---------------------------------------------------------------------
cf = na[na.segmento == "Cobrança falhando"]
M["cobranca_3009"] = n((nb.segmento == "Cobrança falhando").sum())
M["cobranca_taxa"] = pct(100 * cf.saiu_60d.mean())
M["cobranca_continuaram"] = f"{100 * (1 - cf.saiu_60d.mean()):.0f}"
M["cobranca_mensal"] = f"{100 * (cf.plano == 'mensal').mean():.0f}"
M["cobranca_cartao"] = f"{100 * (cf.metodo == 'cartao').mean():.0f}"
M["cobranca_desvios"] = pct((cf.recusas_180d.mean() - na.recusas_180d.mean())
                            / na.recusas_180d.std())
sai = na[na.saiu_60d == 1]
falha = sai.groupby("segmento").motivo_fim_60d.apply(lambda s: (s == "falha_pagamento").mean())
M["cobranca_falha"] = f"{100 * falha['Cobrança falhando']:.0f}"
outros = falha.drop("Cobrança falhando")
M["falha_min"], M["falha_max"] = f"{100 * outros.min():.0f}", f"{100 * outros.max():.0f}"

for c, s in [("ar_livre", "Ativos ao ar livre"), ("fechado", "Ativos em ambiente fechado")]:
    par = j[(j.segmento_l == s) & (j.segmento_n == "Parados")]
    cob = j[(j.segmento_l == s) & (j.segmento_n == "Cobrança falhando")]
    M[f"{c}_parados_n"], M[f"{c}_parados_taxa"] = n(len(par)), pct(100 * par.saiu_60d_l.mean())
    M[f"{c}_cobranca_n"], M[f"{c}_cobranca_taxa"] = n(len(cob)), pct(100 * cob.saiu_60d_l.mean())
recem = j[(j.segmento_l == "Ativos ao ar livre") & (j.segmento_n == "Recém-chegados")]
M["ar_livre_recem"], M["ar_livre_recem_taxa"] = n(len(recem)), pct(100 * recem.saiu_60d_l.mean())
M["cobranca_ar_livre"], M["cobranca_fechado"] = M["ar_livre_cobranca_n"], M["fechado_cobranca_n"]

pn = j[j.segmento_n == "Parados"]
pn_lig = pn[pn.renovacao == "ligada"]
M["n_parados_n"] = n(len(pn))
M["parados_n_jd"] = n((pn.renovacao == "desligada").sum())
M["parados_n_jd_pct"] = f"{100 * (pn.renovacao == 'desligada').mean():.0f}"
M["parados_n_ligada"] = n(len(pn_lig))
M["parados_n_ligada_taxa"] = pct(100 * pn_lig.saiu_60d_l.mean())
M["parados_n_sem_treino"] = f"{100 * (pn.treinos_30d == 0).mean():.0f}"
pn_ativo = pn[pn.segmento_l.isin(ATIVOS)].groupby("segmento_l").saiu_60d_l.mean() * 100
M["parados_n_ativo_min"], M["parados_n_ativo_max"] = pct(pn_ativo.min()), pct(pn_ativo.max())
M["parados_n_concorda"] = n(((j.segmento_l == "Parados") & (j.segmento_n == "Parados")).sum())
M["parados_n"] = n((j.segmento_l == "Parados").sum())
jd_j = j[j.segmento_l == "Já desligou"]
M["jd_em_parados"] = f"{100 * (jd_j.segmento_n == 'Parados').mean():.0f}"
M["jd_anual"] = f"{100 * (jb.plano == 'anual').mean():.0f}"
M["jd_expiraram"] = pct(100 * jd_j.saiu_60d_n.mean())
# religou sozinho: evento `renovacao_automatica_religada` nos 60 dias (01/08–29/09/2026)
ev = ler_prata("eventos_assinatura.csv", ["user_id", "data_hora_brt", "evento"],
               datas=["data_hora_brt"])
rel = ev[(ev.evento == "renovacao_automatica_religada")
         & (ev.data_hora_brt >= "2026-08-01") & (ev.data_hora_brt < "2026-09-30")]
M["jd_religaram"] = pct(100 * rel.user_id.isin(jd.user_id).sum() / len(jd))
M["jd_treino"] = pct(jd[jd.plano == "anual"].treinos_semana.median(), 2)
M["jd_ant_dias"] = f"{sd[(sd.tipo_saida == 'voluntária') & (sd.plano == 'anual')
                        & (sd.data_fim >= '2026-01-01')].antecedencia_dias.median():.0f}"
M["rand_ajustado"] = pct(adjusted_rand_score(base.segmento_l, base.segmento_n), 2)

mn = j[j.segmento_l.isin(ATIVOS) & (j.plano_l == "mensal") & (j.tempo_casa_dias <= 90)]
M["mensais_novos"] = n(len(mn))
M["mensais_novos_recem"] = n((mn.segmento_n == "Recém-chegados").sum())

# --- EDA: churn por tipo e plano (G1 + W1) ---------------------------------------------------
tot = cm[cm.recorte == "total"].set_index("mes")
med = {ano: tot[tot.index.str.startswith(ano)].churn_pct.mean() for ano in ["2025", "2026"]}
M["churn_2025_1c"], M["churn_2026_1c"] = pct(med["2025"]), pct(med["2026"])

sd["mes"] = sd.data_fim.dt.to_period("M").astype(str)
perda = sd[sd.inicio < sd.data_fim.dt.to_period("M").dt.start_time]
TIPOS = ["voluntária", "involuntária", "devolução"]
pt = perda.groupby(["mes", "tipo_saida"]).size().unstack(fill_value=0).reindex(tot.index,
                                                                              fill_value=0)
taxa_tipo = 100 * pt[TIPOS].div(tot.ativos_inicio, axis=0)
tipo_med = {ano: taxa_tipo[taxa_tipo.index.str.startswith(ano)].mean() for ano in ["2025", "2026"]}
M["vol_2025_2c"] = pct(tipo_med["2025"]["voluntária"], 2)
M["vol_2026_2c"] = pct(tipo_med["2026"]["voluntária"], 2)
M["invol_2025_2c"] = pct(tipo_med["2025"]["involuntária"], 2)
M["invol_2026_2c"] = pct(tipo_med["2026"]["involuntária"], 2)
M["vol_pp"] = pct(tipo_med["2026"]["voluntária"] - tipo_med["2025"]["voluntária"], 2)

plano_pp, plano_vol = {}, {}
for plano in ["mensal", "anual"]:
    d = cm[(cm.recorte == "plano") & (cm.segmento == plano)]
    v = {ano: d[d.mes.str.startswith(ano)].churn_pct.mean() for ano in ["2025", "2026"]}
    plano_pp[plano] = v["2026"] - v["2025"]
    pl = d.set_index("mes")
    p = (perda[perda.plano == plano].groupby(["mes", "tipo_saida"]).size()
         .unstack(fill_value=0).reindex(pl.index, fill_value=0))
    tx = 100 * p[TIPOS].div(pl.ativos_inicio, axis=0)
    plano_vol[plano] = {ano: tx[tx.index.str.startswith(ano)]["voluntária"].mean()
                        for ano in ["2025", "2026"]}
M["mensal_pp"], M["anual_pp"] = pct(plano_pp["mensal"], 2), pct(plano_pp["anual"], 2)

vol26 = sd[(sd.tipo_saida == "voluntária") & (sd.data_fim >= "2026-01-01")]
ant = vol26.groupby("plano").antecedencia_dias.median()
M["ant_mensal_dias"], M["ant_anual_dias"] = f"{ant['mensal']:.0f}", f"{ant['anual']:.0f}"
M["ant_anual_meses"] = f"{ant['anual'] / 30.4:.0f}"

men = qs[qs.plano == "mensal"].copy()
men["faixa"] = pd.cut(men.tempo_casa_meses, [-0.1, 3, 6, 12, 24, np.inf],
                      labels=["até 3", "3–6", "6–12", "12–24", "mais de 24"])
t_men = men.groupby("faixa", observed=True).saiu.mean() * 100
M["casa_ate3"], M["casa_24mais"] = pct(t_men.loc["até 3"]), pct(t_men.loc["mais de 24"])

an = qs[(qs.plano == "anual") & (qs.vence_jul_set == 1)]
d = an[["saiu", "dias_treino_abr_jun"]].dropna()
auc = roc_auc_score(d.saiu, d.dias_treino_abr_jun)
lig = an[an.renovacao_30jun == "ligada"][["saiu", "dias_treino_abr_jun"]].dropna()
auc_l = roc_auc_score(lig.saiu, lig.dias_treino_abr_jun)
# O texto diz "quem treina pouco no trimestre antes do anivers\u00e1rio n\u00e3o renova": a dire\u00e7\u00e3o \u00e9
# AUC < 0,5 (menos dias de treino associados a sa\u00edda). max(auc, 1 - auc) s\u00f3 informa o poder de
# discrimina\u00e7\u00e3o; se a dire\u00e7\u00e3o virar, o texto deixa de valer e o gerador para.
if auc >= 0.5 or auc_l >= 0.5:
    sys.exit(f"a dire\u00e7\u00e3o do treino mudou: AUC {auc:.2f} na base do anual que vence e "
             f"{auc_l:.2f} entre quem estava com a renova\u00e7\u00e3o ligada; o texto diz que quem treina "
             f"pouco n\u00e3o renova. Revise a frase da se\u00e7\u00e3o 02, achado 4, e a se\u00e7\u00e3o 05, antes de "
             f"gerar. O relat\u00f3rio N\u00c3O foi escrito.")
M["auc_anual"], M["auc_ligada"] = pct(max(auc, 1 - auc), 2), pct(max(auc_l, 1 - auc_l), 2)

# falha de pagamento por método: involuntárias de jan–set/26 ÷ assinaturas pagas ativas em algum
# dia do período (prata `assinaturas`), por plano × método. O denominador é de período, não o
# estoque de 30/09: quem saiu durante o período também correu o risco de falhar na cobrança.
ass = ler_prata("assinaturas.csv", ["plano_atual", "metodo", "inicio", "data_fim",
                                     "flag_cortesia"], datas=["inicio", "data_fim"])
pago = ass[ass.flag_cortesia == 0]
ativo_periodo = pago[(pago.inicio < "2026-09-30")
                     & (pago.data_fim.isna() | (pago.data_fim >= "2026-01-01"))]
inv = sd[(sd.tipo_saida == "involuntária") & (sd.data_fim >= "2026-01-01")
         & (sd.data_fim <= "2026-09-30")].groupby(["plano", "metodo"]).size()
den = ativo_periodo.groupby(["plano_atual", "metodo"]).size()
den.index = den.index.set_names(["plano", "metodo"])
# A tabela do texto é plano × método. Nem a perda nem o denominador podem sumir: categoria
# ausente de um dos lados viraria divisão por nada, e o recorte com dropna esconderia justamente
# a categoria que falta (o texto continuaria dizendo "outros métodos" sem um deles). Por isso a
# tabela é a união dos dois lados, e o denominador é conferido antes de dividir.
pares = inv.index.union(den.index)
sem_den = den.reindex(pares).fillna(0) == 0
if sem_den.any():
    sys.exit(f"sem denominador para {', '.join(f'{p}/{m}' for p, m in pares[sem_den])}: não há "
             f"assinatura paga ativa em 2026 nesse plano × método em dados/2.prata/assinaturas.csv. "
             f"A taxa de involuntária por 100 assinaturas ativas (seção 02, achado 6, e seção 05) "
             f"sairia de divisão por zero; confira a prata antes de gerar. O relatório NÃO foi "
             f"escrito.")
inv_metodo = 100 * inv.reindex(pares, fill_value=0) / den.reindex(pares)
vazias = [f"{p}/{m}" for (p, m), v in inv_metodo.items() if pd.isna(v)]
if vazias:
    sys.exit(f"a taxa de involuntária por 100 assinaturas ativas ficou vazia em "
             f"{', '.join(vazias)}: o texto cita o cartão do mensal e a faixa dos outros métodos, "
             f"então nenhuma célula pode faltar nem ser escondida. Confira "
             f"dados/2.prata/assinaturas.csv e dados/3.ouro/saidas.csv antes de gerar. O "
             f"relatório NÃO foi escrito.")
inv_metodo = inv_metodo.unstack("metodo")
if "mensal" not in inv_metodo.index:
    sys.exit(f"a prata não tem assinatura paga no plano mensal (planos: "
             f"{', '.join(inv_metodo.index)}): a frase da seção 02, achado 6, compara o cartão com "
             f"os outros métodos do mensal. O relatório NÃO foi escrito.")
mensal_met = inv_metodo.loc["mensal"]
if "cartao" not in mensal_met.index:
    sys.exit(f"a prata não tem o método cartão no mensal (métodos: "
             f"{', '.join(mensal_met.index)}): a seção 02, achado 6, e a célula de cobrança da "
             f"seção 05 falam do cartão, e a frase compara com os outros métodos. O relatório NÃO "
             f"foi escrito.")
outros_met = mensal_met.drop("cartao")
if outros_met.empty:
    sys.exit("o mensal só tem o método cartão: o texto compara o cartão com os outros métodos e "
             "a faixa mínima–máxima não teria de onde sair. Revise a frase da seção 02, achado 6, "
             "antes de gerar. O relatório NÃO foi escrito.")
M["invol_cartao"] = pct(mensal_met["cartao"])
M["invol_outros_min"] = pct(outros_met.min())
M["invol_outros_max"] = pct(outros_met.max())
M["cartao_mensal"] = pct(100 * ag[(ag.plano == "mensal") & (ag.metodo == "cartao")]
                         .saiu_60d.mean())

# --- GPS na população certa: Ativos ao ar livre, mensal, com treino ao ar livre em 31/07 -------
# Quem não treinou ao ar livre fica com pct_gps_falho = 0 e não deveria entrar no "sem falha".
POP_GPS = "Ativos ao ar livre, mensal, com treino ao ar livre em 31/07"
livre_m = ag[(ag.segmento == "Ativos ao ar livre") & (ag.plano == "mensal")
             & (ag.pct_ar_livre > 0)]
# "Com falha" e "sem falha" são recortes de > 0 e == 0: um valor vazio não cai em nenhum dos
# dois e sumiria da comparação da seção 05 sem avisar. Barra antes de recortar.
gps_nulo = livre_m.pct_gps_falho.isna()
if gps_nulo.any():
    sys.exit(f"{n(gps_nulo.sum())} dos {n(len(livre_m))} assinantes de {POP_GPS} estão com "
             f"pct_gps_falho vazio em dados/3.ouro/segmentos.csv. A ressalva da seção 05 compara "
             f"com falha (> 0) com sem falha (== 0), e um valor vazio não entra em nenhum dos "
             f"dois grupos. Rode notebooks/segmentos_ouro.py de novo antes de gerar. O relatório "
             f"NÃO foi escrito.")
com_falha = livre_m[livre_m.pct_gps_falho > 0]
sem_falha = livre_m[livre_m.pct_gps_falho == 0]
if not len(livre_m) or not len(com_falha) or not len(sem_falha):
    sys.exit(f"a base de GPS ({POP_GPS}) ficou com {n(len(livre_m))} assinantes e um dos grupos "
             f"vazio: {n(len(com_falha))} com falha e {n(len(sem_falha))} sem. A narrativa da "
             f"seção 05 não pode ser conferida; revise o texto e a população antes de gerar.")
if len(com_falha) + len(sem_falha) != len(livre_m):
    sys.exit(f"{n(len(livre_m) - len(com_falha) - len(sem_falha))} assinantes de {POP_GPS} ficaram "
             f"fora dos dois grupos de pct_gps_falho: a ressalva da seção 05 perderia esses casos "
             f"em silêncio. Rode notebooks/segmentos_ouro.py de novo antes de gerar. O relatório "
             f"NÃO foi escrito.")
gps_sim = 100 * com_falha.saiu_60d.mean()
gps_nao = 100 * sem_falha.saiu_60d.mean()
# Sentido do trecho contextual: a ressalva da seção 05 diz que o GPS falho NÃO se confirmou como
# driver e imprime "com falha × sem". Se o grupo com falha deixar de sair menos que o sem falha,
# a frase passa a afirmar o contrário do que os números mostram.
if not gps_sim < gps_nao:
    sys.exit(f"no mensal com treino ao ar livre, quem teve GPS falho sai {pct(gps_sim)}% "
             f"({n(len(com_falha))} assinantes) e quem não teve sai {pct(gps_nao)}% "
             f"({n(len(sem_falha))}): o grupo com falha deixou de sair menos. A ressalva da seção "
             f"05 ('GPS falho não se confirmou como driver') e a ordem 'com falha × sem' não valem "
             f"mais; revise a célula de Ativos ao ar livre em "
             f"estudos-analises/customer_segmentation_report.template.html antes de gerar. O "
             f"relatório NÃO foi escrito.")
M["gps_falha"], M["gps_sem"] = pct(gps_sim), pct(gps_nao)

# --- pesquisa de saída (Q7) ------------------------------------------------------------------
ps = ps.sort_values(["user_id", "respondido_em", "resposta_id"]).groupby("user_id").tail(1).copy()
ps["tema"] = ps.comentario.map(lambda c: tema(c)[0] if isinstance(c, str) else None)
ps["tema"] = ps.tema.fillna(pd.Series(np.where(ps.comentario.isna(), "sem comentário", "sem tema"),
                                      index=ps.index))
com_tema = ps[~ps.tema.isin(["sem comentário", "sem tema"])]
M["pesquisa_obj"] = pct(100 * (com_tema.tema == "objetivo_cumprido").mean())
preco = ps[(ps.motivo_principal == "preco") & ps.comentario.notna()]
M["pesquisa_preco_n"] = n(len(preco))
M["pesquisa_preco_dinheiro"] = n((preco.tema == "cobranca").sum())

# --- problemas de GPS na janela de 90 dias (N) -----------------------------------------------
M["prob_3107"], M["prob_3009"] = pct(na.problemas_90d.mean(), 2), pct(nb.problemas_90d.mean(), 2)
M["prob_pct_3107"] = pct(100 * (na.problemas_90d > 0).mean())
M["prob_pct_3009"] = pct(100 * (nb.problemas_90d > 0).mean())

# --- limitações ------------------------------------------------------------------------------
M["teto_dias"] = str((date(2026, 7, 31) - date(2026, 1, 1)).days)
M["zero_ar_sem_treino"] = n(((ag.pct_ar_livre == 0) & (ag.treinos_12s == 0)).sum())
M["zero_ar_so_fechado"] = n(((ag.pct_ar_livre == 0) & (ag.treinos_12s > 0)).sum())
M["loja_saidas"] = pct(100 * (sd[sd.data_fim >= "2026-01-01"].canal == "loja").mean())

# ---------------------------------------------------------------------------------------------
# prioridade pelo critério da seção 06 (não é escolha do notebook)
# ---------------------------------------------------------------------------------------------
maior_volume = max(volumes.values())
acao = {s for s in PERSONAS if taxas[s] >= FATOR_ACAO * media or volumes[s] == maior_volume}

# ---------------------------------------------------------------------------------------------
# blocos repetidos: barras, eixos e a matriz do cruzamento
# ---------------------------------------------------------------------------------------------
def barra(rotulo, valor, aria, larg, classe="", pequeno=None):
    lab = rotulo if pequeno is None else f"{rotulo}<small>{pequeno}</small>"
    return ('<div class="bar-row"><div class="bar-label">' + lab + '</div>'
            + '<div class="bar-track" role="img" aria-label="' + aria + '">'
            + '<div class="bar-fill' + classe + '" style="width:' + larg + '%"></div></div>'
            + '<div class="bar-value">' + valor + "</div></div>")


def eixo(escala, passo, sufixo="%"):
    marcas = [i * passo for i in range(int(round(escala / passo)) + 1)]
    spans = "".join(f"<span>{n(v) if sufixo == '' else f'{v:.0f}{sufixo}'}</span>" for v in marcas)
    return f'<div class="axis" aria-hidden="true">{spans}</div>'


def confere_escala(nome, valores):
    escala, _ = ESCALAS[nome]
    if max(valores) > escala:
        sys.exit(f"gráfico {nome}: o maior valor ({pct(max(valores))}) passou da escala "
                 f"({escala}). Ajuste ESCALAS['{nome}'] em notebooks/relatorio_segmentacao.py "
                 f"e o eixo no template; as barras ficariam cortadas e o texto mentiria.")
    if max(valores) < 0.35 * escala:
        print(f"aviso: gráfico {nome} com valores pequenos para a escala {escala} "
              f"(maior = {pct(max(valores))}); considere reduzir a escala.")


# gráfico 1: churn médio 2025 × jan–set/26
serie_churn = [
    ("Total · 2025", med["2025"], " cinza"),
    ("Total · jan–set/26", med["2026"], ""),
    ("Mensal, voluntária · 2025", plano_vol["mensal"]["2025"], " cinza"),
    ("Mensal, voluntária · jan–set/26", plano_vol["mensal"]["2026"], ""),
    ("Anual, voluntária · 2025", plano_vol["anual"]["2025"], " cinza"),
    ("Anual, voluntária · jan–set/26", plano_vol["anual"]["2026"], ""),
    ("Involuntária (falha de pagamento) · 2025", tipo_med["2025"]["involuntária"], " cinza"),
    ("Involuntária · jan–set/26", tipo_med["2026"]["involuntária"], ""),
]
confere_escala("churn", [v for _, v, _ in serie_churn])
M["barras_churn"] = "\n      ".join(
    barra(rot, pct(v, 2) + "%", f"{pct(v, 2)} por cento",
          largura(round(v, 2), ESCALAS["churn"][0]), cls)
    for rot, v, cls in serie_churn)
M["eixo_churn"] = eixo(*ESCALAS["churn"])

# gráfico 2: decisão de saída em 60 dias por persona
confere_escala("personas", [100 * t for t in taxas.values()])
M["barras_personas"] = "\n      ".join(
    barra(s, pct(100 * taxas[s]) + "%", f"{pct(100 * taxas[s])} por cento",
          largura(round(100 * taxas[s], 1), ESCALAS["personas"][0]),
          " coral" if s in acao else "",
          f"{M[CHAVE[s] + '_3009']} em 30/09 · IC {pct(100 * ics[s][0])}–{pct(100 * ics[s][1])}")
    for s in PERSONAS)
M["eixo_personas"] = eixo(*ESCALAS["personas"])

# gráfico 3: volume esperado de decisões na base de 30/09
ordem_vol = sorted(PERSONAS, key=lambda s: -volumes[s])
confere_escala("volume", list(volumes.values()))
M["barras_volume"] = "\n      ".join(
    barra(s, n(volumes[s]), f"{n(volumes[s])} saídas",
          largura(round(volumes[s]), ESCALAS["volume"][0]),
          " coral" if s in acao else "")
    for s in ordem_vol)
M["eixo_volume"] = eixo(*ESCALAS["volume"], sufixo="")

# matriz do cruzamento L × N (decisão X1)
segmentos_n = set(N.segmento.unique())
if segmentos_n != set(ORDEM_N):
    sys.exit(f"o k-means de 9 variáveis tem segmentos {sorted(segmentos_n)}, e a matriz do "
             f"relatório conhece {ORDEM_N}: atualize ORDEM_N e o cabeçalho da tabela no template")
ct = pd.crosstab(j.segmento_l, j.segmento_n).reindex(index=PERSONAS + ["Já desligou"],
                                                     columns=ORDEM_N, fill_value=0)
taxa_cel = base.groupby(["segmento_l", "segmento_n"]).saiu_60d_l.mean()
linhas = []
for seg in PERSONAS + ["Já desligou"]:
    total = int(ct.loc[seg].sum())
    maior = ct.loc[seg].idxmax()
    segundo = ct.loc[seg].drop(maior).idxmax()
    rotulo = f"<strong>{seg}</strong>" + (" (lista)" if seg == "Já desligou" else "")
    celulas = []
    for col in ORDEM_N:
        v = int(ct.loc[seg, col])
        classe = "num"
        if col == maior:
            classe = "num forte"
        elif seg in PERSONAS and col == segundo and v >= 0.10 * total:
            classe = "num medio"
        txt = n(v)
        if seg in PERSONAS and v >= 10:
            txt += f" ({pct(100 * taxa_cel.loc[(seg, col)])}%)"
        celulas.append(f'<td class="{classe}">{txt}</td>')
    linhas.append(f"<tr><td>{rotulo}</td>" + "".join(celulas)
                  + f'<td class="num">{n(total)}</td></tr>')
col_tot = "".join(f'<td class="num">{n(int(ct[c].sum()))}</td>' for c in ORDEM_N)
linhas.append(f'<tr><td><strong>Total</strong></td>{col_tot}'
              f'<td class="num">{n(int(ct.to_numpy().sum()))}</td></tr>')
M["matriz_conciliacao"] = ("<tbody>\n" + "\n".join("            " + l for l in linhas)
                           + "\n          </tbody>")

# ---------------------------------------------------------------------------------------------
# conclusões qualitativas do texto: se deixarem de valer, o gerador para
# ---------------------------------------------------------------------------------------------
CONCLUSAO = [
    ("o churn mensal subiu de 2025 para jan–set/26 (resumo executivo, seção 01)",
     med["2026"] > med["2025"]),
    ("a alta é voluntária (seção 02, achado 1)", tipo_med["2026"]["voluntária"] > tipo_med["2025"]["voluntária"]),
    ("a involuntária está estável (seção 02, achado 1)",
     abs(tipo_med["2026"]["involuntária"] - tipo_med["2025"]["involuntária"]) < 0.15),
    ("a alta se concentra no mensal (seção 02, achado 1)", plano_pp["mensal"] > plano_pp["anual"]),
    ("quem sai avisa antes, e o anual avisa com mais antecedência (seção 02, achado 2)",
     ant["anual"] > ant["mensal"]),
    ("no mensal pesa o tempo de casa: até 3 meses sai mais que acima de 24 (seção 02, achado 3)",
     t_men.loc["até 3"] > t_men.loc["mais de 24"]),
    ("o treino no anual que vence discrimina a saída (AUC ≥ 0,70, seção 02, achado 4)",
     max(auc, 1 - auc) >= 0.70),
    ("'objetivo cumprido' é o tema dominante da pesquisa (seção 02, achado 5)",
     (com_tema.tema == "objetivo_cumprido").mean() > 0.4),
    ("o GPS falho não se confirmou como driver: com falha sai menos que sem, no mensal com "
     "treino ao ar livre (seção 05, tabela)",
     gps_sim < gps_nao),
    ("a falha de cobrança mora no cartão: no mensal, o cartão tem a maior taxa de involuntária "
     "por 100 assinaturas ativas no período (seção 02, achado 6)",
     mensal_met["cartao"] == mensal_met.max()),
    ("Parados tem a maior taxa de decisão de saída (cartão e seção 06)",
     taxas["Parados"] == max(taxas.values())),
    ("Veteranos tem a menor taxa de decisão de saída (resumo: 'de Veteranos a Parados')",
     taxas["Veteranos"] == min(taxas.values())),
    ("Parados é o menor grupo e Ativos ao ar livre o maior (resumo, seção 03)",
     len(ag[ag.segmento == "Parados"]) == min(len(ag[ag.segmento == s]) for s in PERSONAS)
     and len(ag[ag.segmento == "Ativos ao ar livre"]) == max(len(ag[ag.segmento == s])
                                                             for s in PERSONAS)),
    ("Ativos ao ar livre concentra o maior volume esperado de saídas (resumo, seção 06)",
     volumes["Ativos ao ar livre"] == maior_volume),
    ("a prioridade calculada pelo critério da seção 06 é a mesma dos cartões do template",
     acao == {"Parados", "Ativos ao ar livre"}),
    ("Parados paga o anual (cartão: 'Paga o anual e não treina')",
     (ag[ag.segmento == "Parados"].plano == "anual").mean() > 0.95),
    ("Parados não treina (cartão: '0 treino por semana')",
     ag[ag.segmento == "Parados"].treinos_semana.median() == 0),
    ("Veteranos fica abaixo da metade da média (cartão: 'Menos da metade da média')",
     taxas["Veteranos"] < media / 2),
    (f"Parados fica acima do limiar de ação imediata ({M['fator_acao']} × média)",
     taxas["Parados"] >= FATOR_ACAO * media),
    ("a régua do fim da assinatura é menor que a da decisão na mesma base (seção 04)",
     taxa_fim < taxa_dec),
    ("as duas segmentações cortam eixos diferentes: Rand ajustado < 0,20 (seção 04)",
     adjusted_rand_score(base.segmento_l, base.segmento_n) < 0.20),
    ("os 'Parados' de nove variáveis misturam dois públicos: maioria já desligou (seção 04)",
     (pn.renovacao == "desligada").mean() > 0.5),
    ("'Recém-chegados' é o mensal novo: maioria dos mensais com até 90 dias (seção 04)",
     (mn.segmento_n == "Recém-chegados").mean() > 0.5),
    ("a variável de problemas cai entre 31/07 e 30/09 (seção 04: 'muda de conteúdo')",
     nb.problemas_90d.mean() < na.problemas_90d.mean()),
    ("Cobrança falhando tem a maior fatia de saída por falha de pagamento (seção 03)",
     falha["Cobrança falhando"] == falha.max()),
    ("Já desligou é majoritariamente anual (cartão: '93% anual')",
     (jb.plano == "anual").mean() > 0.5),
    ("os 'Já desligou' se concentram no grupo Parados do outro k-means (cartão: '68%')",
     (j[j.segmento_l == "Já desligou"].segmento_n == "Parados").mean() > 0.5),
]
falhas = [f"  - {txt}" for txt, ok in CONCLUSAO if not ok]
if falhas:
    sys.exit("o ouro não sustenta mais estas conclusões do template:\n" + "\n".join(falhas)
             + "\n\nRevise a frase correspondente em "
               "estudos-analises/customer_segmentation_report.template.html (e a decisão no "
               "decisoes.md) antes de gerar de novo. O relatório NÃO foi escrito.")

# ---------------------------------------------------------------------------------------------
# render
# ---------------------------------------------------------------------------------------------
tpl = TEMPLATE.read_text()
chaves = set(re.findall(r"\{\{(\w+)\}\}", tpl))
if chaves - set(M):
    sys.exit(f"o template usa placeholders sem métrica: {sorted(chaves - set(M))}. "
             f"Ou o texto é novo (acrescente o cálculo em notebooks/relatorio_segmentacao.py) "
             f"ou o nome saiu errado.")
saida = re.sub(r"\{\{(\w+)\}\}", lambda m: str(M[m.group(1)]), tpl)
sobra = re.findall(r"\{\{[^}]*\}\}", saida)
if sobra:
    sys.exit(f"placeholders não substituídos: {sobra}")
SAIDA.write_text(saida)

# ---------------------------------------------------------------------------------------------
# relatório da execução
# ---------------------------------------------------------------------------------------------
usadas = set(re.findall(r"\{\{(\w+)\}\}", tpl))
print(f"{SAIDA.relative_to(RAIZ)}: {len(saida) / 1024:.1f} KB · {len(usadas)} placeholders "
      f"preenchidos · {len(CONCLUSAO)} conclusões conferidas")
print(f"base {REF}: {n(len(a))} pagantes · {n(len(ag))} com renovação ligada · "
      f"{n(len(jd))} já desligados · decisão {pct(100 * media)}% · fim {pct(100 * taxa_fim)}%")
print(f"prioridade pelo critério ({M['fator_acao']} × média ou maior volume): "
      + ", ".join(sorted(acao)))
if set(M) - usadas:
    print("aviso: métricas calculadas e não usadas no template: " + ", ".join(sorted(set(M) - usadas)))
print(f"qualidade: silhueta {M['silhueta_l']} (4 variáveis, k = {SL['k']}, n = {n(SL['n'])}) · "
      f"{M['silhueta_n']} (9 variáveis, amostra {n(SN['amostra'])}) · Rand médio em "
      f"{REAMOSTRAS} reamostras {M['rand_reamostras']} (mínimo {br(SL['rand_minimo'], 3)}, "
      f"outra semente {br(SL['rand_outra_semente'], 3)})")
print(f"GPS ({POP_GPS}): {M['gps_falha']}% com falha × {M['gps_sem']}% sem "
      f"({n(len(livre_m))} assinantes)")
print("falha de pagamento por 100 assinaturas ativas no período: mensal cartão "
      f"{M['invol_cartao']} · outros métodos {M['invol_outros_min']}–{M['invol_outros_max']}")
print(f"fim da assinatura na mesma base: {M['fim_contagem']} · interseção com a decisão: "
      f"{M['fim_intersecao']}")
