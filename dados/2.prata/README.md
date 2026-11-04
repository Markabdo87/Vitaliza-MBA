# Prata — dados limpos

A bronze corrigida, **uma tabela por arquivo de origem e na mesma granularidade** (uma
cobrança continua sendo uma linha, um evento continua sendo uma linha). Aqui não se agrega
nem se cruza tabela: isso é trabalho da ouro.

Os CSVs desta pasta não vão para o git. Eles são gerados pelos notebooks em `notebooks/`
(`<arquivo>_prata.py`) e recriados rodando o notebook de novo:

```bash
for n in notebooks/*_prata.py; do .venv/bin/python "$n"; done
```
(`atividades_prata.py` precisa do venv com `pyarrow`; ver `requirements.txt`.)

O que a prata faz:
- padroniza formato: datas em horário de Brasília, valores numéricos, nomes de categoria;
- remove o que é erro comprovado, como duplicatas;
- corrige valores errados, guardando o original numa coluna `<coluna>_bronze`;
- **marca** o que é suspeito com colunas `flag_*`, sem apagar a linha.

As regras de cada tabela ficam no cabeçalho do notebook que a gera.

| Tabela | Notebook |
|---|---|
| `usuarios.csv` | `notebooks/usuarios_prata.py` |
| `assinaturas.csv` | `notebooks/assinaturas_prata.py` |
| `eventos_assinatura.csv` | `notebooks/eventos_assinatura_prata.py` |
| `pagamentos.csv` | `notebooks/pagamentos_prata.py` |
| `uso_mensal.csv` | `notebooks/uso_mensal_prata.py` |
| `atividades.parquet` | `notebooks/atividades_prata.py` |
| `amizades.csv` | `notebooks/amizades_prata.py` |
| `campanha_ago26.csv` | `notebooks/campanha_ago26_prata.py` |
| `onboarding.csv` | `notebooks/onboarding_prata.py` |
| `feed_posts.csv` | `notebooks/feed_posts_prata.py` |
| `pesquisa_saida.csv` | `notebooks/pesquisa_saida_prata.py` |
| `tickets_suporte.csv` | `notebooks/tickets_suporte_prata.py` |
