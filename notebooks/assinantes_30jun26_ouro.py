"""Prata -> ouro: assinantes_30jun26.csv (um assinante pagante ativo em 30/06/2026) +
artefatos/02_quem_saiu.html.

Pergunta (aula 2): entre quem pagava em 30/06/2026, quem saiu até 30/09 se comportava
diferente de quem ficou? Quais características mais separam os dois grupos?

Regras (decisões K1–K6 no decisoes.md; método e debate no memorial.md, etapa 02):
  1. Base: assinaturas.csv da prata com flag_cortesia = 0, inicio <= 30/06/2026 e data_fim
     vazia ou >= 01/07/2026 (mesma regra de "ativo no dia 1" da G1, aplicada a 01/07).
  2. saiu = 1 se data_fim cai entre 01/07 e 30/09/2026; senão 0 (ficou).
  3. Toda variável é medida até 30/06/2026, e cada log é resumido por user_id antes de juntar
     (uma linha por assinante; o notebook para se a junção multiplicar linhas):
       - assinaturas: plano, canal, método, tempo de casa em meses, início antes do histórico;
       - usuarios: sistema, sexo, idade no corte, canal de aquisição, relógio conectado;
       - atividades (abr–jun/2026): treinos, minutos, dias com treino, treinos em jun menos
         treinos em abr (tendência), % de treinos com GPS falho; sem treino = 0;
       - tickets_suporte (até 30/06): chamados e chamado de falha de GPS (texto aproximado,
         por difflib, a uma das cinco mensagens-base do incidente de mai–jun);
       - pagamentos (abr–jun): cobranças recusadas;
       - amizades (desde <= 30/06, sem flag_id_invalido): seguidores e conexões recíprocas;
       - feed_posts (abr–jun): posts;
       - onboarding: dias por semana e nível declarados.
  4. Fora de propósito: campanha_ago26 (acontece dentro da janela de saída), versao_app de
     usuarios (retrato do corte) e pesquisa_saida (só existe para quem saiu).
  5. Separação de cada variável: AUC univariada (0,5 = não separa). Numérica: AUC do valor
     contra saiu, ignorando nulos; categórica: AUC da taxa de saída da categoria (taxa
     calculada na própria base). Apoio: Mann-Whitney U (numérica) e qui-quadrado com V de
     Cramér (categórica). Taxas com intervalo de Wilson 95%.
  6. Terceira variável: a AUC e as taxas são recalculadas dentro de cada estrato de plano.
     O anual só pode sair no aniversário: vence_jul_set = 1 para o anual iniciado em jul,
     ago ou set (aniversário dentro da janela) e para todo mensal. O estrato do anual é
     "anual que vence em jul–set"; o anual que não vence quase não sai (só devolução).

Conferência com o 01_churn_mensal (o notebook para se não bater): a base é igual aos ativos
no início de jul/2026 e as saídas de jul são as perdas de jul/2026 em churn_mensal.csv.

Uso: .venv/bin/python notebooks/assinantes_30jun26_ouro.py  (a partir da raiz do repo)
"""
import difflib
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy import stats
from sklearn.metrics import roc_auc_score

from _artefato import CORES, Pagina, layout_padrao

RAIZ = Path(__file__).resolve().parent.parent
PRATA = RAIZ / "dados" / "2.prata"
OURO = RAIZ / "dados" / "3.ouro"
SAIDA = OURO / "assinantes_30jun26.csv"

REF = pd.Timestamp("2026-06-30")
JAN_INI, JAN_FIM = pd.Timestamp("2026-07-01"), pd.Timestamp("2026-09-30")
USO_INI = pd.Timestamp("2026-04-01")
FIM_REF = pd.Timestamp("2026-07-01")  # exclusivo: tudo antes de 01/07 00:00

