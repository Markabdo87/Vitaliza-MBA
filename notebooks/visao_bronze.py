"""Bronze -> artefatos/analises/00a_visao_bronze.html: primeiro olhar sobre os arquivos entregues.

Página de apoio para o grupo, não é tabela de análise. Passa arquivo a arquivo da bronze:
o que ele contém, as pontas importantes e as anomalias encontradas (com o ID da decisão
no decisoes.md). O perfil (linhas, colunas, vazios, período, volume por mês) é calculado
aqui, direto da bronze; os textos de anomalia resumem as decisões dos notebooks de prata.

Regras do perfil:
  1. Lê cada arquivo como veio, tudo como texto (nada é convertido).
  2. "Vazio" = célula vazia ou nula.
  3. Volume por mês = os 7 primeiros caracteres da coluna de data, como gravada (sem
     conversão de fuso). Meses depois do corte (30/09/2026) aparecem em vermelho.
  4. Valores de exemplo só para colunas categóricas (até 30 valores distintos); e-mail,
     IDs e texto livre não são mostrados.

Uso: .venv/bin/python notebooks/visao_bronze.py  (a partir da raiz do repo)
"""
import zipfile
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

from _artefato import CORES, Pagina, layout_padrao

RAIZ = Path(__file__).resolve().parent.parent
BRONZE = RAIZ / "dados" / "1.bronze"
# Página de apoio, não artefato de entrega: fica na subpasta de análises intermediárias.
APOIO = RAIZ / "artefatos" / "analises"
CORTE = "2026-09"

# arquivo -> (coluna de data para o volume mensal, rótulo do grão)
ARQUIVOS = {
    "usuarios.csv": ("data_cadastro", "conta"),
    "assinaturas.csv": ("inicio", "assinatura"),
    "eventos_assinatura.csv": ("data_hora", "evento"),
    "pagamentos.csv": ("data_hora", "cobrança"),
    "uso_mensal.csv": ("mes", "usuário × mês"),
    "atividades.parquet": ("inicio", "treino"),
    "amizades.csv": ("desde", "relação de seguir"),
    "campanha_ago26.csv": (None, "assinante sorteado"),
    "onboarding.csv": ("respondido_em", "conta"),
    "feed_posts.csv": ("data_hora", "post"),
    "pesquisa_saida.csv": ("respondido_em", "resposta"),
    "tickets_suporte.csv": ("aberto_em", "chamado"),
}

SEM_EXEMPLO = {"email", "texto", "texto_cliente", "comentario", "objetivo_texto",
               "como_conheceu", "titulo_mensagem"}

