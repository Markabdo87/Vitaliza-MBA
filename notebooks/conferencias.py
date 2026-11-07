"""Conferências da prata e do ouro: roda tudo de uma vez e falha se algum número quebrar.

Não gera tabela. Rode depois de mexer em qualquer notebook, com a prata (e o ouro) já
gerados:

    .venv/bin/python notebooks/conferencias.py   (a partir da raiz do repo)

O que confere:
  1. Contagem de linhas de cada tabela da prata (tabela "Visão geral da prata" do
     decisoes.md) e da bronze (dicionário de dados).
  2. Números de referência: faturamento de set/2026 (R$ 489.873,50 bruto e R$ 434.056,93
     líquido, somando a prata sem filtro, P12); 14.753 assinantes pagantes ativos em
     30/09/2026 (enunciado); 717 expirações em set/26 e 3.389 em jun–set/26 (E1).
  3. Cruzamentos entre tabelas:
     - todo user_id de todas as tabelas existe em usuarios da prata (U1 não deixou órfão);
     - onboarding cobre exatamente as contas da prata menos as de teste (U13);
     - toda cobrança aprovada tem um assinatura_iniciada/renovacao no mesmo dia, e vice-versa;
     - nenhuma cobrança antes do início ou depois do fim da assinatura;
     - só os preços do enunciado nas cobranças aprovadas (34,90 · 39,90 · 299,90 · 239,90);
     - recusados com valor e valor_liquido zero (P12);
     - assinatura_iniciada e assinatura_expirada batem com inicio/data_fim de assinaturas.
  4. Ouro, se já gerado: churn médio 5,6% (2025) e 6,6% (jan–set/26) do enunciado;
     recusas_cobranca com 3.250 recusas e 1.321 perdidas = assinaturas com falha_pagamento.

Sai com código 1 se qualquer conferência falhar.
"""
import sys
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

RAIZ = Path(__file__).resolve().parent.parent
BRONZE, PRATA, OURO = (RAIZ / "dados" / d for d in ("1.bronze", "2.prata", "3.ouro"))

falhas = []


def confere(nome, esperado, obtido):
    ok = esperado == obtido
    print(f"{'OK    ' if ok else 'FALHOU'} {nome}: esperado {esperado}, obtido {obtido}")
    if not ok:
        falhas.append(nome)


def ler(nome, **kw):
    if nome.endswith(".parquet"):
        return pd.read_parquet(PRATA / nome, **kw)
    return pd.read_csv(PRATA / nome, low_memory=False, **kw)


def linhas_csv(caminho):
    return len(pd.read_csv(caminho, usecols=[0], low_memory=False))


# --- 1. contagens -------------------------------------------------------------------------
print("\n1. Contagem de linhas (bronze = dicionário · prata = decisoes.md)")
CONTAGENS = {  # arquivo: (bronze, prata)
    "usuarios.csv": (64948, 63989), "assinaturas.csv": (32643, 32643),
    "eventos_assinatura.csv": (275565, 275565), "pagamentos.csv": (165548, 163607),
    "uso_mensal.csv": (591662, 591662), "atividades.parquet": (1254475, 1252575),
    "amizades.csv": (113480, 113480), "campanha_ago26.csv": (14120, 14120),
    "onboarding.csv": (63929, 63929), "feed_posts.csv": (119309, 119309),
    "pesquisa_saida.csv": (643, 643), "tickets_suporte.csv": (4422, 4422),
}
for arq, (nb, np_) in CONTAGENS.items():
    if arq.endswith(".parquet"):
        b, p = pq.read_metadata(BRONZE / arq).num_rows, pq.read_metadata(PRATA / arq).num_rows
    else:
        b, p = linhas_csv(BRONZE / arq), linhas_csv(PRATA / arq)
    confere(f"{arq} bronze", nb, b)
    confere(f"{arq} prata", np_, p)

# --- 2. números de referência -------------------------------------------------------------
print("\n2. Números de referência")
pag = ler("pagamentos.csv", parse_dates=["data_hora_brt"])
ass = ler("assinaturas.csv", parse_dates=["inicio", "data_fim"])
ev = ler("eventos_assinatura.csv", parse_dates=["data_hora_brt"])
usu = ler("usuarios.csv")

s9 = pag[pag.mes == "2026-09"]
confere("faturamento bruto set/26 (sem filtro de status)", 489873.50, round(s9.valor.sum(), 2))
confere("faturamento líquido set/26 (sem filtro de status)", 434056.93,
        round(s9.valor_liquido.sum(), 2))
confere("assinantes pagantes ativos em 30/09/2026", 14753,
        int(((ass.status_atual == "ativa") & (ass.flag_cortesia == 0)).sum()))
