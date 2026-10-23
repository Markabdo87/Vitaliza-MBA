# AGENTS.md — Case Vitaliza · Grupo 07

Contexto para agentes de IA (Claude Code, Codex, Cursor…) que trabalharem neste repositório.
Este é o arquivo-fonte: o `CLAUDE.md` só importa este aqui. **Edite apenas o AGENTS.md.**

Conversas e textos de entrega em pt-BR; código, nomes de arquivo e commits em inglês ou pt-BR
sem acento, como já está no repo.

## O case

Inteli MBA · Módulo 2 (Inteligência de Mercado e Modelagem Preditiva). A Vitaliza é um app
brasileiro (fictício) de assinatura para quem treina. O churn mensal subiu de 5,6% (2025) para
6,6% (jan–set/2026). O case percorre descritiva → diagnóstica → preditiva → prescritiva:
medir a base, explicar a subida, segmentar, prever quem sai em 60 dias (até 29/11/2026),
extrair variáveis de texto/imagem com IA, decidir quem contatar (uplift, campanha de ago/26),
calcular o retorno em R$ e escrever a mensagem.

Fontes oficiais, na raiz:
- `Vitaliza - Enunciado do case.pdf` — objetivos (seção 02) e premissas de negócio (seção 03:
  preços, taxas, custos, CAC, limites do CRM). Toda conta de R$ parte da seção 03.
- `Vitaliza - Dicionário de dados.pdf` — colunas de cada arquivo. Corte dos dados: 30/09/2026.

Na dúvida sobre um número ou regra de negócio, confira no PDF; não invente premissa.

## Como o grupo trabalha

Quatro pessoas, um repo (`origin` = `github.com/Markabdo87/Vitaliza-MBA`), ramo `main`.
A palavra-chave é **verificável**: qualquer número tem que poder ser refeito por outra
pessoa a partir da bronze, rodando os notebooks e lendo o `decisoes.md`.

Três peças, cada uma com uma skill em `.claude/skills/` (outros agentes: leiam o `SKILL.md`
correspondente quando a situação aparecer):

| Peça | Regra curta | Skill |
|---|---|---|
| **Git** | Ao abrir a sessão, puxe o que o grupo subiu. Ao fechar, commit + `pull --rebase` + push (com confirmação) + handoff na seção "Em aberto" do `decisoes.md` | `git-do-grupo` |
| **`decisoes.md`** | Log de toda decisão e premissa que muda um número: limpeza, premissa de negócio, definição de métrica, escolha de análise. ID, motivo e efeito numérico. Não se apaga linha antiga, risca e aponta para a nova | `registrar-decisao` |
| **Camadas** | bronze (imutável) → prata (limpa, mesmo grão) → ouro (cruzada/agregada). Cada tabela tem um notebook que a gera do zero | `camadas-de-dados` |

Ciclo de uma limpeza: perfila a bronze → decide cada problema → escreve
`notebooks/<arquivo>_prata.py` com as regras na docstring → roda e mede → registra no
`decisoes.md` → cadastra a tabela abaixo → sobe tudo no mesmo commit.

O `.claude/settings.json` bloqueia edição da bronze, leitura de `.env`, `push --force`,
`reset --hard` e `git clean`, e roda um hook no início da sessão que compara o repo com o
`origin`.

## Estrutura

```
dados/
├── 1.bronze/   # arquivos como vieram do curso. NUNCA editar.
├── 2.prata/    # bronze limpa, uma tabela por arquivo de origem, mesma granularidade
└── 3.ouro/     # tabelas de análise (cruzamentos, agregados, base de modelagem, scores)
notebooks/      # um notebook por tabela gerada: <tabela>_<camada>.py
decisoes.md     # ★ fonte da verdade: decisões, premissas e pendências ("Em aberto")
.claude/        # settings do projeto, hook de início de sessão e skills
```

Regras das camadas:
- Bronze é imutável. Toda correção vira código em `notebooks/`, nunca edição à mão de CSV.
- Prata: corrige formato, remove duplicata comprovada e **marca** suspeitas com colunas
  `flag_*` em vez de apagar. Guarde o valor original em `<coluna>_bronze` quando corrigir.
  Não agrega nem cruza tabelas.
- Ouro: lê só da prata; aqui se cruza por `user_id` e se agrega.
- Prata e ouro não vão para o git: são recriadas rodando os notebooks.
- Cada notebook gera sua tabela do zero, roda da raiz e documenta as regras na docstring.
  Pode ser `.py` ou Jupyter (`.ipynb`), a gosto de quem escreve: o que importa é rodar do zero.
- Ao criar uma tabela nova, registre-a em "Tabelas prontas" abaixo.

Rodar (a partir da raiz do repo):
```bash
python3 notebooks/pagamentos_prata.py
```
Notebooks atuais usam só a biblioteca padrão do Python 3. Se uma dependência for necessária,
crie `requirements.txt` e use venv (`python3 -m venv .venv`).

## Armadilhas conhecidas dos dados

O dicionário avisa: ninguém limpou os dados, e formatos, fusos e nomes variam entre arquivos.
Já confirmado:

- **Fusos:** eventos das lojas (App Store / Google Play) vêm em UTC (`...Z`); o site grava em
  horário de Brasília. Converta tudo para Brasília antes de cortar por dia/mês.
- **Nomes de canal diferem entre arquivos:** `pagamentos` usa `cartao`/`pix_automatico`;
  `assinaturas` usa `web_cartao`/`web_pix` (e `interno` para cortesia).
- **pagamentos.csv** (detalhes no notebook `pagamentos_prata.py`):
  - 1.941 cobranças duplicadas (mesmo usuário, segundo, valor e status, IDs seguidos);
  - valor do site em `R$ 39,90` até jun/2025, depois `39.90`;
  - estornos/chargebacks lançados pelo preço de tabela, não pelo valor cobrado
    (−39,90 em quem pagou 34,90; −299,90 em quem pagou 239,90 com cupom);
  - a coluna `tentativa` não registra retentativa: recusa seguida de nova cobrança aparece
    como `tentativa = 1` de novo. Use `tentativa_real` da prata.
- Preço: mensal R$ 34,90 até 28/02/2026 e R$ 39,90 desde 01/03/2026; anual R$ 299,90
  (R$ 239,90 no 1º ano com cupom de influenciador).

Ao descobrir uma armadilha nova, acrescente aqui.

## Tabelas prontas

| Tabela | Notebook | Grão | Observações |
|---|---|---|---|
| `dados/2.prata/pagamentos.csv` | `notebooks/pagamentos_prata.py` | uma cobrança | inclui recusados; para faturamento filtre `status != 'recusado'` e some `valor` (bruto) ou `valor_liquido` (após taxas) |

Número de referência para conferir a prata: faturamento de set/2026 = R$ 489.873,50 bruto,
R$ 434.056,93 líquido de taxas.

## Regras de trabalho

- Mostre a regra junto com o número: a mesma conta dá resultados diferentes conforme o
  arquivo e a regra (o próprio enunciado avisa). Diga qual arquivo, filtro e corte usou.
- Não use informação posterior ao corte (30/09/2026) em variáveis de modelo.
- Textos de entrega descrevem o produto, não o processo ("corrigimos", "primeiro tentamos…").
- Não commite credenciais nem chaves de API (extração com IA). Use `.env`, fora do git.
- Não faça push sem a pessoa confirmar: o repo é do grupo inteiro.
