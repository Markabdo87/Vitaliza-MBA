"""Gera estudos-analises/memorial_tecnico.html: o memorial descritivo técnico do case, com a
explicação de cada etapa ao lado do código que a executa.

Como funciona:
  - Cada bloco do memorial tem um texto e um trecho de código. O trecho NÃO é copiado à mão:
    é lido do notebook de origem entre duas âncoras (o texto exato da primeira e da última
    linha). O memorial mostra o arquivo e as linhas, e acompanha o código quando ele muda.
  - Se uma âncora sumir (alguém reescreveu o trecho), o gerador para e diz qual bloco
    ajustar. Assim o memorial nunca mostra código que não existe mais.
  - Os números citados no texto saem do ouro (dados/3.ouro), não ficam fixos aqui. Rode
    depois do ouro, da conciliação e das conferências.

Uso: .venv/bin/python notebooks/memorial_tecnico.py  (a partir da raiz do repo)
"""
import html
import re
import sys
from datetime import datetime

import pandas as pd

from _ouro import OURO, RAIZ

SAIDA = RAIZ / "estudos-analises" / "memorial_tecnico.html"
NB = RAIZ / "notebooks"


# --- números do ouro ------------------------------------------------------------------------
def br(x, d=1):
    return f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


for arq in ["churn_mensal.csv", "saidas.csv", "segmentos.csv", "segmentos_kmeans.csv",
            "conciliacao_segmentos.csv"]:
    if not (OURO / arq).exists():
        sys.exit(f"falta dados/3.ouro/{arq}: rode o ouro e notebooks/conciliacao_segmentos.py antes")
cm = pd.read_csv(OURO / "churn_mensal.csv")
tot = cm[cm.recorte == "total"]
sd = pd.read_csv(OURO / "saidas.csv")
L = pd.read_csv(OURO / "segmentos.csv")
N = pd.read_csv(OURO / "segmentos_kmeans.csv")
la = L[L.data_ref == "2026-07-31"]
lag = la[la.segmento != "Já desligou"]
na = N[N.data_ref == "2026-07-31"]
V = {
    "churn25": br(tot[tot.mes.str.startswith("2025")].churn_pct.mean(), 2),
    "churn26": br(tot[tot.mes.str.startswith("2026")].churn_pct.mean(), 2),
    "saidas": br(len(sd), 0),
    "base31": br(len(la), 0), "lig31": br(len(lag), 0),
    "jd31": br((la.segmento == "Já desligou").sum(), 0),
    "base30": br((L.data_ref == "2026-09-30").sum(), 0),
    "saidaL": br(100 * lag.saiu_60d.mean()), "saidaN": br(100 * na.saiu_60d.mean()),
}


# --- trechos de código ----------------------------------------------------------------------
def trecho(arquivo, inicio, fim, extra=0):
    """Linhas de notebooks/<arquivo> da primeira que contém `inicio` até a primeira que contém
    `fim` depois dela (mais `extra` linhas). Para se alguma âncora não existir."""
    linhas = (NB / arquivo).read_text().splitlines()
    i = next((k for k, l in enumerate(linhas) if inicio in l), None)
    if i is None:
        sys.exit(f"memorial: âncora de início não encontrada em {arquivo}: {inicio!r}")
    f = next((k for k in range(i, len(linhas)) if fim in linhas[k]), None)
    if f is None:
        sys.exit(f"memorial: âncora de fim não encontrada em {arquivo}: {fim!r}")
    f += extra
    return {"arquivo": arquivo, "de": i + 1, "ate": f + 1, "codigo": "\n".join(linhas[i:f + 1])}


def md(txt):
    """Markdown mínimo: **negrito**, `código`, parágrafos e listas com '- '."""
    t = html.escape(txt.strip())
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"`(.+?)`", r"<code>\1</code>", t)
    blocos = []
    for par in re.split(r"\n\s*\n", t):
        ls = [l.strip() for l in par.splitlines()]
        if all(l.startswith("- ") for l in ls):
            blocos.append("<ul>" + "".join(f"<li>{l[2:]}</li>" for l in ls) + "</ul>")
        else:
            juntas, atual = [], []
            for l in ls:
                if l.startswith("- ") and atual:
                    juntas.append(" ".join(atual)); atual = [l]
                else:
                    atual.append(l)
            juntas.append(" ".join(atual))
            blocos.append("".join(f"<p>{j}</p>" for j in juntas))
    return "".join(blocos)


