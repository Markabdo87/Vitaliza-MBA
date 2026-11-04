"""Bronze -> prata: eventos_assinatura.csv limpo, mesmo grão (um evento por linha).

Correções aplicadas:
  1. fuso: lojas (app_store, google_play) gravam em UTC ("Z"), site (web_cartao, web_pix)
     em Brasília. Tudo vira horário de Brasília em data_hora_brt; o texto original fica em
     data_hora_bronze e a origem em fuso_origem (utc/brt).
  2. ordem: o arquivo não vem ordenado. seq_usuario numera os eventos de cada usuário por
     data_hora_brt (empate: ordem do arquivo). O arquivo sai ordenado por usuário e seq.
  3. colunas derivadas, sem cruzar tabelas: mes (AAAA-MM em Brasília), canal (loja/site,
     mesmo rótulo de pagamentos) e fase (trial quando plano vem vazio, senão assinatura).

Não remove nenhuma linha (não há duplicata exata nem quase exata). plano vazio e detalhe
vazio ficam como vieram. Sequências suspeitas viram flag:
  flag_inicio_antes_log      usuário cuja assinatura já existia em 01/07/2024 (o histórico
                             dele começa no meio: renovação, desligamento, carência ou
                             expiração sem assinatura_iniciada). Vale para todas as linhas.
  flag_apos_fim              evento recebido depois do evento terminal do usuário
                             (trial_expirado ou assinatura_expirada). Aviso que chegou fora
                             de ordem, sempre em menos de 1 dia; a data do fim é a do
                             evento terminal.
  flag_sequencia_invalida    evento que o estado anterior não permite; motivo em
                             problema_sequencia:
                               renovacao_com_renovacao_desligada  renovação depois de
                                 desligamento/cancelamento sem religamento
                               renovacao_apos_chargeback          renovação depois de
                                 chargeback, sem expiração entre eles
                               religada_sem_desligada             religamento com a
                                 renovação já ligada
                               desligada_repetida                 desligamento com a
                                 renovação já desligada
Conferência (não vira coluna): fim ausente. Trial sem trial_expirado nem assinatura mais de
8 dias depois do início, ou assinatura sem expiração mais de 17 dias depois do fim do ciclo
pago (último início/renovação + 30 dias no mensal, 365 no anual; 17 dias cobre a carência,
máx. observado 16,6). O notebook imprime a contagem; na bronze de 30/09/2026 é zero.

Uso: python3 notebooks/eventos_assinatura_prata.py  (a partir da raiz do repo)
"""
import csv
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "dados"
ENTRADA = BASE / "1.bronze" / "eventos_assinatura.csv"
SAIDA = BASE / "2.prata" / "eventos_assinatura.csv"

CORTE = datetime(2026, 10, 1)  # primeiro instante depois de 30/09/2026
CANAL = {"app_store": "loja", "google_play": "loja", "web_cartao": "site", "web_pix": "site"}
CICLO = {"mensal": timedelta(days=30), "anual": timedelta(days=365)}
TRIAL_MAX = timedelta(days=8)
CARENCIA_MAX = timedelta(days=17)
TERMINAIS = {"trial_expirado", "assinatura_expirada"}
EVENTOS = {
    "trial_iniciado", "trial_expirado", "assinatura_iniciada", "renovacao",
    "renovacao_automatica_desligada", "renovacao_automatica_religada", "periodo_carencia",
    "assinatura_expirada", "cancelamento_web", "reembolso", "chargeback",
}

COLUNAS = [
    "user_id", "seq_usuario", "data_hora_brt", "mes", "fuso_origem", "data_hora_bronze",
    "evento", "fase", "plano", "canal_cobranca", "canal", "detalhe",
    "flag_inicio_antes_log", "flag_apos_fim", "flag_sequencia_invalida",
    "problema_sequencia",
]


def parse_data(s):
    if s.endswith("Z"):
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ") - timedelta(hours=3), "utc"
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S"), "brt"


def marcar_usuario(lista):
    """Percorre os eventos de um usuário em ordem e preenche as flags de sequência."""
    tem_plano = any(r["plano"] for r in lista)
    tem_inicio = any(r["evento"] == "assinatura_iniciada" for r in lista)
    antes_log = int(tem_plano and not tem_inicio)

    terminou = False
    renov_ligada = True
    ultimo = None             # último evento válido (fora flag_apos_fim)
    inicio_trial = None
    inicio_ciclo = None       # último assinatura_iniciada/renovacao (ou 1º evento, se antes do log)
    plano = ""
    for i, r in enumerate(lista, start=1):
        r["seq_usuario"] = i
        r["flag_inicio_antes_log"] = antes_log
        r["flag_apos_fim"] = 0
        r["problema_sequencia"] = ""
        r["flag_fim_ausente"] = 0
        ev = r["evento"]
        if terminou:
            r["flag_apos_fim"] = 1
            continue
        if r["plano"]:
            plano = r["plano"]
            if inicio_ciclo is None:
                inicio_ciclo = r["t"]
        problema = ""
        if ev == "trial_iniciado":
            inicio_trial, renov_ligada = r["t"], True
        elif ev == "assinatura_iniciada":
            inicio_ciclo, renov_ligada = r["t"], True
        elif ev == "renovacao":
            if not renov_ligada:
                problema = "renovacao_com_renovacao_desligada"
            elif ultimo is not None and ultimo["evento"] == "chargeback":
                problema = "renovacao_apos_chargeback"
            inicio_ciclo, renov_ligada = r["t"], True
        elif ev in ("renovacao_automatica_desligada", "cancelamento_web"):
            if ev == "renovacao_automatica_desligada" and not renov_ligada \
                    and ultimo is not None and ultimo["evento"] == ev:
                problema = "desligada_repetida"
            renov_ligada = False
        elif ev == "renovacao_automatica_religada":
            if renov_ligada:
                problema = "religada_sem_desligada"
            renov_ligada = True
        elif ev in TERMINAIS:
            terminou = True
        r["problema_sequencia"] = problema
        ultimo = r

    fim_ausente = False
    if not terminou:
        if not tem_plano:
            fim_ausente = inicio_trial is not None and CORTE - inicio_trial > TRIAL_MAX
        elif inicio_ciclo is not None:
            fim_ausente = CORTE > inicio_ciclo + CICLO[plano] + CARENCIA_MAX
    lista[-1]["flag_fim_ausente"] = int(fim_ausente)


