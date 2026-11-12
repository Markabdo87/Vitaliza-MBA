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
  9. Números de outras etapas citados na página não são fixos, e sim refeitos com a regra e a
     população da etapa de origem: AUC univariada da etapa 02 (K4), guardando o valor bruto e o
     sentido; antecedência do aviso (W4) e tema da pesquisa de saída (W5) da etapa 03, esta
     sobre a pesquisa inteira (a última resposta de cada conta), não só sobre quem já expirou;
     comparação de GPS nos recortes declarados (`gps`), que para se um dos lados ficar vazio.

Uso: .venv/bin/python notebooks/segmentos_ouro.py  (a partir da raiz do repo)
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from sklearn.metrics import adjusted_rand_score, roc_auc_score
from sklearn.preprocessing import StandardScaler

from _artefato import CORES, GRADE, Pagina, layout_padrao
from _metricas_segmentacao import (K as K_GRUPOS, LIMIAR_RAND, N_INIT_L, SEMENTE_L, VARS_L,
                                   agrupa, estabilidade_por_k, silhueta)
from pesquisa_saida_prata import tema

RAIZ = Path(__file__).resolve().parent.parent
PRATA = RAIZ / "dados" / "2.prata"
OURO = RAIZ / "dados" / "3.ouro"
SAIDA = OURO / "segmentos.csv"


def le_ouro(arquivo, colunas, datas=()):
    """Lê outra tabela do ouro só com as colunas usadas, com mensagem clara se ela faltar."""
    caminho = OURO / arquivo
    if not caminho.exists():
        sys.exit(f"falta {caminho.relative_to(RAIZ)}: rode .venv/bin/python "
                 f"notebooks/{Path(arquivo).stem}_ouro.py antes deste")
    existentes = pd.read_csv(caminho, nrows=0).columns.tolist()
    faltam = [c for c in colunas if c not in existentes]
    if faltam:
        sys.exit(f"{caminho.relative_to(RAIZ)} não tem as colunas {faltam}; ajuste o notebook "
                 f"que gera essa tabela ou este")
    return pd.read_csv(caminho, usecols=list(colunas), parse_dates=list(datas))

VARS = list(VARS_L)          # as 4 variáveis e a métrica de qualidade vivem no helper comum
EXTRAS = {"pct_gps_falho": "% de treinos ao ar livre com GPS falho",
          "km_treino": "km por treino ao ar livre", "conexoes": "conexões recíprocas"}
AR_LIVRE = ["corrida", "caminhada", "pedal"]
INICIO_ARQUIVO = pd.Timestamp("2026-01-01")
SEMENTE, N_INIT, K_FAIXA, K = SEMENTE_L, N_INIT_L, range(2, 9), K_GRUPOS
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
    desde = b.inicio.clip(lower=INICIO_ARQUIVO)
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
# Silhueta e estabilidade em reamostras pela implementação comum (`_metricas_segmentacao`), a
# mesma que o relatório de segmentação usa: um só código, nenhum número copiado.
curvas = pd.DataFrame([{"k": k, "inércia": m.inertia_, "silhueta": silhueta(X, m.labels_)}
                       for k, m in ((k, agrupa(X, k, SEMENTE, N_INIT)) for k in K_FAIXA)])
estab = estabilidade_por_k(X, range(3, 7), SEMENTE, N_INIT)
print(curvas.round(3).to_string(index=False)); print(estab.round(3).to_string(index=False))

km = agrupa(X)
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
ROT = {"Parados": "parados", "Ativos ao ar livre": "ao ar livre",
       "Ativos em ambiente fechado": "em ambiente fechado", "Veteranos": "veteranos"}
assert set(ROT) == set(ORDEM), "rótulo de grupo faltando"
COR_SEG = dict(zip(ORDEM, [CORES[7], CORES[3], CORES[0], CORES[2]]))
ag["segmento"] = ag.grupo.map(nomes)
ag_atual["segmento"] = pd.Series(km.predict(esc.transform(ag_atual[VARS]))).map(nomes)

teste = []
for col, nome in EXTRAS.items():
    cols = VARS + [col]
    Xe = StandardScaler().fit_transform(ag[cols])
    lab = agrupa(Xe, K, SEMENTE, N_INIT).labels_
    teste.append({"variável somada": nome, "silhueta em k = 4": silhueta(Xe, lab),
                  "Rand com os 4 grupos da aula": adjusted_rand_score(ag.grupo, lab)})