# --- conteúdo -------------------------------------------------------------------------------
# Cada seção: (id, título, introdução, [blocos]); cada bloco: (título, texto, trecho ou None).
SECOES = [
("arquitetura", "Arquitetura e regras do repositório", f"""
O case roda num pipeline de três camadas, todas recriadas por código a partir dos arquivos
originais do curso. Nenhum número das entregas é digitado à mão: cada um sai de um notebook
que qualquer pessoa do grupo roda do zero e chega ao mesmo resultado.

- **Bronze** (`dados/1.bronze`): os arquivos como vieram do curso. Imutáveis; o
  `.claude/settings.json` bloqueia edição.
- **Prata** (`dados/2.prata`): uma tabela por arquivo de origem, mesmo grão, formatos e fusos
  corrigidos, duplicatas comprovadas removidas e suspeitas marcadas com colunas `flag_*`.
- **Ouro** (`dados/3.ouro`): tabelas de análise, que cruzam a prata por `user_id` e agregam.
- **Páginas** (`artefatos/`): HTML gerado pelo ouro, com só agregados; vão para o git.
- **Relatório**: o Customer Segmentation Report é gerado por `notebooks/relatorio_segmentacao.py`
  a partir do ouro e do template de `estudos-analises/`, sai em
  `artefatos/customer_segmentation_report.html` e é conferido número por número contra o ouro
  por `notebooks/confere_relatorio.py`.

Toda decisão que muda um número tem um ID no `decisoes.md` (prefixo da seção + número): G
churn mensal, K quem saiu, W por que saem, L personas, N k-means de nove variáveis, R recusas
de cobrança, X conciliação.
""", [
("Leitura conferida da prata", """
Todo notebook de ouro novo lê a prata por `ler_prata`, que para a execução com uma mensagem
clara em três casos: o arquivo não existe (diz qual notebook rodar), falta uma coluna usada
(a prata mudou de formato) ou o notebook de prata é mais novo que o arquivo (a prata está
velha). Isso protege o ouro quando um colega muda uma regra de limpeza: ou ele roda sobre a
prata certa, ou não roda.
""", trecho("_ouro.py", "def ler_prata(arquivo, colunas, datas=()):", "    return df")),
]),

("prata", "Prata: limpeza que muda os números", """
A prata corrige o que o dicionário avisa (ninguém limpou os dados) e o que o perfil dos
arquivos revelou. As correções abaixo são as que mais afetam churn, faturamento e
segmentação; as demais estão na docstring de cada `notebooks/<arquivo>_prata.py`.
""", [
("Fusos: tudo em horário de Brasília", """
As lojas (App Store e Google Play) gravam em UTC com o sufixo `Z`; o site grava em horário de
Brasília. Sem converter, eventos perto da meia-noite caem no dia (ou mês) errado. A função
reconhece o formato pelo sufixo, subtrai 3 horas do UTC (Brasília não tem horário de verão
desde 2019) e guarda a origem do fuso. O relógio Garmin, em `atividades`, também grava em UTC,
mas sem o `Z`: lá a origem do treino decide a conversão.
""", trecho("eventos_assinatura_prata.py", "def parse_data(s):", 'return datetime.strptime(s, "%Y-%m-%d %H:%M:%S"), "brt"')),
("Pagamentos: duplicatas, retentativas, devoluções e recusas", """
O laço percorre as cobranças de cada usuário em ordem de tempo e aplica quatro regras:

- **Duplicata**: mesma chave (usuário, segundo, valor, status) conta uma vez (1.941 removidas).
- **Retentativa**: a coluna `tentativa` da bronze não registra retentativa. Uma cobrança até 16
  dias depois de uma recusa do mesmo usuário é retentativa (`tentativa_real` 2, 3…).
- **Devolução**: estorno e chargeback vêm lançados pelo preço de tabela. Passam a valer o
  negativo da última cobrança aprovada do usuário (quem pagou 34,90 devolve 34,90).
- **Recusa**: não entra dinheiro, então `valor` = 0; o valor tentado fica em `valor_bronze`.

Com isso, somar `valor` sem filtro dá o faturamento: set/2026 = R$ 489.873,50 bruto, número
de referência que `conferencias.py` confere a cada execução.
""", trecho("pagamentos_prata.py", "    vistos, linhas, duplicatas = set(), [], 0", "                valor = 0.0")),
]),

("churn", "Churn mensal (regra G1)", f"""
O enunciado dá o churn de 5,6% em 2025 e 6,6% em jan–set/2026, mas não a regra. A regra que
reproduz os números dele é: **perdas no mês ÷ assinantes pagantes ativos no dia 1 do mês**,
sem as 60 cortesias internas, e quem assina e sai no mesmo mês não entra em nenhum dos dois
lados. Com ela, a média mensal dá {V['churn25']}% em 2025 e {V['churn26']}% em jan–set/2026.
""", [
("O cálculo, mês a mês", """
Para cada mês, `ativo` marca quem começou antes do dia 1 e não tinha terminado até ele;
`perda` é quem estava ativo e terminou dentro do mês. O mesmo cálculo é agregado por recorte
(total, plano, canal, plano × canal e método) numa única passada. `ativos_inicio` e `perdas`
ficam na tabela, para qualquer pessoa refazer a divisão.
""", trecho("churn_mensal_ouro.py", "for m in MESES:", '"novas": int(r.entrou)})')),
("A conferência com o enunciado", """
O notebook para (`assert`) se qualquer número publicado no enunciado não for reproduzido:
ativos no início de jan/25, abr/26 e set/26, perdas e churn de abr/26, churn de ago e set/26 e
as duas médias anuais. Uma mudança na prata que desloque um desses números quebra o notebook
na hora, em vez de passar despercebida até o relatório.
""", trecho("churn_mensal_ouro.py", "confere = [", "    assert esperado == obtido")),
]),

("eda", "EDA: por que saem e quem já decidiu", f"""
As etapas 02 e 03 da EDA (notebooks `assinantes_30jun26_ouro.py` e `saidas_ouro.py`, da
Douglas) explicam a subida: ela é de saída voluntária, concentrada no mensal, e quem sai avisa
antes. A tabela `saidas.csv` tem as {V['saidas']} assinaturas pagas encerradas desde jul/2024.
""", [
("Tipo de saída", """
O `motivo_fim` da prata diz como a assinatura terminou. O mapa agrupa em três tipos: voluntária
(o assinante desligou a renovação), involuntária (falha de pagamento) e devolução (chargeback
ou reembolso). O `assert` garante que nenhum motivo novo passe sem classificação. Somando os
três tipos mês a mês, o resultado é igual ao churn da regra G1 (W3).
""", trecho("saidas_ouro.py", "TIPO = {", '"chargeback": "devolução", "reembolso": "devolução"}')),
("Antecedência do aviso", """
Para cada saída voluntária, a antecedência é a distância em dias entre o **último**
desligamento da renovação e o fim. Quem desliga segue assinante até o fim do período pago:
no mensal são cerca de duas semanas; no anual, meses. Aviso de loja que chega depois do fim
conta como zero dia (`clip(lower=0)`).
""", trecho("saidas_ouro.py", 'des = (ev[ev.evento == "renovacao_automatica_desligada"]', 'assert s.loc[vol, "antecedencia_dias"]')),
("Situação da renovação numa data passada (K7)", """
`assinaturas.csv` é um retrato de 01/10/2026; para saber se a renovação estava ligada numa data
passada, é preciso reconstruir pelos eventos. O último evento de assinatura antes da data
define o estado: iniciada, renovada ou religada = ligada; desligada ou cancelada no site =
desligada; carência = em carência. Avisos que chegaram depois do fim (`flag_apos_fim`) não
mudam o estado. Essa reconstrução mostrou que parte do "parou de treinar e saiu" é o
contrário: a pessoa decidiu sair e depois parou (causalidade reversa).
""", trecho("assinantes_30jun26_ouro.py", "MUDA_RENOVACAO = {", "base = junta(base, ren,")),
]),

("personas", "Personas: k-means de quatro variáveis (L1–L8)", f"""
As personas do relatório vêm de `segmentos_ouro.py`. Base: {V['base31']} pagantes ativos em
31/07/2026; desses, {V['lig31']} estavam com a renovação ligada e entram no agrupamento; os
{V['jd31']} que já tinham desligado ficam numa lista à parte ("Já desligou"), porque para eles
a decisão já foi tomada. 31/07 é a última data com 60 dias observados antes do corte
(30/09/2026).
""", [
("As quatro variáveis, medidas só até a data", """
`monta(ref)` monta a base de uma data e calcula as variáveis com informação até ela:
treinos por semana (12 semanas antes da data ÷ 12), dias sem treino, tempo de casa e % dos
treinos ao ar livre (corrida, caminhada, pedal). A situação da renovação usa a mesma
reconstrução pelos eventos da etapa anterior. A mesma função serve para 31/07 (ajuste) e
30/09 (base atual), o que garante variáveis com a mesma definição nas duas datas.
""", trecho("segmentos_ouro.py", "def monta(ref):", "    return b.drop(columns=")),
("A saída em 60 dias, fora do agrupamento", f"""
A saída é a **decisão de sair** entre 01/08 e 29/09: desligou a renovação, cancelou no site ou
expirou. Mede o momento em que a pessoa decide, não a data em que a assinatura acaba (no anual
são meses de diferença). Ela não entra no k-means: serve só para descrever os grupos depois.
Média da base com renovação ligada: {V['saidaL']}%. O `assert` confere os 14.753 pagantes de
30/09 do enunciado.
""", trecho("segmentos_ouro.py", "b = monta(REF)", "ag_atual = atual[atual.renovacao")),
("Padronização, escolha de k e estabilidade", """
As variáveis são padronizadas (`StandardScaler`): sem isso, o tempo de casa, em dias, dominaria
a distância. O k-means roda de k = 2 a 8. A silhueta e a estabilidade em reamostras vêm de uma
implementação única, `notebooks/_metricas_segmentacao.py`, que o relatório usa também: o número
publicado é exatamente o que o ouro calculou, e não uma cópia que envelhece sozinha. Ela
devolve os rótulos recalculados, e o notebook confere o Rand ajustado contra a coluna
`segmento` da tabela de ouro — se divergir, a métrica não vale para aquele agrupamento.

A escolha de k usa quatro lentes da aula 3:

- **inércia** (cotovelo): a queda fica pequena depois de k = 4;
- **silhueta**: estrutura fraca em k = 4 (os grupos são regiões de um contínuo);
- **estabilidade**: as reamostras com reposição classificam a base inteira e são comparadas com
  o agrupamento original pelo índice de Rand ajustado; o limiar está declarado em
  `LIMIAR_RAND`, e a série de Rand mínimo por k sai impressa a cada execução;
- **leitura de negócio**: quatro grupos que se descrevem numa frase e pedem ações diferentes.
""", trecho("segmentos_ouro.py", "esc = StandardScaler().fit(ag[VARS])", "estab = estabilidade_por_k(X, range(3, 7), SEMENTE, N_INIT)")),
("Nome dos grupos por regra", """
O k-means devolve números (0 a 3) que mudam de ordem entre execuções. Os nomes saem de uma
regra sobre as medianas: maior "dias sem treino" = Parados; entre os demais, maior tempo de
casa = Veteranos; dos dois restantes, maior % ao ar livre = Ativos ao ar livre e o outro =
Ativos em ambiente fechado. O `assert` para se a regra não separar os quatro. A base de 30/09
recebe o grupo do centro mais próximo com o **mesmo** padronizador e os **mesmos** centros
de 31/07 (`predict`), sem reajustar.
""", trecho("segmentos_ouro.py", "km = agrupa(X)", 'ag_atual["segmento"] =')),
("Intervalo de confiança da taxa de cada grupo", """
A taxa de saída de cada persona vem com o intervalo de Wilson de 95%, que se comporta bem em
grupos pequenos e taxas longe de 50% (caso dos Parados, com ~560 assinantes). O relatório
mostra o intervalo ao lado de cada barra.
""", trecho("segmentos_ouro.py", "def wilson(k, n, z=1.96):", "    return c - m, c + m")),
]),

("nove", "Segunda segmentação: k-means de nove variáveis (N1–N7)", f"""
`segmentos_kmeans_ouro.py` agrupa **todos** os pagantes de 31/07 em nove variáveis de
comportamento, cobrança e tempo de casa. A saída aqui é o **fim da assinatura** em 60 dias
(média {V['saidaN']}%). Ela entra no relatório como cruzamento e como origem da lista
"Cobrança falhando".
""", [
("Uma entrada por variável", """
Cada variável é uma entrada do dicionário `VARIAVEIS`: como calcular (`calc`), se entra em log
e como resumir no perfil. Todas usam só informação até a data de referência: treinos em 30
dias, tendência (30 dias contra os 60 anteriores), dias sem treinar (teto 120), sessões no app,
conexões recíprocas, posts, chamados + treinos com GPS falho, recusas de cobrança em 180 dias e
meses de assinatura. Acrescentar uma variável é acrescentar uma entrada. Plano, canal, sistema e
idade não entram no agrupamento: descrevem o perfil. A idade é a completa na data de referência,
calculada de `data_nascimento` — `idade_corte` da prata é fixa em 30/09/2026 e, na base de 31/07,
contaria meses de idade que ainda não existiam.
""", trecho("segmentos_kmeans_ouro.py", "VARIAVEIS = {", "calc=lambda ref, b: ((ref - b.inicio)", extra=1)),
("Log, padronização e base atual", """
Contagens têm cauda longa (poucos assinantes com muitos posts ou chamados), então entram em
`log1p`. Tudo é padronizado com a média e o desvio de 31/07; a base de 30/09 usa **os mesmos**
média e desvio, para cair no mesmo espaço dos centros. A lista de variáveis em log é conferida
contra `LOG_N` de `notebooks/_metricas_segmentacao.py`: se divergir, o notebook para, porque o
relatório recalcularia outra matriz e a métrica publicada não valeria.
""", trecho("segmentos_kmeans_ouro.py", "def matriz(f):", "z_co = ((matriz(corte) - mu) / sd).values")),
("Escolha de k e rótulos", """
k é o de maior silhueta entre 3 e 4 (faixa pedida pelo guia), medida numa amostra de 5.000 por
`silhueta`, a função da implementação única que o relatório também usa.
Os rótulos saem dos centros, em ordem: maior recusa = Cobrança falhando; mais dias sem treino
= Parados; menos meses de assinatura = Recém-chegados; o grupo restante que mais treina =
Engajados. Um rótulo só é dado se o centro estiver a pelo menos 1 desvio da média naquela
variável; senão o grupo vira "Grupo n" e a página mostra isso.
""", trecho("segmentos_kmeans_ouro.py", "rot = {}", '    rot[i] = f"Grupo {n}"')),
]),

("conciliacao", "Conciliação das duas segmentações (X1)", """
`conciliacao_segmentos.py` cruza as duas tabelas assinante por assinante, nas duas datas, sem
recalcular nada. Ele não termina em `_ouro` de propósito: lê os dois k-means e por isso roda
depois do laço dos notebooks de ouro. A decisão X1 usa o cruzamento para definir o relatório:
os quatro grupos de quatro variáveis viram personas; "Já desligou" e "Cobrança falhando" viram
listas operacionais; "Recém-chegados" vira recorte (mensal com até 90 dias) dentro dos Ativos.
""", [
("Junção completa e tabela do cruzamento", """
A junção é `outer` com `indicator`: se algum assinante estiver numa tabela e não na outra, o
notebook para, porque o cruzamento só faz sentido sobre a mesma base. A tabela final tem uma
linha por par (persona, segmento de nove variáveis, data), com os assinantes e a saída pelas
duas réguas: decisão (L) e fim da assinatura (N).
""", trecho("conciliacao_segmentos.py", "j = L.merge(N,", "tab.to_csv(SAIDA, index=False)")),
("Quanto as duas partições concordam", """
O índice de Rand ajustado compara as duas partições (1 = mesmos grupos; 0 = acaso). Ele fica
perto de zero: as duas segmentações cortam a base por eixos diferentes. Uma olha o que e há
quanto tempo a pessoa treina; a outra, engajamento recente, cobrança e novidade. Por isso o
relatório usa uma para as personas e a outra para listas e recortes, em vez de escolher uma e
descartar a outra.
""", trecho("conciliacao_segmentos.py", "t = j[j.data_ref == REF_TREINO]", 'print(f"Rand ajustado')),
]),

("conferencias", "Conferências: como saber que os números estão certos", """
Duas camadas de conferência rodam depois do ouro e saem com erro se algo quebrar:
`conferencias.py` (dados) e `confere_relatorio.py` (relatório).
""", [
("Conferência dos dados", """
`conferencias.py` confere contagens de linhas da bronze (contra o dicionário) e da prata
(contra o `decisoes.md`), números de referência (faturamento de set/26, 14.753 ativos,
expirações), cruzamentos entre tabelas (nenhum `user_id` órfão, cobrança sempre dentro da
vida da assinatura, só os preços do enunciado) e o ouro (churn de 5,6% e 6,6%, recusas). A
função `confere` imprime OK/FALHOU por item e acumula as falhas.
""", trecho("conferencias.py", "def confere(nome, esperado, obtido):", "        falhas.append(nome)")),
("Conferência do relatório", """
`confere_relatorio.py` recalcula a partir do ouro cada número citado no Customer Segmentation
Report (tamanho, saída, intervalo e medianas de cada persona, as duas listas e as células do
cruzamento) e procura o valor no texto da página, no formato brasileiro. Antes dos números, ele
confere a ligação das duas segmentações (X1): as duas tabelas de ouro têm de ter os mesmos pares
`(user_id, data_ref)`, uma linha por par, e o cruzamento não pode mudar o tamanho da base nem a
taxa de decisão de L. Número que só faz sentido preso a uma frase (decisão de L contra fim da
assinatura de N, que também existe na base inteira) é conferido por âncora de texto: âncora
ausente sai como PENDENTE com o valor do ouro, âncora presente com outro valor reprova. Se algo
não bater, o script lista o que e sai com erro.
""", trecho("confere_relatorio.py", "def confere(rotulo, trecho):", "        faltam.append(")),
]),
]

