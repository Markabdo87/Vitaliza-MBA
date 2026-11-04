"""Bronze -> prata: pesquisa_saida.csv limpa (uma resposta por linha, mesmo grão da bronze).

Correções aplicadas:
  1. comentario: strip, vazio vira nulo (campo vazio no CSV) e reparo de mojibake
     (UTF-8 lido como Latin-1, "nÃ£o" -> "não") quando aparecer. O texto fica como o
     cliente escreveu: erros de digitação, falta de acento e maiúsculas são mantidos,
     porque a leitura do texto é tarefa da extração com IA, não da prata.
  2. motivo_principal: strip + minúsculas e conferência contra a lista do dicionário
     (preco, nao_uso, problema_tecnico, outro_app, saude, outro). Valor fora da lista
     interrompe o script. Na bronze atual nenhum valor muda, por isso não há motivo_bronze.
  3. respondido_em: data sem hora nem fuso (o site grava em Brasília); validada como data
     e conferida contra o corte de 30/09/2026. Coluna nova mes (AAAA-MM).

Não remove nada. Casos que pedem atenção viram flag:
  flag_sem_comentario     comentário vazio (só o motivo marcado)
  flag_resposta_repetida  a conta tem mais de uma resposta na pesquisa

Diagnóstico impresso (não altera a tabela): tema do comentário por palavra-chave contra o
motivo marcado, para medir quanto o motivo declarado diverge do texto.

Uso: python3 notebooks/pesquisa_saida_prata.py  (a partir da raiz do repo)
"""
import csv
import unicodedata
from collections import Counter
from datetime import date
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "dados"
ENTRADA = BASE / "1.bronze" / "pesquisa_saida.csv"
SAIDA = BASE / "2.prata" / "pesquisa_saida.csv"

CORTE = date(2026, 9, 30)
MOTIVOS = {"preco", "nao_uso", "problema_tecnico", "outro_app", "saude", "outro"}

COLUNAS = [
    "resposta_id", "user_id", "respondido_em", "mes", "motivo_principal", "comentario",
    "flag_sem_comentario", "flag_resposta_repetida",
]

# Diagnóstico: tema do comentário -> motivo que seria o esperado. Só para contar.
TEMAS = [
    ("objetivo_cumprido", "outro", ("objetivo", "preciso mais", "era so ate", "era so")),
    ("problema_tecnico", "problema_tecnico", ("bugado", "gps", "atualiza")),
    ("saude", "saude", ("lesao", "machuquei", "parado por causa", "fisioterapia")),
    ("nao_uso", "nao_uso", ("nao estou usando", "perdi a vontade", "rotina chata",
                            "mesma coisa", "mesmo treino", "dar um tempo")),
    ("vida_pessoal", "outro", ("trabalho novo", "sem tempo", "nasceu", "meses fora", "amiga")),
    ("cobranca", "preco", ("cobranca",)),
]


def conserta_mojibake(s):
    if "Ã" in s or "Â" in s:
        try:
            return s.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            return s
    return s


def normaliza(s):
    s = unicodedata.normalize("NFKD", s.lower())
    return " ".join("".join(c for c in s if not unicodedata.combining(c)).split())


def tema(texto):
    t = normaliza(texto)
    for nome, esperado, chaves in TEMAS:
        if any(k in t for k in chaves):
            return nome, esperado
    return None, None


def main():
    with open(ENTRADA, newline="", encoding="utf-8") as f:
        bronze = list(csv.DictReader(f))

    por_usuario = Counter(r["user_id"] for r in bronze)
    saida, mojibake = [], 0
    for r in bronze:
        motivo = r["motivo_principal"].strip().lower()
        if motivo not in MOTIVOS:
            raise ValueError(f"motivo fora do dicionário: {r['resposta_id']} {motivo!r}")
        dia = date.fromisoformat(r["respondido_em"].strip())
        if dia > CORTE:
            raise ValueError(f"resposta depois do corte: {r['resposta_id']} {dia}")
        comentario = conserta_mojibake(r["comentario"].strip())
        mojibake += comentario != r["comentario"].strip()
        saida.append({
            "resposta_id": r["resposta_id"],
            "user_id": r["user_id"],
            "respondido_em": dia.isoformat(),
            "mes": dia.strftime("%Y-%m"),
            "motivo_principal": motivo,
            "comentario": comentario,
            "flag_sem_comentario": int(comentario == ""),
            "flag_resposta_repetida": int(por_usuario[r["user_id"]] > 1),
        })

    saida.sort(key=lambda r: (r["respondido_em"], r["resposta_id"]))
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    with open(SAIDA, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUNAS)
        w.writeheader()
        w.writerows(saida)

    print(f"bronze: {len(bronze)} linhas · prata: {len(saida)} linhas -> {SAIDA}")
    print(f"contas: {len(por_usuario)} · respostas por mês: {sorted(Counter(r['mes'] for r in saida).items())}")
    print(f"mojibake reparado: {mojibake}")
    print(f"flag_sem_comentario: {sum(r['flag_sem_comentario'] for r in saida)}")
    print(f"flag_resposta_repetida: {sum(r['flag_resposta_repetida'] for r in saida)} linhas"
          f" de {sum(1 for n in por_usuario.values() if n > 1)} contas")
    print(f"motivo_principal: {Counter(r['motivo_principal'] for r in saida).most_common()}")

    print("\ndiagnóstico (não altera a tabela): tema do comentário x motivo marcado")
    com_texto = [r for r in saida if r["comentario"]]
    cruz, sem_tema, diverge = Counter(), 0, 0
    for r in com_texto:
        nome, esperado = tema(r["comentario"])
        if nome is None:
            sem_tema += 1
            continue
        cruz[(nome, r["motivo_principal"])] += 1
        diverge += r["motivo_principal"] != esperado
    for nome, esperado, _ in TEMAS:
        linha = {m: n for (t, m), n in cruz.items() if t == nome}
        print(f"  {nome} (esperado {esperado}): {sum(linha.values())} · {dict(sorted(linha.items(), key=lambda x: -x[1]))}")
    print(f"  com comentário: {len(com_texto)} · sem tema: {sem_tema} · motivo diverge do tema: {diverge}")


if __name__ == "__main__":
    main()
