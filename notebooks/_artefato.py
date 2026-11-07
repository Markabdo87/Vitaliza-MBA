"""Monta as páginas HTML de `artefatos/` a partir de figuras plotly e tabelas pandas.

Uso dentro de um notebook de ouro:

    from _artefato import Pagina, layout_padrao, CORES
    p = Pagina("Churn mensal", "Como a base perde assinantes mês a mês.")
    p.texto("Parágrafo em markdown simples (só **negrito** e `código`).")
    p.figura(fig, "Legenda curta embaixo do gráfico")
    p.tabela(df, "Título da tabela")
    p.salvar("01_churn_mensal.html")

O plotly.js vai embutido na página (~4,8 MB): ela abre offline, no Drive e em
visualizadores que bloqueiam scripts externos. As páginas não têm dado
sensível: só agregados do ouro. Cores: paleta categórica validada para daltonismo, sempre
na mesma ordem.
"""
import html
import re
from datetime import datetime
from pathlib import Path

import plotly.graph_objects as go

RAIZ = Path(__file__).resolve().parent.parent
PASTA = RAIZ / "artefatos"

# Paleta categórica (ordem fixa) e tons de texto/grade.
CORES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
TEXTO, TEXTO_2, GRADE, FUNDO = "#0b0b0b", "#52514e", "#e6e5e0", "#fcfcfb"


def layout_padrao(fig, titulo_y="", formato_y=None, altura=380):
    fig.update_layout(
        template="none", height=altura, margin=dict(l=56, r=24, t=16, b=40),
        paper_bgcolor=FUNDO, plot_bgcolor=FUNDO,
        font=dict(family="Inter, system-ui, sans-serif", size=13, color=TEXTO_2),
        hovermode="x unified", legend=dict(orientation="h", y=1.08, x=0),
        hoverlabel=dict(bgcolor="white", font_color=TEXTO),
    )
    fig.update_xaxes(showgrid=False, linecolor=GRADE, ticks="outside", tickcolor=GRADE)
    fig.update_yaxes(gridcolor=GRADE, zeroline=False, title_text=titulo_y,
                     tickformat=formato_y)
    return fig


MESES_PT = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def eixo_meses(fig, inicio, fim, passo=3):
    """Rótulos de mês em português no eixo x (o plotly sem locale escreve em inglês)."""
    import pandas as pd
    datas = pd.date_range(inicio, fim, freq=f"{passo}MS")
    fig.update_xaxes(tickvals=datas, ticktext=[f"{MESES_PT[d.month - 1]}/{d:%y}" for d in datas])
    return fig


def _md(txt):
    txt = html.escape(txt)
    txt = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", txt)
    txt = re.sub(r"`(.+?)`", r"<code>\1</code>", txt)
    return txt


class Pagina:
    def __init__(self, titulo, subtitulo, fonte=""):
        self.titulo, self.subtitulo, self.fonte = titulo, subtitulo, fonte
        self.blocos = []
        self._primeira_fig = True

    def secao(self, titulo):
        self.blocos.append(f"<h2>{html.escape(titulo)}</h2>")

    def texto(self, txt):
        """Parágrafos separados por linha em branco; linhas que começam com '- ' viram lista
        (linhas seguintes sem '- ' continuam o item)."""
        for par in txt.strip().split("\n\n"):
            linhas = [l.strip() for l in par.strip().splitlines()]
            if linhas[0].startswith("- "):
                itens = []
                for l in linhas:
                    if l.startswith("- "):
                        itens.append(l[2:])
                    else:
                        itens[-1] += " " + l
                lis = "".join(f"<li>{_md(i)}</li>" for i in itens)
                self.blocos.append(f"<ul>{lis}</ul>")
            else:
                self.blocos.append(f"<p>{_md(' '.join(linhas))}</p>")

    def figura(self, fig, legenda=""):
        div = fig.to_html(full_html=False, include_plotlyjs=self._primeira_fig,
                          config={"displaylogo": False, "responsive": True})
        self._primeira_fig = False
        leg = f"<figcaption>{_md(legenda)}</figcaption>" if legenda else ""
        self.blocos.append(f"<figure>{div}{leg}</figure>")

    def tabela(self, df, titulo="", formatos=None):
        df = df.copy()
        for col, fmt in (formatos or {}).items():
            df[col] = df[col].map(lambda v: "" if v != v else fmt.format(v))
        tab = df.to_html(index=False, border=0, classes="tab", na_rep="")
        cab = f"<h3>{html.escape(titulo)}</h3>" if titulo else ""
        self.blocos.append(f'{cab}<div class="rolagem">{tab}</div>')

    def salvar(self, nome):
        PASTA.mkdir(exist_ok=True)
        gerado = datetime.now().strftime("%d/%m/%Y %H:%M")
        corpo = "\n".join(self.blocos)
        pagina = f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(self.titulo)} · Vitaliza G07</title>
<style>
body {{ background:{FUNDO}; color:{TEXTO}; font:15px/1.55 Inter, system-ui, sans-serif;
       margin:0; padding:24px 16px 64px; }}
main {{ max-width:960px; margin:0 auto; }}
h1 {{ font-size:26px; margin:0 0 4px; }} h2 {{ font-size:19px; margin:40px 0 8px; }}
h3 {{ font-size:15px; margin:20px 0 6px; }}
.sub {{ color:{TEXTO_2}; margin:0 0 4px; }} .meta {{ color:{TEXTO_2}; font-size:13px; }}
p, li {{ max-width:72ch; }} code {{ background:#f0efea; padding:1px 4px; border-radius:4px; font-size:13px; }}
figure {{ margin:12px 0 4px; }} figcaption {{ color:{TEXTO_2}; font-size:13px; margin-top:4px; }}
.rolagem {{ overflow-x:auto; }}
table.tab {{ border-collapse:collapse; font-size:13px; font-variant-numeric:tabular-nums; }}
table.tab th, table.tab td {{ padding:5px 10px; border-bottom:1px solid {GRADE}; text-align:right; }}
table.tab th:first-child, table.tab td:first-child {{ text-align:left; }}
table.tab th {{ color:{TEXTO_2}; font-weight:600; }}
</style></head><body><main>
<h1>{html.escape(self.titulo)}</h1>
<p class="sub">{_md(self.subtitulo)}</p>
<p class="meta">Gerado em {gerado} · {_md(self.fonte)}</p>
{corpo}
</main></body></html>"""
        destino = PASTA / nome
        destino.write_text(pagina, encoding="utf-8")
        return destino


def linha(fig, x, y, nome, cor, **kw):
    fig.add_trace(go.Scatter(x=x, y=y, name=nome, mode="lines+markers",
                             line=dict(color=cor, width=2), marker=dict(size=6, color=cor), **kw))
