"""The sidereal Rashi chart (D1) — the base of the Vedic layer.

Conventions (all echoed in output):
* Ayanamsa: Lahiri default (Krishnamurti/Raman/Fagan-Bradley knobs), applied
  via Swiss Ephemeris' NATIVE sidereal mode — a manual "tropical minus
  ayanamsa" differs by ~nutation and is forbidden here.
* Grahas: Sun..Saturn + Rahu/Ketu.  Nodes default MEAN (the traditional
  mainstream; 'true' knob).  Ketu = Rahu + 180deg.
* Houses: whole-sign from the sidereal Lagna (Rashi bhavas).
* Sect-free: Jyotish has its own strength systems (later work); this layer
  reports positions, nakshatras, panchanga, karakas, drishti.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ...core.angles import norm360
from ...core.chart import default_ephemeris
from ...core.zodiac import deg_in_sign, sign_index
from ...ephem.engine import Ephemeris
from ...timespace.moment import Moment
from . import drishti as _drishti
from . import karakas as _karakas
from . import nakshatra as _nak
from . import panchanga as _panch

__all__ = ["VedicSettings", "Graha", "VedicChart", "compute_vedic_chart",
           "GRAHA_ORDER"]

GRAHA_ORDER = ("SUN", "MOON", "MARS", "MERCURY", "JUPITER", "VENUS",
               "SATURN", "RAHU", "KETU")

_NODE_KEY = {"mean": "MEAN_NODE", "true": "TRUE_NODE"}


@dataclass(frozen=True, slots=True)
class VedicSettings:
    ayanamsa: str = "lahiri"
    node: str = "mean"           # mean | true (traditional mainstream: mean)
    karaka_scheme: int = 8       # 8 (with Rahu) | 7
    dasha_year_days: float = 365.25   # vimshottari year length
    vargas: tuple[int, ...] = (1, 2, 3, 4, 7, 9, 10, 12, 16, 20, 24, 27,
                               30, 40, 45, 60)   # full Shodashavarga

    def describe(self) -> list[str]:
        return [
            f"ayanamsa={self.ayanamsa}",
            f"node={self.node}(Ketu=Rahu+180)",
            f"houses=whole-sign-from-Lagna",
            f"karakas={self.karaka_scheme}-scheme",
            f"dasha-year={self.dasha_year_days:g}d",
            f"vargas={','.join('D%d' % v for v in self.vargas)}",
        ]


@dataclass(frozen=True, slots=True)
class Graha:
    key: str
    lon: float                  # sidereal ecliptic longitude
    lat: float
    lon_speed: float
    retrograde: bool
    sign: int
    sign_deg: float
    house: int                  # whole-sign house from Lagna, 1..12
    nak: _nak.Nakshatra


@dataclass(frozen=True, slots=True)
class VedicChart:
    moment: Moment
    settings: VedicSettings
    ayanamsa_value: float
    grahas: dict[str, Graha]
    lagna: float | None                  # sidereal ASC
    lagna_sign: int | None
    lagna_nak: _nak.Nakshatra | None
    panchanga: _panch.Panchanga
    karakas: list[tuple[str, str, float]]
    drishti: dict[str, dict[str, object]]
    flags: tuple[str, ...]


def compute_vedic_chart(
    moment: Moment,
    settings: VedicSettings | None = None,
    eph: Ephemeris | None = None,
    unknown_time: bool = False,
) -> VedicChart:
    settings = settings or VedicSettings()
    eph = eph or default_ephemeris()
    eph.configure_sidereal(settings.ayanamsa)
    jd = moment.jd_ut
    flags: list[str] = list(moment.flags)

    # ---- grahas ---------------------------------------------------------------
    raw: dict[str, tuple[float, float, float]] = {}   # lon, lat, speed
    for key in ("SUN", "MOON", "MARS", "MERCURY", "JUPITER", "VENUS", "SATURN"):
        st = eph.state(jd, key, sidereal=True)
        raw[key] = (st.lon, st.lat, st.lon_speed)
    node = eph.state(jd, _NODE_KEY[settings.node], sidereal=True)
    raw["RAHU"] = (node.lon, node.lat, node.lon_speed)
    raw["KETU"] = (norm360(node.lon + 180.0), -node.lat, node.lon_speed)

    # ---- lagna & whole-sign houses ---------------------------------------------
    lagna = lagna_sign = None
    lagna_nak = None
    if not unknown_time:
        _cusps, named = eph.houses(jd, moment.place.lat, moment.place.lon,
                                   "W", sidereal=True)
        lagna = named["ASC"]
        lagna_sign = sign_index(lagna)
        lagna_nak = _nak.of(lagna)
    else:
        flags.append("unknown-birth-time:lagna/houses/karakas-order may shift; "
                     "Moon position is a noon estimate (moves ~13 deg/day)")

    def house_of(sign: int) -> int:
        return ((sign - lagna_sign) % 12) + 1 if lagna_sign is not None else 0

    grahas: dict[str, Graha] = {}
    for key in GRAHA_ORDER:
        lon, lat, speed = raw[key]
        s = sign_index(lon)
        grahas[key] = Graha(
            key=key, lon=lon, lat=lat, lon_speed=speed,
            retrograde=(speed < 0.0) if key not in ("RAHU", "KETU") else True,
            sign=s, sign_deg=deg_in_sign(lon),
            house=house_of(s), nak=_nak.of(lon),
        )

    # ---- panchanga, karakas, drishti ---------------------------------------------
    panch = _panch.compute(raw["SUN"][0], raw["MOON"][0])
    kar, kflags = _karakas.chara_karakas({k: raw[k][0] for k in raw},
                                         settings.karaka_scheme)
    flags.extend(kflags)
    dr = _drishti.graha_drishti({k: grahas[k].sign for k in GRAHA_ORDER})

    return VedicChart(
        moment=moment, settings=settings, ayanamsa_value=eph.ayanamsa(jd),
        grahas=grahas, lagna=lagna, lagna_sign=lagna_sign, lagna_nak=lagna_nak,
        panchanga=panch, karakas=kar, drishti=dr, flags=tuple(flags),
    )
