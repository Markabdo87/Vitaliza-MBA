# Prata — dados limpos

A bronze corrigida, **uma tabela por arquivo de origem e na mesma granularidade** (uma
cobrança continua sendo uma linha, um evento continua sendo uma linha). Aqui não se agrega
nem se cruza tabela: isso é trabalho da ouro.

Os CSVs desta pasta não vão para o git. Eles são gerados pelos scripts em `scripts/`
(`<arquivo>_prata.py`) e recriados rodando o script de novo:

```bash
python3 scripts/pagamentos_prata.py
```

O que a prata faz:
- padroniza formato: datas em horário de Brasília, valores numéricos, nomes de categoria;
- remove o que é erro comprovado, como duplicatas;
- corrige valores errados, guardando o original numa coluna `<coluna>_bronze`;
- **marca** o que é suspeito com colunas `flag_*`, sem apagar a linha.

As regras de cada tabela ficam no cabeçalho do script que a gera.

| Tabela | Script |
|---|---|
| `pagamentos.csv` | `scripts/pagamentos_prata.py` |
