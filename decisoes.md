# Decisões e premissas

Fonte da verdade do grupo: o log de **toda decisão e premissa que muda um número**, seja
limpeza de dado, premissa de negócio, definição de métrica ou escolha de análise. Se não
está aqui, o grupo não decidiu.

Como funciona:
- Cada problema encontrado nos dados tem três saídas: **corrigir**, **remover** ou
  **marcar** (`flag_*`), além de **manter**. Toda escolha entra com o motivo e o efeito
  na contagem (linhas e R$).
- A regra executável de cada decisão está no notebook indicado. Notebook e esta página
  mudam juntos, no mesmo commit.
- IDs: prefixo da seção + número, nunca reaproveitado. Em uso: `P` pagamentos.
- Decisão revista não se apaga: risque a antiga e aponte para a nova.
- "Em aberto", no fim, é a lista de pendências: toda sessão que termina com algo pela
  metade deixa uma linha lá.

Passo a passo em `.claude/skills/registrar-decisao/SKILL.md`.

## Premissas gerais

| Premissa | Valor | Fonte |
|---|---|---|
| Data de corte | 30/09/2026 | dicionário de dados |
| Fuso de referência | horário de Brasília (UTC−3, sem horário de verão desde 2019) | decisão do grupo |
| Preço do mensal | R$ 34,90 até 28/02/2026; R$ 39,90 desde 01/03/2026 | enunciado, seção 03 |
| Preço do anual | R$ 299,90; R$ 239,90 no 1º ano com cupom de influenciador | enunciado, seção 03 |
| Taxa por cobrança | 15% App Store e Google Play · 3,5% cartão · 0,99% Pix Automático | enunciado, seção 03 |
| Arredondamento | comercial (meio para cima), por linha: 39,90 na loja deixa R$ 33,92 | enunciado, seção 03 |

## Pagamentos (`1.bronze/pagamentos.csv` → `2.prata/pagamentos.csv`)

Notebook: `notebooks/pagamentos_prata.py`. Bronze: 165.548 linhas · prata: 163.607 linhas.

| # | Problema | Decisão | Motivo | Efeito na contagem |
|---|---|---|---|---|
| P1 | Cobranças repetidas: mesmo `user_id`, `data_hora`, `valor` e `status`, com `pagamento_id` consecutivos | **Remover** (fica o primeiro `pagamento_id`) | Mesmo segundo e IDs seguidos não são duas cobranças reais; é o registro gravado duas vezes. Todas são `aprovado` | −1.941 linhas · −R$ 118.295,90 no bruto total · set/26: −93 linhas, −R$ 6.830,70 |
| P2 | Valor do site no formato `R$ 39,90` até jun/2025; demais em `39.90` | **Corrigir** para número com ponto | Formato de texto, não erro de valor | 19.520 linhas convertidas · sem efeito em set/26 |
| P3 | Lojas gravam em UTC (`...Z`); site em horário de Brasília | **Corrigir**: lojas −3h; tudo em `data_hora_brt`. Origem guardada em `fuso_origem` | Cortar por dia ou mês com fusos misturados joga cobranças no período errado | 110.824 linhas convertidas · 12.709 mudam de dia · 453 mudam de mês · set/26: −R$ 100,90 |
| P4 | Estornos e chargebacks lançados pelo preço de tabela, não pelo valor cobrado | **Corrigir**: valor = −(última cobrança aprovada do usuário antes da devolução). Original em `valor_bronze`; cobrança de referência em `pagamento_id_original` | Devolver mais do que o cliente pagou distorce a receita líquida | 179 devoluções: 138 de −39,90 → −34,90 e 41 de −299,90 → −239,90 · +R$ 3.150,00 no total · set/26: +R$ 360,00 |
| P5 | Coluna `tentativa` não registra retentativa: recusa seguida de nova cobrança volta a `1`, e `2` aparece em renovações normais | **Corrigir** em coluna nova `tentativa_real`; original em `tentativa_bronze` | Sem isso não se separa quem saiu por cobrança falha. Regra: cobrança até 16 dias depois de uma recusa do mesmo usuário é retentativa (o maior intervalo observado foi 15 dias) | 6.585 linhas com tentativa diferente da bronze · retentativas aprovadas: 4.812 (bronze) → 1.881 (prata) · devoluções ficam sem tentativa |
| P6 | Cobranças recusadas | **Manter** (não entram no faturamento) | São a base da análise de churn involuntário | 3.250 linhas · R$ 191.935,00 tentados e não recebidos · para faturar, filtrar `status != 'recusado'` |
| P7 | Duas cobranças aprovadas do mesmo usuário com menos de 20 dias entre elas | **Marcar** `flag_intervalo_curto = 1` | Pode ser ciclo reiniciado depois de retentativa ou cobrança em dobro; sem cruzar com `eventos_assinatura.csv` não dá para afirmar erro | 223 linhas · nenhum valor removido |
| P8 | Mensal de R$ 34,90 aprovado depois do reajuste de 01/03/2026 | **Marcar** `flag_preco_antigo = 1` | Concentradas nos primeiros dias de março: provável cobrança atrasada do ciclo de fevereiro | 16 linhas · nenhum valor removido |
| P9 | Meio de pagamento com nomes diferentes entre arquivos (`cartao`/`pix_automatico` aqui, `web_cartao`/`web_pix` em `assinaturas.csv`) | **Corrigir** só no cruzamento; coluna nova `canal` (`loja`/`site`) | Mesmo conceito com rótulo diferente; o valor original de `metodo` fica intacto | nenhuma linha alterada |
| P10 | 48 cobranças no cartão de assinantes cadastrados como `web_pix` | **Manter** | Troca de meio de pagamento é plausível; `assinaturas` guarda só a situação atual | nenhuma |
| P11 | Taxa sobre devoluções | **Premissa**: a taxa é devolvida junto (`valor_liquido` da devolução também desconta a taxa) | O enunciado não diz se loja e operadora devolvem a taxa | ≈ R$ 400 em set/26 |

### Resultado de referência

Faturamento com a prata (`status != 'recusado'`):

| Recorte | Bruto | Líquido de taxas |
|---|---:|---:|
| Set/2026 | R$ 489.873,50 | R$ 434.056,93 |
| Jul/2024 – set/2026 | R$ 10.104.367,90 | R$ 8.974.705,14 |

Conciliação de set/2026, do valor puro ao final:

| Etapa | Faturamento | Efeito |
|---|---:|---:|
| Soma de todas as linhas com data de setembro | R$ 509.587,50 | — |
| − recusados (P6) | R$ 496.445,10 | −13.142,40 |
| + fuso (P3) | R$ 496.344,20 | −100,90 |
| − duplicatas (P1) | R$ 489.513,50 | −6.830,70 |
| devoluções pelo valor cobrado (P4) | R$ 489.873,50 | +360,00 |

## Em aberto

- P7 e P8: confirmar com `eventos_assinatura.csv` se são erro; se forem, passar de marcar
  para corrigir ou remover e atualizar os números acima.
