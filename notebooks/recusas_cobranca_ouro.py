"""Prata -> ouro: recusas_cobranca (uma linha por cobrança recusada) + planilha .xlsx +
artefatos/02_recusas_cobranca.html.

Histórico de todos os casos de cobrança recusada e do que aconteceu depois de cada um.

Regras (decisões R1–R5 no decisoes.md):
  1. Uma linha por cobrança com status 'recusado' em pagamentos.csv da prata (3.250).
     Cada recusa tem no máximo uma retentativa: a cobrança seguinte do mesmo usuário com
     tentativa_real = 2 (até 16 dias depois, regra P5).
  2. Desfecho:
       recuperada  a retentativa foi aprovada (o dinheiro entrou)
       perdida     sem retentativa aprovada e a assinatura terminou depois da recusa
                   (motivo_fim = falha_pagamento em assinaturas.csv)
       em_aberto   sem retentativa aprovada e a assinatura segue ativa em 30/09/2026:
                   recusa recente, ainda dentro da janela de retentativa/carência
  3. valor_tentado = valor_bronze da prata (P12: recusado tem valor 0). Valores líquidos
     usam a taxa do método (enunciado, seção 03). Na recuperada, o valor recuperado é o da
     retentativa aprovada.
  4. dias_ate_recuperar = dias corridos entre a recusa e a retentativa aprovada;
     dias_ate_fim = dias entre a recusa e data_fim da assinatura (só na perdida).
  5. recusa_n_usuario numera as recusas de cada usuário em ordem de tempo; recusas_usuario
     é o total de recusas da pessoa no histórico.

Saídas:
  dados/3.ouro/recusas_cobranca.csv   uma linha por recusa
  dados/3.ouro/recusas_cobranca.xlsx  abas: recusas · resumo_mensal · resumo_canal · regras
  artefatos/02_recusas_cobranca.html  só agregados

Conferência (o notebook para se não bater): 3.250 recusas; toda perdida tem
motivo_fim = falha_pagamento e as 1.321 assinaturas com esse motivo são perdidas daqui.

Uso: .venv/bin/python notebooks/recusas_cobranca_ouro.py  (a partir da raiz do repo)
"""
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

from _artefato import CORES, Pagina, eixo_meses, layout_padrao

RAIZ = Path(__file__).resolve().parent.parent
PRATA = RAIZ / "dados" / "2.prata"
OURO = RAIZ / "dados" / "3.ouro"
CSV = OURO / "recusas_cobranca.csv"
XLSX = OURO / "recusas_cobranca.xlsx"
CORTE = pd.Timestamp("2026-09-30")

p = pd.read_csv(PRATA / "pagamentos.csv", parse_dates=["data_hora_brt"])
a = pd.read_csv(PRATA / "assinaturas.csv", parse_dates=["inicio", "data_fim"])

# --- 1. recusa e cobrança seguinte do mesmo usuário ------------------------------------
c = p[p.status.isin(["aprovado", "recusado"])].sort_values(["user_id", "data_hora_brt", "pagamento_id"])
seg = c.groupby("user_id").shift(-1)
c = c.assign(prox_id=seg.pagamento_id, prox_t=seg.data_hora_brt, prox_status=seg.status,
             prox_tent=seg.tentativa_real, prox_valor=seg.valor, prox_liq=seg.valor_liquido)
r = c[c.status == "recusado"].copy()
retentou = r.prox_tent == 2
recuperou = retentou & (r.prox_status == "aprovado")

r = r.merge(a[["user_id", "assinatura_id", "plano_atual", "inicio", "status_atual",
               "data_fim", "motivo_fim", "flag_inicio_antes_historico"]],
            on="user_id", how="left", validate="many_to_one")
assert r.assinatura_id.notna().all(), "recusa sem assinatura"

# --- 2. desfecho ------------------------------------------------------------------------
dia = r.data_hora_brt.dt.normalize()
r["desfecho"] = "em_aberto"
r.loc[recuperou.values, "desfecho"] = "recuperada"
perdida = (~recuperou.values) & r.data_fim.notna() & (r.data_fim >= dia)
r.loc[perdida, "desfecho"] = "perdida"
sobra = (r.desfecho == "em_aberto") & (r.status_atual != "ativa")
assert not sobra.any(), f"{sobra.sum()} recusas sem desfecho claro"

