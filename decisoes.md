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
- IDs: prefixo da seção + número, nunca reaproveitado. Em uso: `U` usuários · `A` assinaturas ·
  `E` eventos de assinatura · `P` pagamentos · `M` uso mensal · `T` atividades · `Z` amizades · `C` campanha ago/26 · `O` onboarding ·
  `F` feed · `Q` pesquisa de saída · `S` tickets de suporte · `G` churn mensal (ouro) · `K` quem saiu em jul–set/26 (ouro) · `W` por que saem (ouro) · `L` segmentação (ouro) · `N` segmentos k-means de nove variáveis (ouro) · `R` recusas de cobrança (ouro) · `X` conciliação dos segmentos (ouro).
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

## Visão geral da prata

Uma tabela de prata por arquivo da bronze, no mesmo grão. Todas são recriadas rodando
`notebooks/<arquivo>_prata.py` a partir da raiz (`atividades` exige o venv com pyarrow:
`.venv/bin/python`). Remoção só em duplicata comprovada; o resto é corrigido (original em
`<coluna>_bronze`) ou marcado (`flag_*`).

| Tabela | Bronze | Prata | Removidas | Seção |
|---|---:|---:|---:|---|
| `usuarios` | 64.948 | 63.989 | −959 contas duplicadas | U |
| `assinaturas` | 32.643 | 32.643 | 0 | A |
| `eventos_assinatura` | 275.565 | 275.565 | 0 | E |
| `pagamentos` | 165.548 | 163.607 | −1.941 cobranças duplicadas | P |
| `uso_mensal` | 591.662 | 591.662 | 0 | M |
| `atividades` | 1.254.475 | 1.252.575 | −1.900 treinos em dobro (relógio + app) | T |
| `amizades` | 113.480 | 113.480 | 0 | Z |
| `campanha_ago26` | 14.120 | 14.120 | 0 | C |
| `onboarding` | 63.929 | 63.929 | 0 | O |
| `feed_posts` | 119.309 | 119.309 | 0 | F |
| `pesquisa_saida` | 643 | 643 | 0 | Q |
| `tickets_suporte` | 4.422 | 4.422 | 0 | S |

`heatmaps/` (imagens) não tem prata: é insumo da extração com IA.

## Usuários (`1.bronze/usuarios.csv` → `2.prata/usuarios.csv`)

Notebook: `notebooks/usuarios_prata.py`. Bronze: 64.948 linhas · prata: 63.989 linhas.

| # | Problema | Decisão | Motivo | Efeito na contagem |
|---|---|---|---|---|
| U1 | Mesma pessoa cadastrada duas vezes: e-mail igual a menos de maiúsculas (a conta mais nova sempre tem maiúscula), todos os demais campos e a hora do cadastro idênticos, data deslocada de 0 a 7 meses, `user_id` diferente | **Remover** a conta mais nova; o `user_id` dela fica em `user_id_duplicado` na conta mantida | É cópia comprovada: nenhuma das 959 contas removidas aparece em `assinaturas`, `pagamentos`, `eventos_assinatura`, `onboarding`, `uso_mensal`, `amizades`, `feed_posts`, `tickets_suporte`, `pesquisa_saida`, `campanha_ago26` ou `atividades.parquet`; sem elas, `onboarding` cobre exatamente as contas da prata menos as de teste (63.929) | −959 linhas (959 pares, nenhum trio) |
| U2 | `data_cadastro` depois do corte (out/2026 a abr/2027) | **Remover** via U1 | Todas as 119 são contas duplicadas de U1; nenhuma conta mantida passa do corte | 119 das 959 de U1 · 0 na prata |
| U3 | Fuso de `data_cadastro` | **Manter**: já está em horário de Brasília | Sem `Z`; horas de 06h a 22h com o mesmo perfil em iOS e Android (loja em UTC deslocaria 3h) | nenhuma linha alterada · coluna nova `mes_cadastro` |
| U4 | Cadastros antes de 01/07/2024 com hora fixa em `12:00:00` | **Marcar** `flag_hora_cadastro_desconhecida = 1` | Só a data é real; a hora não serve para análise de horário. A partir de 01/07/2024 nenhum cadastro da prata cai em 12:00:00 exato | 5.207 linhas (2020–jun/2024) |
| U5 | `data_nascimento` = `1900-01-01` (valor padrão) ou `2031-05-12` (futuro, sempre depois do cadastro) | **Corrigir** para vazio; original em `data_nascimento_bronze`; **marcar** `flag_nascimento_invalido = 1` | Não são datas reais; manter distorce idade média e faixas | 595 linhas: 408 de 1900-01-01 e 187 de 2031-05-12 (a bronze tinha 412 e 194; o resto saiu em U1) |
| U6 | `data_nascimento` vazio | **Manter** vazio | Campo opcional, sem como recuperar | 3.242 linhas · com U5, 3.837 contas sem idade (6,0%) |
| U7 | Idade | **Coluna nova** `idade_corte` = idade completa em 30/09/2026 | Uma referência só para todas as contas | 60.152 contas com idade · faixa 17–74 anos · 1 conta com menos de 18, mantida |
| U8 | `sexo` em seis grafias (`F`/`Fem`/`feminino`, `M`/`Masc`/`masculino`) | **Corrigir** para `F`/`M`; vazio fica vazio; original em `sexo_bronze` | Mesmo valor com rótulo diferente | 24.457 linhas · prata: 32.034 F, 28.864 M, 3.091 vazio |
| U9 | `cidade` em texto livre: 36 grafias para 13 cidades (`Sampa`, `SAO PAULO`, `São Paulo - SP`, `SP`, `Rio`, `BH`, `Floripa`, `BSB`…) | **Corrigir** para o nome oficial com acento; original em `cidade_bronze` | Mesma cidade com rótulo diferente; todas as grafias batem com a `uf` da linha | 13.406 linhas · 13 cidades na prata |
| U10 | `cep_prefixo` com 2 dígitos | **Corrigir** acrescentando o `0` à esquerda; original em `cep_prefixo_bronze` | Zero perdido na exportação: todos são de São Paulo capital, cujo CEP começa em 01–09 | 1.083 linhas |
| U11 | `cep_prefixo` vazio | **Manter** vazio | Sem como recuperar; `uf` e `cidade` seguem preenchidos | 1.874 linhas |
| U12 | `sistema` com maiúsculas variadas (`ios`/`iOS`/`IOS`, `android`/`Android`) | **Corrigir** para minúsculas; original em `sistema_bronze` | Formato, não valor | 15.839 linhas · prata: 34.633 android, 29.356 ios |
| U13 | Contas de teste: canal `interno`, e-mail `teste*`/`qa.*@vitaliza.com.br` | **Marcar** `flag_conta_teste = 1` | Não são clientes, mas têm assinatura (cortesia `interno` em `assinaturas.csv`); remover deixaria assinatura órfã. Excluir das análises de cliente | 60 linhas |
| U14 | `uf`, `canal_aquisicao`, `versao_app`, `relogio_conectado` | **Manter** | Categorias limpas, sem vazio; `uf` bate com a cidade e com a faixa de CEP em todas as linhas | nenhuma |

## Assinaturas (`1.bronze/assinaturas.csv` → `2.prata/assinaturas.csv`)

Notebook: `notebooks/assinaturas_prata.py`. Bronze: 32.643 linhas · prata: 32.643 linhas.

| # | Problema | Decisão | Motivo | Efeito na contagem |
|---|---|---|---|---|
| A1 | `inicio` e `data_fim` são só data (`AAAA-MM-DD`), sem hora nem indicação de fuso, em loja e site | **Manter** sem conversão; colunas novas `mes_inicio` e `mes_fim` | As datas já estão em horário de Brasília: as 27.383 assinaturas com início desde 01/07/2024 batem com a data BRT da 1ª cobrança aprovada (`pagamentos.csv`) e do evento `assinatura_iniciada`; as 17.830 `data_fim` batem com a data BRT de `assinatura_expirada`, inclusive nas 1.406 de loja em que a data UTC seria outra | nenhuma linha alterada |
| A2 | `canal_cobranca` com rótulos próprios (`web_cartao`/`web_pix`/`interno`), diferentes de `metodo` em `pagamentos.csv` (`cartao`/`pix_automatico`) | **Corrigir** em colunas novas: `canal` (`loja`/`site`/`interno`) e `metodo` no rótulo de pagamentos; `canal_cobranca` fica intacto | Mesmo conceito com rótulo diferente; `metodo` deixa o cruzamento por `user_id` direto | nenhuma linha alterada · loja 22.118 · site 10.465 · interno 60 |
| A3 | 60 assinaturas com plano `cortesia`, canal `interno` e ID `s_t000`–`s_t059`, valores que o dicionário não lista. Todas ativas, início em 10/01/2025, sem cobrança nem evento | **Marcar** `flag_cortesia = 1` | Assinatura real, mas não paga: entra em contagem de base, sai de receita, ticket e churn pago | 60 linhas · nenhuma removida |
| A4 | 5.200 assinaturas com `inicio` antes de 01/07/2024 (2.567 anuais, 2.633 mensais) não têm evento de início nem 1ª cobrança nos logs | **Marcar** `flag_inicio_antes_historico = 1` | O histórico de eventos e pagamentos começa em 01/07/2024 (dicionário, seção 06). Para elas, `inicio` só existe aqui | 5.200 linhas · nenhuma removida |
| A5 | Nenhuma assinatura terminada antes de 07/07/2024: as 4.510 iniciadas em 2020–2023 estavam todas vivas em 01/07/2024 | **Manter** | O arquivo só traz assinaturas vivas no início do histórico ou criadas depois; as encerradas antes não estão na base. Churn anterior a jul/2024 não é calculável com este arquivo | nenhuma linha alterada · `data_fim` de 07/07/2024 a 30/09/2026 |
| A6 | Uma assinatura por `user_id` (32.643 contas distintas), embora o dicionário diga que a mesma pessoa pode ter mais de uma | **Manter** | Confirmado em `eventos_assinatura.csv`: nenhuma conta tem mais de um `assinatura_iniciada`. Não há retorno de ex-assinante nos dados | nenhuma linha alterada |
| A7 | Coerência do retrato: ativa ↔ sem `data_fim`/`motivo_fim`; expirada/reembolsada ↔ com ambos; `renovacao_automatica = sim` só em ativa; `reembolsada` ↔ motivo `reembolso`; `data_fim ≥ inicio`; datas até o corte; `assinatura_id` único; duplicatas exatas ou por (`user_id`, `inicio`) | **Manter**; o notebook confere e imprime as violações | Nenhuma violação encontrada | 0 linhas · ativa 14.813 · expirada 17.758 · reembolsada 72 |
| A8 | 5 ativas com `renovacao_automatica = sim` cujo último evento de renovação automática é `desligada` | **Manter** | Em todas houve renovação cobrada depois do desligamento (2 com religada e desligada no mesmo segundo); o retrato de 01/10/2026 prevalece | 5 linhas · nenhuma alterada |
| A9 | 4 mensais ativas sem cobrança aprovada nos 40 dias anteriores ao corte | **Manter** | Pode ser carência ou status desatualizado; afirmar exige cruzar com `pagamentos.csv`, o que é ouro | 4 linhas · nenhuma alterada |
| A10 | `assinatura_id` numérico com lacunas (`s_000000`–`s_063341`, 30.759 números sem linha) e fora da ordem de `inicio` | **Manter** | Identificador, não contador: lacunas não indicam linha perdida | nenhuma linha alterada |

