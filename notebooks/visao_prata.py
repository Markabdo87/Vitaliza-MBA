"""Prata -> artefatos/analises/00b_visao_prata.html: primeiro olhar depois da limpeza.

Página de apoio para o grupo, não é tabela de análise nem conclusão. Mostra o que a limpeza
mudou em cada tabela e, tabela a tabela, os sinais que já aparecem e merecem atenção nas
próximas etapas. Cada sinal é uma hipótese a conferir, não um resultado.

Regras dos números (todos calculados aqui, só da prata):
  1. Base paga = assinaturas com flag_cortesia = 0; contas de cliente = flag_conta_teste = 0.
  2. Churn mensal = perdas no mês ÷ ativos no dia 1 (mesma regra G1 do churn_mensal_ouro.py),
     conferida contra `dados/3.ouro/churn_mensal.csv` quando ele existe e está em dia.
  3. Uso mensal só nos meses com treino (flag_sem_treino = 0), para comparar 2025 com 2026.
  4. Variáveis com data depois do corte ficam de fora (flag_apos_corte = 0).
  5. Campanha: saída até 30/09/2026 = data_fim de assinaturas entre 10/08 e 30/09/2026.

Uso: .venv/bin/python notebooks/visao_prata.py  (a partir da raiz do repo)
"""
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import pyarrow.parquet as pq

from _artefato import CORES, Pagina, eixo_meses, layout_padrao, linha

RAIZ = Path(__file__).resolve().parent.parent
BRONZE = RAIZ / "dados" / "1.bronze"
PRATA = RAIZ / "dados" / "2.prata"
OURO = RAIZ / "dados" / "3.ouro"
NOTEBOOKS = RAIZ / "notebooks"
# Página de apoio, não artefato de entrega: fica na subpasta de análises intermediárias.
APOIO = RAIZ / "artefatos" / "analises"
RODAR_OURO = ".venv/bin/python notebooks/churn_mensal_ouro.py"


def fmt(n):
    return f"{n:,.0f}".replace(",", ".")


def pct(v, casas=1):
    return f"{v:.{casas}f}%".replace(".", ",")


def mes_dt(s):
    return pd.PeriodIndex(s, freq="M").to_timestamp()


# ---------------------------------------------------------------- leitura
u = pd.read_csv(PRATA / "usuarios.csv", low_memory=False)
a = pd.read_csv(PRATA / "assinaturas.csv", parse_dates=["inicio", "data_fim"])
ev = pd.read_csv(PRATA / "eventos_assinatura.csv", usecols=["user_id", "mes", "evento"])
pg = pd.read_csv(PRATA / "pagamentos.csv", low_memory=False)
um = pd.read_csv(PRATA / "uso_mensal.csv")
at = pd.read_parquet(PRATA / "atividades.parquet", columns=["user_id", "mes", "gps_ok", "origem"])
am = pd.read_csv(PRATA / "amizades.csv")
cp = pd.read_csv(PRATA / "campanha_ago26.csv")
ob = pd.read_csv(PRATA / "onboarding.csv")
fp = pd.read_csv(PRATA / "feed_posts.csv")
ps = pd.read_csv(PRATA / "pesquisa_saida.csv")
tk = pd.read_csv(PRATA / "tickets_suporte.csv")

TABELAS = {"usuarios": u, "assinaturas": a, "eventos_assinatura": None, "pagamentos": pg,
           "uso_mensal": um, "atividades": None, "amizades": am, "campanha_ago26": cp,
           "onboarding": ob, "feed_posts": fp, "pesquisa_saida": ps, "tickets_suporte": tk}

# ---------------------------------------------------------------- o que a limpeza fez
limpeza = []
for nome, df in TABELAS.items():
    if nome == "atividades":
        n_bronze = pq.ParquetFile(BRONZE / "atividades.parquet").metadata.num_rows
        df = pd.read_parquet(PRATA / "atividades.parquet")
    else:
        with open(BRONZE / f"{nome}.csv", encoding="utf-8") as f:
            n_bronze = sum(1 for _ in f) - 1
        if df is None:
            df = pd.read_csv(PRATA / f"{nome}.csv", low_memory=False)
    flags = [c for c in df.columns if c.startswith("flag_")]
    corrigidas = [c[:-7] for c in df.columns if c.endswith("_bronze")]
    marcadas = int((df[flags].fillna(0).astype(float) > 0).any(axis=1).sum()) if flags else 0
    limpeza.append({"tabela": nome, "bronze": fmt(n_bronze), "prata": fmt(len(df)),
                    "removidas": fmt(n_bronze - len(df)),
                    "linhas com alguma flag": fmt(marcadas),
                    "colunas corrigidas (original guardado)": ", ".join(corrigidas) or "—"})