teste = pd.DataFrame(teste)
print(teste.round(3).to_string(index=False))

# --- 2b. números das etapas 02 e 03 refeitos aqui ---------------------------------------------
# O texto citava AUC da etapa 02 e antecedência/tema da etapa 03 como valor fixo. São recalculados
# com a regra **e a população** da etapa de origem (K4 para a AUC, W2/W4/W5 para a saída), para a
# página não envelhecer sozinha nem divergir da página de detalhe.
qs = le_ouro("assinantes_30jun26.csv", ["user_id", "plano", "vence_jul_set", "saiu", "sistema",
                                        "tempo_casa_meses", "dias_treino_abr_jun", "pct_gps_falho"])
si = le_ouro("saidas.csv", ["user_id", "plano", "canal", "tipo_saida", "data_fim",
                            "antecedencia_dias", "pesquisa_tema"], datas=["data_fim"])


def auc(col, base, nome):
    """AUC univariada da etapa 02 (K4), guardando o n, o valor bruto e o sentido.

    Bruto = roc_auc_score(saiu, col): abaixo de 0,5 quer dizer que quem saiu tinha valor **menor**
    na variável. O texto cita o AUC dobrado (≥ 0,5) junto do bruto, do n e do sentido — associação
    entre variável e saída, não causa.
    """
    d = base[[col, "saiu"]].dropna()
    assert d.saiu.nunique() == 2, f"AUC de {col} sem os dois desfechos"
    bruto = roc_auc_score(d.saiu, d[col])
    return {"nome": nome, "n": len(d), "bruto": bruto, "auc": max(bruto, 1 - bruto),
            "lado": "menos" if bruto < 0.5 else "mais"}


def gps(base, col, saida, rotulo):
    """Saída de quem teve GPS falho contra a de quem não teve, num recorte declarado.

    Para com mensagem clara se um dos lados ficar vazio: a média sairia NaN e a página
    publicaria uma comparação sem base.
    """
    d = base[base[col].notna()]
    sim, nao = d[d[col] > 0], d[d[col] == 0]
    if min(len(sim), len(nao)) == 0:
        sys.exit(f"recorte GPS '{rotulo}' tem só um lado ({len(sim)} com falha, {len(nao)} sem): "
                 "ajuste o recorte antes de publicar a comparação")
    tx_sim, tx_nao = 100 * sim[saida].mean(), 100 * nao[saida].mean()
    return {"rotulo": rotulo, "n": len(d), "sim": len(sim), "nao": len(nao),
            "tx_sim": tx_sim, "tx_nao": tx_nao, "mais": tx_sim > tx_nao}


def pesquisa_com_tema():
    """Pesquisa de saída da prata com o tema do comentário, regra da etapa 03 (W5).

    Toda a pesquisa (não só quem já expirou, que é o recorte do saidas.csv), a resposta mais
    recente de cada conta e o tema pela função `tema` de pesquisa_saida_prata.
    """
    ps = pd.read_csv(PRATA / "pesquisa_saida.csv", parse_dates=["respondido_em"])
    ps = ps.sort_values(["user_id", "respondido_em", "resposta_id"]).groupby("user_id").tail(1).copy()
    ps["tema"] = ps.comentario.map(lambda c: tema(c)[0] if isinstance(c, str) else None)
    ps["tema"] = ps.tema.fillna(
        pd.Series(np.where(ps.comentario.isna(), "sem comentário", "sem tema"), index=ps.index))
    comum = si[si.pesquisa_tema.notna()][["user_id", "pesquisa_tema"]].merge(
        ps[["user_id", "tema"]], on="user_id", how="left")
    assert (comum.pesquisa_tema == comum.tema).all(), "tema da pesquisa diverge do saidas.csv"
    return ps


mens_q = qs[qs.plano == "mensal"]
anual_q = qs[(qs.plano == "anual") & (qs.vence_jul_set == 1)]
AUC = {"mensal": auc("tempo_casa_meses", mens_q, "tempo de casa"),
       "anual": auc("dias_treino_abr_jun", anual_q, "dias com treino")}