# --- 1. base e desfecho ---------------------------------------------------------------------
a = pd.read_csv(PRATA / "assinaturas.csv", parse_dates=["inicio", "data_fim"])
a = a[(a.flag_cortesia == 0) & (a.inicio <= REF) & (a.data_fim.isna() | (a.data_fim >= JAN_INI))]
base = a[["user_id", "plano_atual", "canal", "metodo", "inicio", "data_fim",
          "flag_inicio_antes_historico"]].rename(columns={"plano_atual": "plano"}).copy()
base["saiu"] = base.data_fim.between(JAN_INI, JAN_FIM).astype(int)
base["tempo_casa_meses"] = ((REF - base.inicio).dt.days / 30.4375).round(1)
base["inicio_antes_historico"] = base.flag_inicio_antes_historico.map({1: "sim", 0: "não"})
base["vence_jul_set"] = ((base.plano == "mensal") | base.inicio.dt.month.isin([7, 8, 9])).astype(int)
N = len(base)
assert base.user_id.is_unique

cm = pd.read_csv(OURO / "churn_mensal.csv")
jul = cm[(cm.recorte == "total") & (cm.mes == "2026-07")].iloc[0]
assert N == jul.ativos_inicio, f"base {N} != ativos jul/26 {jul.ativos_inicio}"
saiu_jul = base.data_fim.dt.to_period("M").eq(pd.Period("2026-07")).sum()
assert saiu_jul == jul.perdas, f"saídas jul {saiu_jul} != perdas jul/26 {jul.perdas}"
print(f"base 30/06/2026: {N} assinantes · saíram jul–set: {base.saiu.sum()} "
      f"({base.saiu.mean():.1%}) · conferência com churn_mensal OK")

contagens = [("base: pagantes ativos em 30/06/2026", N)]


def junta(df, novo, nome):
    """Junção à esquerda por user_id; para se multiplicar linhas."""
    antes = len(df)
    df = df.merge(novo, on="user_id", how="left", validate="one_to_one")
    assert len(df) == antes, f"{nome}: {antes} -> {len(df)} linhas"
    contagens.append((f"+ {nome}", len(df)))
    return df


# --- 2. variáveis por assinante (até 30/06/2026) --------------------------------------------
u = pd.read_csv(PRATA / "usuarios.csv")
u = u[u.flag_conta_teste == 0][["user_id", "sistema", "sexo", "idade_corte", "canal_aquisicao",
                                "relogio_conectado"]].rename(columns={"idade_corte": "idade"})
base = junta(base, u, "usuarios")

t = pd.read_parquet(PRATA / "atividades.parquet",
                    columns=["user_id", "inicio_brt", "mes", "duracao_min", "gps_ok"])
t = t[(t.inicio_brt >= USO_INI) & (t.inicio_brt < FIM_REF)]
t["dia"] = t.inicio_brt.dt.date
uso = t.groupby("user_id").agg(
    treinos_abr_jun=("inicio_brt", "size"),
    minutos_abr_jun=("duracao_min", "sum"),
    dias_treino_abr_jun=("dia", "nunique"),
    treinos_gps_falho=("gps_ok", lambda s: int((~s).sum())),
).reset_index()
por_mes = t.pivot_table(index="user_id", columns="mes", values="inicio_brt", aggfunc="size",
                        fill_value=0)
uso = uso.merge((por_mes["2026-06"] - por_mes["2026-04"]).rename("tendencia_treinos_jun_abr"),
                on="user_id")
base = junta(base, uso, "atividades abr–jun")
for c in ["treinos_abr_jun", "minutos_abr_jun", "dias_treino_abr_jun", "treinos_gps_falho",
          "tendencia_treinos_jun_abr"]:
    base[c] = base[c].fillna(0)
base["pct_gps_falho"] = np.where(base.treinos_abr_jun > 0,
                                 100 * base.treinos_gps_falho / base.treinos_abr_jun, np.nan)
base["sem_treino_abr_jun"] = np.where(base.treinos_abr_jun == 0, "sim", "não")


def normaliza(s):
    s = unicodedata.normalize("NFKD", str(s).lower())
    return "".join(c for c in s if not unicodedata.combining(c)).strip()


