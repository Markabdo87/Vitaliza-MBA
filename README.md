# Case Vitaliza · Módulo 2 · Grupo 07

Case do MBA em IA e Dados para Negócios (Inteli), Módulo 2 — Inteligência de Mercado e
Modelagem Preditiva para Crescimento.

A Vitaliza é um app brasileiro de assinatura para quem treina (corrida com GPS, treinos em
vídeo e rede social). O churn mensal subiu de 5,6% em 2025 para 6,6% em jan–set/2026. O case
pede para medir a base, explicar a subida, segmentar os assinantes, prever quem sai nos 60
dias seguintes ao corte, decidir quem contatar e com qual mensagem, e calcular quanto a ação
rende em reais.

O enunciado e o dicionário de dados estão na raiz, em PDF. Corte dos dados: 30/09/2026.

## Estrutura

```
├── Vitaliza - Enunciado do case.pdf
├── Vitaliza - Dicionário de dados.pdf
├── dados/
│   ├── 1.bronze/   # arquivos originais do curso (não editar)
│   ├── 2.prata/    # bronze limpo — gerado pelos notebooks, fora do git
│   └── 3.ouro/     # tabelas de análise — gerado pelos notebooks, fora do git
└── notebooks/        # um notebook por tabela: <arquivo>_<camada>.py
```

## Como rodar

Requer Python 3. Os notebooks usam a biblioteca padrão, menos `atividades_prata.py`, que
lê parquet com `pyarrow`. A partir da raiz:

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # uma vez
for n in notebooks/*_prata.py; do .venv/bin/python "$n"; done        # gera toda a prata
```

Prata e ouro não são versionados: depois de clonar ou de atualizar um notebook, rode os notebooks
para gerar as tabelas.

## Tabelas

| Tabela | Notebook | O que tem |
|---|---|---|
| `dados/2.prata/usuarios.csv` | `notebooks/usuarios_prata.py` | contas sem duplicatas, cidade/sexo/sistema padronizados, idade no corte, contas de teste marcadas |
| `dados/2.prata/assinaturas.csv` | `notebooks/assinaturas_prata.py` | retrato de cada assinatura no corte, com `canal`/`metodo` nos rótulos de pagamentos e cortesias marcadas |
| `dados/2.prata/eventos_assinatura.csv` | `notebooks/eventos_assinatura_prata.py` | log de eventos em horário de Brasília, ordenado por usuário, com fase trial/assinatura e sequências estranhas marcadas |
| `dados/2.prata/pagamentos.csv` | `notebooks/pagamentos_prata.py` | cobranças sem duplicatas, em horário de Brasília, valor numérico, devoluções pelo valor cobrado, tentativa reconstruída, taxa e valor líquido |
| `dados/2.prata/uso_mensal.csv` | `notebooks/uso_mensal_prata.py` | uso por usuário e mês, valores intactos, com flags para mês sem treino e mudança de contagem de sessões |
| `dados/2.prata/atividades.parquet` | `notebooks/atividades_prata.py` | treinos em horário de Brasília (Garmin corrigido), tipo em português, sem cópias relógio+app, distância e duração corrigidas |
| `dados/2.prata/amizades.csv` | `notebooks/amizades_prata.py` | relações de seguir com `reciproco` e relações depois do corte marcadas |
| `dados/2.prata/campanha_ago26.csv` | `notebooks/campanha_ago26_prata.py` | experimento de ago/26 com `tratado` (1/0) e booleanos em 1/0 |
| `dados/2.prata/onboarding.csv` | `notebooks/onboarding_prata.py` | respostas do onboarding com `dias_por_semana` inteiro e respostas sem conteúdo marcadas |
| `dados/2.prata/feed_posts.csv` | `notebooks/feed_posts_prata.py` | posts com texto limpo, posts removidos e posts depois do corte marcados |
| `dados/2.prata/pesquisa_saida.csv` | `notebooks/pesquisa_saida_prata.py` | respostas de saída com comentário bruto para a extração com IA |
| `dados/2.prata/tickets_suporte.csv` | `notebooks/tickets_suporte_prata.py` | chamados com tempo de resolução, resolvidos depois do corte e abandonados marcados |

As regras de limpeza de cada tabela estão no cabeçalho do notebook correspondente. O porquê de
cada uma, com o efeito na contagem, está em [`decisoes.md`](decisoes.md).

## Para agentes de IA

O contexto para Claude Code, Codex, Cursor e afins está em [`AGENTS.md`](AGENTS.md)
(o `CLAUDE.md` só importa esse arquivo). Armadilhas novas dos dados e tabelas novas devem ser
registradas lá.
