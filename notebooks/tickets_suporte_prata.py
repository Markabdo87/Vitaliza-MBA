"""Bronze -> prata: tickets_suporte.csv limpo (um chamado por linha, mesmo grão da bronze).

Correções aplicadas:
  1. texto_cliente: strip, vazio vira nulo e reparo de mojibake (UTF-8 lido como Latin-1)
     quando aparecer. O texto fica como o cliente escreveu: erros de digitação, falta de
     acento e maiúsculas ("GPS"/"gps") são mantidos; a leitura é tarefa da extração com IA.
  2. canal, categoria_atendente, status: strip + minúsculas e conferência contra a lista
     do dicionário (canal: chat/email/loja; status: resolvido/aberto/sem_resposta;
     categoria: as seis que aparecem). Valor fora da lista interrompe o script. Na bronze
     atual nenhum valor muda, por isso não há colunas <coluna>_bronze.
  3. aberto_em: já está em horário de Brasília em todos os canais (inclusive loja: as
     aberturas caem entre 08h e 21h nos três canais, sem o deslocamento de 3h do UTC).
     Mantido como está; coluna nova mes (AAAA-MM).
  4. resolvido_em: só data. Coluna nova dias_resolucao = resolvido_em - data de abertura.
     Conferido: resolvido_em nunca é anterior à abertura, todo 'resolvido' tem data e
     nenhum 'aberto'/'sem_resposta' tem.

Não remove nada. Casos que pedem atenção viram flag:
  flag_texto_vazio          texto_cliente vazio
  flag_resolvido_pos_corte  resolvido_em depois de 30/09/2026: no corte o chamado estava
                            aberto; variável de modelo tem que tratá-lo como aberto
  flag_aberto_antigo        status 'aberto' com abertura há mais de 20 dias do corte (o
                            maior prazo de resolução observado é 19 dias)

Diagnóstico impresso (não altera a tabela): categoria do atendente x texto. O texto é
normalizado (minúsculas, sem acento), aproximado por difflib à mensagem-base mais próxima
entre as que aparecem 20+ vezes, e comparado à categoria mais comum daquela mensagem.

Uso: python3 notebooks/tickets_suporte_prata.py  (a partir da raiz do repo)
"""
import csv
import difflib
import unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "dados"
ENTRADA = BASE / "1.bronze" / "tickets_suporte.csv"
SAIDA = BASE / "2.prata" / "tickets_suporte.csv"

CORTE = date(2026, 9, 30)
ABERTO_ANTIGO = timedelta(days=20)
CANAIS = {"chat", "email", "loja"}
STATUS = {"resolvido", "aberto", "sem_resposta"}
CATEGORIAS = {"tecnico", "cancelamento", "conta", "cobranca", "conteudo", "duvida_geral"}

