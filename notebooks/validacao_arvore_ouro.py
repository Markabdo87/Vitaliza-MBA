"""Ouro -> ouro: validacao_arvore.csv (um corte de score) + artefatos/08_validacao_arvore.html.

Pergunta: na persona Ativos ao ar livre · mensal, uma árvore de decisão separa quem decide sair
em 60 dias? Em cada corte de score, quanto o modelo acerta (precisão), quanto ele vê (recall) e
quanto vale contatar, conforme a oferta (desafio sem custo × cupom de 30%)? Serve para formular
a hipótese de precisão × recall levada à Tecnologia; não é o modelo final.

Regras (decisões H1–H6 no decisoes.md):
  1. Base: persona L "Ativos ao ar livre" (segmentos.csv, 31/07/2026) com plano mensal.
     Rótulo: saiu_60d de segmentos.csv (decisão de sair entre 01/08 e 29/09, regra L2).
  2. Variáveis: só as medidas até 31/07, das duas tabelas de segmentação (VARS). Fica de fora
     `tratado` da campanha de 10/08/2026: é posterior à data de referência.
  3. Divisão 70% treino × 30% teste, estratificada; árvore com profundidade 3, no mínimo
     80 assinantes por folha, class_weight="balanced", random_state = 0. Com o balanceamento,
     o score da folha não é probabilidade: os cortes são os valores que a árvore produz.
  4. Taxa de reversão de cada oferta, medida na campanha de ago/26 nos mensais das personas
     Ativos (ar livre e ambiente fechado): 1 − decisão de sair no grupo da oferta ÷ no controle,
     de 10/08 a 30/09/2026 (desligou a renovação ou cancelou no site). O custo do cupom depende
     de quantos contatados usam o desconto: dois casos, aceite = clique no grupo cupom (premissa:
     quem clica usa) e aceite total (todo contatado usa, pior caso).
  5. Valor líquido de um corte, no conjunto de teste:
       verdadeiros positivos × LTV × reversão da oferta
       − contatados × custo de contato
       − (cupom) contatados × aceite × custo do cupom.
     Score e cortes arredondados em 2 casas: folhas com score quase igual viram o mesmo corte.
  6. Constantes de negócio em PREMISSAS, cada uma com a fonte.

Uso: .venv/bin/python notebooks/validacao_arvore_ouro.py  (a partir da raiz do repo; depois de
segmentos_ouro.py e segmentos_kmeans_ouro.py, que o laço de ouro roda antes por ordem alfabética)
"""
import sys

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from sklearn.metrics import confusion_matrix, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier, export_text

from _artefato import CORES, Pagina, layout_padrao
from _ouro import OURO, RAIZ, ler_prata

SAIDA = OURO / "validacao_arvore.csv"
REF = "2026-07-31"
CAMPANHA_INI, CAMPANHA_FIM = pd.Timestamp("2026-08-10"), pd.Timestamp("2026-10-01")
SEMENTE = 0
PREMISSAS = {  # valor, fonte
    "ltv": (287.0, "LTV médio do case v2"),
    "email": (0.01, "custo do e-mail, enunciado seção 03 (push: custo desprezível)"),
    "ia": (0.02, "IA por mensagem: ~800 tokens de entrada e 200 de saída no Claude Sonnet 5.5 "
                 "(US$ 2 e US$ 10 por milhão) com câmbio de R$ 5,50 (premissa do grupo)"),
    "cupom": (35.91, "30% por 3 meses no mensal, enunciado seção 03"),
}
CORTES_REF = [0.40, 0.55, 0.70]  # opções do threshold discutidas na Aula 7
VARS = ["treinos_semana", "dias_sem_treino", "tempo_casa_dias", "pct_ar_livre", "pct_gps_falho",
        "km_treino", "conexoes", "treinos_30d", "tendencia_treino", "sessoes_app", "posts_90d",
        "problemas_90d", "recusas_180d", "loja", "cartao", "android"]
