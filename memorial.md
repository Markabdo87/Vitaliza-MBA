# Memorial descritivo — EDA e modelagem do case Vitaliza

Registro dos **conceitos** e das **metodologias** usados em cada etapa da análise, e o lugar
onde o grupo debate qual método usar antes de fixá-lo.

Como ele se encaixa com os outros arquivos:

| Arquivo | Responde | Exemplo |
|---|---|---|
| `memorial.md` (este) | **por que este método** e o que o conceito significa | "usamos mediana e Mann-Whitney porque os minutos de treino são assimétricos" |
| `decisoes.md` | **qual regra** foi aplicada e quanto ela muda o número | "G1: churn = perdas ÷ ativos no dia 1; abr/26 = 8,1%" |
| `notebooks/*.py` | **como** a regra roda | o código |

Quando um debate daqui fecha numa escolha que muda número, a escolha vai para o
`decisoes.md` com ID, e o item aqui passa para **decidido**, apontando o ID.

Formato de cada etapa: pergunta → conceitos → método escolhido e alternativas →
pontos em debate → referências. Status dos debates: **aberto** · **proposto** (há proposta,
falta o grupo) · **decidido** (com ID do `decisoes.md`).

---

## Etapa 00 · Fundamentos do projeto

**Pergunta.** Como organizar o trabalho para que qualquer número possa ser refeito por outra
pessoa do grupo?

### Conceitos

- **CRISP-DM** (Chapman et al., 2000). Ciclo de seis fases que vão e voltam: entendimento do
  negócio → entendimento dos dados → preparação → modelagem → avaliação → implantação. A EDA
  mora nas fases 2 e 3 e volta à fase 1 sempre que um achado muda a pergunta.
- **Análise exploratória × confirmatória** (Tukey, 1977). A exploratória é o detetive: procura
  padrões e levanta suspeitos. A confirmatória é o juiz: testa uma hipótese fixada antes. Na
  semana 5 o grupo faz principalmente exploração; os testes estatísticos servem para
  **dimensionar** diferenças, não para provar causa.
- **Cinco dimensões de qualidade** (Wang; Strong, 1996): completude, validade, consistência,
  unicidade e temporalidade. Cada problema de dado é classificado numa delas e recebe uma das
  saídas: corrigir, remover, marcar (`flag_*`) ou manter (Redman, 2016).
- **Camadas bronze → prata → ouro.** Bronze imutável; prata limpa no mesmo grão; ouro cruzado e
  agregado. É a forma de separar "o dado como veio" de "o dado como decidimos lê-lo".
- **Dado arrumado** (Wickham, 2014). Cada tabela tem um grão (uma linha por conta, assinatura,
  evento, treino, mês). Juntar tabelas de grãos diferentes sem resumir antes **multiplica
  linhas**; por isso toda junção conta as linhas antes e depois.
- **Vazamento** (Kaufman et al., 2012). Usar informação que não existia na data de referência.
  O retrato de 01/10/2026 (`assinaturas.csv`) não descreve 31/07: a situação numa data passada
  se reconstrói pelos eventos.

### Pontos em debate

| # | Ponto | Status |
|---|---|---|
| D00.1 | Fuso de referência: horário de Brasília | **decidido** (Premissas gerais) |
| D00.2 | Data de corte 30/09/2026 para toda variável de modelo | **decidido** (dicionário) |

---

## Etapa 01 · Churn mensal (`artefatos/01_churn_mensal.html`)

**Pergunta.** Quantos assinantes pagantes a Vitaliza perde por mês, e como isso muda por plano
e canal?

### Conceitos

- **Taxa e denominador.** Frequência (n) → proporção (n ÷ total) → taxa com denominador
  definido no tempo. Churn mensal = perdas no mês ÷ **ativos no início do mês**. Trocar o
  denominador (ativos no fim, média do mês) dá outro número; o enunciado usa o início.
- **Viés de sobrevivência.** O histórico começa em 01/07/2024: assinaturas encerradas antes não
  existem no arquivo. Ago–dez/2024 só contém quem estava vivo em jul/24, e o churn sai
  artificialmente baixo.
- **Efeito de mistura (Simpson).** Se a fatia de planos muda, o churn total muda mesmo sem
  nenhum plano piorar. Por isso a série é aberta por plano antes de qualquer leitura.
- **Comparar coisas comparáveis.** O anual só pode sair no aniversário; a taxa mensal do
  anual sobre toda a base anual dilui a não renovação.

### Método

Contagem por mês sobre `assinaturas.csv` da prata (G1–G4), com `assert` dos números do
enunciado (8.540 ativos em jan/25; 8,1% em abr/26; médias de 5,6% e 6,6%).

### Pontos em debate

