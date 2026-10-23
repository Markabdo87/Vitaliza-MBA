---
name: camadas-de-dados
description: Fluxo bronze → prata → ouro do case Vitaliza. Use ao limpar um arquivo da bronze, criar ou alterar uma tabela de prata ou ouro, escrever ou mexer num notebook em notebooks/, ou quando alguém perguntar onde um dado deve morar ou como deixar a análise verificável.
---

# Camadas de dados

A regra que vale para tudo: **qualquer número do trabalho tem que ser reproduzível por
outra pessoa do grupo**, partindo da bronze, rodando os notebooks e lendo o `decisoes.md`.
Código diz como, `decisoes.md` diz por quê, e a bronze nunca muda.

## O que é cada camada

| Camada | O que é | Grão | Vai pro git? |
|---|---|---|---|
| `dados/1.bronze/` | arquivos exatamente como o curso entregou | o do arquivo | sim, **e nunca se edita** |
| `dados/2.prata/` | bronze limpa: formato, fuso, duplicata, valor corrigido, suspeita marcada | **o mesmo da bronze**, uma tabela por arquivo de origem | não (gerada) |
| `dados/3.ouro/` | tabelas de análise: cruzamentos por `user_id`, agregados, base de modelagem, scores, lista do CRM | o que a pergunta pedir | não (gerada) |

- Prata não agrega nem cruza tabelas. Se precisou de `JOIN` ou `GROUP BY`, é ouro.
- Ouro lê **só da prata**, nunca da bronze.
- Variável de modelo não usa nada depois do corte (30/09/2026).

## Notebooks

Todo código que gera tabela mora em `notebooks/`, um arquivo por tabela:
`<tabela>_<camada>.py` (ex.: `pagamentos_prata.py`, `churn_mensal_ouro.py`).

- Gera a tabela **do zero** a cada execução e roda da raiz: `python3 notebooks/<arquivo>.py`.
- Caminhos relativos ao próprio arquivo (`Path(__file__).resolve().parent.parent / "dados"`),
  nunca absolutos da máquina de alguém.
- **Docstring no topo** com as regras aplicadas, em lista numerada, e o comando de uso. A
  docstring e o `decisoes.md` têm que descrever a mesma regra.
- Biblioteca padrão quando der. Se precisar de pandas e afins, crie `requirements.txt` e use
  venv (`python3 -m venv .venv`); avise o grupo no handoff.
- `.py` ou Jupyter (`.ipynb`), a gosto de quem escreve. Num `.ipynb`, as regras vão na
  primeira célula (markdown) e ele tem que rodar inteiro ("Run all") sem erro.

## Fluxo para uma tabela nova de prata

1. **Leia a fonte**: a seção do arquivo no `Vitaliza - Dicionário de dados.pdf` e as
   "Armadilhas conhecidas" do `AGENTS.md`.
2. **Perfile a bronze** antes de corrigir: contagem de linhas, nulos, duplicatas, formatos
   de data/valor, categorias distintas, fuso. Anote o que estranhar.
3. **Decida cada problema**: corrigir, remover, marcar (`flag_*`) ou manter. Guarde o valor
   original em `<coluna>_bronze` quando corrigir. Na dúvida entre remover e marcar, marque.
4. **Escreva o notebook** `notebooks/<arquivo>_prata.py` com a docstring das regras.
5. **Rode e meça**: contagem antes/depois e o efeito de cada regra (linhas e R$). Esses
   números vão para o `decisoes.md`.
6. **Registre** com a skill `registrar-decisao`: uma linha por problema, com ID.
7. **Cadastre a tabela** em "Tabelas prontas" do `AGENTS.md`, na tabela do `README.md` e no
   `README.md` da camada (`dados/2.prata/README.md` ou `dados/3.ouro/README.md`).
8. **Armadilha nova** dos dados (que afeta outros arquivos)? Acrescente em "Armadilhas
   conhecidas" do `AGENTS.md`.
9. **Suba** com a skill `git-do-grupo`: notebook + `decisoes.md` + READMEs no mesmo commit.

Para ouro é o mesmo fluxo, com uma diferença: em vez de "problemas" você registra as
definições (o que é churn, ativo, janela, filtro de população) e o número de referência.

## Antes de dizer que terminou

- Rodou do zero e os números batem com o `decisoes.md`?
- Nenhum arquivo da bronze mudou (`git status dados/1.bronze` limpo)?
- Toda regra da docstring tem linha no `decisoes.md`, e vice-versa?
- Ao apresentar um número, diga de qual tabela, filtro e corte ele saiu.