## Eventos de assinatura (`1.bronze/eventos_assinatura.csv` → `2.prata/eventos_assinatura.csv`)

Notebook: `notebooks/eventos_assinatura_prata.py`. Bronze: 275.565 linhas · prata: 275.565 linhas.

52.196 usuários; cada um tem no máximo uma assinatura no log (nenhum `assinatura_iniciada` depois de `assinatura_expirada`).

| # | Problema | Decisão | Motivo | Efeito na contagem |
|---|---|---|---|---|
| E1 | Lojas gravam em UTC (`...Z`); site em horário de Brasília | **Corrigir**: lojas −3h; tudo em `data_hora_brt` e `mes`. Texto original em `data_hora_bronze`, origem em `fuso_origem` | Com fusos misturados, eventos caem no dia ou mês errado. Em Brasília, `assinatura_iniciada` bate 100% com `assinaturas.inicio` (27.383 de 27.383; no texto original, só 25.214) e `assinatura_expirada` bate 100% com `assinaturas.data_fim` (17.830) | 186.323 linhas convertidas · 21.951 mudam de dia · 753 mudam de mês · 44 linhas com data de 01/10/2026 no texto original voltam para 30/09 (nenhum evento depois do corte) · expirações set/26: 712 → 717 |
| E2 | Arquivo fora de ordem | **Corrigir**: `seq_usuario` numera os eventos de cada usuário por `data_hora_brt`; saída ordenada por usuário e sequência | As regras de churn dependem da ordem dos eventos de cada pessoa | nenhuma linha alterada · nenhum empate de horário no mesmo usuário |
| E3 | Duplicatas | **Manter**: não há | Nenhuma linha repetida, nem com mesmo `user_id`, `data_hora` e `evento`, nem com mesmo `user_id` e `data_hora` | 0 linhas |
| E4 | `plano` vazio em eventos de trial (`trial_iniciado`, `trial_expirado` e o desligamento da renovação durante o trial) | **Manter** vazio; coluna nova `fase` (`trial` quando `plano` vazio, senão `assinatura`) | No trial não há plano contratado. Nenhum evento de assinatura vem sem plano e nenhum usuário troca de plano ou de canal no log | 72.873 linhas `fase = trial` (6.734 delas são `renovacao_automatica_desligada`) · 202.692 `fase = assinatura` |
| E5 | `detalhe` preenchido só em `assinatura_expirada`, e só no site (`renovacao_desligada`, `falha_pagamento`, `chargeback`, `reembolso`); nas lojas vem sempre vazio | **Manter** | É o motivo do fim gravado pelo sistema da Vitaliza; a loja não manda motivo. Na loja, a causa sai dos eventos anteriores (desligamento, carência, devolução) | 6.071 linhas com `detalhe` (5.139 `renovacao_desligada`, 800 `falha_pagamento`, 109 `chargeback`, 23 `reembolso`) · 11.759 expirações sem detalhe, todas de loja |
| E6 | Canal com rótulo diferente de `pagamentos` (`web_cartao`/`web_pix` aqui) | **Corrigir** só no cruzamento; coluna nova `canal` (`loja`/`site`), mesmo rótulo de `pagamentos` | Mesmo conceito, rótulo diferente; `canal_cobranca` fica intacto | nenhuma linha alterada |
| E7 | Histórico que começa no meio da assinatura (primeiro evento é renovação, desligamento, carência ou expiração, sem `assinatura_iniciada`) | **Marcar** `flag_inicio_antes_log = 1` em todas as linhas do usuário | O log começa em 01/07/2024. Os 5.200 usuários têm `assinaturas.inicio` anterior a essa data: não é evento perdido, é assinatura antiga | 5.200 usuários · 40.769 linhas |
| E8 | Evento recebido depois do fim (`trial_expirado` ou `assinatura_expirada`) do mesmo usuário | **Marcar** `flag_apos_fim = 1` | Aviso da loja ou do site que chegou fora de ordem: todos em menos de 1 dia depois do fim, e nenhum usuário volta a assinar. A data do fim é a do evento terminal | 932 linhas: 534 desligamentos de trial depois de `trial_expirado` · 211 desligamentos, 136 chargebacks, 40 reembolsos e 11 `cancelamento_web` depois de `assinatura_expirada` |
| E9 | Sequência que o estado anterior não permite | **Marcar** `flag_sequencia_invalida = 1`, motivo em `problema_sequencia` | Poucos casos, sem prova de erro; ficam visíveis para quem reconstruir o status do assinante | 38 linhas: 18 religamento com renovação já ligada · 12 renovação com renovação desligada, sem religamento · 6 renovação depois de chargeback, sem expiração · 2 desligamento repetido |
| E10 | Fim ausente: trial ou assinatura que deveria ter terminado até o corte e não tem evento de fim | **Manter** (conferido, não há caso) | Regra conferida no notebook: trial sem fim 8 dias depois do início; assinatura sem expiração 17 dias depois do fim do ciclo pago (início/renovação + 30 dias no mensal, 365 no anual; carência máxima observada 16,6 dias) | 0 usuários · os 14.753 usuários sem `assinatura_expirada` são exatamente os ativos em 30/09/2026 do enunciado e todos estão `ativa` em `assinaturas.csv` |
| E11 | `cancelamento_web` sempre acompanhado de `renovacao_automatica_desligada` | **Manter** os dois eventos | No site, cancelar gera os dois avisos; contar os dois dobra o cancelamento | 1.172 de 1.172 `cancelamento_web` com desligamento em até 1 dia |

### Resultado de referência

`assinatura_expirada` na prata, por mês em Brasília: set/2026 = 717; jun–set/2026 = 3.389 (2.271 loja, 1.118 site), igual ao enunciado (seção 02). Total do log: 17.830 expirações.

## Pagamentos (`1.bronze/pagamentos.csv` → `2.prata/pagamentos.csv`)

Notebook: `notebooks/pagamentos_prata.py`. Bronze: 165.548 linhas · prata: 163.607 linhas.

| # | Problema | Decisão | Motivo | Efeito na contagem |
|---|---|---|---|---|
| P1 | Cobranças repetidas: mesmo `user_id`, `data_hora`, `valor` e `status`, com `pagamento_id` consecutivos | **Remover** (fica o primeiro `pagamento_id`) | Mesmo segundo e IDs seguidos não são duas cobranças reais; é o registro gravado duas vezes. Todas são `aprovado` | −1.941 linhas · −R$ 118.295,90 no bruto total · set/26: −93 linhas, −R$ 6.830,70 |
| P2 | Valor do site no formato `R$ 39,90` até jun/2025; demais em `39.90` | **Corrigir** para número com ponto | Formato de texto, não erro de valor | 19.520 linhas convertidas · sem efeito em set/26 |
| P3 | Lojas gravam em UTC (`...Z`); site em horário de Brasília | **Corrigir**: lojas −3h; tudo em `data_hora_brt`. Origem guardada em `fuso_origem` | Cortar por dia ou mês com fusos misturados joga cobranças no período errado | 110.824 linhas convertidas · 12.709 mudam de dia · 453 mudam de mês · set/26: −R$ 100,90 |
| P4 | Estornos e chargebacks lançados pelo preço de tabela, não pelo valor cobrado | **Corrigir**: valor = −(última cobrança aprovada do usuário antes da devolução). Original em `valor_bronze`; cobrança de referência em `pagamento_id_original` | Devolver mais do que o cliente pagou distorce a receita líquida | 179 devoluções: 138 de −39,90 → −34,90 e 41 de −299,90 → −239,90 · +R$ 3.150,00 no total · set/26: +R$ 360,00 |
| P5 | Coluna `tentativa` não registra retentativa: recusa seguida de nova cobrança volta a `1`, e `2` aparece em renovações normais | **Corrigir** em coluna nova `tentativa_real`; original em `tentativa_bronze` | Sem isso não se separa quem saiu por cobrança falha. Regra: cobrança até 16 dias depois de uma recusa do mesmo usuário é retentativa (o maior intervalo observado foi 15 dias) | 6.585 linhas com tentativa diferente da bronze · retentativas aprovadas: 4.812 (bronze) → 1.881 (prata) · devoluções ficam sem tentativa |
| ~~P6~~ | ~~Cobranças recusadas~~ | ~~**Manter** (não entram no faturamento)~~ → ver P12 | São a base da análise de churn involuntário | 3.250 linhas · R$ 191.935,00 tentados e não recebidos · para faturar, filtrar `status != 'recusado'` |
| P7 | Duas cobranças aprovadas do mesmo usuário com menos de 20 dias entre elas | **Marcar** `flag_intervalo_curto = 1` | Pode ser ciclo reiniciado depois de retentativa ou cobrança em dobro; sem cruzar com `eventos_assinatura.csv` não dá para afirmar erro | 223 linhas · nenhum valor removido |
| P8 | Mensal de R$ 34,90 aprovado depois do reajuste de 01/03/2026 | **Marcar** `flag_preco_antigo = 1` | Concentradas nos primeiros dias de março: provável cobrança atrasada do ciclo de fevereiro | 16 linhas · nenhum valor removido |
| P9 | Meio de pagamento com nomes diferentes entre arquivos (`cartao`/`pix_automatico` aqui, `web_cartao`/`web_pix` em `assinaturas.csv`) | **Corrigir** só no cruzamento; coluna nova `canal` (`loja`/`site`) | Mesmo conceito com rótulo diferente; o valor original de `metodo` fica intacto | nenhuma linha alterada |
| P10 | 48 cobranças no cartão de assinantes cadastrados como `web_pix` | **Manter** | Troca de meio de pagamento é plausível; `assinaturas` guarda só a situação atual | nenhuma |
| P11 | Taxa sobre devoluções | **Premissa**: a taxa é devolvida junto (`valor_liquido` da devolução também desconta a taxa) | O enunciado não diz se loja e operadora devolvem a taxa | ≈ R$ 400 em set/26 |
| P12 | Cobranças recusadas com `valor` e `valor_liquido` preenchidos (o valor tentado): somar a coluna sem filtrar `status` contava dinheiro que não entrou | **Manter** as linhas e **corrigir** `valor` e `valor_liquido` para 0; valor tentado em `valor_bronze` | Recusa não gera receita. Com zero, a soma da coluna já é o faturamento, com ou sem filtro; as linhas continuam servindo ao churn involuntário (ver R1–R5) | 3.250 linhas zeradas · R$ 191.935,00 tentados (R$ 178.450,30 líquidos) saem da soma sem filtro · set/26 sem filtro: R$ 503.015,90 → R$ 489.873,50 bruto e R$ 446.246,38 → R$ 434.056,93 líquido · faturamento com filtro inalterado |

### Resultado de referência

Faturamento com a prata (soma de `valor` e `valor_liquido`; desde P12 o filtro `status != 'recusado'` não muda o resultado):

