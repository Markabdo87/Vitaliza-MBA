"""Bronze -> prata: usuarios.csv limpo, uma linha por conta.

Correções aplicadas:
  1. contas duplicadas: mesma pessoa cadastrada duas vezes. O e-mail difere só em
     maiúsculas, todos os outros campos e a hora do cadastro são iguais, a data muda.
     Fica a conta mais antiga; a outra sai e o user_id dela vai para user_id_duplicado.
     A conta removida não aparece em nenhum outro arquivo do data room.
  2. data_cadastro: já está em horário de Brasília (sem "Z", horas de 06h a 22h em iOS e
     Android). Não muda; ganha mes_cadastro.
  3. data_nascimento: 1900-01-01 (valor padrão) e 2031-05-12 (futuro, depois do cadastro)
     viram vazio; original em data_nascimento_bronze. idade_corte = idade em 30/09/2026.
  4. sexo: F/Fem/feminino -> F; M/Masc/masculino -> M; vazio fica vazio.
  5. cidade: grafias da mesma cidade (Sampa, SAO PAULO, BH, Floripa, BSB, "- SP"...) viram
     o nome oficial com acento. Original em cidade_bronze.
  6. cep_prefixo: com 2 dígitos perdeu o zero à esquerda (todos de São Paulo capital,
     CEP 01-09); ganha o "0". Vazio fica vazio.
  7. sistema: ios/iOS/IOS -> ios; Android/android -> android.

Não remove nada além das duplicatas. Casos suspeitos viram flag:
  flag_conta_teste                 canal 'interno', e-mail @vitaliza.com.br (teste/qa)
  flag_nascimento_invalido         data_nascimento da bronze era padrão ou futura
  flag_hora_cadastro_desconhecida  cadastro antes de 01/07/2024: só a data é real, a hora
                                   está fixa em 12:00:00

Uso: python3 notebooks/usuarios_prata.py  (a partir da raiz do repo)
"""
import csv
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "dados"
ENTRADA = BASE / "1.bronze" / "usuarios.csv"
SAIDA = BASE / "2.prata" / "usuarios.csv"

CORTE = "2026-09-30"
INICIO_HORA_REAL = "2024-07-01"
NASCIMENTO_INVALIDO = {"1900-01-01", "2031-05-12"}

SEXO = {"F": "F", "Fem": "F", "feminino": "F", "M": "M", "Masc": "M", "masculino": "M", "": ""}
CIDADE = {
    "Sampa": "São Paulo", "são paulo": "São Paulo", "São Paulo - SP": "São Paulo",
    "Sao Paulo": "São Paulo", "S. Paulo": "São Paulo", "SAO PAULO": "São Paulo", "SP": "São Paulo",
    "Rio de janeiro": "Rio de Janeiro", "rio de janeiro": "Rio de Janeiro", "RJ": "Rio de Janeiro",
    "RIO DE JANEIRO": "Rio de Janeiro", "Rio": "Rio de Janeiro",
    "Belo horizonte": "Belo Horizonte", "B. Horizonte": "Belo Horizonte",
    "BELO HORIZONTE": "Belo Horizonte", "BH": "Belo Horizonte",
    "floripa": "Florianópolis", "Floripa": "Florianópolis", "Florianopolis": "Florianópolis",
    "Brasília - DF": "Brasília", "BSB": "Brasília", "brasilia": "Brasília", "Brasilia": "Brasília",
}
CIDADES_OFICIAIS = {
    "São Paulo", "Rio de Janeiro", "Belo Horizonte", "Florianópolis", "Brasília", "Curitiba",
    "Porto Alegre", "Campinas", "Goiânia", "Santos", "Recife", "Fortaleza", "Salvador",
}

COLUNAS = [
    "user_id", "email", "data_cadastro", "mes_cadastro", "data_nascimento",
    "data_nascimento_bronze", "idade_corte", "sexo", "sexo_bronze", "cidade", "cidade_bronze",
    "uf", "cep_prefixo", "cep_prefixo_bronze", "canal_aquisicao", "sistema", "sistema_bronze",
    "versao_app", "relogio_conectado", "user_id_duplicado", "flag_conta_teste",
    "flag_nascimento_invalido", "flag_hora_cadastro_desconhecida",
]

# campos que têm que ser iguais para duas contas serem a mesma pessoa
COLUNAS_COPIA = [
    "data_nascimento", "sexo", "cidade", "uf", "cep_prefixo", "canal_aquisicao",
    "sistema", "versao_app", "relogio_conectado",
]


def idade(nascimento, em=CORTE):
    if not nascimento:
        return ""
    return int(em[:4]) - int(nascimento[:4]) - (em[5:] < nascimento[5:])


