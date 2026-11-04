"""Bronze -> prata: atividades.parquet limpo (um treino por linha, jan-set/2026).

Correções aplicadas:
  1. fuso: o Garmin grava o início em UTC sem o "Z"; app e Apple Health gravam em
     Brasília. Garmin -3h; tudo em inicio_brt (timestamp). Original em inicio_bronze,
     origem do fuso em fuso_origem (utc/brt).
  2. tipo: desde 15/04/2026 o app grava o tipo em inglês. run->corrida, walk->caminhada,
     ride->pedal, strength->forca, hiit->funcional. Original em tipo_bronze.
  3. duplicatas: o mesmo treino chega pelo app e pelo relógio. Mesma (user_id, inicio_brt,
     tipo, duracao_min, distancia_km, ritmo_min_km) conta uma vez; fica a linha do relógio
     (garmin/apple_health) e, no empate, o menor atividade_id.
  4. distância inflada: distancia_km 40 a 160 vezes maior que duracao_min / ritmo_min_km
     (nos demais treinos a razão fica entre 0,99 e 1,01). Passa a valer
     duracao_min / ritmo_min_km. Original em distancia_km_bronze.
  5. GPS falhou (gps_ok = False): a distância gravada é um trecho do percurso e não há
     ritmo. distancia_km vira nulo. Original em distancia_km_bronze.
  6. duração zero: em treino com distância e ritmo, duracao_min = distancia_km * ritmo_min_km.
     Sem distância e ritmo (ou com distância também inflada: duração recalculada acima do
     teto do tipo), duracao_min vira nulo. Original em duracao_min_bronze.
  7. treino_com: texto vazio vira nulo.

Não remove nada além das duplicatas. Suspeitas viram flag:
  flag_duracao_zero     duração 0 na bronze (recalculada ou nula, ver regra 6)
  flag_inicio_repetido  outro treino do mesmo usuário começa no mesmo minuto (tipo ou
                        duração diferentes, por isso não é duplicata)

Uso: .venv/bin/python notebooks/atividades_prata.py  (a partir da raiz do repo)
"""
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

BASE = Path(__file__).resolve().parent.parent / "dados"
ENTRADA = BASE / "1.bronze" / "atividades.parquet"
SAIDA = BASE / "2.prata" / "atividades.parquet"

TIPO_EN = {"run": "corrida", "walk": "caminhada", "ride": "pedal",
           "strength": "forca", "hiit": "funcional"}
RELOGIO = ("garmin", "apple_health")
RAZAO_INFLADA = 5  # distancia / (duracao / ritmo); não há razão entre 1,01 e 40
# teto de duração por tipo com GPS: acima do maior treino coerente observado
TETO_DURACAO = {"caminhada": 120.0, "corrida": 360.0, "pedal": 600.0}

COLUNAS = [
    "atividade_id", "user_id", "inicio_brt", "mes", "inicio_bronze", "fuso_origem",
    "tipo", "tipo_bronze", "duracao_min", "duracao_min_bronze", "distancia_km",
    "distancia_km_bronze", "ritmo_min_km", "fc_media", "origem", "gps_ok", "treino_com",
    "flag_duracao_zero", "flag_inicio_repetido",
]


def n(mask):
    return pc.sum(pc.cast(pc.fill_null(mask, False), pa.int64())).as_py() or 0


