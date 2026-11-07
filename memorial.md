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

Números de `artefatos/02_quem_saiu.html` (decisões K1–K7). Base de 14.059 assinantes, dos
quais 2.343 (16,7%) saíram em jul–set/2026.

- **O plano esconde o calendário.** Dos 8.212 anuais, só 1.931 venciam na janela, e 46,3% deles
  não renovaram; os outros 6.281 tiveram 3 saídas. Comparar o anual inteiro com o mensal mede
  o calendário. Daí os dois estratos comparáveis: mensal e anual que vence (K6). É o efeito de
  mistura da etapa 01, agora num cruzamento.
- **Dois mundos de saída.** No mensal, o que mais separa é o tempo de casa (AUC 0,60): 31,2% de
  saída até 3 meses, 10,0% acima de 24 meses. No anual que vence, é o engajamento (dias com
  treino, AUC 0,78): 65,7% não renovaram sem treino no trimestre, 43,0% com treino.
- **A decisão já estava tomada para muitos.** Pelos eventos, 734 dos 1.931 anuais que venciam
  já estavam com a renovação desligada em 30/06, e 94,1% deles saíram (mediana de 2 dias com
  treino em abr–jun, contra 22 de quem seguia com a renovação ligada). Só entre os ligados, a
  AUC do engajamento cai de 0,78 para 0,67: o sinal sobrevive, mas parte dele era causalidade
  reversa (K7). Outros 1.313 anuais que não venciam já tinham desligado: decididos a sair,
  ainda pagando.
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
| D02.8 | GPS falho como driver | aceitar a diferença de +4,3 p.p. · controlar por tipo de treino (corrida ao ar livre) | controlar antes de chamar de driver: quem teve GPS falho é quem corria ao ar livre no android. Na etapa 04, entre os mensais ao ar livre, quem teve GPS falho saiu **menos** em ago–set: o sinal não se sustenta fora de jul–set | **aberto** (enfraquecido na etapa 04) |
| D02.10 | Renovação já desligada em 30/06 | ignorar · usar como variável · separar a análise entre ligados e desligados | as duas coisas: é informação disponível na data (sem vazamento) e vira variável; e a separação é medida também só entre os ligados, que ainda decidem. Para o modelo da semana 10, decidir se o alvo da intervenção é quem ainda está ligado | **proposto** (aplicado em K7) |
| D02.9 | Eixos para a segmentação (aula 3) | todas as variáveis · só as que separam e não são redundantes | engajamento (um eixo), tempo de casa, plano × vencimento, experiência técnica (android × GPS falho), método de pagamento. Na etapa 04, as quatro da aula (engajamento em duas, tempo de casa, ar livre); GPS falho e as categóricas ficam no perfil | **proposto** (aplicado em L3, L6) |

### Referências da etapa

Aula 2 (22/10/2026), "Limpeza e Análise Exploratória de Dados", trilha de Tecnologia.

---

## Etapa 03 · Por que saem (`artefatos/03_por_que_saem.html`)

**Pergunta.** De que tipo são as saídas, qual tipo explica a subida de 2026, com quanta
antecedência o assinante avisa e o que ele diz quando sai?

**Para onde vai.** Hipóteses de driver por segmento no Customer Segmentation Report e, na
semana 10, a escolha de quem recebe que tipo de ação (oferta de retenção × correção de
cobrança) e quando.

### Conceitos

- **Decomposição aditiva da taxa.** Com o mesmo denominador (ativos no dia 1, regra G1), o
  churn total é a soma das taxas por tipo de saída. A conferência é exata: a soma dos tipos tem
  de dar as perdas do `01_churn_mensal` em todos os meses. Uma decomposição que não fecha
  esconde linhas perdidas ou contadas duas vezes.
- **Churn voluntário × involuntário.** Voluntário é decisão do cliente (desligou a renovação);
  involuntário é falha de cobrança (cartão recusado até o fim da carência). As alavancas são
  diferentes: oferta, conteúdo e contato para o primeiro; retentativa de cobrança, aviso de
  cartão vencido e troca de método para o segundo. Misturar os dois numa taxa só leva à ação
  errada.
- **Janela de intervenção.** O tempo entre o sinal de decisão (desligar a renovação) e o fim
  da assinatura. É uma distribuição de duração: lida por mediana e quartis, não pela média,
  porque é limitada em 0 e tem cauda longa no anual.
- **Motivo declarado × motivo revelado.** A pesquisa de saída registra o que a pessoa marca
  numa lista fechada (declarado); o comentário livre e o comportamento (treinos, chamados)
  revelam outra coisa. A primeira opção de uma lista tende a ser marcada por quem não quer
  pensar (efeito de primazia), o que explica `preco` sem menção a dinheiro.