AMBIENTE = """
- **Ordem de execução** (da raiz do repositório): toda a prata; `churn_mensal_ouro.py` (o
  `assinantes_30jun26_ouro.py` lê o churn); o laço `notebooks/*_ouro.py`;
  `conciliacao_segmentos.py`; `eda_historia.py`; `relatorio_segmentacao.py` (o relatório que a
  conferência lê); `conferencias.py`; `confere_relatorio.py`; e este `memorial_tecnico.py`.
- **Versões**: `requirements.txt` fixa pandas 3.1.1, scikit-learn 1.9.1, plotly 7.1.0, pyarrow,
  scipy e openpyxl (Python 3.11 ou mais novo). As segmentações usam semente fixa
  (`random_state`), então repetem os grupos a cada execução.
- **Sem informação depois do corte**: toda variável é medida até a data de referência; as
  datas posteriores a 30/09/2026 que aparecem em alguns arquivos ficam marcadas na prata
  (`flag_*`) e fora das variáveis.
- **Limites**: as taxas de saída são históricas (ago–set/2026) e descrevem grupos; não são
  previsão nem efeito de ação. A campanha de 10/08/2026 tratou parte da base de 31/07.
"""


# --- página ---------------------------------------------------------------------------------
def bloco_html(titulo, texto, t):
    cod = ""
    if t:
        cod = (f'<figure class="code"><figcaption><code>notebooks/{t["arquivo"]}</code> · '
               f'linhas {t["de"]}–{t["ate"]}</figcaption>'
               f'<pre><code class="language-python">{html.escape(t["codigo"])}</code></pre></figure>')
    return (f'<div class="pair"><div class="explain"><h3>{html.escape(titulo)}</h3>{md(texto)}</div>'
            f"{cod}</div>")