| Recorte | Bruto | Líquido de taxas |
|---|---:|---:|
| Set/2026 | R$ 489.873,50 | R$ 434.056,93 |
| Jul/2024 – set/2026 | R$ 10.104.367,90 | R$ 8.974.705,14 |

Conciliação de set/2026, do valor puro ao final:

| Etapa | Faturamento | Efeito |
|---|---:|---:|
| Soma de todas as linhas com data de setembro | R$ 509.587,50 | — |
| − recusados (P6, P12) | R$ 496.445,10 | −13.142,40 |
| + fuso (P3) | R$ 496.344,20 | −100,90 |
| − duplicatas (P1) | R$ 489.513,50 | −6.830,70 |
| devoluções pelo valor cobrado (P4) | R$ 489.873,50 | +360,00 |

## Uso mensal (`1.bronze/uso_mensal.csv` → `2.prata/uso_mensal.csv`)

Notebook: `notebooks/uso_mensal_prata.py`. Bronze: 591.662 linhas · prata: 591.662 linhas.

| # | Problema | Decisão | Motivo | Efeito na contagem |
|---|---|---|---|---|
| M1 | Formato: `user_id` `u_` + 8 hex, `mes` `AAAA-MM`, seis métricas inteiras ≥ 0 | **Manter** (o notebook remove a linha fora do formato) | Todas as linhas estão no formato, sem nulo nem vazio | nenhuma linha removida |
| M2 | Duplicata por (`user_id`, `mes`) | **Manter** (o notebook remove a repetida, fica a primeira) | Nenhuma chave repetida, nem linha inteira repetida | nenhuma linha removida |
| M3 | Meses fora do período | **Manter** (o notebook remove mês depois de 2026-09) | Cobre 2025-01 a 2026-09, sem mês depois do corte. Set/2026 está completo: 56.565 linhas, 15.685 com treino, na mesma tendência de jul e ago | nenhuma linha removida |
| M4 | Coerência interna: `atividades_ar_livre + atividades_video = atividades`, `dias_ativos ≤ atividades`, `dias_ativos ≤ dias do mês`, treino ⇔ minutos ⇔ dias ativos | **Marcar** `flag_incoerente = 1` | Regra de proteção; hoje a bronze fecha em todas as linhas. Minutos por treino entre 12 e 222, nenhum negativo | 0 linhas |
| M5 | Mês sem treino: em 2025 só há linha quando houve treino; em 2026 a tabela também traz o mês com `atividades = 0` | **Marcar** `flag_sem_treino = 1`; `flag_sem_uso = 1` quando também `sessoes_app = 0` | A população da linha muda na virada do ano: de dez/25 para jan/26 as linhas vão de 13.624 para 41.130, mas as linhas com treino vão de 13.624 para 15.433. Média por linha ou contagem de linhas entre 2025 e 2026 só se compara com `flag_sem_treino = 0` | 303.735 linhas sem treino (69% de 2026, nenhuma em 2025) · 41.493 delas também sem abrir o app |
| M6 | `sessoes_app` cai de uma vez em mar/2026: 2,50 sessões por treino (jan/25–fev/26) → 1,38 (mar–set/26), com treinos e minutos por usuário estáveis | **Marcar** `flag_sessoes_nova_contagem = 1` (mes ≥ 2026-03); valor mantido | Queda de 45% num único mês, em 86% dos usuários que treinaram em fev e mar, e estável antes e depois: tem jeito de mudança na forma de contar, não de comportamento. Sem fonte para o fator de conversão, não se corrige | 355.023 linhas marcadas · nenhum valor alterado |
| M7 | Volume alto: mais de 180 minutos por dia ativo, em média, no mês (máximo 284; 8.228 minutos num mês) | **Marcar** `flag_volume_alto = 1` | Possível para atleta de longa distância e coerente com treinos e dias; acima do percentil 99,9. Concentrado em poucos usuários | 168 linhas · 98 usuários |
| M8 | Usuário com mês faltando no meio da série | **Manter** | Em 2025 é mês sem treino (M5); em 2026 não há regra que explique (26.757 usuários com lacuna). Preencher com zero seria inventar dado; prata não cria linha | nenhuma |

## Atividades (`1.bronze/atividades.parquet` → `2.prata/atividades.parquet`)

Notebook: `notebooks/atividades_prata.py` (rodar com `.venv/bin/python`, exige pyarrow). Bronze: 1.254.475 linhas · prata: 1.252.575 linhas.

| # | Problema | Decisão | Motivo | Efeito na contagem |
|---|---|---|---|---|
| T1 | `inicio` do Garmin em UTC sem o `Z`, no mesmo formato `AAAA-MM-DD HH:MM:SS` do app e do Apple Health (que gravam em Brasília) | **Corrigir**: Garmin −3h; tudo em `inicio_brt`. Original em `inicio_bronze`; origem em `fuso_origem` (`utc`/`brt`) | Os picos de horário do Garmin ficam 3h depois dos das outras origens (08–12h e 20–00h contra 05–09h e 17–21h), e 1.032 treinos repetidos entre Garmin e app só coincidem depois de −3h. O último registro da bronze (01/10 00:59) vira 30/09 21:59 | 207.954 linhas convertidas · 5.828 mudam de dia · 188 mudam de mês · nenhum treino fora de jan–set/2026 depois da conversão |
| T2 | Desde 15/04/2026 o app grava o tipo em inglês (`run`, `walk`, `ride`, `strength`, `hiit`); antes e nos relógios, em português | **Corrigir**: `run`→`corrida`, `walk`→`caminhada`, `ride`→`pedal`, `strength`→`forca`, `hiit`→`funcional`. Original em `tipo_bronze` | Mesmo treino com rótulo diferente: a troca é de um dia para o outro e duração, ritmo e FC de cada par batem (`hiit` e `funcional`: mediana 32,5 e 32,4 min, FC 141) | 486.864 linhas traduzidas · 6 tipos na prata (eram 11) |
| T3 | O mesmo treino aparece duas vezes, uma pelo relógio e outra pelo app: mesmo `user_id`, `inicio_brt`, tipo, duração, distância e ritmo, com `atividade_id` diferente | **Remover** a cópia do app (fica a linha do relógio; no empate, o menor `atividade_id`) | Mesmo minuto e mesmas medidas não são dois treinos; é o relógio sincronizado também pelo app. A origem que fica é a de onde o treino veio | −1.900 linhas: 1.032 pares Garmin/app, 867 Apple Health/app, 1 app/app · bronze tinha 3.649 durações zero, 4 delas nas cópias removidas |
| T4 | `distancia_km` 40 a 160 vezes maior que `duracao_min / ritmo_min_km` (ex.: caminhada de 81 min a 12,76 min/km com 512,86 km) | **Corrigir**: distância = duração ÷ ritmo, 2 casas. Original em `distancia_km_bronze` | Nos demais treinos com GPS a razão fica entre 0,99 e 1,01 e não há nenhuma entre 1,2 e 40: o erro é só da distância, duração e ritmo estão coerentes com o tipo | 998 linhas · soma dessas distâncias: 992.003 km → 9.933 km |
| T5 | `gps_ok = False`: a distância gravada é um trecho do percurso e não há ritmo | **Corrigir**: `distancia_km` vira nulo. Original em `distancia_km_bronze` | A distância desses treinos não mede o treino (mediana de 0,60 km para uma mediana de 46 min de treino). Só acontece no app, em `run`/`walk`/`ride`, depois da troca de 15/04/2026 | 14.779 linhas com GPS falho · 7.455 tinham distância e viram nulo · 7.324 já vinham sem distância · o treino continua contando |
| T6 | `duracao_min = 0` | **Corrigir**: com distância e ritmo, duração = distância × ritmo (1 casa). Sem eles, nulo. Se a distância também estiver inflada (duração recalculada acima do teto do tipo: caminhada 120, corrida 360, pedal 600 min), duração e distância ficam nulas. Original em `duracao_min_bronze`; todas marcadas com `flag_duracao_zero = 1` | Treino registrado com duração zero não existe; em treino com GPS a duração é recuperável pela relação distância × ritmo, válida nas demais linhas | 3.645 linhas: 1.966 recalculadas · 1.676 sem GPS ficam nulas · 3 com distância inflada ficam sem duração e sem distância · 1.679 durações nulas na prata · minutos somados: 58.269.442 (bronze) → 58.285.655 (prata) |
| T7 | `treino_com` vazio gravado como texto `''` | **Corrigir** para nulo | Ausência de companhia, não um `user_id` | 14.112 treinos com companhia · nenhum aponta para o próprio usuário |
| T8 | Dois treinos do mesmo usuário começando no mesmo minuto, com tipo ou duração diferentes | **Marcar** `flag_inicio_repetido = 1` | Não são cópia um do outro (as medidas diferem); pode ser registro em dobro com medidas divergentes ou dois treinos reais lançados juntos. Sem outra fonte não dá para afirmar erro | 2.934 linhas em 1.467 grupos · 671 grupos com o mesmo tipo · nenhuma removida |
| T9 | Treinos longos: corrida até 333 min, pedal até 544 min | **Manter** | Distância × ritmo bate com a duração (ex.: corridas de 42 km em 4–5h, maratona) | nenhuma |
| T10 | `fc_media` só em parte dos treinos do app | **Manter** | Vem sempre do Garmin e do Apple Health e em 116.719 treinos do app (relógio conectado); faixa de 61 a 195 bpm, fisiológica | nenhuma |
| T11 | `gps_ok = True` em treinos sem GPS (força, funcional, yoga) | **Manter** | O campo só tem significado em corrida, caminhada e pedal; nos demais é o valor padrão | nenhuma |

## Amizades (`1.bronze/amizades.csv` → `2.prata/amizades.csv`)

Notebook: `notebooks/amizades_prata.py`. Bronze: 113.480 linhas · prata: 113.480 linhas.

| # | Problema | Decisão | Motivo | Efeito na contagem |
|---|---|---|---|---|
| Z1 | `desde` é só data (`AAAA-MM-DD`), sem hora nem fuso | **Manter** como está, validada como data | Sem hora não há conversão de fuso possível; para corte por dia ou mês, a data já serve | 113.480 datas válidas · nenhuma linha alterada |
| Z2 | Relações iniciadas depois do corte: `desde` entre 01/10/2026 e 09/10/2026 | **Marcar** `flag_apos_corte = 1` | Dado real, mas posterior a 30/09/2026: não pode entrar em variável de modelo. Nenhuma data além de hoje | 273 linhas · nenhuma removida |
| Z3 | Auto-seguir (`seguidor_id = seguido_id`) | **Remover** (regra fica no notebook) | Não é relação possível | 0 linhas na bronze atual |
| Z4 | Par (`seguidor_id`, `seguido_id`) repetido | **Remover**, fica a linha de `desde` mais antigo | A relação começa uma vez só | 0 linhas na bronze atual |
| Z5 | `seguidor_id`/`seguido_id` fora do padrão `u_` + 8 hexadecimais | **Marcar** `flag_id_invalido = 1` | Id malformado não cruza com outro arquivo | 0 linhas · todos os 54.162 ids existem em `usuarios.csv` (conferido só no perfil, a prata não depende do cruzamento) |
| Z6 | Relação anterior ao cadastro de qualquer das duas contas | **Manter** (sem coluna) | Conferido com `usuarios.data_cadastro` no perfil: nenhum caso; 649 relações começam no dia do cadastro de uma das contas | 0 linhas |
| Z7 | Seguir é mão única: A→B e B→A são duas linhas | **Manter** as duas; coluna nova `reciproco = 1` quando o par inverso existe na tabela | Segue o dicionário; separa conexão mútua de seguir sem retorno, sem cruzar com outro arquivo | 85.044 linhas recíprocas (75%) · 28.436 de mão única |

