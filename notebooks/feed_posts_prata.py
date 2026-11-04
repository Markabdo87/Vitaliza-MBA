"""Bronze -> prata: feed_posts.csv limpo, um post por linha (mesmo grão da bronze).

Regras aplicadas:
  1. texto: só formato. Unicode NFC, strip e sequências de espaço viram um espaço; emojis,
     maiúsculas e erros de digitação ficam. O texto lido fica em texto_bronze.
     A prata não interpreta o texto: tema, evento de vida e intenção de sair saem na
     etapa de extração com IA.
  2. "[post removido]" é marcador do sistema, não texto da pessoa: texto vira nulo,
     flag_post_removido = 1. A linha fica (o post existiu e tem data e curtidas).
  3. data_hora: sem marcador de fuso, entre 06h e 22h; tratada como horário de Brasília
     e mantida. Coluna nova mes (AAAA-MM).
  4. posts depois do corte (30/09/2026) são mantidos e marcados com flag_apos_corte = 1;
     não podem entrar em variável de modelo.
  5. curtidas: inteiro; negativo ou ilegível -> nulo + flag_curtidas_invalida.

Nada é removido: não há duplicata exata, por post_id, nem por (user_id, data_hora, texto).
post_id não segue a ordem do tempo; a prata sai ordenada por data_hora, post_id.

Flags:
  flag_post_removido       post apagado; texto nulo
  flag_apos_corte          data_hora depois de 30/09/2026 23:59:59
  flag_curtidas_invalida   curtidas negativa ou não numérica

Uso: python3 notebooks/feed_posts_prata.py  (a partir da raiz do repo)
"""
import csv
import re
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "dados"
ENTRADA = BASE / "1.bronze" / "feed_posts.csv"
SAIDA = BASE / "2.prata" / "feed_posts.csv"

CORTE = datetime(2026, 9, 30, 23, 59, 59)
REMOVIDO = "[post removido]"

COLUNAS = [
    "post_id", "user_id", "data_hora", "mes", "texto", "texto_bronze", "curtidas",
    "flag_post_removido", "flag_apos_corte", "flag_curtidas_invalida",
]


def normalizar(s):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", s)).strip()


def main():
    with open(ENTRADA, newline="", encoding="utf-8") as f:
        bronze = list(csv.DictReader(f))

    exatas = len(bronze) - len({tuple(r.values()) for r in bronze})
    ids = len(bronze) - len({r["post_id"] for r in bronze})
    repetidos = len(bronze) - len({(r["user_id"], r["data_hora"], r["texto"]) for r in bronze})

    efeito = Counter()
    saida = []
    for r in bronze:
        t = datetime.strptime(r["data_hora"].strip(), "%Y-%m-%d %H:%M:%S")
        texto = normalizar(r["texto"])
        removido = texto.lower() == REMOVIDO
        efeito["texto: espaço normalizado"] += bool(texto) and texto != r["texto"]
        if removido:
            texto = ""
        efeito["texto: post removido -> nulo"] += removido
        efeito["texto: vazio na bronze"] += not normalizar(r["texto"])
        c = r["curtidas"].strip()
        curtidas_ok = re.fullmatch(r"\d+", c) is not None
        efeito["curtidas: inválida"] += not curtidas_ok
        apos = t > CORTE
        efeito["data_hora: após o corte"] += apos
        saida.append({
            "post_id": r["post_id"],
            "user_id": r["user_id"],
            "data_hora": t.strftime("%Y-%m-%d %H:%M:%S"),
            "mes": t.strftime("%Y-%m"),
            "texto": texto,
            "texto_bronze": r["texto"],
            "curtidas": int(c) if curtidas_ok else "",
            "flag_post_removido": int(removido),
            "flag_apos_corte": int(apos),
            "flag_curtidas_invalida": int(not curtidas_ok),
        })

    saida.sort(key=lambda r: (r["data_hora"], r["post_id"]))
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    with open(SAIDA, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUNAS)
        w.writeheader()
        w.writerows(saida)

    print(f"bronze: {len(bronze)} linhas · prata: {len(saida)} linhas -> {SAIDA}")
    print(f"duplicatas: exatas {exatas} · post_id {ids} · (user_id, data_hora, texto) {repetidos}")
    print(f"data_hora: {saida[0]['data_hora']} a {saida[-1]['data_hora']} · "
          f"horas {min(r['data_hora'][11:13] for r in saida)}h-{max(r['data_hora'][11:13] for r in saida)}h")
    for k in sorted(efeito):
        print(f"  {k}: {efeito[k]}")
    apos = [r for r in saida if r["flag_apos_corte"]]
    print(f"após o corte: {len(apos)} posts de {len({r['user_id'] for r in apos})} usuários, "
          f"{apos[0]['data_hora'] if apos else '-'} a {apos[-1]['data_hora'] if apos else '-'}")
    cur = [r["curtidas"] for r in saida if r["curtidas"] != ""]
    print(f"curtidas: {min(cur)} a {max(cur)} · zero em {cur.count(0)} posts")
    validos = [r for r in saida if r["texto"] and not r["flag_apos_corte"]]
    print(f"com texto até o corte (vai para extração): {len(validos)} posts · "
          f"{len({r['texto'] for r in validos})} textos distintos · "
          f"{len({r['user_id'] for r in validos})} usuários")


if __name__ == "__main__":
    main()
