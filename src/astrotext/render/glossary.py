"""EN->ZH terminology table, rendered once per dossier (00_meta).

The dossier data itself is English (compact, unambiguous); this table lets a
Chinese-writing interpretation agent translate consistently.
"""
from __future__ import annotations

from ..core.zodiac import SIGNS_ABBR, SIGNS_EN, SIGNS_ZH
from ..ephem.points import ORDER, REGISTRY

TERMS: list[tuple[str, str]] = [
    # chart kinds
    ("natal", "本命盘"), ("transits", "行运盘"),
    ("secondary progressions", "次限推运"), ("tertiary progressions", "三限推运"),
    ("solar arc", "太阳弧"), ("solar return", "太阳返照(日返)"),
    ("lunar return", "月亮返照(月返)"), ("firdaria", "法达"),
    ("profections", "小限"),
    # structure
    ("ascendant (ASC)", "上升点"), ("midheaven (MC)", "天顶"),
    ("descendant (DSC)", "下降点"), ("imum coeli (IC)", "天底"),
    ("vertex", "宿命点"), ("house", "宫位"), ("cusp", "宫头"),
    ("angles", "四轴"),
    # aspects
    ("conjunction (con)", "合相"), ("sextile (sex)", "六分相"),
    ("square (squ)", "刑相(四分相)"), ("trine (tri)", "拱相(三分相)"),
    ("opposition (opp)", "冲相(对分相)"),
    ("semisextile (ssx)", "十二分相"), ("semisquare (ssq)", "八分相"),
    ("sesquiquadrate (sqq)", "补八分相"), ("quincunx (qcx)", "梅花相(150度)"),
    ("orb", "容许度"), ("applying (A)", "入相"), ("separating (S)", "出相"),
    ("exact (E)", "正相位"),
    # states
    ("retrograde (R)", "逆行"), ("out of bounds (OOB)", "出界(赤纬超黄赤交角)"),
    ("declination", "赤纬"), ("sect", "昼夜区分"),
    ("day chart", "日生盘"), ("night chart", "夜生盘"),
    # dignities
    ("domicile", "入庙"), ("exaltation", "入旺"), ("triplicity", "三分性"),
    ("bound (Egyptian term)", "界(埃及界)"), ("decan / face", "面(十度区间)"),
    ("detriment", "落陷"), ("fall", "入弱"), ("peregrine", "游离(无必然尊贵)"),
    ("mutual reception", "互溶接纳"), ("dispositor", "定位星"),
    ("final dispositor", "最终定位星"),
    # lots & cycles
    ("Lot of Fortune", "福点"), ("Lot of Spirit", "精神点"),
    ("antiscia", "映点"), ("contra-antiscia", "反映点"),
    ("planetary day/hour", "行星日/行星时"),
    ("waxing", "盈(增光)"), ("waning", "亏(减光)"),
    ("new moon", "新月"), ("full moon", "满月"),
    ("elongation", "月日距角"), ("illumination", "照明度"),
    # time
    ("LMT (local mean time)", "地方平时"), ("delta-T", "ΔT(地球自转不均修正)"),
    ("Julian day (JD)", "儒略日"), ("julian calendar", "儒略历"),
]


def render_glossary() -> str:
    L = ["-- GLOSSARY (en = zh) --"]
    for key in ORDER:
        p = REGISTRY[key]
        L.append(f"{key} ({p.en}) = {p.zh}")
    for abbr, en, zh in zip(SIGNS_ABBR, SIGNS_EN, SIGNS_ZH):
        L.append(f"{abbr} ({en}) = {zh}")
    for en, zh in TERMS:
        L.append(f"{en} = {zh}")
    return "\n".join(L) + "\n"