exp = ev[ev.evento == "assinatura_expirada"]
confere("assinatura_expirada set/26", 717, int((exp.mes == "2026-09").sum()))
confere("assinatura_expirada jun–set/26", 3389,
        int(exp.mes.between("2026-06", "2026-09").sum()))

# --- 3. cruzamentos -----------------------------------------------------------------------
print("\n3. Cruzamentos entre tabelas")
ids = set(usu.user_id)
for arq in ["assinaturas.csv", "eventos_assinatura.csv", "pagamentos.csv", "uso_mensal.csv",
            "campanha_ago26.csv", "onboarding.csv", "feed_posts.csv", "pesquisa_saida.csv",
            "tickets_suporte.csv"]:
    u = ler(arq, usecols=["user_id"]).user_id
    confere(f"{arq}: user_id fora de usuarios", 0, int((~u.isin(ids)).sum()))
u = pd.read_parquet(PRATA / "atividades.parquet", columns=["user_id"]).user_id
confere("atividades.parquet: user_id fora de usuarios", 0, int((~u.isin(ids)).sum()))
am = ler("amizades.csv", usecols=["seguidor_id", "seguido_id", "flag_id_invalido"])
am = am[am.flag_id_invalido == 0]
confere("amizades.csv: ids fora de usuarios", 0,
        int((~am.seguidor_id.isin(ids)).sum() + (~am.seguido_id.isin(ids)).sum()))

onb = set(ler("onboarding.csv", usecols=["user_id"]).user_id)
confere("onboarding = usuarios menos contas de teste", True,
        onb == set(usu.loc[usu.flag_conta_teste == 0, "user_id"]))

ap = pag[pag.status == "aprovado"]
ini = ev[ev.evento.isin(["assinatura_iniciada", "renovacao"])]
chave = lambda d: d.user_id + "|" + d.data_hora_brt.dt.strftime("%Y-%m-%d")
ca, ce = chave(ap).value_counts(), chave(ini).value_counts()
confere("cobranças aprovadas sem início/renovação no mesmo dia (e vice-versa)", 0,
        int(ca.sub(ce, fill_value=0).abs().sum()))

m = pag.merge(ass[["user_id", "inicio", "data_fim"]], on="user_id", how="left")
dia = m.data_hora_brt.dt.normalize()
confere("cobranças antes do início da assinatura", 0, int((dia < m.inicio).sum()))
confere("cobranças depois do fim da assinatura", 0, int((dia > m.data_fim).sum()))

confere("preços das cobranças aprovadas", [34.9, 39.9, 239.9, 299.9],
        sorted(ap.valor.round(2).unique().tolist()))
rec = pag[pag.status == "recusado"]
confere("recusados com valor ou valor_liquido diferente de zero (P12)", 0,
        int(((rec.valor != 0) | (rec.valor_liquido != 0)).sum()))
confere("valor tentado nos recusados (valor_bronze)", 191935.00, round(rec.valor_bronze.sum(), 2))

d_ini = ev[ev.evento == "assinatura_iniciada"].set_index("user_id").data_hora_brt.dt.normalize()
a = ass.set_index("user_id")
confere("assinatura_iniciada ≠ assinaturas.inicio", 0, int((d_ini != a.inicio.reindex(d_ini.index)).sum()))
d_fim = exp.set_index("user_id").data_hora_brt.dt.normalize()
confere("assinatura_expirada ≠ assinaturas.data_fim", 0, int((d_fim != a.data_fim.reindex(d_fim.index)).sum()))

# --- 4. ouro ------------------------------------------------------------------------------
print("\n4. Ouro (se já gerado)")
arq = OURO / "churn_mensal.csv"
if arq.exists():
    t = pd.read_csv(arq).query("recorte == 'total'")
    confere("churn médio 2025 (%)", 5.6, round(t[t.mes.str.startswith("2025")].churn_pct.mean(), 1))
    confere("churn médio jan–set/26 (%)", 6.6, round(t[t.mes.str.startswith("2026")].churn_pct.mean(), 1))
else:
    print("-      churn_mensal.csv não gerado: rode notebooks/churn_mensal_ouro.py")
arq = OURO / "recusas_cobranca.csv"
if arq.exists():
    r = pd.read_csv(arq)
    confere("recusas_cobranca: linhas", 3250, len(r))
    confere("recusas_cobranca: perdidas = assinaturas com falha_pagamento",
            int((ass.motivo_fim == "falha_pagamento").sum()), int((r.desfecho == "perdida").sum()))
else:
    print("-      recusas_cobranca.csv não gerado: rode notebooks/recusas_cobranca_ouro.py")

print(f"\n{'Tudo certo.' if not falhas else f'{len(falhas)} conferência(s) falharam: {falhas}'}")
sys.exit(1 if falhas else 0)