NOMES = {"tempo_casa_dias": "tempo de casa (dias)", "dias_sem_treino": "dias sem treino",
         "pct_gps_falho": "% de treinos ao ar livre com GPS falho", "km_treino": "km por treino ao ar livre",
         "treinos_semana": "treinos por semana", "pct_ar_livre": "% ao ar livre", "conexoes": "conexões",
         "treinos_30d": "treinos em 30 dias", "tendencia_treino": "tendência de treino",
         "sessoes_app": "sessões no app/mês", "posts_90d": "posts em 90 dias",
         "problemas_90d": "chamados + GPS falho em 90 dias", "recusas_180d": "recusas em 180 dias",
         "loja": "paga pela loja", "cartao": "paga no cartão", "android": "android"}


def br(x, d=1):
    return f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def ler_ouro(arquivo, notebook):
    caminho = OURO / arquivo
    if not caminho.exists():
        sys.exit(f"falta {caminho.relative_to(RAIZ)}: rode .venv/bin/python notebooks/{notebook}")
    return pd.read_csv(caminho)


# --- 1. base da persona ---------------------------------------------------------------------
L = ler_ouro("segmentos.csv", "segmentos_ouro.py")
N = ler_ouro("segmentos_kmeans.csv", "segmentos_kmeans_ouro.py")
l, n = L[L.data_ref == REF], N[N.data_ref == REF]
extra = ["treinos_30d", "tendencia_treino", "sessoes_app", "posts_90d", "problemas_90d", "recusas_180d"]
b = l.merge(n[["user_id"] + extra], on="user_id", how="inner", validate="one_to_one")
b["loja"] = (b.canal == "loja").astype(int)
b["cartao"] = (b.metodo == "cartao").astype(int)
b["android"] = (b.sistema == "android").astype(int)
p = b[(b.segmento == "Ativos ao ar livre") & (b.plano == "mensal")].reset_index(drop=True)
if p.empty or p.saiu_60d.isna().any():
    sys.exit("persona vazia ou sem rótulo: confira segmentos.csv")
y = p.saiu_60d.astype(int)
assert "tratado" not in VARS, "variável posterior à data de referência"

# --- 2. reversão por oferta (campanha de ago/26) -------------------------------------------
camp = ler_prata("campanha_ago26.csv", ["user_id", "grupo", "clicou", "flag_inconsistente"])
camp = camp[camp.flag_inconsistente == 0]
ev = ler_prata("eventos_assinatura.csv", ["user_id", "data_hora_brt", "evento"], datas=["data_hora_brt"])
decidiu = ev[(ev.data_hora_brt >= CAMPANHA_INI) & (ev.data_hora_brt < CAMPANHA_FIM)
             & ev.evento.isin(["renovacao_automatica_desligada", "cancelamento_web"])].user_id
ativos_m = b[b.segmento.isin(["Ativos ao ar livre", "Ativos em ambiente fechado"]) & (b.plano == "mensal")]
c = camp.merge(ativos_m[["user_id"]], on="user_id")
c["decidiu"] = c.user_id.isin(decidiu).astype(int)
taxa = c.groupby("grupo").decidiu.mean()
for g in ["controle", "desafio", "cupom"]:
    if g not in taxa:
        sys.exit(f"campanha sem o grupo {g} nos mensais das personas Ativos")
reversao = {"desafio": 1 - taxa["desafio"] / taxa["controle"], "cupom": 1 - taxa["cupom"] / taxa["controle"]}
aceite_cupom = c[c.grupo == "cupom"].clicou.mean()
custo_contato = PREMISSAS["email"][0] + PREMISSAS["ia"][0]
LTV, CUPOM = PREMISSAS["ltv"][0], PREMISSAS["cupom"][0]

# --- 3. árvore -------------------------------------------------------------------------------
idx = np.arange(len(p))
i_tr, i_te = train_test_split(idx, test_size=0.3, stratify=y, random_state=SEMENTE)
arv = DecisionTreeClassifier(max_depth=3, min_samples_leaf=80, class_weight="balanced",
                             random_state=SEMENTE).fit(p.loc[i_tr, VARS], y[i_tr])
