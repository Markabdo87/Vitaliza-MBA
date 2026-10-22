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
│   ├── bronze/   # arquivos originais do curso (não editar)
│   ├── prata/    # bronze limpo — gerado pelos scripts, fora do git
│   └── ouro/     # tabelas de análise — gerado pelos scripts, fora do git
└── scripts/      # um script por tabela: <arquivo>_<camada>.py
```

## Como rodar

Requer Python 3 (os scripts atuais usam só a biblioteca padrão). A partir da raiz:

```bash
python3 scripts/pagamentos_prata.py
```

Prata e ouro não são versionados: depois de clonar ou de atualizar um script, rode os scripts
para gerar as tabelas.

## Tabelas

| Tabela | Script | O que tem |
|---|---|---|
| `dados/prata/pagamentos.csv` | `scripts/pagamentos_prata.py` | cobranças sem duplicatas, em horário de Brasília, valor numérico, devoluções pelo valor cobrado, tentativa reconstruída, taxa e valor líquido |

As regras de limpeza de cada tabela estão no cabeçalho do script correspondente.

## Para agentes de IA

O contexto para Claude Code, Codex, Cursor e afins está em [`AGENTS.md`](AGENTS.md)
(o `CLAUDE.md` só importa esse arquivo). Armadilhas novas dos dados e tabelas novas devem ser
registradas lá.