limpeza = pd.DataFrame(limpeza)

# ---------------------------------------------------------------- churn mensal (regra G1)
base = a[a.flag_cortesia == 0].merge(
    u[["user_id", "canal_aquisicao", "sistema", "relogio_conectado"]], on="user_id", how="left")
painel = []
for m in pd.period_range("2025-01", "2026-09", freq="M"):
    ini, fim = m.start_time, m.end_time
    ativo = base[(base.inicio < ini) & (base.data_fim.isna() | (base.data_fim >= ini))].copy()
    ativo["saiu"] = (ativo.data_fim <= fim).astype(int)
    ativo["mes"] = str(m)
    painel.append(ativo)
painel = pd.concat(painel)
painel["ano"] = painel.mes.str[:4]
mensal = painel[painel.plano_atual == "mensal"]


def media_meses(df, col):
    """Média, no ano, das taxas mensais de cada segmento (como o G1): linhas = ano."""
    taxa = df.groupby(["mes", col]).saiu.mean().mul(100).unstack()
    return taxa.groupby(taxa.index.str[:4]).mean()


def conferir_churn_ouro(serie):
    """Confere a série de churn daqui contra dados/3.ouro/churn_mensal.csv (regra G1).

    Três situações, porque a prata roda antes do ouro:
      1. o ouro não existe: a conferência é pulada com o comando que a habilita;
      2. o ouro existe mas é mais velho que o `assinaturas.csv` que ele resume ou que o
         `churn_mensal_ouro.py`: aí um número diferente é ouro obsoleto, não divergência de
         regra — avisa e pula, senão a página deixaria de sair toda vez que a prata fosse
         regerada antes do ouro;
      3. ouro em dia: ativos e perdas de cada mês têm que bater, senão `assert` antes de
         gravar a página (o número divergente não chega ao HTML).

    As duas contas partem da mesma prata (`assinaturas.csv`, flag_cortesia = 0), então
    divergência só vem de regra diferente nos dois notebooks ou de ouro não regerado. Só os
    meses presentes nos dois arquivos são comparados (o ouro começa em ago/24, esta página
    em jan/25).
    """
    arq = OURO / "churn_mensal.csv"
    rel = arq.relative_to(RAIZ)
    if not arq.exists():
        print(f"aviso: falta {rel} — série de churn não conferida (rode {RODAR_OURO})")
        return
    fontes = [PRATA / "assinaturas.csv", NOTEBOOKS / "churn_mensal_ouro.py"]
    velhas = [str(f.relative_to(RAIZ)) for f in fontes
              if f.exists() and f.stat().st_mtime > arq.stat().st_mtime]
    if velhas:
        print(f"aviso: {rel} é mais velho que {', '.join(velhas)} — série de churn não "
              f"conferida (rode {RODAR_OURO} e depois esta página de novo)")
        return

    ouro = pd.read_csv(arq)
    ouro = ouro[(ouro.recorte == "total") & (ouro.segmento == "total")].set_index("mes")
    aqui = serie.set_index("mes")
    comuns = aqui.index.intersection(ouro.index).sort_values()
    if len(comuns) == 0:
        print(f"aviso: {rel} e esta página não têm mês em comum — série de churn não "
              f"conferida (rode {RODAR_OURO})")
        return
    comp = pd.DataFrame({"ativos aqui": aqui.loc[comuns, "ativos"],
                         "ativos ouro": ouro.loc[comuns, "ativos_inicio"],
                         "perdas aqui": aqui.loc[comuns, "perdas"],
                         "perdas ouro": ouro.loc[comuns, "perdas"]})
    maus = comp.index[(comp["ativos aqui"] != comp["ativos ouro"])
                      | (comp["perdas aqui"] != comp["perdas ouro"])]
    detalhe = comp.loc[maus].head(8).to_string()
    assert len(maus) == 0, (
        f"série de churn diverge de {rel} em {len(maus)} de {len(comuns)} meses "
        f"({', '.join(maus[:4])}{'…' if len(maus) > 4 else ''}):\n{detalhe}\n"
        f"as duas contas leem a mesma prata, então ou a regra G1 mudou em um dos dois "
        f"notebooks, ou o ouro não foi regerado. Confira os dois e rode {RODAR_OURO} "
        f"e esta página de novo.")
    print(f"conferência com {rel}: ativos e perdas batem em {len(comuns)} meses "
          f"({comuns[0]}–{comuns[-1]})")