s_te = np.round(arv.predict_proba(p.loc[i_te, VARS])[:, 1], 2)
s_tr = arv.predict_proba(p.loc[i_tr, VARS])[:, 1]
y_te = y[i_te].values
auc_te, auc_tr = roc_auc_score(y_te, s_te), roc_auc_score(y[i_tr], s_tr)
imp = pd.Series(arv.feature_importances_, VARS).sort_values(ascending=False)
imp = imp[imp > 0]

# --- 4. cortes ---------------------------------------------------------------------------------
linhas = []
for corte in sorted(set(s_te)):
    pred = (s_te >= corte).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_te, pred, labels=[0, 1]).ravel()
    cont = int(pred.sum())
    linhas.append({
        "corte": corte, "contatados": cont, "pct_contatados": 100 * cont / len(pred),
        "precisao": tp / cont if cont else np.nan, "recall": tp / (tp + fn),
        "vp": int(tp), "fp": int(fp), "fn": int(fn), "vn": int(tn),
        "liquido_desafio": tp * LTV * reversao["desafio"] - cont * custo_contato,
        "liquido_cupom_clique": tp * LTV * reversao["cupom"] - cont * custo_contato - cont * aceite_cupom * CUPOM,
        "liquido_cupom_total": tp * LTV * reversao["cupom"] - cont * custo_contato - cont * CUPOM,
    })
tab = pd.DataFrame(linhas)
tab["corte_ref"] = ""
for ref in CORTES_REF:
    tab.loc[(tab.corte - ref).abs().idxmin(), "corte_ref"] = f"{ref:.2f}".replace(".", ",")
OURO.mkdir(parents=True, exist_ok=True)
tab.to_csv(SAIDA, index=False)

# folhas: perfil e taxa
folha_te = arv.apply(p.loc[i_te, VARS])
folhas = (pd.DataFrame({"folha": folha_te, "y": y_te, "score": s_te}).groupby("folha")
          .agg(assinantes=("y", "size"), saida=("y", "mean"), score=("score", "mean")))
caminhos = {}
arvore_txt = export_text(arv, feature_names=VARS)
# regra de cada folha: percorre a árvore
t = arv.tree_


def regra(no=0, conds=()):
    if t.children_left[no] == -1:
        caminhos[no] = " e ".join(conds) if conds else "todos"
        return
    v, lim = VARS[t.feature[no]], t.threshold[no]
    nome = NOMES.get(v, v)
    regra(t.children_left[no], conds + (f"{nome} ≤ {br(lim, 1)}",))
    regra(t.children_right[no], conds + (f"{nome} > {br(lim, 1)}",))


regra()
folhas["perfil"] = folhas.index.map(caminhos)
folhas = folhas.sort_values("saida", ascending=False)
topo = folhas.index[0]
p["folha"] = arv.apply(p[VARS])
ctrl = camp[camp.grupo == "controle"].user_id
top_ctrl = p[(p.folha == topo) & p.user_id.isin(ctrl)].saiu_60d
print(f"persona {len(p)} · saída {y.mean():.3f} · AUC teste {auc_te:.3f} treino {auc_tr:.3f}")
print("reversão", {k: round(v, 3) for k, v in reversao.items()}, "aceite cupom", round(aceite_cupom, 3))
print(tab.round(3).to_string(index=False))
print(folhas.round(3).to_string())
print(f"folha de maior risco no controle: {top_ctrl.mean():.3f} (n={len(top_ctrl)})")
print(f"{SAIDA.relative_to(RAIZ)}: {len(tab)} cortes")

