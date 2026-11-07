---
name: git-do-grupo
description: Rotina de git do Grupo 07 no repo compartilhado (origin = Markabdo87/Vitaliza-MBA). Use no início de toda sessão (puxar o que o grupo subiu), ao terminar um bloco de trabalho (commit, push e handoff), ao ver conflito, e sempre que alguém falar em pull, push, subir, commitar, sincronizar ou passar o bastão.
---

# Git do grupo

Quatro pessoas trabalham no mesmo repo, no ramo `main`, cada uma com seu agente. O objetivo é
ninguém perder trabalho de ninguém e qualquer um conseguir continuar de onde o outro parou.

Remote único: `origin` → `github.com/Markabdo87/Vitaliza-MBA`. Não adicione outros remotes.

## 1. Início de sessão

O hook `SessionStart` já roda `git fetch` e põe no contexto quantos commits estão
atrás/à frente e se há mudança sem commit. A partir disso, **antes de começar a tarefa**:

- **Atrás do origin** → diga quantos commits e de quem (o hook lista), e proponha
  `git pull --rebase`. Se houver mudança local sem commit, faça antes
  `git stash` → `git pull --rebase` → `git stash pop`, ou commite primeiro.
- **À frente do origin** → lembre que há commits locais que o grupo ainda não tem e
  pergunte se pode subir.
- **Mudança sem commit herdada** → mostre `git status` resumido e pergunte se é trabalho em
  andamento (manter) ou resto de sessão anterior (commitar).
- **Em dia** → uma linha só ("repo em dia com o grupo") e siga.

Depois do pull, se vieram commits que mexem em `notebooks/`, avise que as tabelas de
prata/ouro locais podem estar velhas (elas não vão para o git) e ofereça rodar os notebooks
afetados.

Leia também a seção "Em aberto" do `decisoes.md`: é ali que o grupo deixa o que falta.

## 2. Durante o trabalho

- Commits pequenos e com um assunto só: uma tabela nova, uma decisão de limpeza, uma
  análise. Não junte "limpei pagamentos + mudei o README + comecei assinaturas".
- Mensagem em inglês no formato `tipo: descrição` (`feat`, `fix`, `docs`, `refactor`,
  `chore`), igual ao histórico. O corpo explica o porquê em pt-BR se ajudar.
- Commit que muda número (limpeza, regra) leva junto, no mesmo commit, o `decisoes.md`
  atualizado. Código e decisão andam juntos.
- Nunca commite: `.env`, chaves, CSVs de `dados/2.prata` e `dados/3.ouro` (o `.gitignore`
  já barra), arquivos de `dados/1.bronze` alterados.

## 3. Fim de sessão: subir e passar o bastão

Quando a pessoa disser que está terminando, ou ao fechar um bloco de trabalho, proponha:

1. `git status` e `git diff --stat`: mostre o que vai subir.
2. Se mudou notebook, rode-o de novo e confira que os números do `decisoes.md` batem.
3. Commit(s) do que estiver pronto. Trabalho pela metade também pode subir, desde que
   o commit diga isso (`wip: ...`) e não quebre nenhum notebook que já funcionava.
4. `git pull --rebase` e depois `git push`. **Peça confirmação antes do push**: é o
   repositório de outras pessoas.
5. **Handoff**: registre o que ficou pendente na seção "Em aberto" do `decisoes.md`
   (commitado junto) e entregue à pessoa um texto curto para mandar no grupo:

   ```
   Subi no Vitaliza-MBA:
   - <o que mudou, 1–3 linhas>
   - números: <se algum mudou, qual e quanto>
   Em aberto: <o que ficou, ou "nada">
   Depois de puxar: rodar <notebooks/xxx.py> (se aplicável)
   ```

## 4. Conflito

- Pare e mostre o conflito à pessoa antes de resolver qualquer coisa que não seja óbvia.
- `decisoes.md` e tabelas de markdown: quase sempre o certo é **manter as duas entradas**.
  Se dois colegas usaram o mesmo ID (ex.: dois `A3`), renumere a sua, não a do outro.
- Notebook com conflito: não escolha um lado às cegas. Entenda as duas mudanças, junte,
  rode o notebook e confira os números.
- Na dúvida, aborte (`git rebase --abort`) e pergunte.

## Proibido aqui

`git push --force`, `git reset --hard`, `git clean`, reescrever commit que já subiu, apagar
ramo de colega, mexer em remote. O `settings.json` do projeto bloqueia a maioria; não tente
contornar.