- **Viés de não resposta e de cobertura.** Só responde quem cancela pelo site, e só quem quer.
  A pesquisa indica **quais** temas existem, não **quanto** cada um pesa na base: a loja, 67%
  das saídas de jun–set, não aparece.
- **Taxa de período × taxa mensal.** Dividir saídas de nove meses pelos que estiveram ativos em
  algum dia do período dá uma taxa que serve para comparar grupos entre si, não para somar ao
  churn mensal nem para o ROI.

### Método

1. Saídas pagas pelo `motivo_fim` da prata, em três tipos (W1–W2); churn por tipo com a regra
   G1 e conferência da soma (W3).
2. Média 2025 × jan–set/26 por tipo e plano; falha de pagamento por plano × método.
3. Antecedência do aviso nas voluntárias de 2026 (W4): histograma por plano, quartis por plano
   e canal.
4. Pesquisa de saída: tema do comentário pela regra de palavra-chave da prata (W5), cruzado com
   o motivo marcado e com o plano.

### O que a etapa mostrou

- **A subida é voluntária.** Voluntária 5,12% → 6,09% ao mês (+0,97 p.p. de +0,99 p.p. do
  total); involuntária 0,43% → 0,46%; devolução estável em 0,07%. No mensal, voluntária 8,04%
  → 9,83%.
- **A falha de pagamento é pequena, estável e concentrada.** Mensal no cartão: 10,7 saídas
  involuntárias por 100 assinaturas em jan–set/26, contra 2,1 a 3,6 nos outros métodos. É um
  segmento operacional, não de produto.
- **Quem sai avisa, e o tempo de aviso depende do plano.** Mediana de 14 dias no mensal (loja e
  site iguais) e 157 dias no anual (loja 151, site 175). O anual que desligou segue pagando e
  usando por meses: é a maior janela de intervenção da base.
- **Um pico que pede explicação.** 287 anuais (12,8%) desligaram exatamente 42 dias antes do
  fim, na loja e no site, com os dias vizinhos abaixo de 10. Seis semanas é um prazo típico de
  lembrete de renovação, mas nada no enunciado ou no dicionário descreve um. Fica como
  pergunta (D03.4).
- **"Objetivo cumprido" domina o texto.** 55,3% dos comentários com tema ("era só até a prova")
  falam de objetivo atingido, motivo que não existe na lista fechada. A mistura de temas é
  quase igual no anual e no mensal.
- **O motivo marcado engana.** Dos 187 que marcaram `preco` e comentaram, 2 falam de cobrança.

Leitura metodológica: a decomposição por tipo mudou a pergunta da segmentação. Como quase toda
a subida é voluntária, os segmentos de ação imediata são de comportamento (engajamento, tempo
de casa, experiência técnica); a cobrança entra como um segmento operacional à parte.

### Pontos em debate

| # | Ponto | Opções | Proposta | Status |
|---|---|---|---|---|
| D03.1 | Fonte do tipo de saída | `motivo_fim` da prata · reconstruir pelos eventos anteriores ao fim | `motivo_fim`: a soma fecha com a G1 em todos os meses e os eventos já foram conferidos na prata (E5, E8) | **proposto** (aplicado em W2) |
| D03.2 | Qual desligamento conta na antecedência | primeiro · último | último: é o que valeu; quem religou e desligou de novo teve a decisão revertida uma vez | **proposto** (aplicado em W4) |
| D03.3 | Tema da pesquisa | palavra-chave (atual) · extração com IA | palavra-chave na EDA; a extração com IA, prevista no case, substitui quando existir e as duas são comparadas | **proposto** (aplicado em W5) |
| D03.4 | Pico de 42 dias no anual | ignorar · tratar como lembrete de renovação · perguntar à empresa | perguntar antes de usar: se for um lembrete, ele é um momento de contato já existente, útil para o plano da semana 10 | **aberto** |
| D03.5 | Denominador da falha de pagamento | ativos em algum dia do período · ativos no dia 1 de cada mês | período para comparar métodos na EDA; mensal (regra G1) quando entrar no ROI | **proposto** |

### Referências da etapa

- BLATTBERG, R. C.; KIM, B.-D.; NESLIN, S. A. **Database marketing**: analyzing and managing
  customers. New York: Springer, 2008. (Cap. 24: churn voluntário e involuntário.)
- GROVES, R. M. Nonresponse rates and nonresponse bias in household surveys. **Public Opinion
  Quarterly**, v. 70, n. 5, 2006.

---

## Etapa 04 · Segmentos de assinantes (`artefatos/04_segmentos.html`)

**Pergunta** (aula 3). Entre os pagantes ativos em 31/07/2026, em quantos grupos os assinantes se
dividem, o que distingue cada grupo e o que a Vitaliza faria diferente com cada um?