# --- 5. página ------------------------------------------------------------------------------
ref = tab[tab.corte_ref != ""].copy()
melhor_des = tab.loc[tab.liquido_desafio.idxmax()]
melhor_cli = tab.loc[tab.liquido_cupom_clique.idxmax()]
melhor_tot = tab.loc[tab.liquido_cupom_total.idxmax()]
pg = Pagina(
    "08 · Validação com árvore de decisão",
    "Na persona Ativos ao ar livre · mensal, quanto um modelo simples acerta e vê em cada corte, e "
    "quanto vale contatar conforme a oferta.",
    "fonte: `dados/3.ouro/validacao_arvore.csv`, gerada por `notebooks/validacao_arvore_ouro.py` "
    "(decisões H1–H6)",
)
pg.texto(f"""
**Regra.** {br(len(p), 0)} assinantes mensais da persona Ativos ao ar livre em 31/07/2026; rótulo =
decisão de sair entre 01/08 e 29/09 ({br(100 * y.mean())}%). Variáveis medidas até 31/07, sem a
campanha de 10/08. Árvore de profundidade 3 (no mínimo 80 por folha, classes balanceadas), treinada em
70% e avaliada nos {br(len(i_te), 0)} do teste. O score da folha não é probabilidade: os cortes são os
valores que a árvore produz, e os mais próximos de 0,40, 0,55 e 0,70 estão marcados.

**Qualidade.** AUC de {br(auc_te, 2)} no teste e {br(auc_tr, 2)} no treino: separação modesta e sem
sobreajuste. Serve para formular a hipótese; o modelo da Tecnologia precisa superar esse patamar.
""")

pg.secao("Precisão e recall em cada corte")
f = go.Figure()
f.add_trace(go.Scatter(x=tab.corte, y=100 * tab.recall, name="recall", mode="lines+markers",
                       line=dict(color=CORES[0], width=2.5), hovertemplate="corte %{x:.2f}: recall %{y:.0f}%<extra></extra>"))
f.add_trace(go.Scatter(x=tab.corte, y=100 * tab.precisao, name="precisão", mode="lines+markers",
                       line=dict(color=CORES[1], width=2.5), hovertemplate="corte %{x:.2f}: precisão %{y:.0f}%<extra></extra>"))
f.add_trace(go.Scatter(x=tab.corte, y=tab.pct_contatados, name="% contatados", mode="lines",
                       line=dict(color=CORES[2], width=1.5, dash="dot"), hovertemplate="corte %{x:.2f}: %{y:.0f}% contatados<extra></extra>"))
layout_padrao(f, "% (teste)")
f.update_xaxes(title="corte de score")
pg.figura(f, "Subir o corte aumenta a precisão e derruba o recall e o número de contatos.")

pg.secao("Quanto vale contatar, conforme a oferta")
f = go.Figure()
f.add_trace(go.Bar(x=[f"{c:.2f}" for c in tab.corte], y=tab.liquido_desafio, name="desafio (sem custo)",
                   marker_color=CORES[2], hovertemplate="corte %{x}: R$ %{y:,.0f}<extra></extra>"))
f.add_trace(go.Bar(x=[f"{c:.2f}" for c in tab.corte], y=tab.liquido_cupom_clique, name="cupom · aceite = clique",
                   marker_color=CORES[3], hovertemplate="corte %{x}: R$ %{y:,.0f}<extra></extra>"))
f.add_trace(go.Bar(x=[f"{c:.2f}" for c in tab.corte], y=tab.liquido_cupom_total, name="cupom · aceite total",
                   marker_color=CORES[7], hovertemplate="corte %{x}: R$ %{y:,.0f}<extra></extra>"))
layout_padrao(f, "valor líquido no teste (R$)")
f.update_layout(barmode="group")
f.update_xaxes(title="corte de score", type="category")
pg.figura(f, f"Valor líquido = acertos × LTV × reversão − custo dos contatos (e do cupom aceito), nos "
             f"{br(len(i_te), 0)} assinantes do teste.")
def leitura(nome, m):
    return (f"**{nome}:** maior valor no corte {br(m.corte, 2)}, com {br(m.pct_contatados, 0)}% da persona "
            f"contatada, recall de {br(100 * m.recall, 0)}% e precisão de {br(100 * m.precisao, 0)}%.")


