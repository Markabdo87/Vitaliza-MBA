# Ouro — tabelas de análise

Tabelas prontas para responder às perguntas do case, montadas a partir da prata (nunca da
bronze). Aqui as tabelas são cruzadas pelo `user_id` e agregadas. Exemplos do que deve
morar aqui:

- situação de cada assinante numa data (ativo, cancelado, em carência), reconstruída pelos
  eventos;
- churn e faturamento por mês, plano e canal;
- base de modelagem: uma linha por assinante no corte, com as variáveis para prever saída em
  60 dias (até 29/11/2026), sem informação posterior a 30/09/2026;
- segmentos, scores de risco e a lista de contato do CRM.

Como na prata, os CSVs não vão para o git: cada tabela tem um notebook em `notebooks/`
(`<tabela>_ouro.py`) que a recria. Registre cada tabela nova no `AGENTS.md`, em
"Tabelas prontas", com o grão e a regra principal.

Tabelas:

| Tabela | Notebook | Grão |
|---|---|---|
| `churn_mensal.csv` | `notebooks/churn_mensal_ouro.py` | mês × recorte × segmento (G1–G4) |
| `assinantes_30jun26.csv` | `notebooks/assinantes_30jun26_ouro.py` | um assinante pagante ativo em 30/06/2026 (K1–K7) |
| `saidas.csv` | `notebooks/saidas_ouro.py` | uma assinatura paga encerrada (W1–W5) |
| `segmentos.csv` | `notebooks/segmentos_ouro.py` | um assinante pagante ativo × data de referência, com o segmento (L1–L8) |
| `pagamentos_mensal.csv` | `notebooks/pagamentos_mensal_ouro.py` | mês × meio de pagamento |
| `segmentos_kmeans.csv` | `notebooks/segmentos_kmeans_ouro.py` | um assinante pagante ativo × data de referência, com o segmento de nove variáveis (N1–N7) |
| `conciliacao_segmentos.csv` | `notebooks/conciliacao_segmentos.py` | segmento L × segmento N × data de referência (X1) |
| `recusas_cobranca.csv` e `recusas_cobranca.xlsx` | `notebooks/recusas_cobranca_ouro.py` | uma cobrança recusada (R1–R5) |

Detalhes de cada tabela: "Tabelas prontas" no `AGENTS.md`.