**Para onde vai.** Os cartões de persona e a priorização do Customer Segmentation Report (semana
5); na semana 10, o segmento entra no briefing da IA generativa e na leitura do modelo de risco.

### Conceitos

- **Aprendizado não supervisionado.** A clusterização agrupa assinantes parecidos **sem** olhar
  quem saiu (JAMES et al., 2023). A saída só entra depois, para descrever os grupos. Se entrasse
  antes, os grupos seriam um modelo de churn disfarçado.
- **K-means.** Sorteia k centros, atribui cada ponto ao centro mais próximo, move cada centro para a
  média do seu grupo e repete até nenhum ponto trocar (LLOYD, 1982). Garante que a inércia não sobe
  entre voltas, não que chegou ao melhor resultado: daí o início k-means++ (ARTHUR; VASSILVITSKII,
  2007), `n_init = 10` (dez inícios, fica o de menor inércia) e a semente fixa.
- **Padronização.** Cada variável em desvios-padrão (z). Sem isso, a distância é dominada pela
  variável de maior escala (tempo de casa em dias, até milhares) e as outras não contam.
- **Variável 0/1 na distância.** Padronizada, uma categoria vira um salto enorme e o grupo passa a
  ser a própria categoria. Plano, canal e método entram no **perfil**, não no agrupamento.
- **Quatro lentes para escolher k.** Inércia (soma das distâncias ao centro, ao quadrado; cai
  sempre, procura-se a dobra); silhueta, s = (b − a) ÷ max(a, b), com faixas de Kaufman e
  Rousseeuw (até 0,25 sem estrutura, até 0,50 fraca, até 0,70 razoável); estabilidade pelo índice
  de Rand ajustado (HUBERT; ARABIE, 1985) entre o agrupamento original e reamostras; e leitura de
  negócio. Nenhuma decide sozinha.
- **Cluster vira segmento quando tem consequência**: distinto (cabe numa frase), estável (se repete
  em outra amostra), grande o bastante (vale uma ação própria) e acionável (a empresa faria algo
  diferente com ele).
- **Classificar a base nova com os mesmos centros.** O padronizador e os centros aprendidos em 31/07
  classificam a base de 30/09. O segmento de hoje é comparável ao de 31/07, e a saída observada em
  ago–set serve de referência para cada grupo.

### Método

1. Base de 31/07 sem quem já desligou a renovação (L1); saída em 60 dias pelos eventos (L2).
2. Quatro variáveis da aula (L3), padronizadas; k-means de k = 2 a 8 (L4).
3. Inércia e silhueta por k; estabilidade em 10 reamostras e com outra semente (L5).
4. Teste das variáveis candidatas do grupo, uma a uma (L6).
5. Perfil em medianas, saída com intervalo de Wilson, cruzamento com plano, tempo de casa e método;
   classificação da base de 30/09 (L8); personas com hipótese de driver e prioridade.

### O que a etapa mostrou

- **A estrutura da aula se reproduz.** k = 4 dá Parados (560), Ativos ao ar livre (5.837), Ativos
  em ambiente fechado (4.219) e Veteranos (1.072), com silhueta 0,43 e Rand 0,999, perto da
  referência da aula (472, 5.927, 4.215 e 1.074; silhueta 0,44).
- **A saída ordena os grupos.** Parados 29,8%, ao ar livre 14,0%, ambiente fechado 10,9%, veteranos
  5,4% (média 12,9%). Os parados são todos anuais: nenhum mensal com a renovação ligada estava sem
  treinar.
- **Taxa × volume.** O grupo com a maior taxa é pequeno (514 em 30/09); o com mais saídas é o ao ar
  livre (6.327 em 30/09, acima da média). A priorização olha as duas coisas.
- **O que a etapa 02 achou aparece dentro dos grupos.** O mensal com até 90 dias de casa sai mais
  em todo grupo (20,8% ao ar livre contra 13,2% depois); o mensal no cartão sai mais (17,2%).
- **As variáveis do grupo não mudam os grupos.** GPS falho, km por treino e conexões recíprocas
  deixam a partição igual (Rand ≥ 0,986) e baixam a silhueta. E o GPS falho, que separava na etapa
  02, aqui vai no sentido contrário (D02.8).

Leitura metodológica: a silhueta de 0,43 diz que os grupos são regiões de um contínuo, não ilhas.
Isso não invalida a segmentação, que é estável e acionável, mas pede cuidado com quem está na
fronteira: o segmento orienta a mensagem; quem recebe a ação é decidido pelo risco individual
(modelo da semana 10).

### Pontos em debate