GPS = [normaliza(m) for m in [
    "GPS parou de funcionar no meu android",
    "corrida registrada com distância zerada",
    "o app não grava meu percurso desde a atualização",
    "perdi meus treinos da semana, o app travou no meio",
    "a rota sai toda torta e a distância errada",
]]
tk = pd.read_csv(PRATA / "tickets_suporte.csv", parse_dates=["aberto_em"])
tk = tk[tk.aberto_em < FIM_REF].copy()
tk["gps"] = tk.texto_cliente.map(
    lambda x: int(bool(difflib.get_close_matches(normaliza(x), GPS, n=1, cutoff=0.8))))
sup = tk.groupby("user_id").agg(chamados_ate_jun=("ticket_id", "size"),
                                chamados_gps=("gps", "sum")).reset_index()
base = junta(base, sup, "tickets até 30/06")
base[["chamados_ate_jun", "chamados_gps"]] = base[["chamados_ate_jun", "chamados_gps"]].fillna(0)
base["teve_chamado"] = np.where(base.chamados_ate_jun > 0, "sim", "não")
base["chamado_gps"] = np.where(base.chamados_gps > 0, "sim", "não")
print(f"chamados até 30/06 classificados como GPS: {int(tk.gps.sum())} de {len(tk)}")

pg = pd.read_csv(PRATA / "pagamentos.csv", parse_dates=["data_hora_brt"])
pg = pg[(pg.data_hora_brt >= USO_INI) & (pg.data_hora_brt < FIM_REF) & (pg.status == "recusado")]
base = junta(base, pg.groupby("user_id").size().rename("recusas_abr_jun").reset_index(),
             "pagamentos recusados abr–jun")
base["recusas_abr_jun"] = base.recusas_abr_jun.fillna(0)
base["teve_recusa"] = np.where(base.recusas_abr_jun > 0, "sim", "não")

z = pd.read_csv(PRATA / "amizades.csv", parse_dates=["desde"])
z = z[(z.desde <= REF) & (z.flag_id_invalido == 0)]
soc = (z.groupby("seguido_id").size().rename("seguidores").reset_index()
       .rename(columns={"seguido_id": "user_id"})
       .merge(z[z.reciproco == 1].groupby("seguidor_id").size().rename("conexoes_reciprocas")
              .reset_index().rename(columns={"seguidor_id": "user_id"}), on="user_id", how="outer"))
base = junta(base, soc, "amizades até 30/06")
base[["seguidores", "conexoes_reciprocas"]] = base[["seguidores", "conexoes_reciprocas"]].fillna(0)

fp = pd.read_csv(PRATA / "feed_posts.csv", parse_dates=["data_hora"])
fp = fp[(fp.data_hora >= USO_INI) & (fp.data_hora < FIM_REF)]
base = junta(base, fp.groupby("user_id").size().rename("posts_abr_jun").reset_index(),
             "posts abr–jun")
base["posts_abr_jun"] = base.posts_abr_jun.fillna(0)

ob = pd.read_csv(PRATA / "onboarding.csv")[["user_id", "dias_por_semana", "nivel"]]
base = junta(base, ob, "onboarding")

base = base.drop(columns=["flag_inicio_antes_historico", "treinos_gps_falho"])
OURO.mkdir(parents=True, exist_ok=True)
base.to_csv(SAIDA, index=False)
print(f"{SAIDA.relative_to(RAIZ)}: {len(base)} linhas, {base.shape[1]} colunas")