## Campanha ago/26 (`1.bronze/campanha_ago26.csv` → `2.prata/campanha_ago26.csv`)

Notebook: `notebooks/campanha_ago26_prata.py`. Bronze: 14.120 linhas · prata: 14.120 linhas.

| # | Problema | Decisão | Motivo | Efeito na contagem |
|---|---|---|---|---|
| C1 | `user_id` repetido | **Remover**, fica a primeira linha (regra fica no notebook) | O dicionário define uma linha por assinante sorteado | 0 linhas · 14.120 `user_id` distintos, todos em `usuarios.csv` e em `assinaturas.csv` (conferido só no perfil) |
| C2 | `grupo` fora de controle/desafio/cupom/conteudo | **Corrigir** caixa e espaços; valor desconhecido para o notebook | Grupo é o tratamento do experimento; não pode haver valor solto | 0 linhas alteradas · controle 3.579 · conteudo 3.554 · desafio 3.515 · cupom 3.472 |
| C3 | Variável de tratamento | **Coluna nova** `tratado` (1 = desafio, cupom ou conteudo; 0 = controle) | Base do uplift: tratado × controle | 10.541 tratados · 3.579 controle |
| C4 | `enviado_em` sem fuso (`2026-08-10 10:00:00`) | **Premissa**: horário de Brasília, sem conversão; coluna `enviado_em_brt` | Gravado pelo CRM da própria Vitaliza, como o site, que grava em Brasília. O dicionário não diz o fuso | 10.541 envios, todos em 10/08/2026 10:00 · nenhum fora de ago/26 |
| C5 | Controle com `enviado_em`, `canal`, `titulo_mensagem` e `oferta` vazios | **Manter** vazio | O controle foi sorteado para não receber nada | 3.579 linhas · nenhuma alterada |
| C6 | Booleanos `abriu_push`, `abriu_email`, `clicou` em texto `True`/`False` | **Corrigir** para 1/0; coluna nova `abriu` (push ou e-mail) | Formato, não erro de valor; outro formato (sim/1…) também seria lido, um desconhecido para o notebook | 14.120 linhas convertidas · só `True`/`False` na bronze |
| C7 | Incoerências: controle com envio ou engajamento; tratado sem envio, com canal diferente de `push+email` ou título de outro grupo; oferta fora do cupom ou cupom sem oferta | **Marcar** `flag_inconsistente = 1` | Mancharia a comparação com o controle; sem prova de qual campo está errado, a linha fica | 0 linhas |
| C8 | Clique sem abertura de push nem de e-mail | **Marcar** `flag_clicou_sem_abrir = 1` | Clique pressupõe abertura | 0 linhas · 1.604 cliques, todos com abertura |
| C9 | Oferta do cupom depende do plano: `30pct_3_meses` (mensal) ou `1_mes_gratis` (anual) | **Manter** | Conferido com `assinaturas.plano_atual` no perfil: 1.420 mensais com 30%, 2.052 anuais com 1 mês grátis, nenhuma troca | 0 linhas |
| C10 | Sorteio: todos pagantes em 10/08/2026 e grupos equilibrados | **Manter** | Conferido com `assinaturas.csv` no perfil: nenhuma assinatura iniciada depois nem encerrada antes de 10/08/2026; anuais por grupo entre 58,6% e 59,8% | 0 linhas |

### Resultado de referência

Engajamento por grupo (`dados/2.prata/campanha_ago26.csv`, % sobre o grupo inteiro):

| Grupo | Assinantes | Abriu push | Abriu e-mail | Abriu algum | Clicou |
|---|---:|---:|---:|---:|---:|
| controle | 3.579 | 0,0% | 0,0% | 0,0% | 0,0% |
| desafio | 3.515 | 30,6% | 18,4% | 42,9% | 14,3% |
| cupom | 3.472 | 31,6% | 19,0% | 44,6% | 16,4% |
| conteudo | 3.554 | 32,0% | 18,0% | 44,3% | 14,9% |

## Onboarding (`1.bronze/onboarding.csv` → `2.prata/onboarding.csv`)

Notebook: `notebooks/onboarding_prata.py`. Bronze: 63.929 linhas · prata: 63.929 linhas.

| # | Problema | Decisão | Motivo | Efeito na contagem |
|---|---|---|---|---|
| O1 | Duplicatas: por linha exata, por `onboarding_id` e por `user_id` (mais de um onboarding por conta) | **Manter** (nenhuma encontrada) | Grão confirmado: uma linha por conta, como diz o dicionário | 0 linhas removidas · 63.929 `user_id` distintos |
| O2 | `respondido_em` é só data (`AAAA-MM-DD`), sem hora nem fuso | **Manter**; `flag_apos_corte` para data depois de 30/09/2026 | Sem hora não há fuso a converter. Intervalo 01/09/2020 a 30/09/2026, dentro do lançamento e do corte | 0 linhas após o corte |
| O3 | Espaços repetidos no texto livre (`"o desafio de 100km de bike  édia 8/07"`) | **Corrigir**: NFC, strip e sequência de espaços vira um. Original em `objetivo_texto_bronze` / `como_conheceu_bronze` | Formato, não conteúdo; o texto segue igual para a extração | `objetivo_texto`: 138 linhas · `como_conheceu`: 17 linhas · 0 com espaço nas pontas · 0 com mojibake |
| O4 | Campo vazio | **Manter** como nulo | Objetivo é opcional (dicionário); vazio já é a ausência de resposta | `objetivo_texto`: 5.467 nulos · `como_conheceu`: 4.586 · `nivel`: 4.513 · `dias_por_semana`: 6.368 |
| O5 | Resposta preenchida sem conteúdo útil: `ok`, `.`, `x`, `-`, `asdf`, `sla`, `kkkk`, `nada`, `nao sei`, `😂` | **Marcar** `flag_objetivo_sem_conteudo` / `flag_como_conheceu_sem_conteudo`; texto mantido | Não é erro do dado, é o que a pessoa respondeu; pode ser sinal de baixo engajamento | `objetivo_texto`: 13.768 linhas (21,5%) · `como_conheceu`: 11.515 (18,0%) · nos dois campos: 2.549 |
| O6 | `como_conheceu` é resposta livre: 572 grafias, com erros de digitação (`vi um aúnncio`, `propagnada no face`), variantes sem acento (`ja conhecia`) e citações de influenciador (`cupom da @carolfit`) | **Manter** como veio | Dicionário define o campo como livre; agrupar em canal é interpretação e fica para a extração | 0 linhas alteradas · 522 grafias com menos de 100 ocorrências somam 2.981 linhas · 7.793 linhas citam um `@perfil` |
| O7 | `dias_por_semana` em texto livre: `3`, `3x`, `3 vezes`, `1 vezes`, `todos` | **Corrigir** para inteiro 1–7 (`todos` = 7). Original em `dias_por_semana_bronze`; ilegível ou fora de 0–7 vira nulo com `flag_dias_invalido` | Mesmo número com grafias diferentes; o dicionário diz que o campo é texto | 24.034 linhas convertidas (917 de `todos`) · 0 inválidas · distribuição: 1 = 4.502, 2 = 12.577, 3 = 17.161, 4 = 12.446, 5 = 6.179, 6 = 2.204, 7 = 2.492 |
| O8 | `nivel`: categoria fechada | **Manter**; padronização para minúscula sem acento e validação do domínio (`iniciante`/`intermediario`/`avancado`), original em `nivel_bronze` | Garante o domínio se a bronze mudar | 0 linhas alteradas · iniciante 23.682 · intermediario 25.631 · avancado 10.103 |

## Feed (`1.bronze/feed_posts.csv` → `2.prata/feed_posts.csv`)

Notebook: `notebooks/feed_posts_prata.py`. Bronze: 119.309 linhas · prata: 119.309 linhas.

| # | Problema | Decisão | Motivo | Efeito na contagem |
|---|---|---|---|---|
| F1 | Duplicatas: linha exata, `post_id` e mesmo usuário com o mesmo texto no mesmo segundo | **Manter** (nenhuma encontrada) | Nenhum post repetido; também não há mesmo texto do mesmo usuário em menos de 1 hora | 0 linhas removidas |
| F2 | `data_hora` sem marcador de fuso (`AAAA-MM-DD HH:MM:SS`), sempre entre 06h e 22h | **Manter** como horário de Brasília; coluna nova `mes` | Sem `Z` nem offset, e a faixa de horário é a de uso local; não há base para converter | 0 linhas convertidas |
| F3 | Posts depois do corte: o dicionário diz até 30/09/2026, mas há posts de 01/10 a 07/10/2026 | **Marcar** `flag_apos_corte = 1` | Não é erro de fuso (o primeiro é 01/10 06:17, continua em outubro com −3h); não pode entrar em variável de modelo | 122 posts de 120 usuários |
| F4 | `[post removido]` no lugar do texto | **Corrigir**: texto vira nulo, `flag_post_removido = 1`; linha mantida, original em `texto_bronze` | É marcador do sistema, não texto da pessoa; a data e as curtidas do post seguem válidas | 1.214 linhas |
| F5 | Espaços repetidos no texto (`"yoga pra fechar  odia"`) | **Corrigir**: NFC, strip e sequência de espaços vira um. Original em `texto_bronze` | Formato, não conteúdo | 230 linhas · 0 vazias · 0 com espaço nas pontas · 0 com mojibake |
| F6 | Erros de digitação, variantes sem acento (`treino de forca feito`), emojis e maiúsculas em nomes (`chegou a Alice!`, `mudei pra Lisboa`) | **Manter** como veio | São o texto da pessoa; normalizar mais apagaria informação da extração | 0 linhas alteradas · 31.620 textos distintos |
| F7 | `curtidas` | **Manter**; validação de inteiro ≥ 0 com `flag_curtidas_invalida` | Faixa plausível | 0 a 38 · 258 posts com 0 · 0 inválidas |
| F8 | `post_id` não segue a ordem do tempo (`f_0000001` é de 01/05/2026) | **Manter**; prata ordenada por `data_hora`, `post_id` | Identificador, não sequência; não use `post_id` para ordenar | 0 linhas alteradas |

## Pesquisa de saída (`1.bronze/pesquisa_saida.csv` → `2.prata/pesquisa_saida.csv`)

Notebook: `notebooks/pesquisa_saida_prata.py`. Bronze: 643 linhas · prata: 643 linhas.

