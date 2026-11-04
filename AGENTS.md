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

## Como o grupo trabalha

Quatro pessoas, um repo (`origin` = `github.com/Markabdo87/Vitaliza-MBA`), ramo `main`.
A palavra-chave é **verificável**: qualquer número tem que poder ser refeito por outra
pessoa a partir da bronze, rodando os notebooks e lendo o `decisoes.md`.

Três peças, cada uma com uma skill em `.claude/skills/` (outros agentes: leiam o `SKILL.md`
correspondente quando a situação aparecer):

| Peça | Regra curta | Skill |
|---|---|---|
| **Git** | Ao abrir a sessão, puxe o que o grupo subiu. Ao fechar, commit + `pull --rebase` + push (com confirmação) + handoff na seção "Em aberto" do `decisoes.md` | `git-do-grupo` |
| **`decisoes.md`** | Log de toda decisão e premissa que muda um número: limpeza, premissa de negócio, definição de métrica, escolha de análise. ID, motivo e efeito numérico. Não se apaga linha antiga, risca e aponta para a nova | `registrar-decisao` |
| **Camadas** | bronze (imutável) → prata (limpa, mesmo grão) → ouro (cruzada/agregada). Cada tabela tem um notebook que a gera do zero | `camadas-de-dados` |

Ciclo de uma limpeza: perfila a bronze → decide cada problema → escreve
`notebooks/<arquivo>_prata.py` com as regras na docstring → roda e mede → registra no
`decisoes.md` → cadastra a tabela abaixo → sobe tudo no mesmo commit.

O `.claude/settings.json` bloqueia edição da bronze, leitura de `.env`, `push --force`,
`reset --hard` e `git clean`, e roda um hook no início da sessão que compara o repo com o
`origin`.

## Estrutura

```
dados/
├── 1.bronze/   # arquivos como vieram do curso. NUNCA editar.
├── 2.prata/    # bronze limpa, uma tabela por arquivo de origem, mesma granularidade
└── 3.ouro/     # tabelas de análise (cruzamentos, agregados, base de modelagem, scores)
notebooks/      # um notebook por tabela gerada: <tabela>_<camada>.py
decisoes.md     # ★ fonte da verdade: decisões, premissas e pendências ("Em aberto")
.claude/        # settings do projeto, hook de início de sessão e skills
```

Regras das camadas:
- Bronze é imutável. Toda correção vira código em `notebooks/`, nunca edição à mão de CSV.
- Prata: corrige formato, remove duplicata comprovada e **marca** suspeitas com colunas
  `flag_*` em vez de apagar. Guarde o valor original em `<coluna>_bronze` quando corrigir.
  Não agrega nem cruza tabelas.
- Ouro: lê só da prata; aqui se cruza por `user_id` e se agrega.
- Prata e ouro não vão para o git: são recriadas rodando os notebooks.
- Cada notebook gera sua tabela do zero, roda da raiz e documenta as regras na docstring.
  Pode ser `.py` ou Jupyter (`.ipynb`), a gosto de quem escreve: o que importa é rodar do zero.
- Ao criar uma tabela nova, registre-a em "Tabelas prontas" abaixo.