# --- 3. separação de cada variável ---------------------------------------------------------
NUM = {
    "tempo_casa_meses": "tempo de casa (meses)",
    "treinos_abr_jun": "treinos abr–jun",
    "minutos_abr_jun": "minutos de treino abr–jun",
    "dias_treino_abr_jun": "dias com treino abr–jun",
    "tendencia_treinos_jun_abr": "treinos jun − treinos abr",
    "pct_gps_falho": "% de treinos com GPS falho",
    "chamados_ate_jun": "chamados até 30/06",
    "recusas_abr_jun": "cobranças recusadas abr–jun",
    "seguidores": "seguidores",
    "conexoes_reciprocas": "conexões recíprocas",
    "posts_abr_jun": "posts abr–jun",
    "dias_por_semana": "dias por semana (onboarding)",
    "idade": "idade",
}
CAT = {
    "plano": "plano", "metodo": "método de pagamento", "canal": "canal",
    "sistema": "sistema do celular", "sexo": "sexo", "canal_aquisicao": "canal de aquisição",
    "relogio_conectado": "relógio conectado", "nivel": "nível (onboarding)",
    "sem_treino_abr_jun": "sem treino abr–jun", "teve_chamado": "abriu chamado",
    "chamado_gps": "chamado de GPS", "teve_recusa": "teve cobrança recusada",
    "inicio_antes_historico": "início antes de jul/24",
}


def wilson(k, n, z=1.96):
    if n == 0:
        return np.nan, np.nan
    p = k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    m = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return c - m, c + m


def separacao(df):
    linhas = []
    for col, nome in NUM.items():
        d = df[[col, "saiu"]].dropna()
        auc = roc_auc_score(d.saiu, d[col])
        s, f = d[d.saiu == 1][col], d[d.saiu == 0][col]
        p = stats.mannwhitneyu(s, f).pvalue
        linhas.append({"variável": nome, "coluna": col, "tipo": "numérica", "n": len(d),
                       "AUC": max(auc, 1 - auc),
                       "sentido": "maior → sai mais" if auc > 0.5 else "menor → sai mais",
                       "saiu: mediana [Q1–Q3]": f"{s.median():.1f} [{s.quantile(.25):.1f}–{s.quantile(.75):.1f}]",
                       "ficou: mediana [Q1–Q3]": f"{f.median():.1f} [{f.quantile(.25):.1f}–{f.quantile(.75):.1f}]",
                       "efeito": np.nan, "p": p})
    for col, nome in CAT.items():
        d = df[[col, "saiu"]].dropna()
        if d[col].nunique() < 2:
            continue
        taxa = d.groupby(col).saiu.transform("mean")
        auc = roc_auc_score(d.saiu, taxa)
        tab = pd.crosstab(d[col], d.saiu)
        chi2, p, _, _ = stats.chi2_contingency(tab)
        v = np.sqrt(chi2 / (tab.values.sum() * (min(tab.shape) - 1)))
        tx = d.groupby(col).saiu.mean().sort_values()
        linhas.append({"variável": nome, "coluna": col, "tipo": "categórica", "n": len(d),
                       "AUC": auc, "sentido": f"mais saída: {tx.index[-1]} ({tx.iloc[-1]:.0%})",
                       "saiu: mediana [Q1–Q3]": "", "ficou: mediana [Q1–Q3]": "",
                       "efeito": v, "p": p})
    return pd.DataFrame(linhas).sort_values("AUC", ascending=False).reset_index(drop=True)


ESTRATOS = {
    "mensal": base.plano == "mensal",
    "anual que vence": (base.plano == "anual") & (base.vence_jul_set == 1),
}
sep = separacao(base)
sep_plano = {e: separacao(base[m]) for e, m in ESTRATOS.items()}
print(sep[["variável", "AUC", "sentido", "n"]].round(3).to_string(index=False))
for e, s in sep_plano.items():
    print(f"\n{e}:\n" + s[["variável", "AUC", "sentido"]].head(8).round(3).to_string(index=False))


def taxa_por(df, col, rotulos=None):
    g = df.groupby(col, observed=True).saiu.agg(["sum", "size"]).reset_index()
    g["taxa"] = 100 * g["sum"] / g["size"]
    ic = [wilson(k, n) for k, n in zip(g["sum"], g["size"])]
    g["ic_baixo"] = [100 * x[0] for x in ic]
    g["ic_alto"] = [100 * x[1] for x in ic]
    return g


