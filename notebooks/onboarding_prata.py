"""Bronze -> prata: onboarding.csv limpo, uma linha por conta (mesmo grão da bronze).

Regras aplicadas:
  1. texto livre (objetivo_texto, como_conheceu): só formato. Unicode NFC, strip e sequências
     de espaço viram um espaço; vazio vira nulo. O texto lido fica em <coluna>_bronze.
     A prata não interpreta o texto: categoria, meta e data saem na etapa de extração com IA.
  2. resposta sem conteúdo ("ok", ".", "x", "-", "asdf", "sla", "kkkk", "nada", "nao sei", "😂")
     é mantida e marcada com flag_<coluna>_sem_conteudo = 1. Nulo não é marcado (já é nulo).
  3. como_conheceu é resposta livre (dicionário): erros de digitação ("vi um aúnncio") e
     variantes sem acento ficam como vieram; o agrupamento em canal é tarefa da extração.
  4. dias_por_semana: texto livre ("3", "3x", "3 vezes", "todos") vira inteiro 1-7;
     "todos" = 7. Original em dias_por_semana_bronze. Fora de 0-7 ou ilegível -> nulo + flag.
  5. nivel: categoria fechada (iniciante / intermediario / avancado), em minúscula e sem acento.
     Valor fora do domínio -> nulo, original em nivel_bronze.
  6. respondido_em: data sem hora nem fuso; mantida. Data depois do corte (30/09/2026)
     é marcada em flag_apos_corte.

Nada é removido: não há duplicata por onboarding_id nem mais de um onboarding por user_id.

Flags:
  flag_objetivo_sem_conteudo       objetivo preenchido, mas sem conteúdo útil
  flag_como_conheceu_sem_conteudo  como_conheceu preenchido, mas sem conteúdo útil
  flag_dias_invalido               dias_por_semana preenchido e ilegível ou fora de 0-7
  flag_apos_corte                  respondido_em depois de 30/09/2026

Uso: python3 notebooks/onboarding_prata.py  (a partir da raiz do repo)
"""
import csv
import re
import unicodedata
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "dados"
ENTRADA = BASE / "1.bronze" / "onboarding.csv"
SAIDA = BASE / "2.prata" / "onboarding.csv"

CORTE = "2026-09-30"
SEM_CONTEUDO = {"ok", ".", "x", "-", "asdf", "sla", "kkkk", "nada", "nao sei", "não sei", "😂"}
NIVEIS = {"iniciante", "intermediario", "avancado"}
RE_DIAS = re.compile(r"^([0-9])\s*(x|vez|vezes)?$")

COLUNAS = [
    "onboarding_id", "user_id", "respondido_em",
    "objetivo_texto", "objetivo_texto_bronze", "flag_objetivo_sem_conteudo",
    "como_conheceu", "como_conheceu_bronze", "flag_como_conheceu_sem_conteudo",
    "nivel", "nivel_bronze", "dias_por_semana", "dias_por_semana_bronze", "flag_dias_invalido",
    "flag_apos_corte",
]


def normalizar(s):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", s)).strip()


def sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def parse_dias(s):
    """Devolve (inteiro ou '', inválido?)."""
    t = normalizar(s).lower()
    if not t:
        return "", False
    if t in ("todos", "todo dia", "todos os dias"):
        return 7, False
    m = RE_DIAS.match(t)
    if m and 0 <= int(m.group(1)) <= 7:
        return int(m.group(1)), False
    return "", True


def main():
    with open(ENTRADA, newline="", encoding="utf-8") as f:
        bronze = list(csv.DictReader(f))

    ids = Counter(r["onboarding_id"] for r in bronze)
    users = Counter(r["user_id"] for r in bronze)
    efeito = Counter()
    saida = []
    for r in bronze:
        linha = {"onboarding_id": r["onboarding_id"], "user_id": r["user_id"],
                 "respondido_em": r["respondido_em"].strip()}
        for col, flag in (("objetivo_texto", "flag_objetivo_sem_conteudo"),
                          ("como_conheceu", "flag_como_conheceu_sem_conteudo")):
            texto = normalizar(r[col])
            linha[col] = texto
            linha[f"{col}_bronze"] = r[col]
            linha[flag] = int(texto.lower() in SEM_CONTEUDO)
            efeito[f"{col}: nulo"] += not texto
            efeito[f"{col}: espaço normalizado"] += bool(texto) and texto != r[col]
            efeito[f"{col}: sem conteúdo"] += linha[flag]

        nivel = sem_acento(normalizar(r["nivel"]).lower())
        if nivel and nivel not in NIVEIS:
            efeito["nivel: fora do domínio"] += 1
            nivel = ""
        linha["nivel"], linha["nivel_bronze"] = nivel, r["nivel"]
        efeito["nivel: nulo"] += not nivel
        efeito["nivel: grafia corrigida"] += bool(nivel) and nivel != r["nivel"]

        dias, invalido = parse_dias(r["dias_por_semana"])
        linha["dias_por_semana"], linha["dias_por_semana_bronze"] = dias, r["dias_por_semana"]
        linha["flag_dias_invalido"] = int(invalido)
        efeito["dias: nulo na bronze"] += not r["dias_por_semana"].strip()
        efeito["dias: convertido de texto"] += dias != "" and str(dias) != r["dias_por_semana"]
        efeito["dias: 'todos' -> 7"] += normalizar(r["dias_por_semana"]).lower() == "todos"
        efeito["dias: inválido"] += invalido

        linha["flag_apos_corte"] = int(linha["respondido_em"] > CORTE)
        efeito["respondido_em: após o corte"] += linha["flag_apos_corte"]
        saida.append(linha)

    saida.sort(key=lambda r: (r["respondido_em"], r["onboarding_id"]))
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    with open(SAIDA, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUNAS)
        w.writeheader()
        w.writerows(saida)

    print(f"bronze: {len(bronze)} linhas · prata: {len(saida)} linhas -> {SAIDA}")
    print(f"onboarding_id repetido: {sum(v - 1 for v in ids.values())} · "
          f"user_id com mais de um onboarding: {sum(1 for v in users.values() if v > 1)}")
    print(f"respondido_em: {min(r['respondido_em'] for r in saida)} a {max(r['respondido_em'] for r in saida)}")
    for k in sorted(efeito):
        print(f"  {k}: {efeito[k]}")
    print("nivel:", dict(Counter(r["nivel"] or "(nulo)" for r in saida)))
    print("dias_por_semana:", dict(sorted(Counter(str(r["dias_por_semana"]) or "(nulo)" for r in saida).items())))
    ambos = sum(1 for r in saida if r["flag_objetivo_sem_conteudo"] and r["flag_como_conheceu_sem_conteudo"])
    util = sum(1 for r in saida if r["objetivo_texto"] and not r["flag_objetivo_sem_conteudo"])
    print(f"objetivo com conteúdo (vai para extração): {util} · sem conteúdo nos dois campos: {ambos}")


if __name__ == "__main__":
    main()