Rodar (a partir da raiz do repo):
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # uma vez
for n in notebooks/*_prata.py; do .venv/bin/python "$n"; done        # toda a prata
```
Os notebooks usam a biblioteca padrão do Python 3, menos `atividades_prata.py`, que lê
parquet e precisa do `pyarrow` (em `requirements.txt`). Dependência nova entra no
`requirements.txt` com versão fixada.

## Armadilhas conhecidas dos dados

O dicionário avisa: ninguém limpou os dados, e formatos, fusos e nomes variam entre arquivos.
Já confirmado:

- **Fusos:** eventos das lojas (App Store / Google Play) vêm em UTC (`...Z`); o site grava em
  horário de Brasília. Converta tudo para Brasília antes de cortar por dia/mês.
- **Nomes de canal diferem entre arquivos:** `pagamentos` usa `cartao`/`pix_automatico`;
  `assinaturas` usa `web_cartao`/`web_pix` (e `interno` para cortesia).
- **pagamentos.csv** (detalhes no notebook `pagamentos_prata.py`):
  - 1.941 cobranças duplicadas (mesmo usuário, segundo, valor e status, IDs seguidos);
  - valor do site em `R$ 39,90` até jun/2025, depois `39.90`;
  - estornos/chargebacks lançados pelo preço de tabela, não pelo valor cobrado
    (−39,90 em quem pagou 34,90; −299,90 em quem pagou 239,90 com cupom);
  - a coluna `tentativa` não registra retentativa: recusa seguida de nova cobrança aparece
    como `tentativa = 1` de novo. Use `tentativa_real` da prata.
- Preço: mensal R$ 34,90 até 28/02/2026 e R$ 39,90 desde 01/03/2026; anual R$ 299,90
  (R$ 239,90 no 1º ano com cupom de influenciador).
- **Nem todo "loja" é UTC.** UTC com `Z`: `pagamentos` e `eventos_assinatura` (lojas).
  **UTC sem `Z`**: `atividades` com origem Garmin (mesmo formato do horário de Brasília, só
  a origem revela). Já em Brasília: `usuarios.data_cadastro`, `assinaturas` (só data, também
  na loja), `tickets_suporte` (inclusive canal `loja`), `feed_posts`, `campanha_ago26`.
- **Datas depois do corte** em arquivos que deveriam parar em 30/09/2026: `amizades.desde`
  (até 09/10), `feed_posts` (até 07/10), `tickets_suporte.resolvido_em`. Use os `flag_*` de
  corte da prata em toda variável de modelo.
- **usuarios.csv** tem 959 contas duplicadas (mesmo e-mail, cópia mais nova com maiúscula;
  inclui todos os cadastros "futuros", até 2027). Nenhum outro arquivo as usa: cruze sempre
  com a prata. Há 60 contas de teste da Vitaliza (`flag_conta_teste`), as mesmas 60
  assinaturas `cortesia`/`interno` (`flag_cortesia`), sem cobrança nem evento.
- **Histórico começa em 01/07/2024.** Assinaturas encerradas antes disso não existem no
  arquivo (churn anterior a jul/2024 não é calculável), e 5.200 assinaturas antigas entram
  no log já no meio, sem `assinatura_iniciada`.
- **Uma assinatura por `user_id`** em `assinaturas` e `eventos_assinatura` (o dicionário diz
  que pode haver mais): ninguém volta a assinar nos dados.
- **eventos_assinatura:** no site, cancelar gera `cancelamento_web` **e**
  `renovacao_automatica_desligada`, então não some os dois. Avisos de loja chegam até 1 dia depois
  da expiração (`flag_apos_fim`). `detalhe` (motivo do fim) só existe no site.
- **uso_mensal:** em 2025 só há linha em mês com treino; em 2026 também em mês sem treino
  (`flag_sem_treino`), então contar linhas entre os anos mistura populações. `sessoes_app` muda
  de escala em mar/2026 (−45% por treino). Em 2026 subconta treinos de relógio frente a
  `atividades`.
- **atividades:** desde 15/04/2026 o app grava `tipo` em inglês (`run`, `walk`…); treino de
  relógio chega duas vezes (relógio + app); GPS falho (`gps_ok = False`) só na versão nova do
  app, com distância sem sentido.
- **Incidente técnico em mai–jun/2026:** pico de tickets de GPS/percurso não gravado
  (~1.200 chamados), coerente com o GPS falho de `atividades`. Candidato a causa do churn.
- **Categorias preenchidas por pessoas divergem do texto livre**: `pesquisa_saida.motivo_principal`
  em ~metade dos casos (`preco` quase nunca fala de dinheiro) e
  `tickets_suporte.categoria_atendente` em ~1/3. Os textos são mensagens-base repetidas com
  variação de digitação; datas no texto são relativas ("daqui 17 semanas") e precisam ser
  ancoradas na data do registro.

Ao descobrir uma armadilha nova, acrescente aqui.

## Tabelas prontas

| Tabela | Notebook | Grão | Observações |
|---|---|---|---|
| `dados/2.prata/usuarios.csv` | `notebooks/usuarios_prata.py` | uma conta | 63.989 contas sem duplicatas; para análise de cliente filtre `flag_conta_teste = 0`; `idade_corte` vazia em 3.837 contas; hora de cadastro só vale com `flag_hora_cadastro_desconhecida = 0` |
| `dados/2.prata/assinaturas.csv` | `notebooks/assinaturas_prata.py` | uma assinatura (= um `user_id`), retrato de 01/10/2026 | situação atual, não histórico (para datas passadas use eventos); `canal`/`metodo` alinhados a pagamentos; filtre `flag_cortesia = 0` para base paga; `flag_inicio_antes_historico` = sem rastro nos logs |
| `dados/2.prata/eventos_assinatura.csv` | `notebooks/eventos_assinatura_prata.py` | um evento | ordenada por `user_id` e `seq_usuario`; horários em Brasília (`data_hora_brt`, `mes`); fim de assinatura = `assinatura_expirada`, fim de trial = `trial_expirado`; linhas com `flag_apos_fim = 1` não mudam o estado (contam como causa do fim, não como evento novo) e conte cancelamento por `renovacao_automatica_desligada` (não some `cancelamento_web`) |
| `dados/2.prata/pagamentos.csv` | `notebooks/pagamentos_prata.py` | uma cobrança | inclui recusados; para faturamento filtre `status != 'recusado'` e some `valor` (bruto) ou `valor_liquido` (após taxas) |
| `dados/2.prata/uso_mensal.csv` | `notebooks/uso_mensal_prata.py` | um usuário e mês | jan/25–set/26; valores da bronze intactos. Para comparar 2025 com 2026 filtre `flag_sem_treino = 0`; não compare `sessoes_app` antes e depois de mar/26 (`flag_sessoes_nova_contagem`); em 2026 subconta treinos de relógio |
| `dados/2.prata/atividades.parquet` | `notebooks/atividades_prata.py` | um treino | `inicio_brt` em Brasília, `tipo` em português (6 tipos). Para minutos e km, ignore nulos em `duracao_min`/`distancia_km`; `flag_inicio_repetido` marca possíveis registros em dobro. Set/2026: 150.946 treinos; 36.551 usuários no arquivo |
| `dados/2.prata/amizades.csv` | `notebooks/amizades_prata.py` | uma relação de seguir (mão única) | `seguidor_id` segue `seguido_id` desde `desde` (data, sem hora); `reciproco` marca conexão mútua; para variável de modelo filtre `flag_apos_corte = 0` |
| `dados/2.prata/campanha_ago26.csv` | `notebooks/campanha_ago26_prata.py` | um assinante sorteado em 10/08/2026 | `tratado` (1/0) é o tratamento do uplift; booleanos em 1/0; controle tem envio, canal, título e oferta vazios; abertura e clique medem atenção, não retenção |
| `dados/2.prata/onboarding.csv` | `notebooks/onboarding_prata.py` | uma conta (`user_id` único) | texto livre com original em `*_bronze`; para extração use `objetivo_texto` não nulo e `flag_objetivo_sem_conteudo = 0`; `dias_por_semana` já é inteiro 1–7 |
| `dados/2.prata/feed_posts.csv` | `notebooks/feed_posts_prata.py` | um post | texto original em `texto_bronze`; post removido tem `texto` nulo e `flag_post_removido = 1`; para modelo filtre `flag_apos_corte = 0` |
| `dados/2.prata/pesquisa_saida.csv` | `notebooks/pesquisa_saida_prata.py` | uma resposta | 643 respostas de 641 contas, só de quem cancelou pelo site, 01/06–30/09/2026; `comentario` é texto bruto para a extração com IA; `motivo_principal` diverge do comentário em 220 de 452 casos com tema (Q7); `flag_resposta_repetida` marca 2 contas com duas respostas |
| `dados/2.prata/tickets_suporte.csv` | `notebooks/tickets_suporte_prata.py` | um chamado | 4.422 chamados de 3.989 contas, 01/07/2025–30/09/2026, `aberto_em` em Brasília; `texto_cliente` é texto bruto para a extração com IA; `categoria_atendente` diverge do texto em 33,6% (S9); para variável de modelo trate `flag_resolvido_pos_corte = 1` como aberto; `flag_aberto_antigo` marca chamados abandonados |

Número de referência para conferir a prata: faturamento de set/2026 = R$ 489.873,50 bruto,
R$ 434.056,93 líquido de taxas.

## Regras de trabalho

- Mostre a regra junto com o número: a mesma conta dá resultados diferentes conforme o
  arquivo e a regra (o próprio enunciado avisa). Diga qual arquivo, filtro e corte usou.
- Não use informação posterior ao corte (30/09/2026) em variáveis de modelo.
- Textos de entrega descrevem o produto, não o processo ("corrigimos", "primeiro tentamos…").
- Não commite credenciais nem chaves de API (extração com IA). Use `.env`, fora do git.
- Não faça push sem a pessoa confirmar: o repo é do grupo inteiro.