def main():
    with open(ENTRADA, newline="") as f:
        bronze = list(csv.DictReader(f))

    # 1. duplicatas: agrupa pelo e-mail em minúsculas, fica a conta mais antiga
    por_email = defaultdict(list)
    for r in bronze:
        por_email[r["email"].lower()].append(r)
    linhas, removidas = [], []
    for grupo in por_email.values():
        grupo.sort(key=lambda r: (r["data_cadastro"], r["user_id"]))
        principal, *extras = grupo
        for e in extras:  # confirma que é cópia: tudo igual menos user_id, e-mail e data
            iguais = all(e[c] == principal[c] for c in COLUNAS_COPIA)
            assert iguais and e["data_cadastro"][11:] == principal["data_cadastro"][11:], e
        principal = {**principal, "user_id_duplicado": ";".join(e["user_id"] for e in extras)}
        linhas.append(principal)
        removidas.extend(extras)

    efeito = Counter()
    saida = []
    for r in linhas:
        nasc = r["data_nascimento"]
        nasc_invalido = nasc in NASCIMENTO_INVALIDO
        cidade = CIDADE.get(r["cidade"], r["cidade"])
        assert cidade in CIDADES_OFICIAIS, r["cidade"]
        cep = r["cep_prefixo"]
        cep_novo = cep.zfill(3) if cep else ""
        sistema = r["sistema"].lower()
        teste = r["canal_aquisicao"] == "interno"
        hora_desconhecida = r["data_cadastro"] < INICIO_HORA_REAL
        if hora_desconhecida:
            assert r["data_cadastro"].endswith("12:00:00"), r
        nasc_novo = "" if nasc_invalido else nasc

        efeito["nascimento_invalido"] += nasc_invalido
        efeito["nascimento_vazio_bronze"] += nasc == ""
        efeito["sexo_corrigido"] += SEXO[r["sexo"]] != r["sexo"]
        efeito["cidade_corrigida"] += cidade != r["cidade"]
        efeito["cep_zero"] += cep_novo != cep
        efeito["sistema_corrigido"] += sistema != r["sistema"]
        efeito["teste"] += teste
        efeito["hora_desconhecida"] += hora_desconhecida
        efeito["cadastro_apos_corte"] += r["data_cadastro"][:10] > CORTE
        saida.append({
            "user_id": r["user_id"],
            "email": r["email"],
            "data_cadastro": r["data_cadastro"],
            "mes_cadastro": r["data_cadastro"][:7],
            "data_nascimento": nasc_novo,
            "data_nascimento_bronze": nasc,
            "idade_corte": idade(nasc_novo),
            "sexo": SEXO[r["sexo"]],
            "sexo_bronze": r["sexo"],
            "cidade": cidade,
            "cidade_bronze": r["cidade"],
            "uf": r["uf"],
            "cep_prefixo": cep_novo,
            "cep_prefixo_bronze": cep,
            "canal_aquisicao": r["canal_aquisicao"],
            "sistema": sistema,
            "sistema_bronze": r["sistema"],
            "versao_app": r["versao_app"],
            "relogio_conectado": r["relogio_conectado"],
            "user_id_duplicado": r["user_id_duplicado"],
            "flag_conta_teste": int(teste),
            "flag_nascimento_invalido": int(nasc_invalido),
            "flag_hora_cadastro_desconhecida": int(hora_desconhecida),
        })

    saida.sort(key=lambda r: (r["data_cadastro"], r["user_id"]))
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    with open(SAIDA, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUNAS)
        w.writeheader()
        w.writerows(saida)

    removidas_futuras = sum(1 for r in removidas if r["data_cadastro"][:10] > CORTE)
    idades = [r["idade_corte"] for r in saida if r["idade_corte"] != ""]
    print(f"bronze: {len(bronze)} linhas · prata: {len(saida)} linhas -> {SAIDA}")
    print(f"1. duplicatas removidas: {len(removidas)} (com cadastro depois do corte: {removidas_futuras})"
          f" · cadastro depois do corte que sobra na prata: {efeito['cadastro_apos_corte']}")
    print(f"2. hora do cadastro desconhecida (antes de {INICIO_HORA_REAL}): {efeito['hora_desconhecida']}")
    print(f"3. nascimento inválido -> vazio: {efeito['nascimento_invalido']}"
          f" ({Counter(r['data_nascimento_bronze'] for r in saida if r['flag_nascimento_invalido'])})"
          f" · já vazio na bronze: {efeito['nascimento_vazio_bronze']}"
          f" · idade_corte {min(idades)}-{max(idades)}, menores de 18: {sum(1 for i in idades if i < 18)}")
    print(f"4. sexo padronizado: {efeito['sexo_corrigido']} · {Counter(r['sexo'] for r in saida)}")
    print(f"5. cidade padronizada: {efeito['cidade_corrigida']}")
    print(f"6. cep com zero à esquerda: {efeito['cep_zero']}"
          f" · cep vazio: {sum(1 for r in saida if not r['cep_prefixo'])}")
    print(f"7. sistema padronizado: {efeito['sistema_corrigido']} · {Counter(r['sistema'] for r in saida)}")
    print(f"flag_conta_teste: {efeito['teste']}")


if __name__ == "__main__":
    main()