COLUNAS = [
    "ticket_id", "user_id", "aberto_em", "mes", "canal", "texto_cliente",
    "categoria_atendente", "status", "resolvido_em", "dias_resolucao",
    "flag_texto_vazio", "flag_resolvido_pos_corte", "flag_aberto_antigo",
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


def categoria_fechada(valor, dominio, coluna, ticket):
    v = valor.strip().lower()
    if v not in dominio:
        raise ValueError(f"{coluna} fora do dicionário: {ticket} {valor!r}")
    return v


def main():
    with open(ENTRADA, newline="", encoding="utf-8") as f:
        bronze = list(csv.DictReader(f))

    saida, mojibake, alteradas = [], 0, Counter()
    for r in bronze:
        tid = r["ticket_id"]
        canal = categoria_fechada(r["canal"], CANAIS, "canal", tid)
        categoria = categoria_fechada(r["categoria_atendente"], CATEGORIAS, "categoria", tid)
        status = categoria_fechada(r["status"], STATUS, "status", tid)
        for col, novo in (("canal", canal), ("categoria_atendente", categoria), ("status", status)):
            alteradas[col] += novo != r[col]
        texto = conserta_mojibake(r["texto_cliente"].strip())
        mojibake += texto != r["texto_cliente"].strip()

        aberto = datetime.strptime(r["aberto_em"].strip(), "%Y-%m-%d %H:%M:%S")
        resolvido = date.fromisoformat(r["resolvido_em"]) if r["resolvido_em"].strip() else None
        if (status == "resolvido") != (resolvido is not None):
            raise ValueError(f"status x resolvido_em inconsistente: {tid}")
        dias = (resolvido - aberto.date()).days if resolvido else None
        if dias is not None and dias < 0:
            raise ValueError(f"resolvido antes de aberto: {tid}")
        saida.append({
            "ticket_id": tid,
            "user_id": r["user_id"],
            "aberto_em": aberto.strftime("%Y-%m-%d %H:%M:%S"),
            "mes": aberto.strftime("%Y-%m"),
            "canal": canal,
            "texto_cliente": texto,
            "categoria_atendente": categoria,
            "status": status,
            "resolvido_em": resolvido.isoformat() if resolvido else "",
            "dias_resolucao": "" if dias is None else dias,
            "flag_texto_vazio": int(texto == ""),
            "flag_resolvido_pos_corte": int(resolvido is not None and resolvido > CORTE),
            "flag_aberto_antigo": int(status == "aberto" and CORTE - aberto.date() > ABERTO_ANTIGO),
        })

    saida.sort(key=lambda r: (r["aberto_em"], r["ticket_id"]))
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    with open(SAIDA, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUNAS)
        w.writeheader()
        w.writerows(saida)

    print(f"bronze: {len(bronze)} linhas · prata: {len(saida)} linhas -> {SAIDA}")
    print(f"período: {saida[0]['aberto_em']} a {saida[-1]['aberto_em']}")
    print(f"categorias fechadas alteradas: {dict(alteradas)} · mojibake reparado: {mojibake}")
    print(f"status: {Counter(r['status'] for r in saida).most_common()}")
    dias = [r["dias_resolucao"] for r in saida if r["dias_resolucao"] != ""]
    print(f"dias_resolucao: min {min(dias)} · max {max(dias)} · média {sum(dias) / len(dias):.1f}")
    for flag in ("flag_texto_vazio", "flag_resolvido_pos_corte", "flag_aberto_antigo"):
        print(f"{flag}: {sum(r[flag] for r in saida)}")
    por_usuario = Counter(r["user_id"] for r in saida)
    print(f"contas: {len(por_usuario)} · com 2+ chamados: {sum(1 for n in por_usuario.values() if n > 1)}")
    print(f"chamados por mês: {sorted(Counter(r['mes'] for r in saida).items())}")
    print(f"textos distintos: {len(set(r['texto_cliente'] for r in saida))}")

    print("\ndiagnóstico (não altera a tabela): categoria do atendente x texto")
    norm = Counter(normaliza(r["texto_cliente"]) for r in saida)
    bases = [t for t, n in norm.items() if n >= 20]
    cat_por_base = defaultdict(Counter)
    base_de = {}
    for r in saida:
        t = normaliza(r["texto_cliente"])
        achou = [t] if t in bases else difflib.get_close_matches(t, bases, n=1, cutoff=0.8)
        base_de[r["ticket_id"]] = achou[0] if achou else None
        if achou:
            cat_por_base[achou[0]][r["categoria_atendente"]] += 1
    esperada = {b: c.most_common(1)[0][0] for b, c in cat_por_base.items()}
    sem_base = sum(1 for b in base_de.values() if b is None)
    diverge = Counter()
    for r in saida:
        b = base_de[r["ticket_id"]]
        if b and r["categoria_atendente"] != esperada[b]:
            diverge[(esperada[b], r["categoria_atendente"])] += 1
    total = len(saida) - sem_base
    print(f"  mensagens-base: {len(bases)} · chamados aproximados: {total} · sem base: {sem_base}")
    print(f"  categoria diferente da mais comum da mensagem: {sum(diverge.values())}"
          f" ({sum(diverge.values()) / total:.1%})")
    por_esperada = Counter()
    for (e, _), n in diverge.items():
        por_esperada[e] += n
    print(f"  por categoria esperada: {por_esperada.most_common()}")
    for b in sorted(esperada, key=lambda b: -sum(cat_por_base[b].values()))[:3]:
        print(f"  ex.: {b!r} -> {dict(cat_por_base[b].most_common())}")

    pico = Counter(base_de[r["ticket_id"]] for r in saida if r["mes"] in ("2026-05", "2026-06"))
    resto = Counter(base_de[r["ticket_id"]] for r in saida if r["mes"] not in ("2026-05", "2026-06"))
    print("\n  mai-jun/2026 x resto (mensagens que mais crescem):")
    for b, n in sorted(pico.items(), key=lambda x: -(x[1] - resto.get(x[0], 0) * 2 / 13))[:5]:
        print(f"    {b!r}: {n} em 2 meses · {resto.get(b, 0)} nos outros 13")


if __name__ == "__main__":
    main()
