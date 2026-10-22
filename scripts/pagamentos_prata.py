"""Bronze -> prata: pagamentos.csv limpo, todos os meses.

Correções aplicadas:
  1. valor: "R$ 39,90" (site até jun/2025) vira 39.90; float com ponto.
  2. fuso: lojas gravam em UTC ("Z"), site em Brasília. Tudo vira horário de Brasília.
  3. duplicatas: mesma (user_id, data_hora, valor, status) conta uma vez; fica o primeiro pagamento_id.
  4. devoluções (estornado/chargeback): lançadas pelo preço de tabela. Passam a valer
     -(última cobrança aprovada do usuário antes dela). O valor do arquivo fica em valor_bronze.
  5. tentativa: a coluna original não registra retentativa. tentativa_real é reconstruída
     pela sequência do usuário: cobrança até 16 dias depois de uma recusa = retentativa.
  6. taxa: 15% loja, 3,5% cartão, 0,99% Pix (enunciado, seção 03) -> valor_liquido.

Não remove nada além das duplicatas. Recusados ficam (servem para churn involuntário);
casos suspeitos e não confirmados viram flag:
  flag_intervalo_curto  aprovado <20 dias depois de outro aprovado do mesmo usuário
  flag_preco_antigo     mensal de 34,90 aprovado a partir de 01/03/2026

Uso: python3 scripts/pagamentos_prata.py  (a partir da raiz do repo)
"""
import csv
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "dados"
ENTRADA = BASE / "bronze" / "pagamentos.csv"
SAIDA = BASE / "prata" / "pagamentos.csv"

TAXA = {"app_store": 0.15, "google_play": 0.15, "cartao": 0.035, "pix_automatico": 0.0099}
CANAL = {"app_store": "loja", "google_play": "loja", "cartao": "site", "pix_automatico": "site"}
JANELA_RETENTATIVA = timedelta(days=16)
INTERVALO_CURTO = timedelta(days=20)
REAJUSTE = datetime(2026, 3, 1)

COLUNAS = [
    "pagamento_id", "user_id", "data_hora_brt", "mes", "fuso_origem", "metodo", "canal",
    "status", "valor", "valor_bronze", "taxa", "valor_liquido", "pagamento_id_original",
    "tentativa_bronze", "tentativa_real", "flag_intervalo_curto", "flag_preco_antigo",
]


def parse_valor(s):
    s = s.strip()
    if s.startswith("R$"):
        s = s[2:].strip().replace(".", "").replace(",", ".")
    return float(s)


def centavos(x):
    """Arredondamento comercial: 39,90 na loja deixa R$ 33,92, como no enunciado."""
    return str(Decimal(repr(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def parse_data(s):
    if s.endswith("Z"):
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ") - timedelta(hours=3), "utc"
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S"), "brt"


def main():
    vistos, linhas, duplicatas = set(), [], 0
    with open(ENTRADA, newline="") as f:
        for r in csv.DictReader(f):
            chave = (r["user_id"], r["data_hora"], r["valor"], r["status"])
            if chave in vistos:
                duplicatas += 1
                continue
            vistos.add(chave)
            t, fuso = parse_data(r["data_hora"])
            linhas.append({**r, "t": t, "fuso": fuso, "v": parse_valor(r["valor"])})

    por_usuario = defaultdict(list)
    for r in linhas:
        por_usuario[r["user_id"]].append(r)

    saida = []
    for lista in por_usuario.values():
        lista.sort(key=lambda r: (r["t"], r["pagamento_id"]))
        ultima_aprovada = None
        ultima_cobranca = None  # aprovado ou recusado
        tentativa = 0
        for r in lista:
            valor, original = r["v"], ""
            curto = antigo = False
            if r["status"] in ("estornado", "chargeback"):
                if ultima_aprovada:
                    valor, original = -ultima_aprovada["v"], ultima_aprovada["pagamento_id"]
                tentativa_real = ""
            else:
                retentativa = (
                    ultima_cobranca is not None
                    and ultima_cobranca["status"] == "recusado"
                    and r["t"] - ultima_cobranca["t"] <= JANELA_RETENTATIVA
                )
                tentativa = tentativa + 1 if retentativa else 1
                tentativa_real = tentativa
                if r["status"] == "aprovado":
                    curto = ultima_aprovada is not None and r["t"] - ultima_aprovada["t"] < INTERVALO_CURTO
                    antigo = r["v"] == 34.90 and r["t"] >= REAJUSTE
                    ultima_aprovada = r
                ultima_cobranca = r
            taxa = TAXA[r["metodo"]]
            saida.append({
                "pagamento_id": r["pagamento_id"],
                "user_id": r["user_id"],
                "data_hora_brt": r["t"].strftime("%Y-%m-%d %H:%M:%S"),
                "mes": r["t"].strftime("%Y-%m"),
                "fuso_origem": r["fuso"],
                "metodo": r["metodo"],
                "canal": CANAL[r["metodo"]],
                "status": r["status"],
                "valor": f"{valor:.2f}",
                "valor_bronze": f"{r['v']:.2f}",
                "taxa": taxa,
                "valor_liquido": centavos(valor * (1 - taxa)),
                "pagamento_id_original": original,
                "tentativa_bronze": r["tentativa"],
                "tentativa_real": tentativa_real,
                "flag_intervalo_curto": int(curto),
                "flag_preco_antigo": int(antigo),
            })

    saida.sort(key=lambda r: (r["data_hora_brt"], r["pagamento_id"]))
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    with open(SAIDA, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUNAS)
        w.writeheader()
        w.writerows(saida)

    corrigidas = sum(1 for r in saida if r["valor"] != r["valor_bronze"])
    print(f"{len(saida)} linhas -> {SAIDA}")
    print(f"duplicatas removidas: {duplicatas} · devoluções corrigidas: {corrigidas}")


if __name__ == "__main__":
    main()
