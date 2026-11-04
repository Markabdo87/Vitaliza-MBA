"""Bronze -> prata: amizades.csv (uma relação de seguir por linha, mão única).

Regras aplicadas:
  1. desde: data sem hora nem fuso (AAAA-MM-DD). Validada como data e mantida como está;
     não há conversão de fuso possível.
  2. ids: seguidor_id e seguido_id no padrão u_ + 8 hex. Fora do padrão vira
     flag_id_invalido = 1 (a linha fica).
  3. auto-seguir (seguidor_id == seguido_id): removido, não é relação possível.
  4. par repetido (mesmo seguidor_id, seguido_id): fica a linha de desde mais antigo.
  5. relação iniciada depois do corte (desde > 2026-09-30): flag_apos_corte = 1.
     Fica na tabela, mas não entra em variável de modelo.
  6. reciproco = 1 quando o par inverso (seguido segue o seguidor) também existe na tabela.
     Calculado na própria tabela, sem cruzar com outro arquivo.

Não cruza com usuarios.csv: a checagem de ids inexistentes e de relação anterior ao
cadastro foi feita só no perfil (0 casos) e fica para o ouro, se precisar.

Uso: python3 notebooks/amizades_prata.py  (a partir da raiz do repo)
"""
import csv
import re
from datetime import date
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "dados"
ENTRADA = BASE / "1.bronze" / "amizades.csv"
SAIDA = BASE / "2.prata" / "amizades.csv"

CORTE = date(2026, 9, 30)
PADRAO_ID = re.compile(r"^u_[0-9a-f]{8}$")
COLUNAS = ["seguidor_id", "seguido_id", "desde", "reciproco", "flag_apos_corte", "flag_id_invalido"]


def main():
    with open(ENTRADA, newline="") as f:
        bronze = list(csv.DictReader(f))
    print(f"bronze: {len(bronze)} linhas")

    auto, repetidos, pares = 0, 0, {}
    for r in bronze:
        seguidor, seguido = r["seguidor_id"].strip(), r["seguido_id"].strip()
        d = date.fromisoformat(r["desde"].strip())  # regra 1: falha alto se vier data inválida
        if seguidor == seguido:  # regra 3
            auto += 1
            continue
        chave = (seguidor, seguido)
        if chave in pares:  # regra 4
            repetidos += 1
            if d < pares[chave]:
                pares[chave] = d
            continue
        pares[chave] = d

    saida = []
    for (seguidor, seguido), d in pares.items():
        saida.append({
            "seguidor_id": seguidor,
            "seguido_id": seguido,
            "desde": d.isoformat(),
            "reciproco": int((seguido, seguidor) in pares),
            "flag_apos_corte": int(d > CORTE),
            "flag_id_invalido": int(not (PADRAO_ID.match(seguidor) and PADRAO_ID.match(seguido))),
        })

    saida.sort(key=lambda r: (r["desde"], r["seguidor_id"], r["seguido_id"]))
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    with open(SAIDA, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUNAS)
        w.writeheader()
        w.writerows(saida)

    print(f"prata: {len(saida)} linhas -> {SAIDA}")
    print(f"  regra 3 auto-seguir removidos: {auto}")
    print(f"  regra 4 pares repetidos removidos: {repetidos}")
    print(f"  regra 2 flag_id_invalido: {sum(r['flag_id_invalido'] for r in saida)}")
    print(f"  regra 5 flag_apos_corte: {sum(r['flag_apos_corte'] for r in saida)}"
          f" (desde {min((r['desde'] for r in saida if r['flag_apos_corte']), default='-')}"
          f" a {max((r['desde'] for r in saida if r['flag_apos_corte']), default='-')})")
    print(f"  regra 6 reciproco: {sum(r['reciproco'] for r in saida)} linhas")
    print(f"  desde: {saida[0]['desde']} a {saida[-1]['desde']}")


if __name__ == "__main__":
    main()