| # | Ponto | Opções | Proposta | Status |
|---|---|---|---|---|
| D04.1 | Quem entra no agrupamento | todos os ativos · só quem não desligou a renovação | só quem não desligou (como a aula); os desligados viram lista operacional de reversão | **proposto** (aplicado em L1) |
| D04.2 | Saída que descreve os grupos | perda (G1, expirou) · decisão (desligou, cancelou ou expirou) | decisão, porque é o momento de agir; o alvo do modelo da semana 10 ainda está em aberto | **proposto** (aplicado em L2) |
| D04.3 | k | 2 (maior silhueta) · 4 · 5 (dobra da inércia) | 4: estável e acionável; k = 2 só separa quem parou | **proposto** (aplicado em L5) |
| D04.4 | Variáveis do grupo | somar até duas (aula) · ficar com as quatro | ficar com as quatro: as candidatas não mudam os grupos e pioram a silhueta | **proposto** (aplicado em L6) |
| D04.5 | Plano no segmento | eixo do k-means · corte depois do grupo · segmento por plano | corte depois do grupo: as ofertas do CRM são por plano, mas como 0/1 o plano dominaria a distância | **proposto** |

### Referências da etapa

Aula 3 (29/10/2026), "Clusterização com k-means", trilha de Tecnologia.

- ARTHUR, D.; VASSILVITSKII, S. k-means++: the advantages of careful seeding. In: ACM-SIAM SYMPOSIUM
  ON DISCRETE ALGORITHMS, 18., 2007. **Proceedings** [...]. Philadelphia: SIAM, 2007. p. 1027-1035.
- HUBERT, L.; ARABIE, P. Comparing partitions. **Journal of Classification**, v. 2, n. 1, p. 193-218,
  1985.
- JAMES, G.; WITTEN, D.; HASTIE, T.; TIBSHIRANI, R.; TAYLOR, J. **An introduction to statistical
  learning**: with applications in Python. Cham: Springer, 2023. Cap. 12.
- KAUFMAN, L.; ROUSSEEUW, P. J. **Finding groups in data**: an introduction to cluster analysis.
  New York: Wiley, 1990.
- LLOYD, S. P. Least squares quantization in PCM. **IEEE Transactions on Information Theory**, v. 28,
  n. 2, p. 129-137, 1982.
- ROUSSEEUW, P. J. Silhouettes: a graphical aid to the interpretation and validation of cluster
  analysis. **Journal of Computational and Applied Mathematics**, v. 20, p. 53-65, 1987.

---

## Etapa 05 · A história da EDA (`artefatos/00_historia_da_eda.html`)

**Pergunta.** Como contar a EDA para quem não vai ler as quatro páginas de detalhe: o professor, o
mentor e a trilha de Negócios, que escreve o Customer Segmentation Report?

**Formato.** O guia pede que a EDA "conte a história num mini deck". O grupo trocou o deck por uma
página HTML (07/11/2026): o mesmo roteiro de deck, um achado por seção, sem copiar número à mão.

### Conceitos

- **Título que afirma** (assertion-evidence; ALLEY, 2013). Cada seção tem no título o achado em
  frase ("A alta é voluntária"), não o tema ("Tipos de saída"); o gráfico é a evidência e duas ou
  três frases dizem como ler.
- **Um gráfico por ideia** (KNAFLIC, 2015). Cada seção usa a forma que responde à sua pergunta:
  linha para o tempo, barras agrupadas para comparar recortes, caixa para duração, barras
  horizontais para ranquear grupos.
- **Uma fonte de número.** A página não tem número digitado: lê as tabelas de ouro e refaz cada
  conta com a regra da etapa. Se o ouro mudar, a história muda junto; o notebook para se um número
  âncora (churn médio do enunciado, 14.753 ativos, soma dos tipos de saída) não bater.

### O roteiro

1. O churn subiu (5,6% → 6,6% ao mês). 2. Veio do mensal e do Google Play. 3. A alta é de saída
voluntária. 4. Quem sai avisa: duas semanas no mensal, cinco meses no anual. 5. No mensal pesa o
tempo de casa; no anual que vence, o treino. 6. Para muitos, a decisão já está tomada
(causalidade reversa). 7. Quatro grupos estáveis. 8. Personas e prioridade. 9. O que a EDA não
responde.

### Pontos em debate

| # | Ponto | Opções | Proposta | Status |
|---|---|---|---|---|
| D05.1 | Formato da história | mini deck (guia) · página HTML | página HTML gerada do ouro, com links para as páginas 01–04 | **decidido** (07/11/2026; não muda número) |
| D05.2 | O que vai para o Segmentation Report | gráficos da página 00 · gráficos das páginas de detalhe | a página 00 dá a sequência; os cartões e tabelas da página 04 dão as personas | **proposto** |

### Referências da etapa

- ALLEY, M. **The craft of scientific presentations**. 2. ed. New York: Springer, 2013.
- KNAFLIC, C. N. **Storytelling with data**: a data visualization guide for business
  professionals. Hoboken: Wiley, 2015.

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