# --- 3 a 5. colunas -----------------------------------------------------------------------
r["recusa_n_usuario"] = r.groupby("user_id").cumcount() + 1
r["recusas_usuario"] = r.groupby("user_id").pagamento_id.transform("size")
rec = r.desfecho == "recuperada"
out = pd.DataFrame({
    "pagamento_id_recusa": r.pagamento_id,
    "user_id": r.user_id,
    "assinatura_id": r.assinatura_id,
    "data_hora_recusa": r.data_hora_brt.dt.strftime("%Y-%m-%d %H:%M:%S"),
    "mes_recusa": r.mes,
    "plano": r.plano_atual,
    "canal": r.canal,
    "metodo": r.metodo,
    "valor_tentado": r.valor_bronze,
    "valor_liquido_tentado": (r.valor_bronze * (1 - r.taxa)).round(2),
    "recusa_n_usuario": r.recusa_n_usuario,
    "recusas_usuario": r.recusas_usuario,
    "desfecho": r.desfecho,
    "pagamento_id_retentativa": r.prox_id.where(retentou.values),
    "data_hora_recuperacao": r.prox_t.where(rec).dt.strftime("%Y-%m-%d %H:%M:%S"),
    "dias_ate_recuperar": (r.prox_t - r.data_hora_brt).dt.days.where(rec),
    "valor_recuperado": r.prox_valor.where(rec, 0.0),
    "valor_liquido_recuperado": r.prox_liq.where(rec, 0.0),
    "data_fim_assinatura": r.data_fim.dt.strftime("%Y-%m-%d"),
    "dias_ate_fim": (r.data_fim - dia).dt.days.where(r.desfecho == "perdida"),
    "status_assinatura_corte": r.status_atual,
    "motivo_fim": r.motivo_fim,
    "flag_inicio_antes_historico": r.flag_inicio_antes_historico,
}).sort_values(["data_hora_recusa", "pagamento_id_recusa"])
for col in ["dias_ate_recuperar", "dias_ate_fim"]:
    out[col] = out[col].astype("Int64")

# --- conferência ------------------------------------------------------------------------
assert len(out) == 3250, len(out)
per = out[out.desfecho == "perdida"]
assert (per.motivo_fim == "falha_pagamento").all()
fp = set(a.loc[a.motivo_fim == "falha_pagamento", "assinatura_id"])
assert fp == set(per.assinatura_id), "falha_pagamento sem recusa perdida correspondente"
assert per.assinatura_id.is_unique

OURO.mkdir(parents=True, exist_ok=True)
out.to_csv(CSV, index=False)

# --- resumos ----------------------------------------------------------------------------
def resumo(df, por):
    g = df.groupby(por)
    s = pd.DataFrame({
        "recusas": g.size(),
        "recuperadas": g.desfecho.apply(lambda d: (d == "recuperada").sum()),
        "perdidas": g.desfecho.apply(lambda d: (d == "perdida").sum()),
        "em_aberto": g.desfecho.apply(lambda d: (d == "em_aberto").sum()),
        "valor_tentado": g.valor_tentado.sum().round(2),
        "valor_recuperado": g.valor_recuperado.sum().round(2),
        "valor_liquido_recuperado": g.valor_liquido_recuperado.sum().round(2),
    })
    fechadas = s.recuperadas + s.perdidas
    s["taxa_recuperacao_pct"] = (100 * s.recuperadas / fechadas).round(1)
    return s.reset_index()

res_mes = resumo(out, "mes_recusa")
res_canal = resumo(out, ["canal", "metodo", "plano"])
tot = resumo(out.assign(total="total"), "total").iloc[0]
dias_fim = out[out.desfecho == "perdida"].groupby("metodo").dias_ate_fim.agg(["median", "min", "max"])

regras = pd.DataFrame({"regra": [l.strip() for l in __doc__.splitlines() if l.strip()]})
with pd.ExcelWriter(XLSX, engine="openpyxl") as xw:
    out.to_excel(xw, sheet_name="recusas", index=False)
    res_mes.to_excel(xw, sheet_name="resumo_mensal", index=False)
    res_canal.to_excel(xw, sheet_name="resumo_canal", index=False)
    regras.to_excel(xw, sheet_name="regras", index=False)
    for ws in xw.book.worksheets:
        ws.freeze_panes = "A2"
        for col in ws.columns:
            larg = max(len(str(c.value or "")) for c in list(col)[:200])
            ws.column_dimensions[col[0].column_letter].width = min(max(10, larg + 2), 60)

print(f"{CSV.relative_to(RAIZ)}: {len(out)} recusas de {out.user_id.nunique()} usuários · "
      f"{XLSX.relative_to(RAIZ)}")
