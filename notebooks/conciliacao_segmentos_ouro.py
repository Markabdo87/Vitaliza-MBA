"""Ouro -> ouro: conciliacao_segmentos.csv (segmento L × segmento K × data de referência).

Cruza, assinante por assinante, as duas segmentações k-means do grupo para o Customer
Segmentation Report:

  - L (Douglas, `segmentos.csv`, notebook `segmentos_ouro.py`, decisões L1–L8): pagantes com
    a renovação ligada, quatro variáveis da aula (treinos/semana, dias sem treino, tempo de
    casa, % ao ar livre); quem já desligou a renovação vira o grupo à parte "Já desligou".
    Saída em 60 dias = decisão de sair (desligou, cancelou ou expirou de 01/08 a 29/09).
  - K (`segmentos_kmeans.csv`, notebook `segmentos_kmeans_ouro.py`, decisões K1–K7 do ramo
    main): todos os pagantes ativos, nove variáveis de comportamento, cobrança e tempo de
    casa. Saída em 60 dias = assinatura terminada (`data_fim`) de 01/08 a 29/09.

Regras (decisão R1 no decisoes.md):
  1. As duas tabelas têm de cobrir os mesmos `user_id` em cada data de referência (31/07 e
     30/09/2026); o notebook para se não cobrirem.
  2. Uma linha por par (segmento L, segmento K, data): assinantes e, em 31/07, a saída em 60
     dias pelas duas definições (`saida_decisao_pct` de L, `saida_fim_pct` de K).
  3. Índice de Rand ajustado entre as duas partições em 31/07, sem o grupo "Já desligou"
     (que não é agrupamento, é regra de entrada).
  4. Nada é recalculado: só se cruzam as colunas já gravadas pelos dois notebooks.

Pré-requisito: rodar antes `notebooks/segmentos_kmeans_ouro.py` e `notebooks/segmentos_ouro.py`
(este último está no ramo `feat/eda-etapa-02` até ser integrado ao main).

Uso: .venv/bin/python notebooks/conciliacao_segmentos_ouro.py  (a partir da raiz do repo)
"""
import sys

import pandas as pd
pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 20)
from sklearn.metrics import adjusted_rand_score

from _ouro import OURO, RAIZ

SAIDA = OURO / "conciliacao_segmentos.csv"
REF_TREINO = "2026-07-31"
ORDEM_L = ["Parados", "Ativos ao ar livre", "Ativos em ambiente fechado", "Veteranos", "Já desligou"]
ORDEM_K = ["Engajados", "Recém-chegados", "Parados", "Cobrança falhando"]


def ler_ouro(arquivo, notebook, colunas):
    caminho = OURO / arquivo
    if not caminho.exists():
        sys.exit(f"falta {caminho.relative_to(RAIZ)}: rode .venv/bin/python notebooks/{notebook}")
    df = pd.read_csv(caminho)
    faltam = [c for c in colunas if c not in df.columns]
    if faltam:
        sys.exit(f"{arquivo} não tem as colunas {faltam}: rode notebooks/{notebook} de novo")
    return df[colunas]


L = ler_ouro("segmentos.csv", "segmentos_ouro.py",
             ["data_ref", "user_id", "segmento", "saiu_60d", "renovacao", "plano", "tempo_casa_dias"])
K = ler_ouro("segmentos_kmeans.csv", "segmentos_kmeans_ouro.py",
             ["data_ref", "user_id", "segmento", "saiu_60d", "metodo"])

j = L.merge(K, on=["data_ref", "user_id"], how="outer", suffixes=("_l", "_k"), indicator=True)
sobra = j[j._merge != "both"]
if len(sobra):
    sys.exit(f"as duas tabelas não cobrem os mesmos assinantes: {sobra._merge.value_counts().to_dict()}")

tab = (j.groupby(["data_ref", "segmento_l", "segmento_k"])
         .agg(assinantes=("user_id", "size"),
              saida_decisao_pct=("saiu_60d_l", "mean"),
              saida_fim_pct=("saiu_60d_k", "mean"))
         .reset_index())
for c in ["saida_decisao_pct", "saida_fim_pct"]:
    tab[c] = (100 * tab[c]).round(1)
OURO.mkdir(parents=True, exist_ok=True)
tab.to_csv(SAIDA, index=False)

# --- leitura -----------------------------------------------------------------------------
t = j[j.data_ref == REF_TREINO]
ag = t[t.segmento_l != "Já desligou"]
print(f"{REF_TREINO}: {len(t)} assinantes nas duas tabelas")
print(f"Rand ajustado (sem 'Já desligou'): {adjusted_rand_score(ag.segmento_l, ag.segmento_k):.3f}")
for ref in sorted(j.data_ref.unique()):
    print(f"\nassinantes, {ref} (linhas = L, colunas = K)")
    print(pd.crosstab(j[j.data_ref == ref].segmento_l, j[j.data_ref == ref].segmento_k,
                      margins=True).reindex(index=ORDEM_L + ["All"], columns=ORDEM_K + ["All"]))
print("\nsaída em 60 dias, % (decisão, definição L)")
print(pd.crosstab(t.segmento_l, t.segmento_k, values=t.saiu_60d_l, aggfunc="mean")
        .reindex(index=ORDEM_L, columns=ORDEM_K).mul(100).round(1))
print("\nsaída em 60 dias, % (fim da assinatura, definição K)")
print(pd.crosstab(t.segmento_l, t.segmento_k, values=t.saiu_60d_k, aggfunc="mean")
        .reindex(index=ORDEM_L, columns=ORDEM_K).mul(100).round(1))
print("\nsegmento K por situação da renovação em 31/07 (%)")
print(pd.crosstab(t.segmento_k, t.renovacao, normalize="index").reindex(ORDEM_K).mul(100).round(1))
print("\nsaída por definição: decisão × fim")
print(pd.crosstab(t.saiu_60d_l, t.saiu_60d_k, margins=True))
ativos = t[t.segmento_l.isin(ORDEM_L[1:3]) & (t.plano == "mensal")]
print("\nmensais ativos (L) por tempo de casa ≤ 90 dias × segmento K")
print(pd.crosstab(ativos.tempo_casa_dias <= 90, ativos.segmento_k, margins=True))
print("\nCobrança falhando (K) por método e por segmento L")
cf = t[t.segmento_k == "Cobrança falhando"]
print(cf.metodo.value_counts().to_dict(), cf.segmento_l.value_counts().to_dict())
print(f"\n{SAIDA.relative_to(RAIZ)}: {len(tab)} linhas")