| # | Problema | Decisão | Motivo | Efeito na contagem |
|---|---|---|---|---|
| Q1 | Comentário vazio (só o motivo marcado) | **Marcar** `flag_sem_comentario = 1`; campo fica nulo | O comentário é opcional; a resposta vale pelo motivo | 183 linhas · nenhuma removida |
| Q2 | Comentário com erro de digitação, sem acento ou com letras trocadas (`era só ate a prova`, `naoe stou usando`, `app ubgado`) | **Manter** o texto como veio (só `strip`) | A leitura do texto é da extração com IA; corrigir à mão mudaria o insumo | nenhuma linha alterada · 460 comentários, 142 textos distintos |
| Q3 | Mojibake (UTF-8 lido como Latin-1) | **Corrigir** quando aparecer (regra no notebook) | Texto quebrado atrapalha a extração | 0 linhas na bronze atual |
| Q4 | `motivo_principal` | **Manter**; o notebook confere contra a lista do dicionário e para se aparecer valor fora dela | Todos os valores já estão na grafia do dicionário, por isso não há `motivo_principal_bronze` | 0 linhas alteradas · preco 264 · outro 223 · nao_uso 81 · outro_app 34 · problema_tecnico 27 · saude 14 |
| Q5 | Conta com mais de uma resposta | **Marcar** `flag_resposta_repetida = 1` | Cancelar, voltar a assinar e cancelar de novo é plausível; sem cruzar com `assinaturas.csv` não dá para dizer que é duplicata. Uma das contas muda de motivo (`outro` → `preco`) | 4 linhas de 2 contas · 641 contas na tabela |
| Q6 | `respondido_em` só com data, sem hora nem fuso | **Manter**; coluna nova `mes` | O site grava em horário de Brasília; não há UTC. Período 01/06–30/09/2026, nenhuma resposta depois do corte | 643 linhas · jun 210 · jul 182 · ago 154 · set 97 |
| Q7 | Motivo marcado não bate com o comentário (ex.: `preco` com "treinei pra prova e consegui, objetivo cumprido") | **Manter** sem corrigir; o notebook imprime a contagem | Reclassificar é tarefa da extração com IA. Contagem por palavra-chave: dos 460 com comentário, 452 têm tema reconhecível e 220 divergem do motivo. Dos 187 `preco` com comentário, só 2 falam de dinheiro: 104 são objetivo cumprido, 39 desuso, 22 falha técnica, 12 vida pessoal, 5 saúde | nenhuma linha alterada |

## Tickets de suporte (`1.bronze/tickets_suporte.csv` → `2.prata/tickets_suporte.csv`)

Notebook: `notebooks/tickets_suporte_prata.py`. Bronze: 4.422 linhas · prata: 4.422 linhas.

| # | Problema | Decisão | Motivo | Efeito na contagem |
|---|---|---|---|---|
| S1 | `canal`, `categoria_atendente`, `status` | **Manter**; o notebook padroniza (`strip`, minúsculas) e para se aparecer valor fora da lista do dicionário | Todos os valores já estão na grafia do dicionário, por isso não há colunas `<coluna>_bronze` | 0 linhas alteradas · canal: chat 2.195 · email 1.120 · loja 1.107 · status: resolvido 2.917 · aberto 981 · sem_resposta 524 |
| S2 | Fuso de `aberto_em` | **Manter**: já está em horário de Brasília nos três canais, inclusive `loja` | Aberturas entre 08h e 21h em chat, e-mail e loja, sem o deslocamento de 3h que o UTC das lojas produz em `pagamentos.csv` | 0 linhas convertidas |
| S3 | `resolvido_em` só com data; `aberto_em` com hora | **Manter**; coluna nova `dias_resolucao` = `resolvido_em` − data de abertura; coluna nova `mes` | Tempo de resolução só tem precisão de dias | 2.917 linhas com `dias_resolucao` · mín. 1 · máx. 19 · média 3,9 dias |
| S4 | Coerência entre `status` e `resolvido_em` | **Manter**; o notebook para se achar inconsistência | Todo `resolvido` tem data, nenhum `aberto`/`sem_resposta` tem, nenhuma resolução é anterior à abertura | 0 inconsistências |
| S5 | `resolvido_em` depois do corte de 30/09/2026 | **Marcar** `flag_resolvido_pos_corte = 1` | Informação posterior ao corte: no corte o chamado estava aberto. Variável de modelo trata como aberto | 41 linhas, todas abertas em set/2026 |
| S6 | Chamado `aberto` há mais de 20 dias no corte | **Marcar** `flag_aberto_antigo = 1` | O maior prazo de resolução observado é 19 dias; aberto depois disso é chamado abandonado, não fila | 935 de 981 `aberto` · 602 deles abertos em mai–jun/2026 |
| S7 | Texto com erro de digitação, sem acento ou com maiúscula variável (`GPS`/`gps`, `não consgio entrar`) | **Manter** o texto como veio (só `strip`) | A leitura do texto é da extração com IA | nenhuma linha alterada · 303 textos distintos, que se reduzem a 27 mensagens-base depois de normalizar |
| S8 | Texto vazio ou mojibake | **Marcar** `flag_texto_vazio`; **corrigir** mojibake quando aparecer (regras no notebook) | Insumo limpo para a extração | 0 linhas na bronze atual |
| S9 | `categoria_atendente` não bate com o texto (ex.: "quero cancelar minha assinatura" como `tecnico`; "corrida registrada com distância zerada" como `cobranca`) | **Manter** sem corrigir; o notebook imprime a contagem | Reclassificar é tarefa da extração com IA. Regra da contagem: texto normalizado, aproximado à mensagem-base mais próxima (difflib, corte 0,8) e comparado à categoria mais comum daquela mensagem | 1.488 de 4.422 chamados (33,6%) com categoria diferente da mais comum da mensagem · por categoria esperada: tecnico 588 · cobranca 344 · cancelamento 201 · conta 176 · conteudo 91 · duvida_geral 88 |
| S10 | Conta com mais de um chamado; 16 pares com o mesmo texto | **Manter** | Os pares de mesmo texto estão de 21 a 169 dias um do outro; nenhuma conta tem dois chamados no mesmo minuto (2 casos no mesmo dia, textos diferentes). Reincidência é sinal, não duplicata | 401 contas com 2+ chamados · 3.989 contas · 0 linhas removidas |
| S11 | `ticket_id` começa em `t_000368` | **Manter** | Sequência contínua até `t_004789`, sem buraco; os IDs anteriores são de antes de 01/07/2025 | nenhuma |

## Churn mensal (ouro) (`2.prata/assinaturas.csv` → `3.ouro/churn_mensal.csv`)

Notebook: `notebooks/churn_mensal_ouro.py`. Grão: mês × recorte (total, plano, canal,
plano × canal, método) × segmento; ago/2024–set/2026, 338 linhas. Artefato:
`artefatos/01_churn_mensal.html`.

| # | Problema | Decisão | Motivo | Efeito na contagem |
|---|---|---|---|---|
| G1 | Definição de churn mensal | **Definir**: perdas no mês ÷ ativos no dia 1 do mês. Ativo no dia 1 = `inicio` antes do dia 1 e `data_fim` vazia ou no dia 1 ou depois. Perda = `data_fim` no mês **e** ativo no dia 1 | É a métrica que a empresa acompanha (enunciado, seção 01). Quem assina e sai no mesmo mês fica fora da base e das perdas: só assim os números do enunciado batem (abr/26: 1.154 perdas; contando todos os fins seriam 1.158) | 8.540 ativos em jan/25 · abr/26 8,1% (1.154 ÷ 14.237) · 14.319 ativos em set/26 · média 5,68% em 2025 e 6,67% em jan–set/26, iguais ao enunciado. O notebook para se algum desses números não bater |
| G2 | Cortesias internas | **Remover** da base paga (`flag_cortesia = 1`) | Não pagam; são as 60 contas de teste (A3, U13) | −60 assinaturas, todas ativas no período |
| G3 | Jul/2024 incompleto | **Remover** o mês da série; começa em ago/2024 | O log de fins começa em 07/07/2024: jul/24 sai com 2,0%, artefato do corte do histórico. Ago–dez/24 seguem com viés de sobrevivência (A5) e não servem de referência de "normal" | −1 mês |
| G4 | Plano e canal por mês | **Usar** `plano_atual` e `canal` da prata como fixos | Ninguém troca de plano nem de canal no log (E4) | nenhuma linha alterada |

### Resultado de referência

Média mensal de churn, 2025 → jan–set/2026: mensal 8,97% → 10,83% (+1,86 p.p.); anual
2,63% → 3,33% (+0,70 p.p.); loja 5,38% → 6,34%; site 6,15% → 7,26%; Google Play 5,35% →
6,71% (+1,36 p.p.) contra App Store 5,40% → 5,98% (+0,57 p.p.).

## Quem saiu em jul–set/2026 (ouro) (`2.prata/*` → `3.ouro/assinantes_30jun26.csv`)

Notebook: `notebooks/assinantes_30jun26_ouro.py`. Grão: um assinante pagante ativo em
30/06/2026; 14.059 linhas, 34 colunas. Artefato: `artefatos/02_quem_saiu.html`. Conceitos e
debate de método: `memorial.md`, etapa 02.

| # | Problema | Decisão | Motivo | Efeito na contagem |
|---|---|---|---|---|
| K1 | Base e desfecho | **Definir**: base = pagas (`flag_cortesia = 0`) com `inicio` ≤ 30/06/2026 e `data_fim` vazia ou ≥ 01/07/2026; saiu = `data_fim` entre 01/07 e 30/09/2026 | Pergunta da aula 2; mesma regra de ativo da G1 aplicada a 01/07, então a base é a de jul/26 do `01_churn_mensal` | 14.059 assinantes (= ativos no início de jul/26) · 2.343 saíram (16,7%) · saídas de jul = perdas de jul/26. O notebook para se não bater |
| K2 | Data das variáveis | **Definir**: tudo medido até 30/06/2026; uso, posts e cobranças recusadas em abr–jun/2026 | Sem vazamento: a janela de saída começa em 01/07. Fica de fora `campanha_ago26` (dentro da janela), `versao_app` (retrato do corte) e `pesquisa_saida` (só existe para quem saiu) | nenhuma linha alterada |
| K3 | Fonte de engajamento | **Usar** `atividades` (treino a treino), não `uso_mensal` | `uso_mensal` subconta treinos de relógio em 2026 (M9) | assinante sem treino em abr–jun = 0 (não nulo): 746 na base |
| K4 | Uma linha por assinante | **Resumir** cada log por `user_id` antes de juntar; junção à esquerda com `validate="one_to_one"` | Juntar log direto multiplica linhas (aula 2) | 14.059 linhas em todas as oito junções |
| K5 | Chamado de GPS | **Definir**: texto do chamado (normalizado, sem acento) aproximado por difflib (corte 0,8) a uma das cinco mensagens-base do incidente (S, Em aberto) | A categoria do atendente erra em ~1/3 (S9) | 1.200 chamados de GPS até 30/06, os mesmos do pico de mai–jun |
| K6 | Comparar coisas comparáveis no anual | **Estratificar** em mensal e anual que vence em jul–set (`vence_jul_set`: anual iniciado em jul, ago ou set) | O anual só sai no aniversário; o anual inteiro mede o calendário, não o comportamento | anual que vence: 1.931 (46,3% saíram) · anual que não vence: 6.281 (3 saídas, devoluções) · mensal: 5.847 (24,7%) |
| K7 | Decisão já tomada em 30/06 | **Reconstruir** pelos eventos (fase assinatura, antes de 01/07, sem `flag_apos_fim`) a situação da renovação em 30/06: último evento entre início/renovação/religada (ligada), desligada/cancelamento_web (desligada) e carência; medir a separação também só entre quem estava com a renovação **ligada** | Aula 2, passo 5: "a renovação foi desligada antes ou depois do uso medido?". Uso baixo pode vir depois de desligar (causalidade reversa); o retrato de 01/10 não serve para 30/06 | ligada 11.711 · desligada 2.333 · em carência 15. Anual que vence: 734 desligados (94,1% saíram), 1.197 ligados (17,0%); mensal: 286 desligados (99,7%), 5.547 ligados (20,7%). AUC de dias com treino no anual que vence: 0,78 com todos, 0,67 só ligados. 1.313 anuais que não vencem já estavam com a renovação desligada |