print(f"desfecho: {out.desfecho.value_counts().to_dict()} · taxa de recuperação "
      f"{tot.taxa_recuperacao_pct}% · R$ {tot.valor_tentado:,.2f} tentados, "
      f"R$ {tot.valor_recuperado:,.2f} recuperados")
print("dias até recuperar:", out.dias_ate_recuperar.describe()[["50%", "max"]].to_dict())
print("dias até o fim (perdida), por método:\n" + dias_fim.to_string())
print(res_canal.to_string(index=False))

# --- artefato -----------------------------------------------------------------------------
pg = Pagina(
    "02 · Cobranças recusadas",
    "Quantas cobranças são recusadas por mês e quantas a retentativa recupera.",
    "fonte: `dados/3.ouro/recusas_cobranca.csv`, gerada por "
    "`notebooks/recusas_cobranca_ouro.py` (decisões P12, R1–R5)",
)
def br(x, casas=0):
    """Número no formato brasileiro: 1.234,56."""
    return f"{x:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


pg.texto(f"""
**Regra.** Uma linha por cobrança recusada em `pagamentos` (prata). Cada recusa tem no máximo
uma retentativa, até 16 dias depois. **Recuperada** = retentativa aprovada; **perdida** = sem
retentativa aprovada e a assinatura terminou por falha de pagamento; **em aberto** = recusa
recente de assinatura ainda ativa em 30/09/2026.

- {br(len(out))} recusas de {br(out.user_id.nunique())} assinantes, jul/24–set/26.
- {br(tot.recuperadas)} recuperadas, {br(tot.perdidas)} perdidas e {br(tot.em_aberto)} em
  aberto: a retentativa salva **{br(tot.taxa_recuperacao_pct, 1)}%** das recusas já resolvidas.
- R$ {br(tot.valor_tentado, 2)} tentados; R$ {br(tot.valor_recuperado, 2)} recuperados na
  retentativa.
- Depois da recusa, a assinatura do site expira em **7 dias** e a da loja em **16 dias** se
  nenhuma retentativa for aprovada.
""")

m = res_mes.copy()
m["dt"] = pd.PeriodIndex(m.mes_recusa, freq="M").to_timestamp()
f = go.Figure()
for i, (col, nome) in enumerate([("recuperadas", "recuperada"), ("perdidas", "perdida"),
                                 ("em_aberto", "em aberto")]):
    f.add_trace(go.Bar(x=m.dt, y=m[col], name=nome,
                       marker=dict(color=CORES[[2, 7, 3][i]], line=dict(color="#fcfcfb", width=1)),
                       hovertemplate=f"{nome}: %{{y:,.0f}}<extra></extra>"))
layout_padrao(f, "recusas no mês")
eixo_meses(f, "2024-07-01", "2026-09-01")
f.update_layout(barmode="stack", margin=dict(t=48))
pg.figura(f, "Cobranças recusadas por mês da recusa e desfecho. Em aberto: só nos últimos "
             "dias de set/26.")

f = go.Figure()
f.add_trace(go.Scatter(x=m.dt, y=m.taxa_recuperacao_pct, mode="lines+markers",
                       line=dict(color=CORES[0], width=2), marker=dict(size=6, color=CORES[0]),
                       hovertemplate="%{y:.1f}%<extra></extra>"))
layout_padrao(f, "recuperadas ÷ (recuperadas + perdidas) (%)")
eixo_meses(f, "2024-07-01", "2026-09-01")
f.update_layout(showlegend=False)
pg.figura(f, "Taxa de recuperação da retentativa por mês da recusa (recusas em aberto fora).")

tab = res_canal.copy()
for c in ["recusas", "recuperadas", "perdidas", "em_aberto"]:
    tab[c] = tab[c].map(br)
for c in ["valor_tentado", "valor_recuperado", "valor_liquido_recuperado"]:
    tab[c] = tab[c].map(lambda v: "R$\u00a0" + br(v, 2))
tab["taxa_recuperacao_pct"] = tab.taxa_recuperacao_pct.map(lambda v: br(v, 1))
pg.tabela(tab, "Por canal, método e plano")
pg.tabela(dias_fim.astype(int).reset_index().rename(columns={"median": "mediana"}),
          "Dias entre a recusa e o fim da assinatura, nas perdidas")
destino = pg.salvar("02_recusas_cobranca.html")
print(f"artefato: {destino.relative_to(RAIZ)}")