# O que cada arquivo contém, pontas importantes e anomalias (IDs do decisoes.md).
TEXTOS = {
    "usuarios.csv": dict(
        o_que="Toda conta criada desde o lançamento (set/2020), pague ou não. Cadastro "
              "(e-mail, nascimento, sexo, cidade, UF, CEP), sistema do celular, última versão "
              "do app, relógio conectado e canal de aquisição.",
        pontas="""
- É a tabela-mãe: o `user_id` liga todos os arquivos.
- Cerca de 65 mil contas para 32,6 mil assinaturas: metade das contas nunca assinou.
- A base antes de jul/2024 é rala (~5,2 mil contas em 46 meses, contra ~1,9 mil por mês
depois): o histórico útil começa em jul/2024.
- `canal_aquisicao` é a peça que liga a aquisição ao churn (influenciador, ads, orgânico…).""",
        anomalias="""
- **959 contas duplicadas**: mesmo e-mail, a cópia mais nova com maiúscula, todos os
campos iguais. Incluem os 119 cadastros "futuros" (out/2026 a abr/2027). Nenhum outro
arquivo usa essas cópias (U1, U2).
- **60 contas de teste** da Vitaliza (canal `interno`, e-mail `teste*`/`qa.*`) (U13).
- Nascimento `1900-01-01` (valor padrão) e `2031-05-12` (futuro) (U5).
- `sexo` em seis grafias (`F`, `Fem`, `feminino`…) e `cidade` em 36 grafias para 13
cidades (`Sampa`, `SAO PAULO`, `BH`, `Floripa`…) (U8, U9).
- CEP de SP capital com o zero da frente perdido (1.083) e `sistema` com maiúsculas
variadas (U10, U12).
- Antes de jul/2024 a hora do cadastro é sempre `12:00:00`: só a data vale (U4)."""),
    "assinaturas.csv": dict(
        o_que="Retrato de cada assinatura em 01/10/2026: plano, canal de cobrança, início, "
              "status atual, renovação automática, data e motivo do fim.",
        pontas="""
- É uma **foto**, não histórico: para saber quem estava ativo numa data passada, use os
eventos.
- Uma assinatura por pessoa: ninguém volta a assinar nos dados (A6).
- Assinaturas encerradas antes de jul/2024 não estão no arquivo: churn só é calculável de
ago/2024 em diante (A5).
- 5.200 assinaturas antigas (início antes de jul/2024) não têm rastro nos logs (A4).""",
        anomalias="""
- **60 assinaturas `cortesia` / `interno`**, valores que o dicionário não lista: são as
contas de teste (A3).
- Rótulos de canal diferentes dos de pagamentos (`web_cartao`/`web_pix` aqui,
`cartao`/`pix_automatico` lá) (A2).
- Fora isso, coerente: status, datas e motivo batem entre si em todas as linhas (A7).
- `assinatura_id` tem lacunas e não segue a ordem do início: é identificador, não
contador (A10)."""),
    "eventos_assinatura.csv": dict(
        o_que="Log de tudo o que acontece com trial e assinatura desde 01/07/2024: início, "
              "renovação, desligamento e religamento da renovação, carência, expiração, "
              "cancelamento no site, chargeback e reembolso.",
        pontas="""
- É a fonte para reconstruir o estado de cada assinante em qualquer data.
- Cerca de 47 mil trials iniciados para 27 mil assinaturas iniciadas no período.
- O motivo do fim (`detalhe`) só existe no site; na loja a causa sai dos eventos
anteriores (E5).""",
        anomalias="""
- **Fusos misturados**: lojas em UTC (`...Z`), site em Brasília. Convertido, 21.951
eventos mudam de dia e 753 mudam de mês (E1).
- Arquivo fora de ordem (E2).
- No site, cancelar gera `cancelamento_web` **e** `renovacao_automatica_desligada`:
somar os dois conta o cancelamento em dobro (E11).
- 932 avisos chegam até 1 dia depois do fim da assinatura ou do trial (E8).
- 38 sequências que o estado anterior não permite (ex.: renovação depois de
chargeback) (E9).
- 5.200 usuários aparecem já no meio da assinatura, sem início no log (E7)."""),
    "pagamentos.csv": dict(
        o_que="Toda cobrança desde jul/2024 (aprovada, recusada, estorno, chargeback): "
              "valor, método, status e número da tentativa.",
        pontas="""
- Única fonte de R$. Referência: faturamento de set/2026 = R$ 489.873,50 bruto,
depois da limpeza.
- As recusas (3.250) são o rastro do churn involuntário.
- Taxa por método vem do enunciado: 15% loja, 3,5% cartão, 0,99% Pix.""",
        anomalias="""
- **1.941 cobranças gravadas duas vezes** (mesmo usuário, segundo e valor, IDs
seguidos): R$ 118 mil a mais no bruto (P1).
- Valor do site como texto `R$ 39,90` até jun/2025, depois `39.90` (P2).
- Fuso UTC nas lojas: 453 cobranças mudam de mês (P3).
- Estornos e chargebacks lançados pelo preço de tabela, não pelo valor pago (−39,90
em quem pagou 34,90) (P4).
- A coluna `tentativa` não registra retentativa: recusa seguida de nova cobrança volta
a `1` (P5).
- 16 mensais cobradas a R$ 34,90 depois do reajuste de 01/03/2026 (P8)."""),
    "uso_mensal.csv": dict(
        o_que="Resumo de uso por usuário e mês, jan/2025 a set/2026: treinos (ao ar livre e "
              "em vídeo), minutos, dias ativos e sessões no app.",
        pontas="""
- É a série de engajamento mais longa (21 meses) e a mais fácil de cruzar com o churn.
- Para 2026 há também `atividades.parquet`, treino a treino.""",
        anomalias="""
- **A população muda em jan/2026**: em 2025 só há linha em mês com treino; em 2026
também em mês sem treino. As linhas vão de 13,6 mil (dez/25) para 41,1 mil (jan/26)
(M5).
- **`sessoes_app` cai 45% de uma vez em mar/2026**, com treinos estáveis: mudança na
forma de contar, não de comportamento (M6).
- Em 2026 conta menos treinos que `atividades` para quem usa relógio (383 mil treinos
a menos) (M9, em aberto).
- 168 meses com volume muito alto (mais de 180 min por dia ativo), possíveis para
atleta (M7)."""),
    "atividades.parquet": dict(
        o_que="Um treino por linha, jan a set/2026: tipo, duração, distância, ritmo, "
              "frequência cardíaca, origem (app, Garmin, Apple Health), GPS e companhia.",
        pontas="""
- O grão mais fino de comportamento, mas só cobre 2026.
- A coluna `gps_ok` é o rastro do incidente técnico de mai–jun/2026.
- `treino_com` mostra quem treina acompanhado (14 mil treinos).""",
        anomalias="""
- **Garmin em UTC sem o `Z`**, no mesmo formato do horário de Brasília: só a origem
revela (T1).
- Desde 15/04/2026 o app grava o tipo em inglês (`run`, `walk`…): 11 rótulos para 6
tipos (T2).
- **1.900 treinos em dobro** (relógio + app, mesmas medidas) (T3).
- 998 distâncias 40 a 160 vezes maiores que o possível (caminhada de 81 min com
512 km) (T4).
- **14.779 treinos com GPS falho**, só na versão nova do app, com distância sem
sentido (T5).
- 3.645 treinos com duração zero (T6)."""),
    "amizades.csv": dict(
        o_que="Quem segue quem no app (mão única) e desde quando.",
        pontas="""
- 75% das relações são recíprocas (os dois se seguem).
- É a rede social do app: candidata a variável de retenção.""",
        anomalias="""
- 273 relações com data depois do corte (até 09/10/2026) (Z2).
- Fora isso, limpa: ninguém segue a si mesmo, nenhum par repetido e todos os IDs existem
em `usuarios` (Z3–Z5)."""),
    "campanha_ago26.csv": dict(
        o_que="Os 14.120 assinantes sorteados em 10/08/2026 em quatro grupos (controle, "
              "desafio, cupom, conteúdo): envio, canal, título, oferta, abertura e clique.",
        pontas="""
- É o único experimento dos dados: a base do uplift ("quem vale contatar").
- O cupom muda conforme o plano: 30% por 3 meses no mensal e 1 mês grátis no anual (C9).
- Abertura e clique medem atenção, não retenção: o resultado tem que vir de quem
continuou assinando.""",
        anomalias="""
- Praticamente limpa: o sorteio é equilibrado entre os grupos (C10) e não há
incoerência entre grupo, envio e oferta (C7).
- Booleanos gravados como texto `True`/`False` (C6).
- O fuso do envio não está no dicionário: assumido Brasília (C4)."""),
    "onboarding.csv": dict(
        o_que="O questionário de entrada de cada conta: objetivo (texto livre), como "
              "conheceu o app (texto livre), nível e dias de treino por semana.",
        pontas="""
- O objetivo em texto ("prova de 10k", "viagem pra praia"…) é insumo para a extração
com IA e conversa com o churn de "objetivo cumprido".
- `como_conheceu` cita perfis de influenciador (`cupom da @carolfit`) em 7.793 linhas.""",
        anomalias="""
- **21,5% dos objetivos sem conteúdo** (`ok`, `.`, `asdf`, `kkkk`, `nada`) (O5).
- `como_conheceu` em 572 grafias, com erros de digitação (`vi um aúnncio`,
`propagnada no face`) (O6).
- `dias_por_semana` em texto: `3`, `3x`, `3 vezes`, `todos` (O7)."""),
    "feed_posts.csv": dict(
        o_que="Os posts do feed social do app: texto curto e curtidas.",
        pontas="""
- Texto livre para a extração: humor, lesão, viagem, mudança de cidade ("mudei pra
Lisboa").
- `post_id` não segue a ordem do tempo: ordene por `data_hora`.""",
        anomalias="""
- 122 posts depois do corte (até 07/10/2026) (F3).
- 1.214 posts com o marcador `[post removido]` no lugar do texto (F4).
- Erros de digitação, falta de acento e emojis: são o texto da pessoa e ficam como
vieram (F6)."""),
    "pesquisa_saida.csv": dict(
        o_que="As respostas de quem cancelou pelo site entre jun e set/2026: o motivo "
              "marcado numa lista e um comentário livre.",
        pontas="""
- É a única voz direta de quem saiu, mas só do site (1/3 da base) e só de 4 meses.
- Os comentários são poucas mensagens-base repetidas com variação de digitação.""",
        anomalias="""
- **O motivo marcado contradiz o comentário em 220 de 452 respostas**. Dos 187 `preco`
com comentário, só 2 falam de dinheiro; 104 são objetivo cumprido ("era só até a
prova") (Q7).
- 183 respostas sem comentário (Q1).
- 2 contas responderam duas vezes (Q5)."""),
    "tickets_suporte.csv": dict(
        o_que="Os chamados de suporte de jul/2025 a set/2026: canal, texto do cliente, "
              "categoria dada pelo atendente, status e data de resolução.",
        pontas="""
- O volume explode em mai–jun/2026: é o incidente de GPS e percurso não gravado.
- Os 303 textos distintos se reduzem a 27 mensagens-base.""",
        anomalias="""
- **A categoria do atendente diverge do texto em 33,6% dos chamados** ("quero cancelar
minha assinatura" como `tecnico`) (S9).
- 935 chamados abertos há mais de 20 dias no corte: abandonados, 602 deles de mai–jun
(S6).
- 41 resolvidos depois do corte (S5)."""),
}