# ---------------------------------------------------------------- página
p = Pagina(
    "Primeiro olhar: a prata",
    "Os dados depois da limpeza: o que mudou e os sinais que já aparecem em cada tabela. "
    "Página de apoio para o grupo. Cada sinal é uma pista a conferir, não uma conclusão.",
    "Fonte: `dados/2.prata/` (corte 30/09/2026). Gerado por `notebooks/visao_prata.py`.",
)
p.texto("""
A prata é a bronze limpa, uma tabela por arquivo e no mesmo grão. Remoção só em duplicata
comprovada; o resto foi corrigido (o valor original fica numa coluna `<coluna>_bronze`) ou
marcado com uma coluna `flag_*` para cada um decidir se filtra. As regras estão na
docstring de cada `notebooks/<tabela>_prata.py` e o porquê no `decisoes.md`.

Nesta página, os números de churn usam a regra do grupo (G1): perdas no mês ÷ ativos no
dia 1, só a base paga. A série completa está em `artefatos/01_churn_mensal.html`.""")

p.secao("O que a limpeza mudou")
p.tabela(limpeza)
p.texto("""
- Só três tabelas perderam linhas, todas por duplicata: **959 contas** copiadas em
`usuarios`, **1.941 cobranças** gravadas duas vezes em `pagamentos` e **3.367 treinos**
em `atividades` — 1.900 em dobro (relógio + app, mesmas medidas) e 1.467 no mesmo minuto do
mesmo usuário, que ficam com um só registro (T12).
- "Linhas com alguma flag" não é erro: inclui marcações de contexto, como mês sem treino
em `uso_mensal` ou assinatura iniciada antes do histórico. Leia o nome da flag antes de
filtrar.""")

# ---- 1. assinaturas
p.secao("assinaturas: a base parou de crescer e quase todo mundo sai por vontade própria")
serie = painel.groupby("mes").agg(ativos=("saiu", "size"), perdas=("saiu", "sum")).reset_index()
serie["churn"] = 100 * serie.perdas / serie.ativos
conferir_churn_ouro(serie)
f = go.Figure()
linha(f, mes_dt(serie.mes), serie.ativos, "assinantes ativos no dia 1", CORES[0])
layout_padrao(f, "assinantes", altura=260)
eixo_meses(f, "2025-01-01", "2026-09-01")
p.figura(f, "Assinantes pagantes ativos no início de cada mês, jan/25–set/26.")
por_ano = media_meses(painel, "plano_atual")
motivo = a[a.flag_cortesia == 0].motivo_fim.value_counts(normalize=True).mul(100)
p.texto(f"""
- A base cresce até mar/26 e depois fica parada, perto de 14 mil: desde então entra tanta
gente quanto sai.
- Churn médio do plano **mensal** (média dos meses): {pct(por_ano.loc['2025', 'mensal'])} em 2025 →
{pct(por_ano.loc['2026', 'mensal'])} em 2026. O **anual** fica perto de 3%
({pct(por_ano.loc['2025', 'anual'])} → {pct(por_ano.loc['2026', 'anual'])}). A alta é do mensal.
- **{pct(motivo['renovacao_desligada'], 0)} das saídas são renovação desligada** pelo
cliente; falha de pagamento é {pct(motivo['falha_pagamento'], 0)} e chargeback
{pct(motivo['chargeback'], 0)}. O problema é de vontade, não de cobrança.""")