G02 = gps(qs[(qs.plano == "mensal") & (qs.sistema == "android")], "pct_gps_falho", "saiu",
          "etapa 02, mensal android, jul–set/26")
vol26 = si[(si.tipo_saida == "voluntária") & (si.data_fim >= "2026-01-01")]
aviso = vol26.groupby("plano").antecedencia_dias.agg(["median", "size"])
com_tema = pesquisa_com_tema()
com_tema = com_tema[~com_tema.tema.isin(["sem comentário", "sem tema"])]
pct_objetivo = 100 * com_tema.tema.eq("objetivo_cumprido").mean()
print(f"etapa 02: AUC tempo de casa no mensal {AUC['mensal']['auc']:.2f} "
      f"(bruto {AUC['mensal']['bruto']:.2f}, quem saiu tinha {AUC['mensal']['lado']}), dias com "
      f"treino no anual que vence {AUC['anual']['auc']:.2f} (bruto {AUC['anual']['bruto']:.2f}, "
      f"quem saiu tinha {AUC['anual']['lado']})")
print(f"etapa 03: aviso no anual {aviso.loc['anual', 'median']:.0f} dias "
      f"(n = {aviso.loc['anual', 'size']:.0f}) · 'objetivo cumprido' em {pct_objetivo:.1f}% dos "
      f"{len(com_tema)} comentários com tema (pesquisa inteira) · GPS etapa 02: "
      f"{G02['sim']} com falha × {G02['nao']} sem")

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
G04 = gps(ag[(ag.segmento == "Ativos ao ar livre") & (ag.plano == "mensal")], "pct_gps_falho",
          "saiu_60d", "etapa 04, mensal ao ar livre, ago–set/26")
met = ag[ag.plano == "mensal"].groupby("metodo").saiu_60d.mean()
sil4 = curvas.set_index("k").loc[K, "silhueta"]
e4 = estab.set_index("k").loc[K]

# --- frases derivadas: o texto não carrega número, sentido nem grupo fixo ----------------------
taxas_seg = pf["saída 60 dias (%)"]
topo, base_seg = taxas_seg.idxmax(), taxas_seg.idxmin()
anual_par = 100 * (ag[ag.segmento == "Parados"].plano == "anual").mean()
mensal_par = int(((ag.segmento == "Parados") & (ag.plano == "mensal")).sum())
estoque = {sg: n_atual[sg] * taxas_seg[sg] / 100 for sg in ORDEM}
maior_vol = max(estoque, key=estoque.get)

ativos = ["Ativos ao ar livre", "Ativos em ambiente fechado"]
dif_plano = {sg: 100 * (sx.loc[(sg, "mensal"), "mean"] - sx.loc[(sg, "anual"), "mean"]) for sg in ativos}
mensal_maior = [sg for sg, d in dif_plano.items() if d > 0]
sentido_plano = (f"O mensal sai mais que o anual nos {len(ativos)} grupos ativos" if len(mensal_maior) == len(ativos)
                else f"O mensal sai mais que o anual em {len(mensal_maior)} de {len(ativos)} grupos ativos")
pares_plano = "; ".join(f"{br(100 * sx.loc[(sg, 'mensal'), 'mean'])}% × {br(100 * sx.loc[(sg, 'anual'), 'mean'])}% "
                       f"{ROT[sg]}" for sg in ativos)

novo_gap = {sg: 100 * (nov.loc[(sg, "até 90 dias"), "mean"] - nov.loc[(sg, "mais de 90 dias"), "mean"])
            for sg in ORDEM if (sg, "até 90 dias") in nov.index and (sg, "mais de 90 dias") in nov.index}
novo_pos = [sg for sg, d in novo_gap.items() if d > 0]
if not novo_gap:
    sys.exit("nenhum grupo tem mensal nas duas faixas de tempo de casa; revisar a leitura do plano")
novo_maior = max(novo_gap, key=novo_gap.get)
sentido_novo = (f"O mensal recém-chegado sai mais nos {len(novo_gap)} grupos com as duas faixas"
                if len(novo_pos) == len(novo_gap) else
                f"O mensal recém-chegado sai mais em {len(novo_pos)} dos {len(novo_gap)} grupos "
                f"com as duas faixas" if novo_pos else
                "O mensal recém-chegado não sai mais em nenhum grupo")