pg.texto("\n".join([
    "- " + leitura("Desafio (sem custo direto)", melhor_des),
    "- " + leitura(f"Cupom, se só quem clica usa ({br(100 * aceite_cupom, 0)}% de aceite)", melhor_cli),
    "- " + leitura("Cupom, se todo contatado usa (pior caso)", melhor_tot),
    f"- Quanto mais barato o falso positivo, mais baixo o corte que maximiza o valor (mais recall); "
    f"quanto mais caro, mais alto o corte (mais precisão). O custo do falso positivo é o custo da oferta "
    f"para quem não ia sair: R$ {br(custo_contato, 2)} no desafio, até R$ {br(CUPOM + custo_contato, 2)} no cupom.",
    f"- Reversão medida na campanha de ago/26, nos mensais das personas Ativos: desafio "
    f"{br(100 * reversao['desafio'], 0)}%, cupom {br(100 * reversao['cupom'], 0)}%.",
]))

ref_tab = ref[["corte_ref", "corte", "pct_contatados", "precisao", "recall", "vp", "fp", "fn",
               "liquido_desafio", "liquido_cupom_clique", "liquido_cupom_total"]].rename(columns={
    "corte_ref": "opção da Aula 7", "corte": "corte da árvore", "pct_contatados": "% contatados",
    "precisao": "precisão", "recall": "recall", "vp": "acertos (VP)", "fp": "falsos positivos",
    "fn": "falsos negativos", "liquido_desafio": "líquido desafio (R$)",
    "liquido_cupom_clique": "líquido cupom, aceite = clique (R$)", "liquido_cupom_total": "líquido cupom, aceite total (R$)"})
pg.tabela(ref_tab, "As três opções de threshold da Aula 7, no teste",
          {"corte da árvore": "{:.2f}", "% contatados": "{:.0f}", "precisão": "{:.2f}", "recall": "{:.2f}",
           "líquido desafio (R$)": "{:,.0f}", "líquido cupom, aceite = clique (R$)": "{:,.0f}",
           "líquido cupom, aceite total (R$)": "{:,.0f}"})

pg.secao("Quem a árvore marca como maior risco")
ft = folhas.reset_index()[["perfil", "assinantes", "saida", "score"]].rename(columns={
    "perfil": "perfil da folha", "assinantes": "assinantes (teste)", "saida": "decisão de sair (%)", "score": "score"})
ft["decisão de sair (%)"] *= 100
pg.tabela(ft, "Folhas da árvore, da maior para a menor taxa no teste",
          {"decisão de sair (%)": "{:.1f}", "score": "{:.2f}"})
pg.tabela(pd.DataFrame({"variável": [NOMES.get(v, v) for v in imp.index], "importância": imp.values}),
          "Importância das variáveis", {"importância": "{:.2f}"})
pg.texto(f"""
**Hipótese para a Tecnologia.** Na folha de maior risco ({folhas.perfil.iloc[0]}), a decisão de sair é
de {br(100 * folhas.saida.iloc[0])}% no teste e de {br(100 * top_ctrl.mean())}% entre os do grupo
controle da campanha (n = {len(top_ctrl)}), contra {br(100 * y.mean())}% na persona. O modelo da
Tecnologia deve confirmar se separa esse perfil e com que recall.

**Limites.** AUC modesta; scores não calibrados; teste de {br(len(i_te), 0)} assinantes, em que o valor
líquido varia com a amostra; base v1 do repositório (refazer no arquivo do case v2); a reversão vem de
uma campanha só (10/08–30/09/2026).

**Perguntas para a próxima etapa.** Qual oferta o grupo leva para o mensal (desafio ou cupom), já que
ela muda o corte, e qual aceite do cupom é realista? O modelo da Tecnologia mantém o recall acima de 80% com até 70% da persona contatada?
""")
destino = pg.salvar("08_validacao_arvore.html")
print(f"artefato: {destino.relative_to(RAIZ) if hasattr(destino, 'relative_to') else destino}")
