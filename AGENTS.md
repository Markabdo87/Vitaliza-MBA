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

## Estrutura

```
dados/
├── bronze/   # arquivos como vieram do curso. NUNCA editar.
├── prata/    # bronze limpo, uma tabela por arquivo de origem, mesma granularidade
└── ouro/     # tabelas de análise (agregados, base de modelagem, métricas)
scripts/      # um script por tabela gerada: <arquivo>_<camada>.py
```

Regras das camadas:
- Bronze é imutável. Toda correção vira código em `scripts/`, nunca edição à mão de CSV.
- Cada tabela de prata/ouro tem um script que a gera do zero e pode ser rodado de novo.
  As regras de limpeza ficam documentadas no cabeçalho (docstring) do próprio script.
- Prata não descarta informação que a análise pode precisar: corrige formato, remove
  duplicata comprovada e **marca** suspeitas com colunas `flag_*` em vez de apagar.
  Guarde o valor original em `<coluna>_bronze` quando corrigir um valor.
- Ao criar uma tabela nova, registre-a na seção "Tabelas prontas" abaixo.

Rodar (a partir da raiz do repo):
```bash
python3 scripts/pagamentos_prata.py
```
Scripts atuais usam só a biblioteca padrão do Python 3. Se uma dependência for necessária,
crie `requirements.txt` e use venv (`python3 -m venv .venv`).

## Armadilhas conhecidas dos dados

O dicionário avisa: ninguém limpou os dados, e formatos, fusos e nomes variam entre arquivos.
Já confirmado:

- **Fusos:** eventos das lojas (App Store / Google Play) vêm em UTC (`...Z`); o site grava em
  horário de Brasília. Converta tudo para Brasília antes de cortar por dia/mês.
- **Nomes de canal diferem entre arquivos:** `pagamentos` usa `cartao`/`pix_automatico`;
  `assinaturas` usa `web_cartao`/`web_pix` (e `interno` para cortesia).
- **pagamentos.csv** (detalhes no script `pagamentos_prata.py`):
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

| Tabela | Script | Grão | Observações |
|---|---|---|---|
| `dados/prata/pagamentos.csv` | `scripts/pagamentos_prata.py` | uma cobrança | inclui recusados; para faturamento filtre `status != 'recusado'` e some `valor` (bruto) ou `valor_liquido` (após taxas) |

Número de referência para conferir a prata: faturamento de set/2026 = R$ 489.873,50 bruto,
R$ 434.056,93 líquido de taxas.

## Regras de trabalho

- Mostre a regra junto com o número: a mesma conta dá resultados diferentes conforme o
  arquivo e a regra (o próprio enunciado avisa). Diga qual arquivo, filtro e corte usou.
- Não use informação posterior ao corte (30/09/2026) em variáveis de modelo.
- Textos de entrega descrevem o produto, não o processo ("corrigimos", "primeiro tentamos…").
- Não commite credenciais nem chaves de API (extração com IA). Use `.env`, fora do git.
