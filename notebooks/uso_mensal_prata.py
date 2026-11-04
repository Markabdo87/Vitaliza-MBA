"""Bronze -> prata: uso_mensal.csv limpo, uma linha por usuário e mês (jan/2025 a set/2026).

A bronze já vem sem nulos, sem duplicata e com todas as contas fechando; as regras abaixo
protegem contra isso e marcam o que muda a leitura da série. Nenhum valor é alterado.

Regras aplicadas:
  1. formato: user_id "u_" + 8 hex, mes "AAAA-MM", métricas inteiras >= 0. Linha fora do
     formato é removida (hoje: nenhuma).
  2. duplicata: mesma (user_id, mes) conta uma vez; fica a primeira linha (hoje: nenhuma).
  3. corte: mês posterior a 2026-09 é removido (hoje: nenhum; set/2026 está completo).
  4. coerência interna: ar_livre + video = atividades, dias_ativos <= atividades,
     dias_ativos <= dias do mês, atividades > 0 <=> minutos > 0 <=> dias_ativos > 0.
     Quem quebrar alguma vira flag_incoerente (hoje: nenhuma linha).
  5. mês sem treino: em 2025 a tabela só tem linha quando houve treino; em 2026 também
     traz o mês sem treino (atividades = 0). flag_sem_treino marca essas linhas, para
     comparar 2025 com 2026 filtrando flag_sem_treino = 0.
  6. sessoes_app: a partir de mar/2026 a contagem cai ~45% de um mês para o outro para
     quase todos os usuários, com treinos e minutos estáveis. flag_sessoes_nova_contagem
     marca mes >= 2026-03: não compare sessoes_app entre os dois lados dessa data.
  7. volume alto: mais de 180 minutos por dia ativo, em média, no mês. flag_volume_alto
     (possível, mas raro: acima do percentil 99,9).

Flags (0/1):
  flag_incoerente             quebra alguma regra de coerência da regra 4
  flag_sem_treino             atividades = 0 (só existe em 2026)
  flag_sem_uso                atividades = 0 e sessoes_app = 0 (não abriu o app no mês)
  flag_sessoes_nova_contagem  mes >= 2026-03
  flag_volume_alto            minutos / dias_ativos > 180

Uso: python3 notebooks/uso_mensal_prata.py  (a partir da raiz do repo)
"""
import calendar
import csv
import re
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "dados"
ENTRADA = BASE / "1.bronze" / "uso_mensal.csv"
SAIDA = BASE / "2.prata" / "uso_mensal.csv"

CORTE = "2026-09"
NOVA_CONTAGEM_SESSOES = "2026-03"
MINUTOS_POR_DIA_ALTO = 180
METRICAS = ["atividades", "atividades_ar_livre", "atividades_video", "minutos",
            "dias_ativos", "sessoes_app"]
FLAGS = ["flag_incoerente", "flag_sem_treino", "flag_sem_uso",
         "flag_sessoes_nova_contagem", "flag_volume_alto"]
COLUNAS = ["user_id", "mes"] + METRICAS + FLAGS

RE_USER = re.compile(r"u_[0-9a-f]{8}")
RE_MES = re.compile(r"\d{4}-(0[1-9]|1[0-2])")
RE_INT = re.compile(r"\d+")


def valida(r):
    if not RE_USER.fullmatch(r["user_id"].strip()) or not RE_MES.fullmatch(r["mes"].strip()):
        return False
    return all(RE_INT.fullmatch(r[c].strip()) for c in METRICAS)


def incoerente(r):
    a, al, av = r["atividades"], r["atividades_ar_livre"], r["atividades_video"]
    mi, d = r["minutos"], r["dias_ativos"]
    ano, mes = map(int, r["mes"].split("-"))
    return (
        al + av != a
        or d > a
        or d > calendar.monthrange(ano, mes)[1]
        or not ((a > 0) == (mi > 0) == (d > 0))
    )


def main():
    bronze = 0
    removidas = Counter()
    vistos, saida = set(), []
    with open(ENTRADA, newline="") as f:
        for r in csv.DictReader(f):
            bronze += 1
            if not valida(r):
                removidas["formato"] += 1
                continue
            r = {"user_id": r["user_id"].strip(), "mes": r["mes"].strip(),
                 **{c: int(r[c]) for c in METRICAS}}
            chave = (r["user_id"], r["mes"])
            if chave in vistos:
                removidas["duplicata"] += 1
                continue
            vistos.add(chave)
            if r["mes"] > CORTE:
                removidas["pos_corte"] += 1
                continue
            r["flag_incoerente"] = int(incoerente(r))
            r["flag_sem_treino"] = int(r["atividades"] == 0)
            r["flag_sem_uso"] = int(r["atividades"] == 0 and r["sessoes_app"] == 0)
            r["flag_sessoes_nova_contagem"] = int(r["mes"] >= NOVA_CONTAGEM_SESSOES)
            r["flag_volume_alto"] = int(
                r["dias_ativos"] > 0 and r["minutos"] / r["dias_ativos"] > MINUTOS_POR_DIA_ALTO
            )
            saida.append(r)

    saida.sort(key=lambda r: (r["mes"], r["user_id"]))
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    with open(SAIDA, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUNAS)
        w.writeheader()
        w.writerows(saida)

    print(f"bronze: {bronze} linhas · prata: {len(saida)} linhas -> {SAIDA}")
    print("removidas: " + " · ".join(f"{k} {removidas[k]}" for k in ("formato", "duplicata", "pos_corte")))
    for fl in FLAGS:
        n = sum(r[fl] for r in saida)
        print(f"{fl}: {n} linhas")
    alto = [r for r in saida if r["flag_volume_alto"]]
    print(f"  flag_volume_alto: {len(set(r['user_id'] for r in alto))} usuários")

    print("\nmes      linhas  com_treino  sessoes/treino")
    por_mes = {}
    for r in saida:
        m = por_mes.setdefault(r["mes"], [0, 0, 0, 0])
        m[0] += 1
        if r["atividades"]:
            m[1] += 1
            m[2] += r["sessoes_app"]
            m[3] += r["atividades"]
    for mes, (n, com, s, a) in sorted(por_mes.items()):
        print(f"{mes}  {n:6d}  {com:10d}  {s / a:14.2f}")


if __name__ == "__main__":
    main()
