"""Catálogo de tags da bancada de bombeamento (>= 25 grandezas do CLP).

Os endereços das 12 primeiras tags vêm do README do projeto. As demais
(correntes S/T/N/média, tensões ST/TR, demanda e FP S/T/total) vêm dos
scripts anteriores (valor_tensoes.py / tensão.py): confirme no mapa do CLP.
"""
import math
import struct
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Tag:
    nome: str
    descricao: str
    tipo: str                 # "float32" | "uint16" | "bit"
    endereco: int
    div: float = 1.0
    unidade: str = ""
    grupo: str = ""
    bit: Optional[int] = None
    historico: bool = False   # grava no banco?
    alarme_alto: Optional[float] = None
    alarme_baixo: Optional[float] = None

    @property
    def n_regs(self):
        return 2 if self.tipo == "float32" else 1


def _f(n, d, e, div, u, g, **k): return Tag(n, d, "float32", e, div, u, g, **k)
def _i(n, d, e, div, u, g, **k): return Tag(n, d, "uint16", e, div, u, g, **k)


TAGS = [
    # Temperaturas (alarmes alto: valores sugeridos, ajuste ao motor da bancada)
    _f("bc.temp_r", "Temperatura enrolamento R", 700, 10,
       "°C", "Temperaturas", historico=True, alarme_alto=90),
    _f("bc.temp_s", "Temperatura enrolamento S", 702, 10,
       "°C", "Temperaturas", historico=True, alarme_alto=90),
    _f("bc.temp_t", "Temperatura enrolamento T", 704, 10,
       "°C", "Temperaturas", historico=True, alarme_alto=90),
    _f("bc.temp_carc", "Temperatura da carcaça", 706, 10,
       "°C", "Temperaturas", historico=True, alarme_alto=80),
    # Processo
    _f("bc.pit01", "Pressão (PIT01)", 710, 1, "bar", "Processo", historico=True),
    _f("bc.fit01", "Vazão (FIT01)", 712, 1, "L/s", "Processo", historico=True),
    _i("bc.frequencia", "Frequência", 830, 100, "Hz", "Processo", historico=True),
    _f("bc.sp_pid", "Setpoint de vazão", 1302,
       1, "L/s", "Processo", historico=True),
    Tag("bc.habilita", "Motor habilitado", "bit", 1328,
        1, "", "Processo", bit=6, historico=True),
    # Correntes
    _i("bc.corrente_r", "Corrente R", 840, 10, "A", "Elétricas", historico=True),
    _i("bc.corrente_s", "Corrente S", 841, 10, "A", "Elétricas", historico=True),
    _i("bc.corrente_t", "Corrente T", 842, 10, "A", "Elétricas", historico=True),
    _i("bc.corrente_n", "Corrente neutro", 843, 10, "A", "Elétricas"),
    _i("bc.corrente_media", "Corrente média", 845, 10, "A", "Elétricas"),
    # Tensões
    _i("bc.tensao_rs", "Tensão R-S", 847, 10, "V", "Elétricas", historico=True),
    _i("bc.tensao_st", "Tensão S-T", 848, 10, "V", "Elétricas"),
    _i("bc.tensao_tr", "Tensão T-R", 849, 10, "V", "Elétricas"),
    # Fator de potência
    _i("bc.fp_r", "Fator de potência R", 868, 1000, "", "Fator de potência"),
    _i("bc.fp_s", "Fator de potência S", 869, 1000, "", "Fator de potência"),
    _i("bc.fp_t", "Fator de potência T", 870, 1000, "", "Fator de potência"),
    _i("bc.fp_total", "Fator de potência total", 871,
       1000, "", "Fator de potência", historico=True),
    # Demanda
    _i("bc.demanda_ant", "Demanda anterior", 1204, 10, "kW", "Demanda"),
    _i("bc.demanda_atual", "Demanda atual", 1205,
       10, "kW", "Demanda", historico=True),
    _i("bc.demanda_media", "Demanda média", 1206, 10, "kW", "Demanda"),
    _i("bc.demanda_pico", "Demanda de pico", 1207, 10, "kW", "Demanda"),
    _i("bc.demanda_prev", "Demanda prevista", 1208, 10, "kW", "Demanda"),
]

TAGS_POR_NOME = {t.nome: t for t in TAGS}
TAG_SETPOINT = TAGS_POR_NOME["bc.sp_pid"]
TAG_HABILITA = TAGS_POR_NOME["bc.habilita"]


def agrupar_blocos(tags=TAGS, max_gap=3, max_regs=100):
    """Junta endereços próximos em poucas leituras: [(inicio, quantidade)]."""
    blocos = []
    for t in sorted(tags, key=lambda x: x.endereco):
        ini, fim = t.endereco, t.endereco + t.n_regs
        if blocos and ini <= blocos[-1][1] + max_gap and fim - blocos[-1][0] <= max_regs:
            blocos[-1][1] = max(blocos[-1][1], fim)
        else:
            blocos.append([ini, fim])
    return [(i, f - i) for i, f in blocos]


def decodificar(tag, mapa):
    """mapa: {endereço: palavra de 16 bits}. Float32 big-endian (palavra alta primeiro)."""
    try:
        if tag.tipo == "float32":
            raw = (mapa[tag.endereco] << 16) | mapa[tag.endereco + 1]
            v = struct.unpack(">f", struct.pack(">I", raw))[0]
            return v / tag.div if math.isfinite(v) else None
        palavra = mapa[tag.endereco]
        if tag.tipo == "bit":
            return float((palavra >> tag.bit) & 1)
        return palavra / tag.div
    except KeyError:
        return None


def estado_alarme(tag, valor):
    """Retorna "", "ALTO" ou "BAIXO"."""
    if valor is None:
        return ""
    if tag.alarme_alto is not None and valor >= tag.alarme_alto:
        return "ALTO"
    if tag.alarme_baixo is not None and valor <= tag.alarme_baixo:
        return "BAIXO"
    return ""
