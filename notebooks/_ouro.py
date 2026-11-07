"""Leitura da prata para os notebooks de ouro, com conferência antes de calcular.

Os colegas regeneram a prata (e o ouro) quando mudam uma regra de limpeza. Para o ouro não
rodar em silêncio sobre um arquivo velho ou com coluna renomeada, `ler_prata` confere:

  1. o arquivo existe (senão, diz qual notebook de prata rodar);
  2. as colunas que o notebook usa estão lá (senão, lista as que faltam);
  3. o arquivo é mais novo que o notebook que o gera (senão, avisa para rodar de novo).

Uso:
    from _ouro import ler_prata
    ass = ler_prata("assinaturas.csv", ["user_id", "inicio"], datas=["inicio"])
"""
import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
PRATA = RAIZ / "dados" / "2.prata"
OURO = RAIZ / "dados" / "3.ouro"
NOTEBOOKS = RAIZ / "notebooks"


def _notebook_de(arquivo):
    return NOTEBOOKS / f"{Path(arquivo).stem}_prata.py"


def ler_prata(arquivo, colunas, datas=()):
    """Lê `dados/2.prata/<arquivo>` (csv ou parquet) só com `colunas`, já conferido."""
    caminho = PRATA / arquivo
    nb = _notebook_de(arquivo)
    rodar = f".venv/bin/python {nb.relative_to(RAIZ)}"
    if not caminho.exists():
        sys.exit(f"falta {caminho.relative_to(RAIZ)}: rode {rodar}")
    if nb.exists() and nb.stat().st_mtime > caminho.stat().st_mtime:
        print(f"aviso: {nb.name} mudou depois de {arquivo} ser gerado; rode {rodar}")

    if caminho.suffix == ".parquet":
        import pyarrow.parquet as pq
        existentes = pq.read_schema(caminho).names
    else:
        existentes = pd.read_csv(caminho, nrows=0).columns.tolist()
    faltam = [c for c in colunas if c not in existentes]
    if faltam:
        sys.exit(f"{caminho.relative_to(RAIZ)} não tem as colunas {faltam}. "
                 f"A prata mudou de formato: ajuste o notebook de ouro ou rode {rodar}")

    if caminho.suffix == ".parquet":
        df = pd.read_parquet(caminho, columns=list(colunas))
    else:
        df = pd.read_csv(caminho, usecols=list(colunas), parse_dates=list(datas))
    if df.empty:
        sys.exit(f"{caminho.relative_to(RAIZ)} está vazio: rode {rodar}")
    return df
