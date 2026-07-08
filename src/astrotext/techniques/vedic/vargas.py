"""Shodashavarga — the 16 divisional charts (BPHS ch. 6, Parashara rules).

Every varga maps a sidereal longitude to a SIGN (divisional charts have no
degrees in mainstream practice; the part index is retained for reference).
Sign counting below is 0-based internal (0=Aries); "counted from X" means
part 0 lands in X.

Rules implemented (variants noted; adversarially re-derived in review):
  D1  Rashi        identity
  D2  Hora         15deg halves; odd signs: 1st half Leo, 2nd Cancer;
                   even signs reversed (Parashara hora — only Leo/Cancer)
  D3  Drekkana     10deg thirds -> 1st/5th/9th from the sign
  D4  Chaturthamsa 7.5deg quarters -> 1st/4th/7th/10th from the sign
  D7  Saptamsa     odd: counted from the sign; even: from the 7th from it
  D9  Navamsa      3deg20 ninths; universal formula (sign*9 + part) % 12
                   (equivalent to the fire->Aries / earth->Capricorn /
                   air->Libra / water->Cancer element rule)
  D10 Dashamsa     3deg tenths; odd: from the sign; even: from the 9th
  D12 Dwadashamsa  2.5deg twelfths, counted from the sign
  D16 Shodashamsa  movable: from Aries; fixed: from Leo; dual: from Sagittarius
  D20 Vimshamsa    movable: Aries; fixed: Sagittarius; dual: Leo
  D24 Chaturvimshamsa  odd: from Leo; even: from Cancer
  D27 Bhamsa       fire: Aries; earth: Cancer; air: Libra; water: Capricorn
  D30 Trimshamsa   irregular spans; odd: Mars5/Sat5/Jup8/Mer7/Ven5 ->
                   Ari/Aqu/Sag/Gem/Lib; even: Ven5/Mer7/Jup8/Sat5/Mars5 ->
                   Tau/Vir/Pis/Cap/Sco
  D40 Khavedamsa   odd: from Aries; even: from Libra
  D45 Akshavedamsa movable: Aries; fixed: Leo; dual: Sagittarius
  D60 Shashtiamsa  0.5deg parts, counted from the sign itself
"""
from __future__ import annotations

from ...core.angles import norm360
from ...core.zodiac import deg_in_sign, sign_index

__all__ = ["VARGA_NAMES", "varga_sign", "varga_table", "vargottama"]

VARGA_NAMES = {
    1: "Rashi", 2: "Hora", 3: "Drekkana", 4: "Chaturthamsa", 7: "Saptamsa",
    9: "Navamsa", 10: "Dashamsa", 12: "Dwadashamsa", 16: "Shodashamsa",
    20: "Vimshamsa", 24: "Chaturvimshamsa", 27: "Bhamsa", 30: "Trimshamsa",
    40: "Khavedamsa", 45: "Akshavedamsa", 60: "Shashtiamsa",
}

#: D30 spans: (upper_limit_deg, target_sign) for odd and even signs
_D30_ODD = [(5, 0), (10, 10), (18, 8), (25, 2), (30, 6)]    # Ari Aqu Sag Gem Lib
_D30_EVEN = [(5, 1), (12, 5), (20, 11), (25, 9), (30, 7)]   # Tau Vir Pis Cap Sco

#: start sign per modality (movable/fixed/dual), used by D16/D45 and D20
_START_MFD_16_45 = {0: 0, 1: 4, 2: 8}     # Aries / Leo / Sagittarius
_START_MFD_20 = {0: 0, 1: 8, 2: 4}        # Aries / Sagittarius / Leo
#: start sign per element, used by D27
_START_ELEMENT_27 = {0: 0, 1: 3, 2: 6, 3: 9}  # Ari / Can / Lib / Cap


def varga_sign(sid_lon: float, d: int) -> tuple[int, int]:
    """(sign 0..11, part index) of a sidereal longitude in divisional chart D<d>."""
    lon = norm360(sid_lon)
    sign = sign_index(lon)
    deg = deg_in_sign(lon)
    odd = sign % 2 == 0          # Aries=0 is an ODD sign (1st)

    if d == 1:
        return sign, 0
    if d == 2:
        part = int(deg // 15.0)
        first, second = (4, 3) if odd else (3, 4)   # Leo/Cancer or Cancer/Leo
        return (first if part == 0 else second), part
    if d == 3:
        part = int(deg // 10.0)
        return (sign + 4 * part) % 12, part
    if d == 4:
        part = int(deg // 7.5)
        return (sign + 3 * part) % 12, part
    if d == 7:
        part = int(deg // (30.0 / 7.0))
        start = sign if odd else (sign + 6) % 12
        return (start + part) % 12, part
    if d == 9:
        part = int(deg // (30.0 / 9.0))
        return (sign * 9 + part) % 12, part
    if d == 10:
        part = int(deg // 3.0)
        start = sign if odd else (sign + 8) % 12
        return (start + part) % 12, part
    if d == 12:
        part = int(deg // 2.5)
        return (sign + part) % 12, part
    if d == 16:
        part = int(deg // (30.0 / 16.0))
        return (_START_MFD_16_45[sign % 3] + part) % 12, part
    if d == 20:
        part = int(deg // 1.5)
        return (_START_MFD_20[sign % 3] + part) % 12, part
    if d == 24:
        part = int(deg // 1.25)
        start = 4 if odd else 3                      # Leo / Cancer
        return (start + part) % 12, part
    if d == 27:
        part = int(deg // (30.0 / 27.0))
        return (_START_ELEMENT_27[sign % 4] + part) % 12, part
    if d == 30:
        table = _D30_ODD if odd else _D30_EVEN
        for i, (limit, target) in enumerate(table):
            if deg < limit:
                return target, i
        return table[-1][1], len(table) - 1
    if d == 40:
        part = int(deg // 0.75)
        start = 0 if odd else 6                      # Aries / Libra
        return (start + part) % 12, part
    if d == 45:
        part = int(deg // (30.0 / 45.0))
        return (_START_MFD_16_45[sign % 3] + part) % 12, part
    if d == 60:
        part = int(deg // 0.5)
        return (sign + part) % 12, part
    raise ValueError(f"unsupported varga D{d}")


def varga_table(sid_lons: dict[str, float], vargas: tuple[int, ...]
                ) -> dict[str, dict[int, int]]:
    """{graha: {d: sign}} for the requested divisional charts."""
    return {g: {d: varga_sign(lon, d)[0] for d in vargas}
            for g, lon in sid_lons.items()}


def vargottama(sid_lon: float) -> bool:
    """A point is vargottama when its D1 and D9 signs coincide."""
    return varga_sign(sid_lon, 1)[0] == varga_sign(sid_lon, 9)[0]