# ---- 2. usuarios
p.secao("usuarios: o influenciador virou o maior canal de aquisição")
cad = u[(u.flag_conta_teste == 0) & (u.mes_cadastro >= "2024-07")].copy()
cad["semestre"] = cad.mes_cadastro.str[:4] + "-S" + ((cad.mes_cadastro.str[5:7].astype(int) - 1)
                                                     // 6 + 1).astype(str)
mix = pd.crosstab(cad.semestre, cad.canal_aquisicao, normalize="index").mul(100)
f = go.Figure()
for i, c in enumerate(["influenciador", "organico", "meta_ads", "indicacao", "google_ads",
                       "parceria_corporativa"]):
    linha(f, mix.index, mix[c], c, CORES[i])
layout_padrao(f, "% dos cadastros", altura=300)
p.figura(f, "Participação de cada canal nos cadastros de clientes, por semestre (jul/24–set/26).")
ch_canal = media_meses(mensal, "canal_aquisicao").T.sort_values("2026", ascending=False)
p.tabela(pd.DataFrame({"canal": ch_canal.index,
                       "churn mensal 2025": ch_canal["2025"].map(pct),
                       "churn mensal 2026": ch_canal["2026"].map(pct)}),
         "Churn médio do plano mensal por canal de aquisição")
p.texto(f"""
- O influenciador sai de ~{pct(mix.loc['2025-S1', 'influenciador'], 0)} dos cadastros no
1º semestre de 2025 para {pct(mix.iloc[-1]['influenciador'], 0)} em jul–set/2026, e é o canal
que mais perde assinante.
- **A conferir:** quanto da alta do churn é só mudança de mix (mais gente de um canal que
sempre saiu mais) e quanto é piora dentro de cada canal.""")

# ---- 3. atividades × sistema
p.secao("atividades: o GPS falho é só do Android, e o churn do Android sobe em seguida")
at2 = at[at.mes >= "2026-03"].merge(u[["user_id", "sistema"]], on="user_id", how="left")
gps = (at2.assign(falho=at2.gps_ok == False)  # noqa: E712 (coluna bool com nulos)
       .groupby(["mes", "sistema"]).falho.mean().mul(100).unstack())
ch_sis = mensal[mensal.ano == "2026"].groupby(["mes", "sistema"]).saiu.mean().mul(100).unstack()
f = go.Figure()
linha(f, mes_dt(ch_sis.index), ch_sis["android"], "churn mensal · Android", CORES[1])
linha(f, mes_dt(ch_sis.index), ch_sis["ios"], "churn mensal · iOS", CORES[0])
layout_padrao(f, "% ao mês", altura=280)
eixo_meses(f, "2026-01-01", "2026-09-01", passo=1)
p.figura(f, "Churn mensal do plano mensal por sistema do celular, 2026.")
tab = pd.DataFrame({"mês": gps.index, "% treinos GPS falho · Android": gps["android"].map(pct),
                    "% treinos GPS falho · iOS": gps["ios"].map(pct)})
p.tabela(tab, "Treinos com GPS falho por sistema (mar–set/26)")
p.texto("""
- O GPS falho aparece em mai–jun/26 e **só no Android**. O churn do Android descola do
iOS em jun–jul e volta a encostar em agosto.
- O pico de **abril** é outro fenômeno: atinge Android e iOS por igual e vem logo depois
do reajuste de preço (R$ 34,90 → 39,90 em 01/03/26). Duas causas, dois momentos.""")

# ---- 4. tickets
p.secao("tickets_suporte: o incidente de mai–jun aparece no suporte")
tk["grupo"] = tk.categoria_atendente.where(tk.categoria_atendente == "tecnico", "outras categorias")
vol = pd.crosstab(tk.mes, tk.grupo)
f = go.Figure()
for i, c in enumerate(["outras categorias", "tecnico"]):
    f.add_trace(go.Bar(x=mes_dt(vol.index), y=vol[c], name=c, marker_color=CORES[[0, 7][i]]))
layout_padrao(f, "chamados", altura=260)
f.update_layout(barmode="stack")
eixo_meses(f, "2025-07-01", "2026-09-01", passo=2)
p.figura(f, "Chamados por mês e categoria do atendente.")
abandonados = int(tk.flag_aberto_antigo.sum())
p.texto(f"""
- De ~200 chamados por mês para **{fmt(vol.loc['2026-05'].sum())} em mai/26** e
{fmt(vol.loc['2026-06'].sum())} em jun/26, puxados pelos técnicos.
- {fmt(abandonados)} chamados ficaram abertos por mais de 20 dias (abandonados), a maior
parte de mai–jun. Quem reclamou e não teve resposta é candidato natural a sair.
- A categoria do atendente diverge do texto em 1/3 dos chamados: para o modelo, vale
reclassificar o texto com IA.""")

# ---- 5. pesquisa de saída
p.secao("pesquisa_saida: o motivo marcado esconde o \"objetivo cumprido\"")
mot = ps.motivo_principal.value_counts()
p.tabela(pd.DataFrame({"motivo marcado": mot.index, "respostas": mot.values}),
         "Motivo marcado (643 respostas, jun–set/26, só site)")
p.texto("""
- "Preço" é o motivo mais marcado, mas o comentário quase nunca fala de dinheiro: "era só
até a prova", "era só até a viagem pra praia". Dos 187 `preco` com comentário, 104 são
objetivo cumprido e só 2 falam de dinheiro (Q7).
- Sinal de um churn **natural**, de quem assinou para um objetivo com data. O objetivo
do onboarding (texto livre) pode antecipar isso.
- `problema_tecnico` aparece em junho e some em agosto, junto com o incidente.""")

# ---- 6. campanha
p.secao("campanha_ago26: só o mês grátis parece reter")
cp2 = cp.merge(a[["user_id", "data_fim"]], on="user_id", how="left")
cp2["saiu"] = cp2.data_fim.notna() & (cp2.data_fim <= "2026-09-30")
cp2["braço"] = cp2.grupo + cp2.oferta.map(lambda o: f" · {o}" if isinstance(o, str) else "")
res = cp2.groupby("braço").agg(n=("user_id", "size"), abriu=("abriu", "mean"),
                                clicou=("clicou", "mean"), saiu=("saiu", "mean"))
ctrl = res.loc["controle", "saiu"]
res = res.reset_index()
res["vs controle"] = (100 * (res.saiu - ctrl)).map(lambda v: f"{v:+.1f}".replace(".", ",") + " p.p.")
for c in ["abriu", "clicou", "saiu"]:
    res[c] = (100 * res[c]).map(pct)
res["n"] = res.n.map(fmt)
p.tabela(res.rename(columns={"saiu": "saiu até 30/09"}),
         "Saída até 30/09/26 por braço da campanha de 10/08/26")
p.texto("""
- Abertura e clique são parecidos entre os braços (~44% e ~15%): atenção não diferencia.
- **1 mês grátis (anuais)** é o único com diferença clara frente ao controle. Conteúdo,
desafio e o cupom de 30% (mensais) ficam perto do controle.
- **A conferir:** significância, e comparar cada braço com o controle **do mesmo plano**
(o controle mistura mensal e anual, e anual sai menos). É a base do uplift.""")

# ---- 7. uso mensal
p.secao("uso_mensal: quem treina continua treinando igual")
um2 = um[um.flag_sem_treino == 0].copy()
um2["tri"] = um2.mes.str[:4] + "-T" + ((um2.mes.str[5:7].astype(int) - 1) // 3 + 1).astype(str)
uso = um2.groupby("tri").agg(usuarios=("user_id", "nunique"), treinos=("atividades", "mean"),
                             minutos=("minutos", "mean"), dias=("dias_ativos", "mean"))
p.tabela(pd.DataFrame({"trimestre": uso.index, "usuários com treino": uso.usuarios.map(fmt),
                       "treinos/mês": uso.treinos.map(lambda v: f"{v:.1f}".replace(".", ",")),
                       "minutos/mês": uso.minutos.map(fmt),
                       "dias ativos/mês": uso.dias.map(lambda v: f"{v:.1f}".replace(".", ","))}),
         "Média por usuário, só meses com treino")
p.texto("""
- A intensidade de quem treina é estável de 2025 a 2026 (6–7 treinos e ~290 minutos por
mês), com sazonalidade (jan alto, mar e jul baixos). Não há queda geral de engajamento.
- O sinal de churn deve estar na **trajetória individual** (quem vinha caindo), não na
média.""")

# ---- 8. pagamentos
p.secao("pagamentos: receita sobe com o reajuste, recusa estável")
pg2 = pg[pg.mes >= "2025-01"]
fat = pg2[pg2.status != "recusado"].groupby("mes").valor.sum() / 1000
rec = pg2.groupby("mes").status.apply(lambda s: (s == "recusado").mean() * 100)
f = go.Figure(go.Bar(x=mes_dt(fat.index), y=fat.values, marker_color=CORES[0],
                     name="faturamento bruto (R$ mil)"))
layout_padrao(f, "R$ mil", altura=240)
eixo_meses(f, "2025-01-01", "2026-09-01")
p.figura(f, "Faturamento bruto por mês (cobranças não recusadas).")
p.texto(f"""
- Set/26: R$ {fmt(fat.loc['2026-09'] * 1000)} bruto (referência do grupo: R$ 489.873,50).
- Recusa entre {pct(rec.min())} e {pct(rec.max())} das cobranças em todo o período: a
cobrança não piorou. Churn involuntário é pequeno e estável.""")

# ---- 9. onboarding, amizades, feed, eventos
p.secao("onboarding: o que a pessoa marca não separa quem sai")
ob2 = a[a.flag_cortesia == 0].merge(ob[["user_id", "nivel", "dias_por_semana"]], on="user_id")
niv = ob2.groupby(ob2.nivel.fillna("(vazio)")).status_atual.apply(
    lambda s: (s != "ativa").mean() * 100)
p.tabela(pd.DataFrame({"nível declarado": niv.index, "% já saiu": niv.map(pct).values}),
         "Assinantes que já saíram, por nível declarado no onboarding")
p.texto("""
- Nível e dias por semana declarados quase não mudam a taxa de saída (54–57% em todas as
faixas).
- O sinal, se houver, está no **texto** do objetivo (prova, viagem, emagrecer…), que é
trabalho para a extração com IA. 21,5% dos objetivos vêm sem conteúdo ("ok", "asdf"),
o que também pode ser sinal de baixo engajamento.""")

p.secao("eventos_assinatura: o funil do trial")
ev2 = ev[ev.mes >= "2024-08"]
funil = ev2[ev2.evento.isin(["trial_iniciado", "assinatura_iniciada"])]
funil = pd.crosstab(funil.mes.str[:4], funil.evento)
p.tabela(pd.DataFrame({"ano": funil.index, "trials iniciados": funil.trial_iniciado.map(fmt),
                       "assinaturas iniciadas": funil.assinatura_iniciada.map(fmt),
                       "assinaturas por trial": (funil.assinatura_iniciada / funil.trial_iniciado)
                       .map(lambda v: f"{v:.2f}".replace(".", ","))}),
         "Trials e assinaturas iniciados por ano (desde ago/24)")
p.texto("""
- O log permite medir o funil trial → assinatura e o tempo até cada desligamento da
renovação, que antecede a saída. É a fonte para montar o histórico de cada assinante na
base de modelagem.""")

p.secao("amizades e feed_posts: social é estável, mas cuidado com a leitura")
am2 = am[am.flag_apos_corte == 0]
fp2 = fp[fp.flag_apos_corte == 0]
p.texto(f"""
- {fmt(len(am2))} relações de seguir, {pct(100 * am2.reciproco.mean(), 0)} recíprocas;
{fmt(fp2.user_id.nunique())} pessoas postaram, com ~{fp2.curtidas.mean():.0f} curtidas por
post. O volume do feed é estável trimestre a trimestre.
- Cuidado: à primeira vista, quem não segue ninguém tem mais assinatura ativa. É quase
certamente efeito de tempo de casa (quem chegou agora ainda não seguiu ninguém e ainda não
teve tempo de sair). Só vale comparar dentro da mesma safra.""")

p.secao("O que levar para a próxima etapa")
p.texto("""
- **Três candidatos a causa da alta do churn**, em momentos diferentes: reajuste de preço
(abr/26, todos), bug de GPS no Android (jun–jul/26) e mudança no mix de aquisição para
influenciador (estrutural, 2026 inteiro).
- **Churn de objetivo cumprido**, escondido nas categorias da pesquisa de saída e
possivelmente previsível pelo texto do onboarding.
- **Campanha**: o mês grátis parece funcionar; falta medir por plano e com significância
antes de virar premissa de ROI.
- Variáveis de modelo: respeitar os `flag_apos_corte` e o `flag_resolvido_pos_corte`
(nada depois de 30/09/2026).""")

APOIO.mkdir(parents=True, exist_ok=True)
# Caminho absoluto: `Pagina.salvar` grava em `PASTA / nome`, e o pathlib respeita o
# destino absoluto (não cai em artefatos/).
destino = p.salvar(APOIO / "00b_visao_prata.html")
assert destino == APOIO / "00b_visao_prata.html", destino
print(f"-> {destino.relative_to(RAIZ)}")
