"""Prata -> ouro: volume de pagamentos por mês e meio de pagamento.

Grão: uma linha por (mes, metodo). mes em horário de Brasília (coluna mes da prata).

Regras:
  - aprovadas / valor_aprovado: status = aprovado.
  - devolucoes / valor_devolvido: status estornado ou chargeback, contados no mês em que
    foram lançados (não no mês da cobrança original); valor já corrigido na prata
    (= -valor efetivamente cobrado).
  - recusadas: status = recusado. Não entram em valor.
  - valor_bruto = valor_aprovado + valor_devolvido; valor_liquido idem, após a taxa de
    cada meio (15% loja, 3,5% cartão, 0,99% Pix).

Uso: python3 notebooks/pagamentos_mensal_ouro.py  (a partir da raiz, depois de pagamentos_prata.py)
"""
import csv
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "dados"
ENTRADA = BASE / "2.prata" / "pagamentos.csv"
SAIDA = BASE / "3.ouro" / "pagamentos_mensal.csv"

COLUNAS = [
    "mes", "metodo", "canal", "aprovadas", "valor_aprovado", "devolucoes", "valor_devolvido",
    "recusadas", "valor_bruto", "valor_liquido",
]


def main():
    agg = defaultdict(lambda: {
        "aprovadas": 0, "valor_aprovado": Decimal(0), "devolucoes": 0,
        "valor_devolvido": Decimal(0), "recusadas": 0, "valor_liquido": Decimal(0),
    })
    canal = {}
    with open(ENTRADA, newline="") as f:
        for r in csv.DictReader(f):
            a = agg[(r["mes"], r["metodo"])]
            canal[r["metodo"]] = r["canal"]
            if r["status"] == "recusado":
                a["recusadas"] += 1
                continue
            if r["status"] == "aprovado":
                a["aprovadas"] += 1
                a["valor_aprovado"] += Decimal(r["valor"])
            else:
                a["devolucoes"] += 1
                a["valor_devolvido"] += Decimal(r["valor"])
            a["valor_liquido"] += Decimal(r["valor_liquido"])

    saida = []
    for (mes, metodo), a in sorted(agg.items()):
        saida.append({
            "mes": mes, "metodo": metodo, "canal": canal[metodo], **a,
            "valor_bruto": a["valor_aprovado"] + a["valor_devolvido"],
        })

    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    with open(SAIDA, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUNAS)
        w.writeheader()
        w.writerows(saida)
    print(f"{len(saida)} linhas -> {SAIDA}")


if __name__ == "__main__":
    main()