def perfil_colunas(df):
    linhas = []
    for c in df.columns:
        s = df[c]
        vazio = (s.isna() | (s.astype(str).str.strip() == "")).mean()
        n = s.nunique(dropna=True)
        if c in SEM_EXEMPLO or c.endswith("_id") or n > 30:
            ex = "—"
        else:
            ex = ", ".join(f"{k} ({v:,})".replace(",", ".")
                           for k, v in s.value_counts().head(4).items())
        linhas.append({"coluna": c, "% vazio": 100 * vazio, "valores distintos": n,
                       "mais comuns": ex})
    return pd.DataFrame(linhas)


def grafico_mensal(meses):
    cont = meses.value_counts().sort_index()
    cont = cont[cont.index.str.match(r"^\d{4}-\d{2}$")]
    cores = [CORES[7] if m > CORTE else CORES[0] for m in cont.index]
    fig = go.Figure(go.Bar(x=cont.index, y=cont.values, marker_color=cores,
                           hovertemplate="%{x}: %{y:,} linhas<extra></extra>"))
    layout_padrao(fig, "linhas", altura=200)
    fig.update_layout(margin=dict(l=56, r=16, t=8, b=32), showlegend=False)
    return fig


def fmt(n):
    return f"{n:,}".replace(",", ".")