def saiu_novo(sg):
    """Saída do mensal com até 90 dias de casa no grupo, ou aviso se a faixa não existir."""
    return (f"{br(100 * nov.loc[(sg, 'até 90 dias'), 'mean'])}% com até 90 dias de casa"
            if (sg, "até 90 dias") in nov.index else "sem mensal com até 90 dias de casa")


def frase_auc(x):
    """Sentido, AUC dobrado, AUC bruto e n — associação entre variável e saída, não causa."""
    return (f"quem saiu tinha **{x['lado']}** {x['nome']} (AUC {br(x['auc'], 2)}; bruto "
            f"{br(x['bruto'], 2)}, n = {br(x['n'], 0)})")


mesmo_gps = G04["mais"] == G02["mais"]
gps_frase = (f"saiu **{'mais' if G04['mais'] else 'menos'}** "
             f"({br(G04['tx_sim'])}% × {br(G04['tx_nao'])}%)")
gps_titulo = ("GPS falho aponta no mesmo sentido da etapa 02" if mesmo_gps else
              "GPS falho não se confirma aqui")
gps_02_frase = (f"no mesmo sentido da etapa 02 ({br(G02['tx_sim'])}% × {br(G02['tx_nao'])}%)"
                if mesmo_gps else
                f"o contrário da etapa 02 ({br(G02['tx_sim'])}% × {br(G02['tx_nao'])}%)")
gps_n = (f"recortes declarados: etapa 02, mensal android em jul–set, {br(G02['sim'], 0)} com falha e "
         f"{br(G02['nao'], 0)} sem; etapa 04, mensal ao ar livre em ago–set, {br(G04['sim'], 0)} com "
         f"falha e {br(G04['nao'], 0)} sem")

# quanto da queda total de inércia (k = 2 a 8) acontece nas passagens até k = K + 2
queda = -curvas.set_index("k")["inércia"].diff().dropna()
share_ate = 100 * queda.loc[queda.index <= K + 2].sum() / queda.sum()
k_sil = int(curvas.loc[curvas.silhueta.idxmax(), "k"])
ei = estab.set_index("k")
# "até k = N" só vale para a sequência contígua a partir do menor k testado: para no primeiro k
# que não atinge o limiar, em vez de pegar o maior k estável solto.
assert list(ei.index) == list(range(int(ei.index.min()), int(ei.index.max()) + 1)), \
    "estabilidade com k fora de sequência: o texto 'até k' não valeria"
quebra = ei[ei["Rand mínimo"] < LIMIAR_RAND].index
k_quebra = int(quebra.min()) if len(quebra) else None
k_rep = (k_quebra - 1) if k_quebra is not None else int(ei.index.max())
k_rep = k_rep if k_rep >= int(ei.index.min()) else None
seq_rand = " · ".join(f"k = {k}: {br(ei.loc[k, 'Rand mínimo'], 3)}" for k in ei.index)
frase_rep = (
    f"O Rand mínimo por k é {seq_rand}: fica ≥ {br(LIMIAR_RAND, 2)} "
    f"de k = {int(ei.index.min())} até k = {k_rep}"
    + (f" e quebra em k = {k_quebra}" if k_quebra is not None else " e não quebra em nenhum k")
    if k_rep else "Os grupos não se repetem nas reamostras em nenhum k testado")
viz_estavel = ((K + 1) in ei.index and ei.loc[K, "Rand mínimo"] >= LIMIAR_RAND
               and ei.loc[K + 1, "Rand mínimo"] >= LIMIAR_RAND)
frase_viz = (
    f"A estabilidade não separa k = {K} de k = {K + 1}: os dois ficam acima do limiar "
    f"({br(ei.loc[K, 'Rand mínimo'], 3)} e {br(ei.loc[K + 1, 'Rand mínimo'], 3)}), e o médio é "
    f"{br(ei.loc[K, 'Rand médio'], 3)} e {br(ei.loc[K + 1, 'Rand médio'], 3)}. As silhuetas "
    f"são {br(sil4, 3)} e {br(curvas.set_index('k').loc[K + 1, 'silhueta'], 3)}; "
    f"a escolha também depende da leitura dos grupos" if viz_estavel else
    f"k = {K + 1} fica abaixo do limiar ({br(ei.loc[K + 1, 'Rand mínimo'], 3)}): a estabilidade "
    f"também separa k = {K} do próximo" if (K + 1) in ei.index else
    f"k = {K + 1} não foi testado na estabilidade")

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
  5 para 6, {br(-ganho[6], 0)}. Essas passagens até k = {K + 2} respondem por {br(share_ate, 0)}% da queda
  total de 2 para 8 grupos, e a curva cai sempre, sem cotovelo que isole um k: quem escolhe são a
  silhueta, a estabilidade e a leitura de negócio.
