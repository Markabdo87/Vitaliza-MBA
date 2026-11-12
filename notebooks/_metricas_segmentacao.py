"""Qualidade das duas segmentações: silhueta e estabilidade em reamostras.

Uma implementação só, usada pelos dois notebooks de ouro e pelo relatório de segmentação, para
o número que o relatório publica ser exatamente o que o ouro calculou — e não uma cópia que
envelhece sozinha.

A regra é a dos notebooks (L5 no de 4 variáveis, N5 no de 9):

  - matriz de variáveis padronizada (z-score); nas variáveis de contagem do k-means de 9,
    `log1p` antes de padronizar (N2);
  - k-means com `n_init` e `random_state` declarados (`SEMENTE_L`/`SEMENTE_N`);
  - silhueta média: na base inteira no k-means de 4 variáveis (11,7 mil linhas) e numa amostra
    sem reposição de 5.000 no de 9 (N5);
  - estabilidade: `REAMOSTRAS` amostras com reposição, k-means reajustado em cada uma e a base
    inteira reclassificada; índice de Rand ajustado contra o agrupamento original. O número
    publicado é a **média** (o mínimo e outra semente inicial saem no relatório da execução).

`metricas_l`/`metricas_n` recebem a base já montada (as mesmas linhas que o notebook agrupou) e
devolvem a métrica com o vetor de rótulos: quem chama confere o Rand ajustado contra a coluna
`segmento` da tabela de ouro. Rand = 1 quer dizer que a partição recalculada é a publicada; se
não for, a regra aqui divergiu do notebook e a métrica não vale para aquele agrupamento.

Uso:
    from _metricas_segmentacao import metricas_l, metricas_n
    SL, SN = metricas_l(ag), metricas_n(na)
"""
import sys

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.preprocessing import StandardScaler

# Variáveis de cada agrupamento (as mesmas dos notebooks de ouro: L1 e N2).
VARS_L = ("treinos_semana", "dias_sem_treino", "tempo_casa_dias", "pct_ar_livre")
VARS_N = ("treinos_30d", "tendencia_treino", "dias_sem_treino", "sessoes_app", "conexoes",
          "posts_90d", "problemas_90d", "recusas_180d", "meses_assinatura")
# Variáveis que entram no k-means de 9 em log1p (`log=True` em segmentos_kmeans_ouro.py).
LOG_N = ("treinos_30d", "sessoes_app", "conexoes", "posts_90d", "problemas_90d",
         "recusas_180d", "meses_assinatura")

K = 4                          # k escolhido pelos dois notebooks (L5, N5)
SEMENTE_L, N_INIT_L = 0, 10    # segmentos_ouro.py
SEMENTE_N, N_INIT_N = 7, 20    # segmentos_kmeans_ouro.py
REAMOSTRAS = 10                # reamostras com reposição da estabilidade (L5)
AMOSTRA_SIL = 5000             # amostra sem reposição da silhueta de 9 variáveis (N5)

# Limiares que o texto usa como adjetivo: "estrutura fraca" (abaixo da faixa de 0,50) e
# "estável em reamostras" (Rand mínimo ≥ 0,90 no notebook, média ≥ 0,90 no relatório).
LIMIAR_FRACA, LIMIAR_RAND = 0.50, 0.9


def _colunas(df, cols, origem):
    faltam = [c for c in cols if c not in df.columns]
    if faltam:
        sys.exit(f"{origem} não tem as colunas {faltam}: a base do k-means mudou de formato "
                 f"(VARS em notebooks/_metricas_segmentacao.py)")
    return df[list(cols)].astype(float)


def matriz_l(base, origem="a base do k-means de 4 variáveis"):
    """Matriz padronizada das 4 variáveis do agrupamento L (mesma regra de L1)."""
    return StandardScaler().fit_transform(_colunas(base, VARS_L, origem))


def matriz_n(base, origem="a base do k-means de 9 variáveis"):
    """Matriz padronizada das 9 variáveis do agrupamento N: log1p nas contagens, depois z-score."""
    x = _colunas(base, VARS_N, origem).copy()
    log = list(LOG_N)
    x[log] = np.log1p(x[log].clip(lower=0))
    mu, sd = x.mean(), x.std().replace(0, 1)   # variável constante não divide por zero
    return ((x - mu) / sd).values


def agrupa(X, k=K, semente=SEMENTE_L, n_init=N_INIT_L):
    """k-means ajustado na matriz `X`, com os parâmetros da regra declarados."""
    if len(X) < k:
        sys.exit(f"base com {len(X)} linhas não sustenta k = {k}")
    return KMeans(k, n_init=n_init, random_state=semente).fit(X)


def silhueta(X, rotulos, amostra=None):
    """Silhueta média dos rótulos; com `amostra` (índices), só nas linhas amostradas (N5)."""
    rotulos = np.asarray(rotulos)
    if amostra is not None:
        X, rotulos = X[amostra], rotulos[amostra]
    if len(np.unique(rotulos)) < 2:
        sys.exit("agrupamento com um grupo só: silhueta indefinida")
    return silhouette_score(X, rotulos)


def indices_reamostras(n, semente=SEMENTE_L, reamostras=REAMOSTRAS):
    """Índices das reamostras com reposição (mesmo gerador e ordem do notebook: L5)."""
    rng = np.random.default_rng(semente)
    return [rng.integers(0, n, n) for _ in range(reamostras)]


def estabilidade(X, rotulos, amostras, k=K, semente=SEMENTE_L, n_init=N_INIT_L):
    """Rand ajustado nas reamostras: média e mínimo; mais o agrupamento com outra semente."""
    aris = [adjusted_rand_score(rotulos, agrupa(X[i], k, semente, n_init).predict(X))
            for i in amostras]
    outra = adjusted_rand_score(rotulos, agrupa(X, k, 1, n_init).labels_)
    return {"medio": float(np.mean(aris)), "minimo": float(np.min(aris)), "outra": outra}


def estabilidade_por_k(X, ks, semente=SEMENTE_L, n_init=N_INIT_L, reamostras=REAMOSTRAS):
    """Tabela de estabilidade por k (a mesma do notebook de 4 variáveis: L5)."""
    amostras = indices_reamostras(len(X), semente, reamostras)
    linhas = []
    for k in ks:
        est = estabilidade(X, agrupa(X, k, semente, n_init).labels_, amostras, k, semente, n_init)
        linhas.append({"k": k, "Rand médio": est["medio"], "Rand mínimo": est["minimo"],
                       "outra semente": est["outra"]})
    return pd.DataFrame(linhas)


def metricas_l(base):
    """Silhueta e estabilidade do agrupamento de 4 variáveis, com os rótulos recalculados."""
    X = matriz_l(base)
    km = agrupa(X)
    est = estabilidade(X, km.labels_, indices_reamostras(len(X)))
    return {"silhueta": silhueta(X, km.labels_), "rand_medio": est["medio"],
            "rand_minimo": est["minimo"], "rand_outra_semente": est["outra"],
            "n": len(X), "k": K, "rotulos": km.labels_}


def metricas_n(base):
    """Silhueta do agrupamento de 9 variáveis (amostra de 5.000) e os rótulos recalculados."""
    Z = matriz_n(base)
    rng = np.random.default_rng(SEMENTE_N)
    amostra = rng.choice(len(Z), size=min(AMOSTRA_SIL, len(Z)), replace=False)
    km = agrupa(Z, K, SEMENTE_N, N_INIT_N)
    return {"silhueta": silhueta(Z, km.labels_, amostra), "n": len(Z), "k": K,
            "amostra": len(amostra), "rotulos": km.labels_}
