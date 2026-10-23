# Bronze — dados originais

Os arquivos exatamente como o curso entregou, com corte em 30/09/2026. **Não edite nada aqui**:
toda correção é feita por um notebook em `notebooks/` que lê a bronze e grava na prata.

Nenhum arquivo foi limpo antes da entrega. Formatos de data, fusos, maiúsculas e nomes de
categoria variam entre arquivos (ver "Armadilhas conhecidas" no `AGENTS.md`). O `user_id`
liga todos os arquivos. As colunas de cada um estão no `Vitaliza - Dicionário de dados.pdf`,
na seção indicada.

| Forma | Arquivo | Uma linha por | Linhas | Seção |
|---|---|---|---:|---:|
| Tabela | `usuarios.csv` | conta | 64.948 | 02 |
| Tabela | `assinaturas.csv` | assinatura | 32.643 | 03 |
| Tabela | `amizades.csv` | relação de seguir | 113.480 | 04 |
| Tabela | `campanha_ago26.csv` | assinante sorteado | 14.120 | 05 |
| Log de eventos | `eventos_assinatura.csv` | evento | 275.565 | 06 |
| Log de eventos | `pagamentos.csv` | cobrança | 165.548 | 07 |
| Log de eventos | `uso_mensal.csv` | usuário e mês | 591.662 | 08 |
| Log de eventos | `atividades.parquet` | treino | 1.254.475 | 09 |
| Texto e imagem | `onboarding.csv` | conta | 63.929 | 10 |
| Texto e imagem | `pesquisa_saida.csv` | resposta | 643 | 11 |
| Texto e imagem | `feed_posts.csv` | post | 119.309 | 12 |
| Texto e imagem | `tickets_suporte.csv` | chamado | 4.422 | 13 |
| Texto e imagem | `heatmaps/` (dois .zip) | imagem | 12.426 + 13.047 | 14 |

Se o curso mandar uma versão nova de algum arquivo, substitua o arquivo aqui, rode os
scripts de novo e anote a troca na mensagem do commit.