| # | Ponto | Status |
|---|---|---|
| D01.1 | Separar perda voluntária, involuntária e devolução | **aberto** (Em aberto do `decisoes.md`) |
| D01.2 | Medir a taxa de não renovação do anual em vez da taxa mensal | **aberto** |

---

## Etapa 02 · Quem saiu se comportava diferente? (`artefatos/02_quem_saiu.html`)

**Pergunta** (aula 2). Entre quem pagava em 30/06/2026, quem saiu até 30/09 se comportava
diferente de quem ficou? Quais características mais separam os dois grupos, e por que cada
uma pode ser só correlação?

**Para onde vai.** EDA da semana 5 (padrões e correlações com churn) e base empírica dos 3–4
segmentos do Customer Segmentation Report.

### Conceitos

- **Coorte com data de referência.** Fixa-se uma data (30/06/2026), mede-se tudo **até** ela e
  observa-se o desfecho numa janela **depois** dela (01/07–30/09). É o mesmo desenho que o
  modelo da semana 10 vai usar (corte 30/09, janela de 60 dias), então a EDA já treina a
  disciplina contra vazamento.
- **Uma linha por assinante.** Cada log (treinos, chamados, amizades, posts) é resumido por
  `user_id` antes de juntar.
- **Centro e dispersão.** Média, mediana, moda; desvio padrão, coeficiente de variação
  (CV = s ÷ x̄), quartis e IQR. Em distribuições assimétricas à direita (minutos de treino:
  média 83, mediana 0 em set/26) a média descreve uma conta que quase não existe; a mediana e
  os quartis descrevem a conta típica.
- **Extremos: a regra marca, o grupo decide.** Q3 + 1,5 × IQR e |z| > 3 apontam candidatos; nada
  é apagado por estar longe.
- **Correlação não é causa.** Quatro armadilhas: terceira variável, seleção, causalidade reversa
  e coincidência. Cruzamento aponta suspeito; só o experimento sorteado (campanha de ago/26)
  chega perto de causa.

### Ferramentas estatísticas

| Para quê | Ferramenta | Por que esta |
|---|---|---|
| Descrever cada variável | n, nulos, média, mediana, Q1/Q3, IQR, desvio padrão, CV; histograma e boxplot | as variáveis de uso são assimétricas e cheias de zeros: centro + dispersão + forma, nunca só a média |
| Taxa de saída por categoria | proporção com **intervalo de confiança de Wilson (95%)** | grupos pequenos (ex.: um método de pagamento raro) dão taxas instáveis; o intervalo mostra o quanto confiar |
| Numérica contínua × saída | taxa de saída por **quintil** da variável | mostra a forma da relação (linear, limiar, em U) sem supor reta |
| Comparar dois grupos (numérica) | diferença de medianas + **Mann-Whitney U** | não supõe normalidade, ao contrário do teste t |
| Comparar grupos (categórica) | **qui-quadrado** + **V de Cramér** | o V dá o tamanho do efeito numa escala 0–1 |
| Ranquear o que mais separa | **AUC univariada** (0,5 = não separa; 1 = separa tudo) | escala única para numéricas e categóricas; é o Mann-Whitney normalizado e a mesma métrica do modelo da semana 10 |
| Redundância entre variáveis | **correlação de Spearman** entre as candidatas | treinos, minutos e dias ativos andam juntos; evita contar o mesmo sinal três vezes na segmentação |
| Terceira variável | **estratificação**: repetir a comparação dentro de cada plano (e canal) | é o teste da aula 2: a diferença se mantém, diminui, some ou inverte? |

Com cerca de 14 mil assinantes, quase qualquer diferença dá p < 0,05. Por isso a leitura
principal é o **tamanho do efeito** (diferença de taxas em p.p., AUC, V de Cramér), e o valor-p
entra só como apoio.

### Método proposto

1. Base: assinaturas pagas (`flag_cortesia = 0`) ativas em 30/06/2026 (`inicio` ≤ 30/06 e
   `data_fim` vazia ou ≥ 01/07). Saiu = `data_fim` entre 01/07 e 30/09/2026. Conferência: a
   taxa de saída fica perto do churn acumulado de jul–set no `01_churn_mensal`.
2. Variáveis medidas até 30/06/2026: plano, canal, método, tempo de casa, cupom de
   influenciador; treinos, minutos e dias com treino em abr–jun/26 e % com GPS falho
   (`atividades`); chamados (qualquer e de GPS); seguidores recíprocos; posts; dias por semana
   do onboarding; sistema, idade e sexo.
3. Tabela lado a lado, ranking por AUC, distribuição das duas que mais separam, estratificação
   por plano, três frases.

### O que a etapa mostrou

Números de `artefatos/02_quem_saiu.html` (decisões K1–K6). Base de 14.059 assinantes, dos
quais 2.343 (16,7%) saíram em jul–set/2026.