def faixas(df, col, q=5):
    """Quintis da variável; com muitos empates (zeros) as faixas se fundem."""
    x = df[col]
    cortes = np.unique(np.nanquantile(x, np.linspace(0, 1, q + 1)))
    if len(cortes) <= 2:
        return pd.Series(np.where(x > cortes[0], f"> {cortes[0]:g}", f"{cortes[0]:g}"), index=df.index)
    fx = pd.cut(x, cortes, include_lowest=True, duplicates="drop")
    return fx.map(lambda i: f"{max(i.left, x.min()):.0f}–{i.right:.0f}").astype(str).where(fx.notna())


# --- 4. artefato ------------------------------------------------------------------------------
def br(x, d=1):
    """Número no padrão brasileiro: 14.059 · 16,7."""
    return f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def taxa(m):
    return 100 * base.loc[m, "saiu"].mean()


mens, anual = base.plano == "mensal", base.plano == "anual"
an_vence = ESTRATOS["anual que vence"]
an_nao = anual & (base.vence_jul_set == 0)
android = base.sistema == "android"
gps_sim = base.pct_gps_falho > 0

p = Pagina(
    "02 · Quem saiu se comportava diferente?",
    "Entre os pagantes ativos em 30/06/2026, o que separa quem saiu até 30/09 de quem ficou.",
    "fonte: `dados/3.ouro/assinantes_30jun26.csv`, gerada por "
    "`notebooks/assinantes_30jun26_ouro.py` (decisões K1–K6) · método em `memorial.md`, etapa 02",
)
p.texto(f"""
**Regra.** Base: as {br(N, 0)} assinaturas pagas ativas em 30/06/2026 (as mesmas dos ativos no
início de jul/26 do `01_churn_mensal`). **Saiu**: a assinatura terminou entre 01/07 e
30/09/2026 ({br(base.saiu.sum(), 0)} assinantes, {br(taxa(base.index == base.index))}%).
**Ficou**: o restante. Toda característica é medida até 30/06/2026; uso, posts e cobranças
olham o trimestre abr–jun.
""")

p.secao("A base e as junções")
p.tabela(pd.DataFrame(contagens, columns=["etapa", "linhas"]),
         "Linhas depois de cada junção (uma por assinante em todas)", {"linhas": "{:,.0f}"})

p.secao("Primeiro corte: plano e calendário")
cal = pd.DataFrame([
    ("mensal", mens.sum(), base.loc[mens, "saiu"].sum()),
    ("anual que vence em jul–set", an_vence.sum(), base.loc[an_vence, "saiu"].sum()),
    ("anual que não vence em jul–set", an_nao.sum(), base.loc[an_nao, "saiu"].sum()),
], columns=["estrato", "assinantes", "saíram"])
cal["saída (%)"] = 100 * cal["saíram"] / cal["assinantes"]
p.tabela(cal, "Saída em jul–set por estrato", {"assinantes": "{:,.0f}", "saíram": "{:,.0f}",
                                               "saída (%)": "{:.1f}"})
p.texto(f"""
- O mensal pode sair todo mês: {br(taxa(mens))}% saíram em três meses.
- O anual só sai no aniversário. Dos {br(anual.sum(), 0)} anuais, {br(an_vence.sum(), 0)}
  venciam em jul–set, e **{br(taxa(an_vence))}% deles não renovaram**. Os outros
  {br(an_nao.sum(), 0)} tiveram {base.loc[an_nao, 'saiu'].sum()} saídas (devoluções).
- Por isso as comparações abaixo usam dois estratos comparáveis: **mensal** e **anual que vence
  em jul–set**. Olhar o anual inteiro mede o calendário, não o comportamento.
""")

p.secao("O que mais separa quem saiu de quem ficou")
comp = sep[["variável", "tipo", "AUC"]].rename(columns={"AUC": "AUC base"})
for e, s in sep_plano.items():
    comp = comp.merge(s[["variável", "AUC", "sentido"]].rename(
        columns={"AUC": f"AUC {e}", "sentido": f"sentido {e}"}), on="variável", how="left")
