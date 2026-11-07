"""Bronze -> prata: assinaturas.csv limpo (retrato de 01/10/2026, uma linha por assinatura).

Regras aplicadas:
  1. datas: `inicio` e `data_fim` já vêm como data (AAAA-MM-DD) em horário de Brasília, para
     loja e site. Ficam como estão; nenhuma conversão de fuso. Colunas novas `mes_inicio` e
     `mes_fim` (AAAA-MM) para cortar por mês.
  2. canal: `canal_cobranca` usa nomes próprios (web_cartao/web_pix/interno). Colunas novas:
     `canal` (loja/site/interno) e `metodo` com o rótulo de pagamentos.csv
     (app_store/google_play/cartao/pix_automatico; vazio para interno). Original intacto.
  3. cortesia: plano `cortesia`, canal `interno` e ID `s_t...` (fora do dicionário) ficam,
     marcados com flag_cortesia. Não pagam: fora de receita e de churn pago.
  4. início antes do histórico: assinaturas com `inicio` < 01/07/2024 não têm o evento de
     início em eventos_assinatura.csv nem a primeira cobrança em pagamentos.csv. Ficam,
     marcadas com flag_inicio_antes_historico.
  5. coerência do retrato: ativa <-> sem data_fim e sem motivo_fim; expirada/reembolsada <->
     com data_fim e motivo_fim; renovação automática `sim` só em ativa; data_fim >= inicio;
     nenhuma data depois do corte (30/09/2026); assinatura_id único. O notebook confere e
     imprime as violações (esperado: zero). Nada é removido.

Não remove nenhuma linha.
Flags:
  flag_cortesia               plano cortesia / canal interno (60 linhas)
  flag_inicio_antes_historico inicio antes de 01/07/2024, sem rastro em eventos e pagamentos

Uso: python3 notebooks/assinaturas_prata.py  (a partir da raiz do repo)
"""
import csv
from collections import Counter
from datetime import date
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "dados"
ENTRADA = BASE / "1.bronze" / "assinaturas.csv"
SAIDA = BASE / "2.prata" / "assinaturas.csv"

CORTE = date(2026, 9, 30)
INICIO_HISTORICO = date(2024, 7, 1)
CANAL = {"app_store": "loja", "google_play": "loja", "web_cartao": "site", "web_pix": "site",
         "interno": "interno"}
METODO = {"app_store": "app_store", "google_play": "google_play", "web_cartao": "cartao",
          "web_pix": "pix_automatico", "interno": ""}

COLUNAS = [
    "assinatura_id", "user_id", "plano_atual", "canal_cobranca", "canal", "metodo",
    "inicio", "mes_inicio", "status_atual", "renovacao_automatica", "data_fim", "mes_fim",
    "motivo_fim", "flag_cortesia", "flag_inicio_antes_historico",
]


def violacoes(r, ini, fim):
    """Regras de coerência do retrato; devolve a lista de regras quebradas pela linha."""
    v = []
    ativa = r["status_atual"] == "ativa"
    if ativa and (r["data_fim"] or r["motivo_fim"]):
        v.append("ativa com fim")
    if not ativa and not (r["data_fim"] and r["motivo_fim"]):
        v.append("encerrada sem fim")
    if r["renovacao_automatica"] == "sim" and not ativa:
        v.append("renovacao sim em encerrada")
    if fim and fim < ini:
        v.append("data_fim antes do inicio")
    if ini > CORTE or (fim and fim > CORTE):
        v.append("data depois do corte")
    if r["status_atual"] == "reembolsada" and r["motivo_fim"] != "reembolso":
        v.append("reembolsada sem motivo reembolso")
    return v


def main():
    with open(ENTRADA, newline="") as f:
        bronze = list(csv.DictReader(f))

    saida, quebras = [], Counter()
    ids = Counter(r["assinatura_id"] for r in bronze)
    quebras["assinatura_id repetido"] = sum(n - 1 for n in ids.values() if n > 1)
    for r in bronze:
        ini = date.fromisoformat(r["inicio"])
        fim = date.fromisoformat(r["data_fim"]) if r["data_fim"] else None
        for v in violacoes(r, ini, fim):
            quebras[v] += 1
        cortesia = r["plano_atual"] == "cortesia" or r["canal_cobranca"] == "interno"
        saida.append({
            "assinatura_id": r["assinatura_id"],
            "user_id": r["user_id"],
            "plano_atual": r["plano_atual"],
            "canal_cobranca": r["canal_cobranca"],
            "canal": CANAL[r["canal_cobranca"]],
            "metodo": METODO[r["canal_cobranca"]],
            "inicio": r["inicio"],
            "mes_inicio": r["inicio"][:7],
            "status_atual": r["status_atual"],
            "renovacao_automatica": r["renovacao_automatica"],
            "data_fim": r["data_fim"],
            "mes_fim": r["data_fim"][:7],
            "motivo_fim": r["motivo_fim"],
            "flag_cortesia": int(cortesia),
            "flag_inicio_antes_historico": int(ini < INICIO_HISTORICO),
        })

    saida.sort(key=lambda r: (r["inicio"], r["assinatura_id"]))
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    with open(SAIDA, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUNAS)
        w.writeheader()
        w.writerows(saida)

    print(f"bronze: {len(bronze)} linhas · prata: {len(saida)} linhas -> {SAIDA}")
    print(f"usuários distintos: {len({r['user_id'] for r in saida})}")
    print("canal:", dict(Counter(r["canal"] for r in saida)))
    print("status:", dict(Counter(r["status_atual"] for r in saida)))
    print("motivo_fim:", dict(Counter(r["motivo_fim"] or "(ativa)" for r in saida)))
    print(f"flag_cortesia: {sum(r['flag_cortesia'] for r in saida)}")
    print(f"flag_inicio_antes_historico: {sum(r['flag_inicio_antes_historico'] for r in saida)}"
          f" (sem cortesia: {sum(r['flag_inicio_antes_historico'] and not r['flag_cortesia'] for r in saida)})")
    fins = sorted(r["data_fim"] for r in saida if r["data_fim"])
    print(f"data_fim: {len(fins)} preenchidas, de {fins[0]} a {fins[-1]}")
    print("violações de coerência:", dict(quebras) if sum(quebras.values()) else "nenhuma")


if __name__ == "__main__":
    main()