def br(df, inteiros=(), decimais=()):
    """Formata números no padrão brasileiro (1.234 e 12,5) para as tabelas da página."""
    df = df.copy()
    for c in inteiros:
        df[c] = df[c].map(lambda v: "" if v is None or v != v else fmt(int(v)))
    for c in decimais:
        df[c] = df[c].map(lambda v: f"{v:.1f}".replace(".", ","))
    return df


def ler(nome):
    if nome.endswith(".parquet"):
        return pd.read_parquet(BRONZE / nome).astype("string")
    return pd.read_csv(BRONZE / nome, dtype=str, keep_default_na=True)


# ---------------------------------------------------------------- perfil de todos
perfis, resumo = {}, []
for nome, (col_data, grao) in ARQUIVOS.items():
    df = ler(nome)
    linha = {"arquivo": nome, "uma linha por": grao, "linhas": len(df),
             "colunas": df.shape[1],
             "user_id distintos": df["user_id"].nunique() if "user_id" in df else None,
             "linhas repetidas": int(df.duplicated().sum())}
    if col_data:
        d = df[col_data].dropna().str[:10]
        linha["de"], linha["até"] = d.min(), d.max()
    resumo.append(linha)
    perfis[nome] = (df, col_data)
    print(f"{nome}: {fmt(len(df))} linhas")

zips = sorted((BRONZE / "heatmaps").glob("*.zip"))
imagens = {z.name: sum(n.endswith(".png") for n in zipfile.ZipFile(z).namelist()) for z in zips}