comp = comp.sort_values("AUC mensal", ascending=False)
top = comp[comp["variável"] != "plano"].head(12).iloc[::-1]
f = go.Figure()
for i, e in enumerate(ESTRATOS):
    f.add_trace(go.Bar(x=top[f"AUC {e}"], y=top["variável"], orientation="h", name=e,
                       marker_color=CORES[i],
                       hovertemplate=f"{e} · %{{y}}: AUC %{{x:.3f}}<extra></extra>"))
f.add_vline(x=0.5, line=dict(color="#52514e", width=1, dash="dot"))
layout_padrao(f, altura=520)
f.update_xaxes(range=[0.45, 0.85], title_text="AUC univariada")
f.update_layout(barmode="group", hovermode="closest", margin=dict(l=220, t=48))
p.figura(f, "AUC de cada variável sozinha para separar saiu × ficou, dentro de cada estrato "
            "(0,5 = não separa, 1 = separa todos). Ordem: AUC no mensal.")
p.tabela(comp, "AUC na base inteira e dentro de cada estrato",
         {c: "{:.3f}" for c in comp.columns if c.startswith("AUC")})
p.texto("""
**Como ler.** AUC é a chance de um assinante que saiu, sorteado, ter valor "mais de saída" que
um que ficou. Na base inteira, o plano domina e mistura os dois mundos; dentro dos estratos
aparece o que de fato separa cada um.
""")
p.tabela(sep.drop(columns=["coluna"]), "Detalhe na base inteira: centro, dispersão e efeito",
         {"AUC": "{:.3f}", "efeito": "{:.3f}", "p": "{:.1e}", "n": "{:,.0f}"})
p.texto("""
Efeito = V de Cramér (categóricas, 0 a 1). Com 14 mil assinantes quase todo p é minúsculo: o
critério é o tamanho do efeito (AUC, V, diferença em p.p.), e o p entra só como apoio.
""")


def grafico_faixas(col, titulo):
    nome = NUM[col]
    p.secao(titulo)
    f = go.Figure()
    for i, (e, m) in enumerate(ESTRATOS.items()):
        d = base[m].copy()
        d["faixa"] = faixas(d, col)
        g = taxa_por(d.dropna(subset=["faixa"]), "faixa")
        ordem = d.groupby("faixa")[col].min().sort_values().index
        g = g.set_index("faixa").loc[ordem].reset_index()
        f.add_trace(go.Bar(x=[[e] * len(g), g.faixa], y=g.taxa, name=e, marker_color=CORES[i],
                           error_y=dict(type="data", symmetric=False,
                                        array=g.ic_alto - g.taxa, arrayminus=g.taxa - g.ic_baixo,
                                        color="#52514e", thickness=1),
                           customdata=g["size"],
                           hovertemplate=f"{e} · %{{x}}: %{{y:.1f}}% de %{{customdata:,}}<extra></extra>"))
    layout_padrao(f, "saíram jul–set (%)")
    f.update_layout(hovermode="closest", margin=dict(t=48), showlegend=False)
    f.update_xaxes(title_text=f"{nome} · faixas por quintil dentro do estrato")
    p.figura(f, "Barra: % que saiu em jul–set. Traço: intervalo de Wilson 95%. As faixas são "
                "quintis dentro de cada estrato; com muitos empates, quintis se fundem.")

    f = go.Figure()
    for i, (k, rot) in enumerate([(0, "ficou"), (1, "saiu")]):
        for j, (e, m) in enumerate(ESTRATOS.items()):
            d = base[m & (base.saiu == k)][col].dropna()
            f.add_trace(go.Box(y=d, x=[e] * len(d), name=rot, marker_color=CORES[2 + i],
                               boxpoints=False, offsetgroup=rot, legendgroup=rot,
                               showlegend=(j == 0)))
    layout_padrao(f, nome)
    f.update_layout(boxmode="group", hovermode="closest", margin=dict(t=48))
    p.figura(f, f"Distribuição de {nome}, saiu × ficou, por estrato (caixa = Q1 a Q3; "
                "linha = mediana; bigodes até 1,5 × IQR).")


