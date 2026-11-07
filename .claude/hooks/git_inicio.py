"""SessionStart: compara o repo local com o origin e avisa o agente.

Roda `git fetch` e entrega ao agente (como contexto) quantos commits do grupo
ainda não foram puxados, quantos locais ainda não subiram e se há mudança sem
commit. Quem decide o que fazer é o agente, seguindo a skill git-do-grupo.

Nunca falha a sessão: sem rede ou sem git, sai calado.
"""
import json
import os
import subprocess

RAIZ = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()


def git(*args, timeout=10):
    r = subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True, timeout=timeout)
    return r.stdout.strip() if r.returncode == 0 else None


def main():
    if git("rev-parse", "--is-inside-work-tree") != "true":
        return
    fetch_ok = git("fetch", "origin", "--quiet", timeout=20) is not None
    ramo = git("rev-parse", "--abbrev-ref", "HEAD") or "?"
    upstream = git("rev-parse", "--abbrev-ref", "@{u}")
    linhas = [f"[git-do-grupo] ramo `{ramo}`"]
    if not fetch_ok:
        linhas.append("- `git fetch` falhou (sem rede?): a comparação abaixo pode estar desatualizada.")
    if upstream:
        contagem = git("rev-list", "--left-right", "--count", f"HEAD...{upstream}") or "0 0"
        frente, atras = (int(x) for x in contagem.split())
        if atras:
            novos = git("log", "--format=  - %h %an: %s", f"HEAD..{upstream}") or ""
            linhas.append(f"- {atras} commit(s) do grupo em `{upstream}` ainda não puxados:\n{novos}")
        if frente:
            linhas.append(f"- {frente} commit(s) locais ainda não enviados ao `{upstream}`.")
        if not atras and not frente:
            linhas.append(f"- em dia com `{upstream}`.")
    else:
        linhas.append("- ramo sem upstream configurado.")
    sujos = (git("status", "--porcelain") or "").splitlines()
    if sujos:
        linhas.append(f"- {len(sujos)} arquivo(s) com mudança sem commit.")
    linhas.append("Siga .claude/skills/git-do-grupo/SKILL.md (início de sessão) antes de começar o trabalho.")
    print(json.dumps({
        "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "\n".join(linhas)}
    }))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