### Resultado de referência

Separação por AUC univariada dentro de cada estrato. Mensal: tempo de casa 0,60 (31,2% de
saída até 3 meses de casa, 10,0% acima de 24 meses), dias com treino abr–jun 0,55. Anual que
vence: dias com treino abr–jun 0,78 (65,7% não renovaram sem nenhum treino no trimestre, 43,0%
com treino); só entre quem estava com a renovação ligada em 30/06, 0,67 (K7). Mensal android: 29,3% de saída com algum treino de GPS falho contra 25,0% sem.

## Por que saem (ouro) (`2.prata/*` → `3.ouro/saidas.csv`)

Notebook: `notebooks/saidas_ouro.py`. Grão: uma assinatura paga encerrada (= um `user_id`);
17.830 linhas, 07/07/2024–30/09/2026. Artefato: `artefatos/03_por_que_saem.html`. Conceitos e
debate de método: `memorial.md`, etapa 03.

| # | Problema | Decisão | Motivo | Efeito na contagem |
|---|---|---|---|---|
| W1 | Quais saídas | **Definir**: assinaturas com `flag_cortesia = 0` e `data_fim` preenchida | Mesma base paga da G2 | 17.830 saídas |
| W2 | Tipo de saída | **Definir** pelo `motivo_fim` da prata: voluntária = `renovacao_desligada`; involuntária = `falha_pagamento`; devolução = `chargeback` ou `reembolso` | Separa decisão do cliente, falha de cobrança e dinheiro devolvido, que pedem ações diferentes (Em aberto da G) | voluntária 16.145 · involuntária 1.321 · devolução 364 |
| W3 | Churn por tipo | **Usar** a regra G1 por tipo; ago/24–set/26 (G3) | A soma dos tipos tem de ser o churn do `01_churn_mensal` | soma = perdas da G1 em todos os 26 meses; o notebook para se não bater |
| W4 | Antecedência do aviso | **Definir** (só voluntária): dias entre o **último** `renovacao_automatica_desligada` e a `data_fim`; desligamento que chega depois do fim (`flag_apos_fim`, loja) conta como 0 e fica em `flag_aviso_apos_fim` | É a janela para intervir. O último desligamento é o que valeu; aviso atrasado da loja (E8) não é antecedência negativa | 91 saídas voluntárias de 2026 com aviso depois do fim (= 0 dia) |
| W5 | Tema da pesquisa de saída | **Usar** a função `tema` de `pesquisa_saida_prata.py` (palavra-chave, a mesma do diagnóstico Q7); conta que respondeu duas vezes vale a resposta mais recente | Mesmo critério da prata, sem segunda regra. Extração com IA fica para a etapa de variáveis de texto | 641 contas (643 respostas); 353 delas já expiraram até 30/09 |

### Resultado de referência

Média mensal 2025 → jan–set/2026: voluntária 5,12% → 6,09% (+0,97 p.p.), involuntária 0,43%
→ 0,46%, devolução 0,07% → 0,07%. Mensal voluntária 8,04% → 9,83% (+1,79 p.p.); anual
voluntária 2,51% → 3,16%. Falha de pagamento em jan–set/26: mensal no cartão 10,7 por 100
assinaturas, 2,1 a 3,6 nos outros métodos. Antecedência mediana (voluntárias de 2026): mensal
14 dias (loja 14, site 15), anual 157 (loja 151, site 175); 287 anuais (12,8%) desligaram
exatamente 42 dias antes do fim. Pesquisa: "objetivo cumprido" em 55,3% dos comentários com
tema; dos 187 que marcaram `preco` e comentaram, 2 falam de cobrança.

## Segmentação (ouro) (`2.prata/*` → `3.ouro/segmentos.csv`)

Notebook: `notebooks/segmentos_ouro.py`. Grão: um assinante pagante ativo × data de referência
(31/07/2026 e 30/09/2026); 28.785 linhas, 18 colunas. Artefato: `artefatos/04_segmentos.html`.
Conceitos e debate de método: `memorial.md`, etapa 04. Segue o roteiro da aula 3 (29/10/2026).

| # | Problema | Decisão | Motivo | Efeito na contagem |
|---|---|---|---|---|
| L1 | Base do agrupamento | **Definir**: pagas ativas em 31/07/2026 (regra G1 aplicada a 01/08) com a renovação **não desligada** em 31/07 (regra K7 aplicada a 01/08). Quem já desligou fica fora e recebe o rótulo `Já desligou` | Pergunta da aula 3; quem desligou já decidiu (D02.10) e puxaria um grupo só por isso | 14.032 ativos · 11.688 no agrupamento (ligada 11.666, em carência 22), o mesmo número da aula · 2.344 já desligados (90% anuais) |
| L2 | Saída para descrever os grupos | **Definir**: `saiu_60d` = evento `renovacao_automatica_desligada`, `cancelamento_web` ou `assinatura_expirada` entre 01/08 e 29/09/2026. Não entra no agrupamento | Mede a decisão de sair, como na aula ("pelos eventos"): o anual desliga meses antes de expirar (W4). Carência sozinha não conta (pode pagar) | 1.502 de 11.688 (12,9%; a aula mostra 12,5%) · vazio para `Já desligou` e para 30/09 |
| L3 | Variáveis do agrupamento | **Usar** as quatro da aula, medidas até 31/07 em `atividades`: treinos por semana (12 semanas, 09/05–31/07, ÷ 12); dias sem treino (sem treino no arquivo: desde 01/01/2026 ou desde o início, o que vier depois); tempo de casa em dias; % dos treinos das 12 semanas em corrida, caminhada ou pedal (0 sem treino) | Aula 3; `atividades` começa em 01/01/2026, daí o teto de dias sem treino | medianas: 1,9 treino por semana, 2 dias sem treino, 267 dias de casa, 69% ao ar livre · 562 sem treino nas 12 semanas |
| L4 | Escala e algoritmo | **Padronizar** (StandardScaler) e rodar k-means de k = 2 a 8, `n_init = 10`, `random_state = 0` | Sem padronizar, o tempo de casa (dias) dominaria a distância; semente fixa para refazer | nenhuma linha alterada |
| L5 | Número de grupos | **k = 4** pelas quatro lentes: inércia dobra entre 4 e 5 (−7.522 de 3 para 4, −4.252 de 4 para 5); silhueta 0,43 (fraca; a maior é 0,59 em k = 2); Rand ajustado em 10 reamostras médio 0,999, mínimo 0,998 (k = 6: mínimo 0,63); outra semente 1,000; quatro grupos com ação diferente | Nenhuma lente decide sozinha (aula 3) | Parados 560 · Ativos ao ar livre 5.837 · Ativos em ambiente fechado 4.219 · Veteranos 1.072 |
| L6 | Variáveis do grupo (até duas, aula 3) | **Testar e deixar de fora**: % de treinos ao ar livre com GPS falho, km por treino ao ar livre e conexões recíprocas; plano, canal e método também fora | Nenhuma muda os grupos (Rand 0,986–0,998 com os quatro) e todas baixam a silhueta (0,32–0,37). Variável 0/1 padronizada pesa demais na distância (aula 3) | ficam no perfil (colunas da tabela), não no agrupamento |
| L7 | Nome dos grupos | **Definir por regra** sobre as medianas: maior dias sem treino = Parados; maior tempo de casa = Veteranos; dos dois restantes, maior % ao ar livre = Ativos ao ar livre | O k-means devolve números; a regra fixa o nome se a ordem dos rótulos mudar | o notebook para se a regra não separar os quatro |
| L8 | Tamanho atual | **Classificar** os pagantes de 30/09/2026 com o mesmo padronizador e os mesmos centros, variáveis medidas até 30/09 | O relatório prioriza a base de hoje; a de 31/07 só serve para ver a saída | 14.753 ativos (= enunciado) · Parados 514 · Ao ar livre 6.327 · Ambiente fechado 4.616 · Veteranos 1.046 · Já desligou 2.250 |

### Resultado de referência

Saída em 60 dias (01/08–29/09/2026) por grupo: Parados 29,8% (todos anuais), Ativos ao ar livre
14,0% (mensal 15,4%, anual 12,6%), Ativos em ambiente fechado 10,9% (12,8% e 8,7%), Veteranos 5,4%;
média 12,9%. Mensal com até 90 dias de casa: 20,8% ao ar livre, 15,2% em ambiente fechado. Mensal
no cartão: 17,2%. Já desligou: 32,3% expiraram em 60 dias, 6,9% religaram.
## Segmentos k-means (ouro) (prata → `3.ouro/segmentos_kmeans.csv`)

Notebook: `notebooks/segmentos_kmeans_ouro.py`. Grão: assinante × data de referência
(31/07/2026 e 30/09/2026), 28.785 linhas. Artefato: `artefatos/05_segmentos_kmeans.html`.

