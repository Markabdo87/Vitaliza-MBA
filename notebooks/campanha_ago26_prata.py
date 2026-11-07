"""Bronze -> prata: campanha_ago26.csv (um assinante sorteado por linha, campanha de 10/08/2026).

Regras aplicadas:
  1. user_id repetido: fica a primeira linha (a bronze não tem nenhum).
  2. grupo: minúsculo e sem espaço; só controle, desafio, cupom ou conteudo. Outro valor
     faz o notebook parar.
  3. tratado = 1 para desafio, cupom e conteudo; 0 para controle. É a variável de
     tratamento do uplift.
  4. enviado_em: "AAAA-MM-DD HH:MM:SS" sem fuso, gravado pelo CRM da própria Vitaliza.
     Premissa: horário de Brasília (como o site); vai para enviado_em_brt sem conversão.
     Vazio no controle, que não recebeu nada.
  5. booleanos abriu_push, abriu_email, clicou: "True"/"False" viram 1/0.
     abriu = 1 se abriu o push ou o e-mail.
  6. incoerências que viram flag (a linha fica):
       flag_inconsistente  controle com envio, canal, título, oferta ou engajamento;
                           tratado sem envio, ou envio fora de ago/2026;
                           oferta fora do grupo cupom, ou cupom sem oferta;
                           título diferente do previsto para o grupo.
       flag_clicou_sem_abrir  clicou = 1 com abriu_push = abriu_email = 0.

Mesmo grão da bronze. Não cruza com assinaturas.csv: a coerência da oferta com o plano
(30pct_3_meses = mensal, 1_mes_gratis = anual) foi conferida só no perfil.

Uso: python3 notebooks/campanha_ago26_prata.py  (a partir da raiz do repo)
"""
import csv
from collections import Counter
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "dados"
ENTRADA = BASE / "1.bronze" / "campanha_ago26.csv"
SAIDA = BASE / "2.prata" / "campanha_ago26.csv"

TITULO = {
    "desafio": "Novo desafio de 6 semanas montado para você",
    "cupom": "Oferta para voltar a treinar",
    "conteudo": "Seu plano de treino personalizado está pronto",
}
GRUPOS = {"controle", *TITULO}
OFERTAS = {"30pct_3_meses", "1_mes_gratis"}
BOOL = {"true": 1, "false": 0, "1": 1, "0": 0, "sim": 1, "nao": 0, "não": 0}

COLUNAS = [
    "user_id", "grupo", "tratado", "enviado_em_brt", "canal", "titulo_mensagem", "oferta",
    "abriu_push", "abriu_email", "abriu", "clicou", "flag_inconsistente", "flag_clicou_sem_abrir",
]


def booleano(s):
    return BOOL[s.strip().lower()]  # valor fora do mapa faz o notebook parar


def main():
    with open(ENTRADA, newline="") as f:
        bronze = list(csv.DictReader(f))
    print(f"bronze: {len(bronze)} linhas · grupos: {dict(Counter(r['grupo'] for r in bronze))}")

    vistos, saida, repetidos = set(), [], 0
    for r in bronze:
        uid = r["user_id"].strip()
        if uid in vistos:  # regra 1
            repetidos += 1
            continue
        vistos.add(uid)

        grupo = r["grupo"].strip().lower()  # regra 2
        if grupo not in GRUPOS:
            raise ValueError(f"grupo desconhecido: {r['grupo']!r}")
        tratado = int(grupo != "controle")  # regra 3

        enviado = r["enviado_em"].strip()  # regra 4
        t = datetime.strptime(enviado, "%Y-%m-%d %H:%M:%S") if enviado else None
        canal, titulo, oferta = r["canal"].strip(), r["titulo_mensagem"].strip(), r["oferta"].strip()

        push, email, clicou = booleano(r["abriu_push"]), booleano(r["abriu_email"]), booleano(r["clicou"])  # regra 5
        abriu = int(push or email)

        if tratado:  # regra 6
            inconsistente = bool(
                t is None or (t.year, t.month) != (2026, 8) or canal != "push+email"
                or titulo != TITULO[grupo]
                or (grupo == "cupom") != (oferta in OFERTAS) or (oferta and oferta not in OFERTAS)
            )
        else:
            inconsistente = bool(enviado or canal or titulo or oferta or push or email or clicou)

        saida.append({
            "user_id": uid,
            "grupo": grupo,
            "tratado": tratado,
            "enviado_em_brt": t.strftime("%Y-%m-%d %H:%M:%S") if t else "",
            "canal": canal,
            "titulo_mensagem": titulo,
            "oferta": oferta,
            "abriu_push": push,
            "abriu_email": email,
            "abriu": abriu,
            "clicou": clicou,
            "flag_inconsistente": int(inconsistente),
            "flag_clicou_sem_abrir": int(clicou and not abriu),
        })

    saida.sort(key=lambda r: r["user_id"])
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    with open(SAIDA, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUNAS)
        w.writeheader()
        w.writerows(saida)

    print(f"prata: {len(saida)} linhas -> {SAIDA}")
    print(f"  regra 1 user_id repetidos removidos: {repetidos}")
    print(f"  regra 3 tratado: {sum(r['tratado'] for r in saida)} · controle: {sum(1 - r['tratado'] for r in saida)}")
    print(f"  regra 4 envios: {dict(Counter(r['enviado_em_brt'] for r in saida if r['enviado_em_brt']))}")
    print(f"  regra 6 flag_inconsistente: {sum(r['flag_inconsistente'] for r in saida)}"
          f" · flag_clicou_sem_abrir: {sum(r['flag_clicou_sem_abrir'] for r in saida)}")
    print("  por grupo (n · abriu push · abriu e-mail · abriu algum · clicou):")
    for g in ["controle", "desafio", "cupom", "conteudo"]:
        rs = [r for r in saida if r["grupo"] == g]
        n = len(rs)
        taxa = lambda c: f"{sum(r[c] for r in rs) / n:.1%}"
        print(f"    {g:9s} {n:5d} · {taxa('abriu_push')} · {taxa('abriu_email')} · {taxa('abriu')} · {taxa('clicou')}")
    print(f"  ofertas no cupom: {dict(Counter(r['oferta'] for r in saida if r['grupo'] == 'cupom'))}")


if __name__ == "__main__":
    main()