- **Silhueta.** A maior é a de k = {k_sil} ({br(curvas.loc[curvas.k == k_sil, 'silhueta'].iloc[0], 2)}).
  Em k = 4 é {br(sil4, 2)}, estrutura fraca: os grupos são regiões de um
  contínuo, não ilhas.
- **Estabilidade.** {frase_rep}. {frase_viz}. Em k = 4, o Rand médio é {br(e4['Rand médio'], 3)},
  o mínimo {br(e4['Rand mínimo'], 3)} e outra semente dá {br(e4['outra semente'], 3)}.
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
p.figura(f, f"As quatro variáveis na unidade original, {br(len(am_), 0)} assinantes sorteados. "
            "À esquerda, o eixo que separa ar livre de ambiente fechado; à direita, os que isolam "
            "parados e veteranos.")
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
f.update_xaxes(title_text="% que decidiu sair entre 01/08 e 29/09/2026",
               range=[0, float(taxas.max()) * 1.15])
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
p.figura(f, "Saída em 60 dias por grupo e plano. " +
            (f"Os parados são {br(anual_par, 0)}% anuais: nenhum dos "
             f"{br(len(ag[ag.segmento == 'Parados']), 0)} com a renovação ligada estava sem treinar."
             if mensal_par == 0 else
             f"Os parados são {br(anual_par, 0)}% anuais; {br(mensal_par, 0)} são mensais."))
nov_t = nov.reset_index().rename(columns={"novo": "tempo de casa", "size": "mensais", "mean": "saída 60 dias (%)"})
nov_t["saída 60 dias (%)"] *= 100
p.tabela(nov_t, "Mensal: saída em 60 dias por tempo de casa dentro de cada grupo",
         {"mensais": "{:,.0f}", "saída 60 dias (%)": "{:.1f}"})