m_tc = base[mens].groupby(pd.cut(base.loc[mens, "tempo_casa_meses"], [-1, 3, 6, 12, 24, 999]),
                          observed=True).saiu.mean() * 100
grafico_faixas("tempo_casa_meses", "Mensal: quem acabou de chegar sai mais")
p.texto(f"""
- No mensal, a saída cai com o tempo de casa: {br(m_tc.iloc[0])}% entre quem tinha até 3 meses,
  {br(m_tc.iloc[2])}% de 6 a 12 meses e {br(m_tc.iloc[4])}% acima de 24 meses.
- No anual que vence, o tempo de casa mede quantas renovações já passaram e separa menos
  (AUC {br(sep_plano['anual que vence'].set_index('coluna').loc['tempo_casa_meses', 'AUC'], 2)}):
  a primeira renovação perde mais que as seguintes.
- Limite: assinaturas antigas só existem se sobreviveram até jul/24 (viés de sobrevivência,
  A5). Parte da queda pode ser seleção: quem ficaria muito tempo já está entre os antigos.
""")

an_q = base[an_vence].groupby(faixas(base[an_vence], "dias_treino_abr_jun"), observed=True).saiu.mean() * 100
grafico_faixas("dias_treino_abr_jun", "Anual: quem parou de treinar não renova")
sem_an = base[an_vence].groupby(base.loc[an_vence, "treinos_abr_jun"] == 0).saiu.mean() * 100
p.texto(f"""
- No anual que vence, dias com treino em abr–jun é a variável que mais separa
  (AUC {br(sep_plano['anual que vence'].set_index('coluna').loc['dias_treino_abr_jun', 'AUC'], 2)}).
  Sem nenhum treino no trimestre, {br(sem_an.loc[True])}% não renovaram; com treino,
  {br(sem_an.loc[False])}%.
- No mensal a relação existe, mas é mais fraca
  (AUC {br(sep_plano['mensal'].set_index('coluna').loc['dias_treino_abr_jun', 'AUC'], 2)}): a
  saída é maior no quintil de menor uso e se estabiliza a partir do terceiro.
- Treinos, minutos e dias com treino têm ρ de Spearman acima de 0,95 entre si (abaixo): são um
  único sinal de engajamento, não três.
""")

p.secao("Categorias: taxa de saída com intervalo")
for col in ["metodo", "sistema", "canal_aquisicao", "relogio_conectado", "teve_recusa"]:
    g = pd.concat([taxa_por(base[m], col).assign(estrato=e) for e, m in ESTRATOS.items()])
    g = g.rename(columns={col: "categoria", "size": "assinantes", "sum": "saíram",
                          "taxa": "saída (%)", "ic_baixo": "IC 95% baixo", "ic_alto": "IC 95% alto"})
    p.tabela(g[["estrato", "categoria", "assinantes", "saíram", "saída (%)", "IC 95% baixo", "IC 95% alto"]],
             CAT[col], {"assinantes": "{:,.0f}", "saíram": "{:,.0f}", "saída (%)": "{:.1f}",
                        "IC 95% baixo": "{:.1f}", "IC 95% alto": "{:.1f}"})

p.secao("GPS falho: só existe no android")
gps = base[mens & android].groupby(gps_sim[mens & android]).saiu.agg(["sum", "size"])
gps.index = gps.index.map({True: "teve treino com GPS falho", False: "sem GPS falho"})
gps["saída (%)"] = 100 * gps["sum"] / gps["size"]
ic = [wilson(k, n) for k, n in zip(gps["sum"], gps["size"])]
gps["IC 95%"] = [f"{100 * a:.1f}–{100 * b:.1f}" for a, b in ic]
ios_tx = taxa(mens & ~android)
p.tabela(gps.reset_index().rename(columns={"pct_gps_falho": "mensal no android", "sum": "saíram",
                                           "size": "assinantes"}),
         "Mensal no android: saída por GPS falho em mai–jun", {"saída (%)": "{:.1f}"})