| # | Problema | Decisão | Motivo | Efeito na contagem |
|---|---|---|---|---|
| N1 | Quem segmentar | **Definir**: assinaturas pagas (`flag_cortesia = 0`) ativas no fim da data de referência (`inicio <= ref` e `data_fim` vazia ou depois de `ref`) | O relatório da semana 5 segmenta a base que pode sair | 14.032 em 31/07/26 · 14.753 em 30/09/26 |
| N2 | Data de ajuste | **Ajustar** o k-means em 31/07/2026 e medir a saída nos 60 dias seguintes (`data_fim` de 01/08 a 29/09/26); em 30/09 só **atribuir** o centróide mais próximo, com a padronização de 31/07 | Em 30/09 o horizonte de 60 dias ainda não aconteceu; 31/07 é a última data com 60 dias observados até o corte | saída em 60 dias da base de 31/07: 10,5% |
| N3 | Variáveis | **Usar** nove variáveis de comportamento até `ref`: treinos em 30 dias, tendência (30 dias contra os 60 anteriores), dias sem treinar (teto 120), sessões no app (média de 3 meses), conexões recíprocas, posts em 90 dias, chamados + treinos com GPS falho em 90 dias, recusas em 180 dias, meses de assinatura. Contagens em `log1p`, z-score com média e desvio de 31/07 | Só informação até a data de referência; treinos de `atividades` (sem `flag_inicio_repetido`), que conta o relógio que `uso_mensal` subconta (M9) | — |
| N4 | Plano, canal, sistema | **Não usar** no agrupamento; só para descrever os segmentos | O anual só sai na renovação: com plano no k-means o segmento repetiria o plano | — |
| N5 | Número de segmentos | **k = 4** (k-means++, 20 inicializações, `random_state = 7`) | Guia pede 3–4 segmentos; entre 3 e 4, k = 4 tem o maior silhouette (0,237; k = 3: 0,203). k = 5 (0,253) separa Android com GPS falho, que sai 7,6%, abaixo da média | — |
| N6 | Nome dos segmentos | **Rotular** pelo traço do centróide: maior recusa = Cobrança falhando; mais dias sem treino = Parados; menos meses de assinatura = Recém-chegados; o restante = Engajados | Rótulo estável se a ordem dos clusters mudar | — |
| N7 | Prioridade e rótulo quando a prata muda | **Definir**: prioridade "ação imediata" se o segmento sai em 60 dias ≥ 1,5 × a média da base, senão "monitorar". Rótulo de N6 só vale se o centróide está a ≥ 1 desvio da média na variável; grupo sem rótulo vira "Grupo n". k recalculado pela regra de N5 a cada execução | O ouro é refeito quando os colegas atualizam a prata: prioridade, rótulos, k e todo número da página saem do cálculo, não do código | Recém-chegados (9,4% contra limite de 15,7%) passa de "ação imediata" (escolha manual anterior) para "monitorar"; demais iguais |

### Resultado de referência

Base de 31/07/2026, saída em 60 dias: Engajados 8.218 (58,6%) saem 6,8% · Recém-chegados
2.614 (18,6%) saem 9,4% · Parados 2.755 (19,6%, 93% anual) saem 20,9% · Cobrança falhando
445 (3,2%, 90% mensal, 64% site) saem 18,9%, 32% das saídas por falha de pagamento. No
mensal, Parados saem 46,7% contra 12,6% dos Engajados. Base de 30/09: 8.368 · 3.477 · 2.446 ·
462.

## Conciliação dos segmentos (ouro) (`3.ouro/segmentos.csv` + `3.ouro/segmentos_kmeans.csv` → `3.ouro/conciliacao_segmentos.csv`)

Notebook: `notebooks/conciliacao_segmentos.py`. Grão: segmento L × segmento N × data de
referência (31/07 e 30/09/2026), 36 linhas. Cruza `segmentos.csv` (decisões L1–L8) com `segmentos_kmeans.csv` (N1–N7). Página:
`estudos-analises/rascunho_customer_segmentation_report.html`, seção 04.

| # | Problema | Decisão | Motivo | Efeito na contagem |
|---|---|---|---|---|
| X1 | Duas segmentações k-means para o mesmo relatório | **Usar** os quatro grupos de L (renovação ligada, quatro variáveis da aula) como personas e a saída por decisão de L2; **usar** "Já desligou" (L) e "Cobrança falhando" (N) como listas operacionais; "Recém-chegados" (N) vira recorte (mensal com até 90 dias) dentro dos Ativos; "Parados" e "Engajados" de N ficam só no cruzamento. Prioridade: ação imediata se a saída em 60 dias ≥ 1,5 × a média **ou** o grupo tem o maior número esperado de saídas (taxa × base de 30/09) | Mesma base de 14.032 em 31/07, mas eixos diferentes (Rand ajustado 0,046 sem "Já desligou"). Em N, 58% dos Parados já tinham desligado a renovação (causalidade reversa, K7 da etapa "quem saiu"); L separa estável (Rand 0,999 em reamostras, silhueta 0,43). Recusas e treino dos últimos 30 dias, que só N tem, separam a cobrança. A saída por decisão chega meses antes do fim no anual (1.502 decidiram, 711 já tinham `data_fim` na janela) | Personas em 30/09: Parados 514 · Ativos ao ar livre 6.327 · Ativos em ambiente fechado 4.616 · Veteranos 1.046 (12.503). Listas: Já desligou 2.250 · Cobrança falhando 462 (se sobrepõe às personas). Ação imediata: Parados (29,8%) e Ativos ao ar livre (≈ 887 saídas) |

### Resultado de referência

31/07/2026: 558 dos 560 Parados (L) estão nos Parados de N. Dos 1.422 mensais ativos (L) com
até 90 dias de casa, 1.104 estão em Recém-chegados (N). Cobrança falhando (N): 54% no cartão;
193 nos Ativos ao ar livre e 189 nos de ambiente fechado. Dentro dos Ativos ao ar livre, quem
está em Parados de N (pouco treino nos últimos 30 dias) sai 25,9% pela decisão, contra 11,7%
dos Engajados.
## Recusas de cobrança (ouro) (`2.prata/pagamentos.csv` + `2.prata/assinaturas.csv` → `3.ouro/recusas_cobranca.csv`)

Notebook: `notebooks/recusas_cobranca_ouro.py`. Grão: uma cobrança recusada; jul/2024–set/2026,
3.250 linhas de 3.013 assinantes. Saídas: `dados/3.ouro/recusas_cobranca.csv`, a planilha
`dados/3.ouro/recusas_cobranca.xlsx` (abas `recusas`, `resumo_mensal`, `resumo_canal`,
`regras`) e o artefato `artefatos/06_recusas_cobranca.html`.

| # | Problema | Decisão | Motivo | Efeito na contagem |
|---|---|---|---|---|
| R1 | O que é um caso de recusa | **Definir**: uma linha por cobrança com `status = 'recusado'`; a retentativa é a cobrança seguinte do mesmo usuário com `tentativa_real = 2` (até 16 dias, P5) | Nos dados cada recusa tem no máximo uma retentativa: nenhuma cobrança tem `tentativa_real` 3 | 3.250 recusas · 3.013 assinantes · 1.881 retentativas, todas aprovadas |
| R2 | Desfecho de cada recusa | **Definir**: `recuperada` = retentativa aprovada; `perdida` = sem retentativa aprovada e a assinatura terminou depois da recusa; `em_aberto` = sem retentativa aprovada e assinatura ativa em 30/09/2026 | Separa o que a retentativa salva do que vira churn involuntário. O notebook para se alguma recusa não cair em um dos três | 1.881 recuperadas · 1.321 perdidas · 48 em aberto (recusas de 16 a 30/09/2026) |
| R3 | Perdida = `motivo_fim = falha_pagamento` | **Conferir** no notebook | As 1.321 perdidas são exatamente as 1.321 assinaturas com `falha_pagamento` em `assinaturas`, uma recusa por assinatura | 0 divergências |
| R4 | Taxa de recuperação | **Definir**: recuperadas ÷ (recuperadas + perdidas); em aberto fica fora | Recusa em aberto ainda não tem desfecho | 58,7% (1.881 ÷ 3.202) |
| R5 | Valores | **Usar** `valor_bronze` como valor tentado (P12) e a taxa do método (enunciado, seção 03); valor recuperado = valor da retentativa aprovada | Mesmas premissas do faturamento | R$ 191.935,00 tentados · R$ 110.186,90 recuperados (R$ 102.610,77 líquidos) |

### Resultado de referência

3.250 recusas: 1.881 recuperadas, 1.321 perdidas, 48 em aberto; recuperação de 58,7%. Sem
retentativa aprovada, a assinatura expira **7 dias** depois da recusa no site (cartão e Pix) e
**16 dias** na loja (App Store e Google Play), sem exceção. Recuperação por método e plano:
de 42,4% (App Store anual, 33 recusas) a 63,6% (Pix anual, 11); no volume, cartão mensal
60,3% (1.488 recusas) e Google Play mensal 58,8% (645).

## Conferências (`notebooks/conferencias.py`)

Não gera tabela: confere de uma vez as contagens de cada tabela (bronze = dicionário, prata =
"Visão geral da prata"), os números de referência (faturamento de set/26, 14.753 ativos, 717 e
3.389 expirações), os cruzamentos entre tabelas (nenhum `user_id` órfão; cada cobrança
aprovada com início/renovação no mesmo dia; nenhuma cobrança fora da vida da assinatura;
só os preços do enunciado; P12) e o ouro já gerado (5,6% e 6,6%; R3). Sai com erro se algo
quebrar. Rode depois de mexer em qualquer notebook.

## Em aberto

### Usuários

- U4: a base antes de jul/2024 é rala (5.207 contas em 46 meses, contra ~1.900 por mês
  depois) e `pagamentos` começa em jul/2024. Confirmar com `eventos_assinatura.csv` se as
  contas antigas são completas ou só as que sobreviveram, antes de usar safra de cadastro
  anterior a jul/2024.
- U13: decidir no ouro se as 60 contas de teste saem de todas as métricas (churn, receita,
  uplift) e conferir se têm linha em `eventos_assinatura`/`uso_mensal` com outro `user_id`.

### Assinaturas

- A9: no ouro, cruzar as 4 mensais ativas sem cobrança recente com `pagamentos.csv` e
  `eventos_assinatura.csv` (`periodo_carencia`) para decidir se contam como ativas em set/26.
- `eventos_assinatura.csv` tem 296 eventos `chargeback` e este arquivo 292 assinaturas
  encerradas por `chargeback`: conferir na limpeza de eventos se os 4 restantes são
  chargebacks sem encerramento.
- A5: definir no ouro de churn se a base de jul/2024 em diante é o recorte oficial (antes
  disso faltam as assinaturas encerradas).

### Eventos de assinatura

- P7 (pagamentos, `flag_intervalo_curto`): os 223 pares de cobranças aprovadas com menos de 20 dias têm renovação (ou início) em `eventos_assinatura` nas duas datas; o log tem 220 intervalos início/renovação → renovação abaixo de 20 dias. É ciclo curto registrado nos dois sistemas, não cobrança em dobro. Proposta: passar P7 de marcar para manter.
- P8 (pagamentos, `flag_preco_antigo`): as 16 cobranças de R$ 34,90 em março/2026 têm renovação no mesmo momento, 32 a 45 dias depois da renovação anterior (ciclo de fevereiro cobrado com atraso, dentro da janela de retentativa). Proposta: passar P8 de marcar para manter.
- As 60 assinaturas de `assinaturas.csv` sem nenhum evento no log são as cortesias `interno` (A3, `flag_cortesia`): ficam fora da base paga.
- Na loja, a causa da expiração vem dos eventos anteriores, inclusive os marcados em E8 (chargeback e desligamento que chegam até 1 dia depois). A regra de churn voluntário/involuntário vai para o ouro.

### Pagamentos

- P7 e P8: conferidos com `eventos_assinatura.csv` (ver "Eventos de assinatura" acima): os
  dois casos têm renovação registrada no log, então não são erro. Falta o grupo decidir se
  passam de marcar para manter (riscar P7/P8 e abrir P13/P14); as flags continuam na prata.

### Uso mensal

- M9 (não aplicado): em 2026, `uso_mensal` conta **menos** treinos que `atividades.parquet`
  em 58.806 usuário-mês (13,4% das linhas de 2026; 16.313 usuários), somando 383.386 treinos
  a menos; nunca conta mais. Todo usuário que bate em todos os meses só tem treinos de origem
  `app`: a divergência está em quem sincroniza Garmin ou Apple Health. Outros 2.205
  usuário-mês com treino no parquet (3.258 treinos) não têm linha aqui. Confirmar depois de
  limpar o parquet e decidir a fonte de engajamento em 2026 (ouro).