p.texto(f"""
- **O plano não é eixo do agrupamento, mas muda a taxa dentro dele.** {sentido_plano}
  ({pares_plano}). As ofertas do CRM são por plano, então o plano entra na escolha da ação, depois do
  grupo.
- **{sentido_novo}**: {br(100 * nov.loc[(novo_maior, 'até 90 dias'), 'mean'])}%
  {ROT[novo_maior]} com até 90 dias de casa, contra {br(100 * nov.loc[(novo_maior, 'mais de 90 dias'), 'mean'])}%
  depois disso. É o achado da etapa 02 visto dentro dos grupos: {frase_auc(AUC['mensal'])} —
  associação, não causa.
- **Cartão no mensal**: {br(100 * met['cartao'])}% de saída, contra {br(100 * met.drop('cartao').min())}% a
  {br(100 * met.drop('cartao').max())}% nos outros métodos. É a falha de pagamento da etapa 03 (a
  expiração por falha de cobrança conta como saída).
- **{gps_titulo}.** Entre os mensais ao ar livre, quem teve treino com GPS falho
  {gps_frase}, {gps_02_frase}. {gps_n}. Seleção provável: quem teve a falha em mai–jun e saiu em
  julho já não está na base de 31/07, então os tamanhos acima são os que sobraram, não o incidente.
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
f.update_xaxes(title_text="assinantes no grupo em 30/09/2026", range=[0, float(n_atual.max()) * 1.2])
f.update_yaxes(range=[0, float(taxas_seg.max()) * 1.2])
p.figura(f, "Taxa × tamanho atual. A área da bolha é o número de saídas se a taxa de ago–set se "
            "repetisse no grupo de 30/09 (ordem de grandeza, não previsão).")


p.cartoes([
    {"titulo": "Parados", "cor": COR_SEG["Parados"],
     "destaque": f"{br(pf.loc['Parados', 'assinantes'], 0)} em 31/07 · {br(n_atual['Parados'], 0)} em 30/09 · "
                 f"{br(anual_par, 0)}% anuais",

     "linhas": [
         ("Perfil", f"Pagam o anual e não treinam: {br(pf.loc['Parados', 'dias sem treino'], 0)} dias sem treino "
                    f"(mediana), {br(pf.loc['Parados', 'tempo de casa (dias)'] / 30.4375, 0)} meses de casa."),
         ("Saída em 60 dias", f"**{br(pf.loc['Parados', 'saída 60 dias (%)'])}%**, "
                              f"{br(pf.loc['Parados', 'saída 60 dias (%)'] / (100 * media))} vezes a média."),
         ("Hipótese de driver", "Perda de rotina ou objetivo cumprido (\"era só até a prova\", tema de "
                                f"{br(pct_objetivo)}% dos comentários da pesquisa, etapa 03). No anual, quem "
                                f"treinou menos saiu mais (etapa 02: {frase_auc(AUC['anual'])}; associação,"
                                " não causa)."),
         ("Prioridade", "**Ação imediata**: " + ("a maior taxa da base." if topo == "Parados" else
                                                    f"a {br(taxas_seg.rank(ascending=False)['Parados'], 0)}ª "
                                                    f"maior taxa da base.")),
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
         ("Saída em 60 dias", f"**{br(pf.loc['Ativos ao ar livre', 'saída 60 dias (%)'])}%**, "
                              f"{br(pf.loc['Ativos ao ar livre', 'saída 60 dias (%)'] / (100 * media))} vezes a média; "
                              + (f"o maior volume (≈ {br(estoque['Ativos ao ar livre'], 0)} saídas em 60 dias "
                                 f"se a taxa se repetir na base de 30/09)." if maior_vol == "Ativos ao ar livre"
                                 else f"≈ {br(estoque['Ativos ao ar livre'], 0)} saídas em 60 dias se a taxa se "
                                      f"repetir na base de 30/09; o maior volume é {ROT[maior_vol]}.")),
         ("Hipótese de driver", "Treino com data marcada (prova, evento): cumprido o objetivo, sai. O mensal "
                                f"recém-chegado sai {saiu_novo('Ativos ao ar livre')}."),
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
         ("Saída em 60 dias", f"**{br(pf.loc['Ativos em ambiente fechado', 'saída 60 dias (%)'])}%**, "
                              f"{br(pf.loc['Ativos em ambiente fechado', 'saída 60 dias (%)'] / (100 * media))} "
                              f"vezes a média."),
         ("Hipótese de driver", "Rotina estável; o risco está no mensal recém-chegado "
                                f"({saiu_novo('Ativos em ambiente fechado')}) e no cartão (falha de cobrança)."),
         ("Prioridade", "**Monitoramento**, com ação só no mensal novo e no cartão."),
         ("Direção da ação", "Conteúdo e progressão de treino (sem custo); aviso de cartão e troca de "
                             "método para quem paga no cartão."),
     ]},
    {"titulo": "Veteranos", "cor": COR_SEG["Veteranos"],
     "destaque": f"{br(pf.loc['Veteranos', 'assinantes'], 0)} em 31/07 · {br(n_atual['Veteranos'], 0)} em 30/09",
     "linhas": [
         ("Perfil", f"{br(pf.loc['Veteranos', 'tempo de casa (dias)'] / 365.25)} anos de casa (mediana), "
                    f"{br(pf.loc['Veteranos', 'treinos/semana'])} treinos por semana."),
         ("Saída em 60 dias", f"**{br(pf.loc['Veteranos', 'saída 60 dias (%)'])}%**, "
                              f"{br(pf.loc['Veteranos', 'saída 60 dias (%)'] / (100 * media))} vezes a média."),
         ("Hipótese de driver", "Hábito formado; parte é sobrevivência (só ficou quem gosta)."),
         ("Prioridade", "**Monitoramento.** Oferta para quem ficaria de qualquer jeito é custo sem retorno."),
         ("Direção da ação", "Reconhecimento e indicação de amigos, sem desconto."),
     ]},
])
exp = fora_b.groupby("plano")[["expirou_60d", "religou_60d"]].mean()
# prazo desta lista, medido em 31/07: dias até a data de fim já registrada na prata (não é projeção)
lista = fora_b[["user_id", "plano"]].merge(a[["user_id", "data_fim"]], on="user_id", how="left")
prazo = (lista[lista.plano == "anual"].data_fim - REF).dt.days.dropna()
prazo_m = (lista[lista.plano == "mensal"].data_fim - REF).dt.days.dropna()
if len(prazo) == 0 or len(prazo_m) == 0:
    sys.exit("lista com a renovação desligada sem data de fim registrada: o prazo sairia vazio")
p.secao("À parte: quem já desligou a renovação")
p.texto(f"""
- **{br(len(fora_b), 0)} assinantes ativos em 31/07** ({br(100 * (fora_b.plano == 'anual').mean(), 0)}% anuais;
  {br(len(fora_a), 0)} em 30/09) já tinham desligado a renovação e seguem pagando até o fim do período.
  Treinavam pouco: mediana de {br(fora_b[fora_b.plano == 'anual'].treinos_semana.median(), 2)} treino por semana no anual.
- Em 60 dias, {br(100 * fora_b.expirou_60d.mean())}% expiraram (mensal {br(100 * exp.loc['mensal', 'expirou_60d'], 0)}%,
  anual {br(100 * exp.loc['anual', 'expirou_60d'], 0)}%) e só {br(100 * fora_b.religou_60d.mean())}% religaram sozinhos.
- Prazo desta lista, medido em 31/07 e não projetado: entre os {br(len(prazo), 0)} anuais com data de
  fim registrada, a mediana é de {br(prazo.median(), 0)} dias até expirar (Q1 {br(prazo.quantile(.25), 0)},
  Q3 {br(prazo.quantile(.75), 0)}); nos mensais, {br(prazo_m.median(), 0)}. Nas saídas voluntárias anuais
  de 2026 a mediana entre desligar e expirar foi de {br(aviso.loc['anual', 'median'], 0)} dias
  (n = {br(aviso.loc['anual', 'size'], 0)}, etapa 03) — é a medida histórica do aviso, não o prazo
  futuro de quem está nesta lista.
- Não é segmento de comportamento, é uma **lista operacional** de reversão.
""")

p.secao("Três frases")
p.texto(f"""
- **O que o dado diz.** Os pagantes se dividem em {K} grupos
  {'estáveis' if e4['Rand mínimo'] >= LIMIAR_RAND else 'que só se repetem em parte'} por engajamento e
  tempo de casa; a saída vai de {br(pf['saída 60 dias (%)'].min())}% ({ROT[base_seg]}) a
  {br(pf['saída 60 dias (%)'].max())}% ({ROT[topo]}), e o maior volume de saídas está
  {ROT[maior_vol]} (≈ {br(estoque[maior_vol], 0)} em 60 dias se a taxa se repetir na base de 30/09).
- **O que ele não diz.** Que o grupo causa a saída, nem quanto uma ação reduziria cada taxa: a
  separação é fraca (silhueta {br(sil4, 2)}) e a taxa é histórica.
- **A próxima pergunta.** Dentro de cada grupo, quem tem o maior risco individual (modelo da semana
  10), e qual ação muda a decisão (uplift da campanha de ago/26)?
""")

p.secao("Limites")
p.texto(f"""
- Estrutura fraca (silhueta {br(sil4, 2)}, abaixo da faixa de 0,50): os grupos cortam um contínuo;
  assinantes na fronteira mudam de grupo com pouca mudança de comportamento.
- Taxa de saída histórica (ago–set/26), não previsão. A saída inclui a expiração por falha de
  pagamento, que não é decisão do cliente.
- Seleção: a base de 31/07 não tem quem saiu antes. Viés de sobrevivência no tempo de casa (D02.4).
- O k-means procura grupos redondos em torno de médias, com distância euclidiana; outra régua forma
  outros grupos (aula 3).
- A referência da aula (12,5% de saída média e 472 parados) é valor externo, não recalculado aqui: com
  a nossa regra a média é {br(100 * media)}% e Parados tem {br(pf.loc['Parados', 'assinantes'], 0)}
  assinantes. A borda de cada variável (sem treino, janela de 12 semanas) desloca dezenas de
  assinantes e muda as taxas; os quatro grupos saem da regra de nomes (checada acima).
""")

destino = p.salvar("04_segmentos.html")
print(f"artefato: {destino.relative_to(RAIZ)}")