- **O plano esconde o calendário.** Dos 8.212 anuais, só 1.931 venciam na janela, e 46,3% deles
  não renovaram; os outros 6.281 tiveram 3 saídas. Comparar o anual inteiro com o mensal mede
  o calendário. Daí os dois estratos comparáveis: mensal e anual que vence (K6). É o efeito de
  mistura da etapa 01, agora num cruzamento.
- **Dois mundos de saída.** No mensal, o que mais separa é o tempo de casa (AUC 0,60): 31,2% de
  saída até 3 meses, 10,0% acima de 24 meses. No anual que vence, é o engajamento (dias com
  treino, AUC 0,78): 65,7% não renovaram sem treino no trimestre, 43,0% com treino.
- **Um sinal, três nomes.** Treinos, minutos e dias com treino têm ρ de Spearman ≥ 0,96: na
  segmentação entram como um eixo só.
- **Suspeito técnico.** No mensal android, quem teve treino com GPS falho saiu 4,3 p.p. a mais
  (29,3% × 25,0%). O chamado de GPS em si não separa (AUC 0,50).
- **O que quase não separa** (AUC < 0,52 nos dois estratos): idade, sexo, nível e dias por
  semana declarados no onboarding, chamados, recusa de cobrança.

Leitura metodológica: a AUC univariada funcionou como régua comum para numéricas e
categóricas, e a estratificação mudou a resposta (o plano, primeiro da lista na base inteira,
some como explicação quando se compara dentro de estratos comparáveis). Isso confirma a
escolha de estratificar antes de ranquear.

### Pontos em debate

| # | Ponto | Opções | Proposta | Status |
|---|---|---|---|---|
| D02.1 | Data de referência e janela | 30/06 + jul–set (aula 2) · 31/07 + 60 dias (igual ao modelo) | 30/06 + jul–set: janela de 3 meses fechada antes do corte, comparável ao enunciado | **proposto** (aplicado em K1) |
| D02.2 | Fonte de engajamento em 2026 | `uso_mensal` (subconta relógio, M9) · `atividades` (treino a treino) | `atividades`, com `uso_mensal` só para conferência | **proposto** (aplicado em K3) |
| D02.3 | Janela das variáveis de uso | último mês (jun) · último trimestre (abr–jun) · tendência (jun − abr) | trimestre abr–jun, mais a tendência como variável extra. A tendência separou pouco (AUC 0,51 no mensal, 0,55 no anual que vence) | **proposto** (aplicado em K2) |
| D02.4 | Tempo de casa e viés de sobrevivência | usar como está · marcar quem começou antes de jul/24 | marcar (`inicio_antes_historico`) e ler a queda da saída com o tempo como parte seleção | **proposto** |
| D02.5 | Anual × mensal na mesma comparação | juntos · por plano · por plano e vencimento | por plano **e** vencimento: só o anual que vence em jul–set entra na comparação | **proposto** (aplicado em K6) |
| D02.6 | Valor-p com amostra grande | reportar e decidir por ele · usar o tamanho do efeito | tamanho do efeito como critério, valor-p como apoio | **proposto** |
| D02.7 | AUC de categórica | taxa na própria base (atual) · taxa com validação cruzada | a atual serve para a EDA; para o modelo (semana 10), codificar com validação cruzada para não superestimar categorias pequenas | **aberto** |
| D02.8 | GPS falho como driver | aceitar a diferença de +4,3 p.p. · controlar por tipo de treino (corrida ao ar livre) | controlar antes de chamar de driver: quem teve GPS falho é quem corria ao ar livre no android | **aberto** |
| D02.9 | Eixos para a segmentação (aula 3) | todas as variáveis · só as que separam e não são redundantes | engajamento (um eixo), tempo de casa, plano × vencimento, experiência técnica (android × GPS falho), método de pagamento | **aberto** |

### Referências da etapa

Aula 2 (22/10/2026), "Limpeza e Análise Exploratória de Dados", trilha de Tecnologia.

---

## Referências gerais

- CHAPMAN, P. et al. **CRISP-DM 1.0**: step-by-step data mining guide. SPSS, 2000.
- KAUFMAN, S.; ROSSET, S.; PERLICH, C.; STITELMAN, O. Leakage in data mining: formulation,
  detection, and avoidance. **ACM TKDD**, v. 6, n. 4, 2012.
- REDMAN, T. C. Bad data costs the U.S. $3 trillion per year. **Harvard Business Review**, 2016.
- TUKEY, J. W. **Exploratory data analysis**. Reading: Addison-Wesley, 1977.
- WANG, R. Y.; STRONG, D. M. Beyond accuracy: what data quality means to data consumers.
  **Journal of Management Information Systems**, v. 12, n. 4, 1996.
- WICKHAM, H. Tidy data. **Journal of Statistical Software**, v. 59, n. 10, 2014.
