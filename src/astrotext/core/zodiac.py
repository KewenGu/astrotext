"""Zodiac sign tables and helpers (tropical/sidereal agnostic: they operate on
whatever longitude they are given)."""
from __future__ import annotations

from .angles import norm360

SIGNS_EN = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]
SIGNS_ABBR = [
    "Ari", "Tau", "Gem", "Can", "Leo", "Vir",
    "Lib", "Sco", "Sag", "Cap", "Aqu", "Pis",
]
SIGNS_ZH = [
    "白羊座", "金牛座", "双子座", "巨蟹座", "狮子座", "处女座",
    "天秤座", "天蝎座", "射手座", "摩羯座", "水瓶座", "双鱼座",
]

ELEMENTS = ["fire", "earth", "air", "water"]          # sign i -> ELEMENTS[i % 4]
MODALITIES = ["cardinal", "fixed", "mutable"]         # sign i -> MODALITIES[i % 3]


def sign_index(lon: float) -> int:
    """0=Aries .. 11=Pisces for an ecliptic longitude."""
    return int(norm360(lon) // 30.0) % 12


def deg_in_sign(lon: float) -> float:
    """Degrees inside the sign, [0, 30)."""
    return norm360(lon) % 30.0


def element(sign: int) -> str:
    return ELEMENTS[sign % 4]


def modality(sign: int) -> str:
    return MODALITIES[sign % 3]