indice = "".join(f'<li><a href="#{sid}">{html.escape(tit)}</a></li>' for sid, tit, _, _ in SECOES)
corpo = ""
for n, (sid, tit, intro, blocos) in enumerate(SECOES, start=1):
    corpo += (f'<section id="{sid}"><p class="section-kicker">{n:02d}</p><h2>{html.escape(tit)}</h2>'
              f'<div class="intro">{md(intro)}</div>'
              + "".join(bloco_html(*b) for b in blocos) + "</section>")
n_trechos = sum(len(b) for *_, b in SECOES)
gerado = datetime.now().strftime("%d/%m/%Y %H:%M")

pagina = f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Memorial técnico | Vitaliza</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@300;600;700&family=Platypi:wght@700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github-dark.min.css">
<style>
  :root {{ --roxo:#2e2640; --coral:#ff4545; --verde:#066d73; --cinza-medio:#caced6; --cinza-claro:#e6eaeb;
          --branco:#fff; --codigo:#1f1b2b; --titulo:'Platypi', Georgia, serif; --texto:'Manrope', Arial, sans-serif; }}
  * {{ box-sizing:border-box; border-radius:0; }}
  html {{ scroll-behavior:smooth; }}
  body {{ margin:0; background:var(--branco); color:var(--roxo); font-family:var(--texto); font-size:16px; font-weight:300; line-height:1.55; }}
  .page {{ width:min(100%, 1280px); margin:0 auto; padding:28px 30px 64px; }}
  h1, h2 {{ font-family:var(--titulo); font-weight:700; line-height:1.15; }}
  h1 {{ font-size:40px; margin:10px 0; }} h2 {{ font-size:28px; margin:0 0 12px; }}
  h3 {{ font-size:18px; font-weight:700; margin:0 0 8px; }}
  p {{ margin:0 0 10px; }} ul {{ margin:0 0 10px; padding-left:20px; }} li {{ margin:4px 0; }}
  strong {{ font-weight:700; }}
  code {{ font-family:ui-monospace, Menlo, Consolas, 'Courier New', monospace; font-size:.92em; overflow-wrap:anywhere; }}
  .eyebrow, .section-kicker {{ font-size:13px; font-weight:600; letter-spacing:.06em; text-transform:uppercase; margin:0 0 6px; }}
  header {{ padding-bottom:22px; border-bottom:1px solid var(--cinza-medio); }}
  .sub {{ font-size:18px; max-width:80ch; }}
  .meta {{ font-size:13px; margin-top:12px; }}
  nav {{ margin:22px 0 0; padding:16px 18px; background:var(--cinza-claro); border-left:4px solid var(--roxo); }}
  nav ol {{ margin:6px 0 0; padding-left:22px; columns:2; column-gap:32px; }}
  nav a {{ color:var(--roxo); }}
  section {{ padding:36px 0; border-bottom:1px solid var(--cinza-medio); }}
  .intro {{ max-width:90ch; margin-bottom:18px; }}
  .pair {{ display:grid; grid-template-columns:minmax(0, 5fr) minmax(0, 7fr); gap:22px; margin:18px 0; padding-top:18px; border-top:1px solid var(--cinza-claro); align-items:start; }}
  .pair:first-of-type {{ border-top:0; }}
  .explain {{ font-size:15px; }}
  .code {{ margin:0; background:var(--codigo); position:sticky; top:12px; }}
  .code figcaption {{ padding:8px 12px; font-size:12px; color:#d9d4e8; border-bottom:1px solid #3a3450; }}
  .code pre {{ margin:0; padding:12px; overflow:auto; max-height:560px; font-size:12.5px; line-height:1.5; }}
  .code pre code {{ background:transparent; color:#e8e6f0; padding:0; }}
  .hljs {{ background:transparent; }}
  footer {{ padding-top:22px; font-size:13px; }}
  @media (max-width:900px) {{
    .page {{ padding:20px 16px 48px; }} h1 {{ font-size:32px; }} h2 {{ font-size:24px; }}
    .pair {{ grid-template-columns:1fr; }} .code {{ position:static; }} nav ol {{ columns:1; }}
  }}
  @media print {{ .code {{ position:static; }} .code pre {{ max-height:none; white-space:pre-wrap; }} .pair {{ break-inside:avoid; }} }}
</style>
</head>
<body>
<div class="page">
<header>
  <p class="eyebrow">Case Vitaliza · MBA em IA e Dados para Negócios · Módulo 2 · Grupo 07</p>
  <h1>Memorial técnico</h1>
  <p class="sub">Como cada número da EDA e do Customer Segmentation Report é produzido: a explicação de cada etapa, à esquerda, e o código que a executa, à direita.</p>
  <p class="meta">Gerado em {gerado} por <code>notebooks/memorial_tecnico.py</code> · {n_trechos} trechos lidos dos notebooks no momento da geração · números do texto lidos de <code>dados/3.ouro</code> · base de {V['base30']} pagantes ativos em 30/09/2026</p>
  <nav aria-label="Sumário"><strong>Sumário</strong><ol>{indice}<li><a href="#ambiente">Execução, ambiente e limites</a></li></ol></nav>
</header>
{corpo}
<section id="ambiente"><p class="section-kicker">{len(SECOES) + 1:02d}</p><h2>Execução, ambiente e limites</h2><div class="intro">{md(AMBIENTE)}</div></section>
<footer>Fontes: <code>documentos/</code> (enunciado, dicionário, guia), <code>decisoes.md</code> (decisões por ID), <code>memorial.md</code> (conceitos e debate de método por etapa), <code>notebooks/</code>. Os trechos de código mostram as linhas exatas dos arquivos no momento da geração; a numeração de linhas acompanha o arquivo.</footer>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/languages/python.min.js"></script>
<script>if (window.hljs) hljs.highlightAll();</script>
</body>
</html>
"""
SAIDA.write_text(pagina)
print(f"{SAIDA.relative_to(RAIZ)}: {len(SECOES) + 1} seções · {n_trechos} trechos de código")
