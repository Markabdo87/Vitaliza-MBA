---
name: registrar-decisao
description: Como registrar uma decisão ou premissa no decisoes.md, a fonte da verdade do grupo. Use sempre que uma escolha mudar um número - limpeza de dado (corrigir, remover, marcar), premissa de negócio usada numa conta em R$, definição de métrica (o que conta como churn, ativo, corte), filtro de análise - e quando uma decisão antiga for revista.
---

# Registrar decisão

`decisoes.md` é o **log de todas as decisões e premissas** do grupo. Se uma escolha mudou
um número e não está lá, para o grupo ela não existe. Notebook diz *como*; `decisoes.md` diz
*o quê* e *por quê*, e quanto isso mexeu na contagem.

## O que entra

- **Limpeza** (bronze → prata): todo problema encontrado tem três saídas, **corrigir**,
  **remover** ou **marcar** (`flag_*`), e também **manter** quando se decide não mexer.
- **Premissa de negócio**: preço, taxa, custo, CAC, limite do CRM. Sempre com a fonte
  (seção do enunciado ou do dicionário). Se o enunciado não diz, é uma premissa **do grupo**
  e isso tem que estar escrito.
- **Definição de métrica**: o que conta como churn, como assinante ativo, janela, corte.
- **Escolha de análise/modelo**: filtro de população, variáveis excluídas, limiar de
  decisão. Tudo o que outra pessoa precisaria saber para chegar no mesmo número.

Não entra: passo a passo de código (isso fica no notebook) nem narrativa de processo.

## Formato

Uma seção por tabela de origem (ou por etapa: `## Churn mensal (ouro)`, `## Modelo`…), com
cabeçalho dizendo origem → destino, notebook e contagem antes/depois:

```
## Assinaturas (`1.bronze/assinaturas.csv` → `2.prata/assinaturas.csv`)

Notebook: `notebooks/assinaturas_prata.py`. Bronze: N linhas · prata: M linhas.

| # | Problema | Decisão | Motivo | Efeito na contagem |
|---|---|---|---|---|
| A1 | ... | **Corrigir** ... | ... | −123 linhas · set/26: −R$ 456,70 |
```

- **ID**: prefixo da seção + número sequencial, nunca reaproveitado. Os prefixos em uso
  estão no topo do `decisoes.md`; ao abrir seção nova, escolha um livre e acrescente lá.
- **Efeito na contagem** é obrigatório e é número, não adjetivo: linhas afetadas e,
  quando houver dinheiro, o efeito em R$ (total e no mês de referência, set/2026).
  "Nenhuma linha alterada" é uma resposta válida.
- Premissas gerais (valem para o case inteiro) vão na tabela "Premissas gerais" do topo.
- Ao terminar uma tabela, atualize o **resultado de referência** (o número que qualquer um
  deve conseguir reproduzir rodando o notebook).

## Revisar uma decisão

Não apague a linha antiga: o histórico é parte da verificação. Risque e aponte para a nova:

```
| ~~P7~~ | ... | ~~Marcar~~ → ver P12 | ... | ... |
| P12 | ... | **Remover** ... | confirmado com eventos_assinatura.csv | −180 linhas |
```

Depois atualize os números de referência afetados e diga isso no commit.

## Em aberto

A seção "Em aberto" no fim do arquivo é a lista de pendências do grupo: dúvida não
resolvida, decisão provisória a confirmar, próximo passo. Toda sessão que termina com algo
pela metade deixa uma linha lá (ver skill `git-do-grupo`, handoff). Quando resolver, tire a
linha e registre a decisão na tabela.

## Checklist

1. A decisão tem ID, motivo e efeito numérico?
2. A regra está implementada no notebook citado, e o cabeçalho (docstring) do notebook
   descreve a mesma regra?
3. Rodando o notebook do zero, os números escritos aqui saem iguais?
4. Vai no mesmo commit que a mudança do notebook.