- M6: confirmar a causa da queda de `sessoes_app` em mar/2026 (versão do app em
  `usuarios.csv`, tickets de suporte). Coincide com o reajuste de 01/03/2026.
- Quem entra na tabela em 2026 (assinante? conta ativa?) não está no dicionário: 63.830
  usuários em 2026 contra 32.640 em 2025 (todos os de 2025 seguem em 2026). Cruzar com
  `assinaturas.csv`/`eventos_assinatura.csv` no ouro.

### Atividades

- `treino_com` não foi conferido contra `usuarios.csv` (prata não cruza): validar na ouro se toda companhia é uma conta existente.
- GPS falho (T5) só aparece na versão do app que passou a gravar o tipo em inglês: provável defeito da versão de 15/04/2026. Candidato a variável de experiência ruim no modelo de churn; cruzar com a versão do app em `usuarios.csv`.
- Duplicatas em que só uma das cópias tem distância inflada ou duração zero não casam na regra T3 e ficam como `flag_inicio_repetido`. Ao contar minutos ou km por usuário, decidir se esses grupos contam uma vez.
- Minutos de treino: 1.679 treinos sem duração (T6). O treino conta na frequência; a métrica de minutos precisa dizer se ignora ou imputa.

### Campanha ago/26

- C4: o fuso de `enviado_em` é premissa; não muda dia nem mês (10h em Brasília é 13h UTC do mesmo dia).
- Resultado da campanha (saída por grupo) fica para o ouro, cruzando com `eventos_assinatura.csv`. `plano_atual` de `assinaturas.csv` é a situação atual, não a de 10/08: para o plano no dia do envio, use os eventos.

### Onboarding

- Extração com IA (próxima etapa, não é prata): enviar `objetivo_texto` com
  `objetivo_texto is not null and flag_objetivo_sem_conteudo = 0` (44.694 linhas). Variáveis
  candidatas: tipo de objetivo (saúde, estética, social, mental, desempenho), meta numérica
  (`perder uns 7kg`) e evento com data (`meia maratona dia 16/12`, `daqui 17 semanas`).
- Datas no objetivo são relativas ou sem ano (≈ 9.600 linhas com data ou prazo): a extração
  precisa ancorar em `respondido_em` para virar data absoluta.
- `como_conheceu` → canal (busca, anúncio por rede, indicação, influenciador, empresa,
  loja): decidir entre extração com IA ou dicionário de grafias; tratar os erros de
  digitação e extrair o `@perfil` do influenciador (cruzar com o cupom em `assinaturas`).
- Conferir no ouro se `respondido_em` bate com a criação da conta em `usuarios.csv`.
- Avaliar no modelo se `flag_*_sem_conteudo` (resposta vazia de propósito) explica churn.

### Feed

- Extração com IA (próxima etapa, não é prata): enviar `texto` com
  `texto is not null and flag_apos_corte = 0` (117.974 posts, 31.551 textos distintos,
  26.811 usuários). Como os textos se repetem muito, extrair por texto distinto e juntar de
  volta por `texto`.
- Variáveis candidatas: modalidade e distância/duração (`5km leves`, `pedal de 25km`),
  intenção de sair ou pausa (`cancelei o premium…`, `acho que vou dar um tempo do app`,
  `último mês aqui` — ≈ 2.600 posts com termos desse tipo), evento de vida (filho, mudança
  de cidade, viagem, aniversário) e prova com data.
- Datas no texto são relativas (`daqui 17 semanas`) ou sem ano (`dia 15/08`): ancorar em
  `data_hora`.
- Post removido (F4): decidir no ouro se conta como atividade no feed (tem data e curtidas).
- Confirmar o fuso de `data_hora` com outro arquivo do app, se algum trouxer o mesmo evento.

### Pesquisa de saída

- Q7: o `motivo_principal` não serve, sozinho, como motivo de saída. `preco` concentra respostas
  cujo comentário fala de outra coisa, o que sugere opção padrão ou primeira da lista. A
  extração com IA deve tirar o motivo do `comentario` e comparar com o marcado; as 183
  respostas sem comentário ficam só com o motivo marcado.
- Tema dominante no texto: objetivo cumprido / evento passado ("era só até a prova",
  "já fiz o casamento, agora não preciso mais"), 251 de 460 comentários. É um motivo que não
  existe na lista fechada; vale virar categoria na extração.
- Q5: confirmar com `assinaturas.csv` se as 2 contas com duas respostas tiveram dois
  cancelamentos.
- Cobertura: o dicionário diz que as 643 respostas incluem 289 de quem cancelou pelo site e
  seguia ativo em 30/09/2026; o enunciado fala em 353 respondentes entre os 3.389 fins de
  assinatura de jun–set/2026. Separar os dois grupos exige cruzar com `assinaturas.csv` (ouro).
  Amostra autosselecionada e só do site: não generalizar para quem paga pela loja.

### Tickets de suporte

- S9: a categoria do atendente erra em cerca de um terço dos chamados. A extração com IA deve
  classificar o `texto_cliente` (tema, pedido de cancelamento, problema de cobrança, falha
  técnica) e usar a categoria só como comparação.
- Pico de mai–jun/2026: 886 e 741 chamados contra ~200 nos outros meses. Cinco mensagens de
  falha de rastreio ("GPS parou de funcionar no meu android", "corrida registrada com distância
  zerada", "o app não grava meu percurso desde a atualização", "perdi meus treinos da semana, o
  app travou no meio", "a rota sai toda torta e a distância errada") somam 1.200 chamados nesses
  dois meses e nenhum nos outros 13. Candidato a causa na análise diagnóstica do churn de 2026
  (cruzar com atividades, versão do app e sistema do celular em `usuarios.csv`).
- S6: o dicionário não diz a diferença entre `aberto` e `sem_resposta`. Hoje os dois parecem
  chamado não atendido; confirmar antes de usar como variável.
- S5: na base de modelagem (ouro), recalcular `status` no corte: `resolvido` com
  `flag_resolvido_pos_corte = 1` vira `aberto`.

### Churn mensal (ouro)

- ~~Separar a perda voluntária (renovação desligada, cancelamento) da involuntária (falha de
  pagamento, carência) e da devolução (chargeback, reembolso), usando os eventos anteriores
  ao fim (E5, E8).~~ Feito pelo `motivo_fim` em W2–W3: a subida de 2026 é voluntária.
- Anual: medir a taxa de não renovação (venceu no mês e não renovou). A taxa mensal sobre
  toda a base anual dilui o efeito.
- Janeiro alto nos dois anos (6,4% e 7,4%): conferir se é vencimento de anuais.
- A G1 registra média de 5,68% (2025) e 6,67% (jan–set/26), mas a tabela `churn_mensal.csv` atual dá
  5,62% e 6,62% (média dos 12 e dos 9 meses de `churn_pct`, recorte total), que arredondam para os
  5,6% e 6,6% do enunciado. Conferir de onde veio o 5,68/6,67 e corrigir a G1 (riscando a antiga).
  Conferido em 07/11/2026 ao montar a `00_historia_da_eda.html`.

### Quem saiu em jul–set/2026 (ouro)

- Debates do `memorial.md` (D02.1–D02.6) estão como **proposto**: o grupo confirma a janela
  30/06 + jul–set, a fonte `atividades`, o trimestre abr–jun e o uso do tamanho do efeito.
- Separar a saída voluntária da involuntária na base K1 (`motivo_fim`): a recusa de cobrança
  separa pouco no total. Tipos definidos em W2; falta aplicar na base K1 (etapa 04).
- GPS falho no android mensal (+4,3 p.p.): testar se sobrevive ao tipo de treino (quem corre ao
  ar livre) antes de chamar de driver.

### Por que saem (ouro)

- Anual: 287 desligamentos (12,8%) exatamente 42 dias antes do fim, na loja e no site. Conferir
  se há lembrete de renovação ou e-mail de aviso nessa data (não está no enunciado nem no
  dicionário).
- Taxa involuntária por método usa denominador de período (ativos em algum dia de jan–set/26):
  trocar por taxa mensal se for para o ROI.
- Tema da pesquisa por palavra-chave (W5): comparar com a extração por IA quando ela existir.
- Debates D03.1–D03.4 do `memorial.md` estão como **proposto**.

### Segmentação (ouro)

- GPS falho: entre os mensais ao ar livre, quem teve treino com GPS falho saiu **menos** em ago–set
  (11,8% × 16,6%), o contrário da etapa 02. Suspeita de seleção (quem teve a falha e saiu em julho
  não está na base de 31/07): testar no modelo com a base de 30/06.
- Alvo do modelo da semana 10: decisão de sair (L2, desligar ou expirar) ou perda (G1, expirar)?
  Muda o anual, que desliga meses antes de expirar.
- `Já desligou` (2.250 em 30/09, 93% anuais): decidir se entra no plano de intervenção como lista
  de reversão.
- Diferença para a referência da aula (12,5% de saída; parados 472): não sabemos a regra de borda da
  aula; os grupos e as taxas batem dentro de poucos pontos.
- Debates D04.1–D04.5 do `memorial.md`.

### Segmentos k-means (ouro)

- Discutir com o grupo os quatro segmentos e os rótulos antes do Segmentation Report (15/11).
- Decidir se o segmento entra no modelo de churn como variável ou fica só para comunicação.
- Reajustar quando a extração com IA trouxer objetivo do onboarding e intenção de sair no feed.
- Cruzar segmentos com o resultado da campanha de ago/26 (uplift por segmento).

### Conciliação dos segmentos (ouro)

- ~~Os IDs K1–K7 colidem entre o k-means de nove variáveis e a etapa "quem saiu".~~ Resolvido
  na integração de 07/11: o k-means de nove variáveis passou a N1–N7; K fica com "quem saiu".
- ~~Numeração das páginas colide (`02_segmentos_kmeans` × `02_quem_saiu`).~~ Resolvido na
  integração: a página do k-means de nove variáveis é `05_segmentos_kmeans.html` e a de
  recusas de cobrança, `06_recusas_cobranca.html`.
- ~~A letra R da conciliação colide com R1–R5 (recusas de cobrança).~~ Resolvido na
  integração: a conciliação passou a X1.
- ~~O laço `notebooks/*_ouro.py` roda em ordem alfabética: `assinantes_30jun26_ouro.py` lê o
  `churn_mensal.csv` antes de ele existir, e a conciliação lê os dois k-means.~~ Resolvido na
  integração: `churn_mensal_ouro.py` roda antes do laço e a conciliação virou
  `conciliacao_segmentos.py`, rodado depois (instruções no `AGENTS.md` e no `README.md`).
- ~~`segmentos_ouro.py` quebra no pandas 2.x (`np.maximum` entre data e `Timestamp`).~~
  Trocado por `b.inicio.clip(lower=INICIO_ARQUIVO)` na integração; mesmo resultado.
- Validar X1 com o grupo (Camila, Douglas) antes de fechar o relatório de 15/11.