p.texto(f"""
- O GPS falho aparece só na versão nova do app no android (T5). Comparado dentro do android
  mensal, quem teve treino com GPS falho saiu {br(gps['saída (%)'].iloc[1] - gps['saída (%)'].iloc[0])}
  p.p. a mais ({br(gps['saída (%)'].iloc[1])}% contra {br(gps['saída (%)'].iloc[0])}%). O iOS
  mensal ficou em {br(ios_tx)}%.
- O chamado de GPS quase não separa (AUC 0,50): poucos reclamam; o sinal está no treino que
  falhou, não no chamado.
- Limite: quem teve GPS falho é quem corria ao ar livre no android em mai–jun; pode ser o perfil
  de uso, não a falha. A diferença é suspeita a investigar, não causa.
""")

p.secao("Variáveis que contam a mesma história")
nums = [c for c in NUM if c != "pct_gps_falho"]
rho = base[nums].corr(method="spearman").round(2)
rot = [NUM[c] for c in nums]
f = go.Figure(go.Heatmap(z=rho.values, x=rot, y=rot, zmin=-1, zmax=1,
                         colorscale=[[0, CORES[1]], [0.5, "#fcfcfb"], [1, CORES[0]]],
                         text=rho.values, texttemplate="%{text:.2f}", textfont=dict(size=10),
                         hovertemplate="%{y} × %{x}: ρ = %{z:.2f}<extra></extra>"))
layout_padrao(f, altura=560)
f.update_layout(hovermode="closest", margin=dict(l=200, b=160))
f.update_xaxes(tickangle=-45)
p.figura(f, "Correlação de Spearman entre as variáveis numéricas (base inteira). Acima de 0,7: "
            "as duas medem quase a mesma coisa e não devem virar dois eixos da segmentação.")

p.secao("Três frases")
p.texto(f"""
- **O que o dado diz.** Há dois mundos de saída: no mensal, quem acabou de chegar sai mais
  ({br(m_tc.iloc[0])}% até 3 meses de casa contra {br(m_tc.iloc[4])}% acima de 2 anos); no anual,
  quem chega ao vencimento sem treinar não renova ({br(sem_an.loc[True])}% sem treino no
  trimestre contra {br(sem_an.loc[False])}% com treino).
- **O que ele não diz.** Que pouco uso ou pouco tempo de casa **causam** a saída: tempo de casa
  carrega viés de sobrevivência, e uso baixo pode ser consequência de quem já decidiu sair
  (causalidade reversa).
- **A próxima pergunta.** Esses dois sinais, mais android com GPS falho e método de pagamento,
  formam segmentos distintos quando cruzados, ou são o mesmo grupo visto de ângulos diferentes?
""")

p.secao("Limites")
p.texto("""
- Uma janela só (jul–set/2026), depois do reajuste e do incidente de GPS: não diz se o padrão
  vale em 2025.
- `atividades` só cobre 2026; o uso de abr–jun não pode ser comparado com o ano anterior.
- Idade é a do corte (30/09/2026), não a de 30/06: diferença de no máximo três meses.
- Categorias com poucos assinantes têm intervalos largos; leia o IC antes da taxa.
- AUC das categóricas usa a taxa calculada na própria base: é otimista para categorias pequenas.
""")

p.secao("Perguntas para a próxima etapa")
p.texto("""
- Segmentação (aula 3): agrupar os assinantes por engajamento, tempo de casa, plano e
  experiência técnica (android × GPS falho), e checar se os grupos têm taxas de saída distintas.
- Separar a saída voluntária (desligou a renovação) da involuntária (falha de pagamento): a
  recusa de cobrança separa pouco no total, mas pode concentrar um segmento.
- Trazer as variáveis de texto (objetivo do onboarding, intenção de sair no feed) depois da
  extração com IA: "objetivo cumprido" é o tema dominante da pesquisa de saída.
""")

destino = p.salvar("02_quem_saiu.html")
print(f"artefato: {destino.relative_to(RAIZ)}")