def main():
    t = pq.read_table(ENTRADA)
    total_bronze = t.num_rows
    print(f"bronze: {total_bronze} linhas")

    # 1. fuso
    garmin = pc.equal(t["origem"], "garmin")
    ts = pc.strptime(t["inicio"], format="%Y-%m-%d %H:%M:%S", unit="s")
    tres_h = pa.scalar(3 * 3600, pa.duration("s"))
    brt = pc.if_else(garmin, pc.subtract(ts, tres_h), ts)
    dia_mudou = pc.not_equal(pc.strftime(ts, "%Y-%m-%d"), pc.strftime(brt, "%Y-%m-%d"))
    mes_mudou = pc.not_equal(pc.strftime(ts, "%Y-%m"), pc.strftime(brt, "%Y-%m"))
    print(f"[1] fuso: {n(garmin)} linhas Garmin -3h · {n(dia_mudou)} mudam de dia · "
          f"{n(mes_mudou)} mudam de mês")

    # 2. tipo
    tipo = t["tipo"]
    for en, pt in TIPO_EN.items():
        tipo = pc.if_else(pc.equal(tipo, en), pt, tipo)
    print(f"[2] tipo em inglês traduzido: {n(pc.not_equal(tipo, t['tipo']))} linhas")

    t = t.append_column("inicio_brt", brt).append_column("tipo_pt", tipo)
    t = t.append_column("prio", pc.if_else(pc.is_in(t["origem"], pa.array(RELOGIO)), 0, 1))

    # 3. duplicatas: ordena pela chave + prioridade e descarta quem repete a linha anterior
    chave = ["user_id", "inicio_brt", "tipo_pt", "duracao_min", "distancia_km", "ritmo_min_km"]
    t = t.sort_by([(c, "ascending") for c in chave] + [("prio", "ascending"),
                                                       ("atividade_id", "ascending")])
    repete = None
    for c in chave:
        col = t[c].combine_chunks()
        if pa.types.is_floating(col.type):
            col = pc.fill_null(col, -1.0)
        igual = pc.equal(col.slice(1), col.slice(0, len(col) - 1))
        repete = igual if repete is None else pc.and_(repete, igual)
    dup = pa.concat_arrays([pa.array([False]), repete])
    removidas = t.filter(dup)
    print(f"[3] duplicatas removidas: {removidas.num_rows} · origem da removida: "
          f"{dict((r['values'], r['counts']) for r in pc.value_counts(removidas['origem']).to_pylist())}")
    t = t.filter(pc.invert(dup))

    dist = t["distancia_km"]
    ritmo = t["ritmo_min_km"]
    dur = t["duracao_min"]
    gps_ok = t["gps_ok"]

    # 4. distância inflada
    esperada = pc.divide(dur, ritmo)
    inflada = pc.fill_null(pc.and_(pc.greater(dur, 0),
                                   pc.greater(pc.divide(dist, esperada), RAZAO_INFLADA)), False)
    dist_nova = pc.if_else(inflada, pc.round(esperada, 2), dist)
    print(f"[4] distância inflada corrigida: {n(inflada)} linhas · "
          f"km somados bronze {pc.sum(pc.filter(dist, inflada)).as_py():,.0f} -> "
          f"prata {pc.sum(pc.filter(dist_nova, inflada)).as_py():,.0f}")

    # 5. GPS falhou
    falhou = pc.invert(gps_ok)
    com_dist = pc.and_(falhou, pc.is_valid(dist))
    dist_nova = pc.if_else(falhou, pa.scalar(None, pa.float64()), dist_nova)
    print(f"[5] GPS falhou: {n(falhou)} linhas · {n(com_dist)} tinham distância "
          f"(mediana {pc.approximate_median(pc.filter(dist, com_dist)).as_py():.2f} km) e "
          f"viram nulo")

    # 6. duração zero
    zero = pc.less_equal(dur, 0)
    recalc = pc.round(pc.multiply(dist_nova, ritmo), 1)
    teto = pc.fill_null(pc.cast(t["tipo_pt"], pa.string()), "")
    teto_val = pa.array([TETO_DURACAO.get(x) for x in teto.to_pylist()], pa.float64())
    acima = pc.fill_null(pc.greater(recalc, teto_val), False)
    recuperada = pc.and_(pc.and_(zero, pc.is_valid(recalc)), pc.invert(acima))
    zero_inflada = pc.and_(pc.and_(zero, pc.is_valid(recalc)), acima)
    dur_nova = pc.if_else(recuperada, recalc,
                          pc.if_else(zero, pa.scalar(None, pa.float64()), dur))
    dist_nova = pc.if_else(zero_inflada, pa.scalar(None, pa.float64()), dist_nova)
    print(f"[6] duração zero: {n(zero)} linhas · {n(recuperada)} recalculadas por distância x "
          f"ritmo · {n(zero_inflada)} com distância também inflada (duração e distância nulas) · "
          f"{n(zero) - n(recuperada) - n(zero_inflada)} sem GPS (duração nula)")

    # 7. treino_com
    com = pc.if_else(pc.equal(t["treino_com"], ""), pa.scalar(None, pa.string()),
                     t["treino_com"])
    print(f"[7] treinos com companhia: {n(pc.is_valid(com))}")

    # flags
    g = pa.table({"user_id": t["user_id"], "inicio_brt": t["inicio_brt"],
                  "um": pa.array([1] * t.num_rows, pa.int64())})
    cont = g.group_by(["user_id", "inicio_brt"]).aggregate([("um", "sum")])
    cont = cont.filter(pc.greater(cont["um_sum"], 1))
    # join não preserva ordem: re-ancora por posição
    g = g.append_column("pos", pa.array(range(t.num_rows), pa.int64()))
    marca = g.join(cont, ["user_id", "inicio_brt"], join_type="left outer").sort_by("pos")
    repetido = pc.is_valid(marca["um_sum"])
    print(f"flags: inicio_repetido {n(repetido)} · duracao_zero {n(zero)}")

    def flag(m):
        return pc.cast(pc.fill_null(m, False), pa.int8())

    s = pa.table({
        "atividade_id": t["atividade_id"],
        "user_id": t["user_id"],
        "inicio_brt": t["inicio_brt"],
        "mes": pc.strftime(t["inicio_brt"], "%Y-%m"),
        "inicio_bronze": t["inicio"],
        "fuso_origem": pc.if_else(pc.equal(t["origem"], "garmin"), "utc", "brt"),
        "tipo": t["tipo_pt"],
        "tipo_bronze": t["tipo"],
        "duracao_min": dur_nova,
        "duracao_min_bronze": dur,
        "distancia_km": dist_nova,
        "distancia_km_bronze": dist,
        "ritmo_min_km": ritmo,
        "fc_media": t["fc_media"],
        "origem": t["origem"],
        "gps_ok": gps_ok,
        "treino_com": com,
        "flag_duracao_zero": flag(zero),
        "flag_inicio_repetido": flag(repetido),
    }).select(COLUNAS)
    s = s.sort_by([("inicio_brt", "ascending"), ("atividade_id", "ascending")])

    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(s, SAIDA)
    print(f"prata: {s.num_rows} linhas -> {SAIDA} (bronze {total_bronze}, "
          f"-{total_bronze - s.num_rows})")
    print(f"inicio_brt: {pc.min(s['inicio_brt'])} a {pc.max(s['inicio_brt'])}")


if __name__ == "__main__":
    main()