# ---------------------------------------------------------------- página
p = Pagina(
    "Primeiro olhar: a bronze",
    "O que veio em cada arquivo entregue pelo curso, o que importa saber e o que está "
    "estranho. Página de apoio para o grupo, antes de qualquer análise.",
    "Fonte: `dados/1.bronze/` (corte 30/09/2026), lida como veio. Gerado por "
    "`notebooks/visao_bronze.py`.",
)
p.texto("""
São 12 tabelas e duas pastas de imagens, ligadas pelo `user_id`. O dicionário avisa que
ninguém limpou os dados: formatos, fusos e nomes variam entre arquivos. Cada anomalia
abaixo traz entre parênteses o ID da decisão no `decisoes.md`, onde estão o motivo e o
efeito de cada correção.

Nos gráficos de volume, a data é a gravada no arquivo, sem converter fuso. Barra
vermelha = mês depois do corte de 30/09/2026.""")

p.secao("Os arquivos num quadro só")
tab = pd.DataFrame(resumo)
p.tabela(br(tab, inteiros=["linhas", "user_id distintos", "linhas repetidas"]), "")
p.texto("""
"Linhas repetidas" conta só linha inteira idêntica. As duplicatas reais da bronze não
são idênticas (contas com e-mail em maiúscula, cobranças com ID diferente, treinos
relógio + app) e aparecem nas anomalias de cada arquivo.""")

p.texto("""
Três famílias de arquivo:

- **Cadastro e situação atual**: `usuarios`, `assinaturas`, `amizades`, `campanha_ago26`.
- **Logs no tempo**: `eventos_assinatura`, `pagamentos`, `uso_mensal`, `atividades`.
- **Texto e imagem** (insumo da extração com IA): `onboarding`, `feed_posts`,
`pesquisa_saida`, `tickets_suporte`, `heatmaps/`.""")

for nome, (df, col_data) in perfis.items():
    t = TEXTOS[nome]
    p.secao(nome)
    p.texto(t["o_que"])
    p.blocos.append('<p class="meta">' + " · ".join(
        f"{k}: {fmt(v) if isinstance(v, int) else v}"
        for k, v in next(r for r in resumo if r["arquivo"] == nome).items()
        if k not in ("arquivo", "colunas") and v is not None) + "</p>")
    if col_data:
        p.figura(grafico_mensal(df[col_data].dropna().str[:7]),
                 f"Linhas por mês, pela coluna `{col_data}` como gravada.")
    p.blocos.append("<h3>Pontas importantes</h3>")
    p.texto(t["pontas"])
    p.blocos.append("<h3>Anomalias</h3>")
    p.texto(t["anomalias"])
    p.blocos.append(f"<details><summary>As {df.shape[1]} colunas</summary>")
    p.tabela(br(perfil_colunas(df), inteiros=["valores distintos"], decimais=["% vazio"]), "")
    p.blocos.append("</details>")

p.secao("heatmaps/")
p.texto("""
Uma imagem PNG por assinante (`<user_id>.png`) com o mapa de calor das rotas dos treinos ao
ar livre nos 90 dias até a data da pasta: quanto mais vezes a pessoa passou por um trecho,
mais forte a cor. Duas datas: 31/07/2026 e 30/09/2026.""")
p.tabela(br(pd.DataFrame({"arquivo": list(imagens), "imagens": list(imagens.values())}),
            inteiros=["imagens"]), "")
p.blocos.append("<h3>Pontas importantes</h3>")
p.texto("""
- É a única fonte que mostra **onde e como** a pessoa treina, não só quanto.
- Só existe imagem para quem era assinante pagante na data e treinou ao ar livre no
período. Comparar as duas datas mostra quem parou de sair para treinar.
- Para virar variável, a imagem precisa ser lida: contando pixels por cor ou com um
modelo que interpreta imagem.""")
p.blocos.append("<h3>Anomalias</h3>")
p.texto("""
- O mapa de fundo é estilizado e não corresponde a ruas reais (dicionário).
- O zip de 31/07 tem 12.431 imagens; o dicionário fala em 12.426. A diferença de 5 ainda
não foi conferida.
- Ainda não perfilado: não tem prata, é insumo direto da extração.""")

APOIO.mkdir(parents=True, exist_ok=True)
# Caminho absoluto: `Pagina.salvar` grava em `PASTA / nome`, e o pathlib respeita o
# destino absoluto (não cai em artefatos/).
destino = p.salvar(APOIO / "00a_visao_bronze.html")
assert destino == APOIO / "00a_visao_bronze.html", destino
print(f"-> {destino.relative_to(RAIZ)}")