def main():
    linhas = []
    with open(ENTRADA, newline="") as f:
        for i, r in enumerate(csv.DictReader(f)):
            assert r["evento"] in EVENTOS, r["evento"]
            t, fuso = parse_data(r["data_hora"])
            linhas.append({**r, "t": t, "fuso": fuso, "i": i})
    n_bronze = len(linhas)

    chave = Counter((r["user_id"], r["data_hora"], r["evento"]) for r in linhas)
    duplicatas = sum(v - 1 for v in chave.values() if v > 1)

    por_usuario = defaultdict(list)
    for r in linhas:
        por_usuario[r["user_id"]].append(r)
    for lista in por_usuario.values():
        lista.sort(key=lambda r: (r["t"], r["i"]))
        marcar_usuario(lista)

    saida = []
    for u in sorted(por_usuario):
        for r in por_usuario[u]:
            saida.append({
                "user_id": r["user_id"],
                "seq_usuario": r["seq_usuario"],
                "data_hora_brt": r["t"].strftime("%Y-%m-%d %H:%M:%S"),
                "mes": r["t"].strftime("%Y-%m"),
                "fuso_origem": r["fuso"],
                "data_hora_bronze": r["data_hora"],
                "evento": r["evento"],
                "fase": "assinatura" if r["plano"] else "trial",
                "plano": r["plano"],
                "canal_cobranca": r["canal_cobranca"],
                "canal": CANAL[r["canal_cobranca"]],
                "detalhe": r["detalhe"],
                "flag_inicio_antes_log": r["flag_inicio_antes_log"],
                "flag_apos_fim": r["flag_apos_fim"],
                "flag_sequencia_invalida": int(bool(r["problema_sequencia"])),
                "problema_sequencia": r["problema_sequencia"],
            })

    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    with open(SAIDA, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUNAS)
        w.writeheader()
        w.writerows(saida)

    utc = [r for r in linhas if r["fuso"] == "utc"]
    muda_dia = sum(1 for r in utc if r["t"].strftime("%Y-%m-%d") != r["data_hora"][:10])
    muda_mes = sum(1 for r in utc if r["t"].strftime("%Y-%m") != r["data_hora"][:7])
    depois_corte_bruto = sum(1 for r in linhas if r["data_hora"][:10] >= "2026-10-01")
    depois_corte_brt = sum(1 for r in linhas if r["t"] >= CORTE)
    usuarios_antes = sum(1 for l in por_usuario.values() if l[0]["flag_inicio_antes_log"])
    print(f"bronze: {n_bronze} linhas · prata: {len(saida)} linhas -> {SAIDA}")
    print(f"usuários: {len(por_usuario)} · duplicatas (usuário, data_hora, evento): {duplicatas}")
    print(f"fuso: {len(utc)} linhas convertidas de UTC · {muda_dia} mudam de dia · "
          f"{muda_mes} mudam de mês · depois do corte: {depois_corte_bruto} no texto original, "
          f"{depois_corte_brt} em Brasília")
    print(f"flag_inicio_antes_log: {usuarios_antes} usuários · "
          f"{sum(r['flag_inicio_antes_log'] for r in saida)} linhas")
    apos = [r for r in saida if r["flag_apos_fim"]]
    print(f"flag_apos_fim: {len(apos)} linhas · {Counter(r['evento'] for r in apos)}")
    seq = Counter(r["problema_sequencia"] for r in saida if r["problema_sequencia"])
    print(f"flag_sequencia_invalida: {sum(seq.values())} linhas · {dict(seq)}")
    fa = sum(r["flag_fim_ausente"] for r in linhas)
    print(f"conferência fim ausente: {fa} usuários")
    canc = [r for r in linhas if r["evento"] == "cancelamento_web"]
    desl = {(r["user_id"], r["t"].date()) for r in linhas
            if r["evento"] == "renovacao_automatica_desligada"}
    pares = sum(1 for r in canc if any((r["user_id"], (r["t"] + timedelta(days=d)).date()) in desl
                                       for d in (-1, 0, 1)))
    print(f"cancelamento_web com desligamento em até 1 dia: {pares} de {len(canc)}")
    exp = [r for r in saida if r["evento"] == "assinatura_expirada"]
    s26 = [r for r in exp if r["mes"] == "2026-09"]
    js = [r for r in exp if "2026-06" <= r["mes"] <= "2026-09"]
    print(f"assinatura_expirada: {len(exp)} · set/26: {len(s26)} · jun–set/26: {len(js)} "
          f"({Counter(r['canal'] for r in js)})")


if __name__ == "__main__":
    main()
