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

Nenhuma tabela criada ainda.
