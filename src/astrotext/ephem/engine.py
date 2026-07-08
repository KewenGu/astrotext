"""L0 Swiss Ephemeris wrapper.

Design decisions:

* Positions are **apparent geocentric on the ecliptic of date** with speed —
  Swiss Ephemeris defaults, the same convention as astro.com and virtually
  all astrology software.  Sidereal (ayanamsa) support arrives with the
  Vedic layer as a *flag*, not a fork.
* Data-file fallback is a hard error: if the .se1 files are missing, Swiss
  Ephemeris silently degrades to the Moshier analytic theory (~0.02" planets,
  worse for the Moon).  We detect that via the returned flag word and raise —
  a quality guarantee, not an inconvenience (axiom #4).
* ``swe.set_ephe_path`` is process-global; the Ephemeris object re-asserts it
  on construction.  Not thread-safe — neither is the underlying C library.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import swisseph as swe

from .. import config
from .points import REGISTRY, SE_POINTS, get as get_point

__all__ = ["BodyState", "Ephemeris", "EphemerisDataMissing", "BASE_FLAGS"]

BASE_FLAGS = swe.FLG_SWIEPH | swe.FLG_SPEED


class EphemerisDataMissing(RuntimeError):
    """Swiss Ephemeris data files are absent and computation would silently
    fall back to the lower-precision Moshier model."""


@dataclass(frozen=True, slots=True)
class BodyState:
    """Full kinematic state of a point at one instant (degrees, AU, per-day)."""

    key: str
    jd_ut: float
    lon: float          # ecliptic longitude of date, [0, 360)
    lat: float          # ecliptic latitude
    dist_au: float
    lon_speed: float    # deg/day; negative => retrograde
    lat_speed: float
    dist_speed: float
    ra: float           # right ascension, degrees
    dec: float          # declination, degrees
    ra_speed: float
    dec_speed: float

    @property
    def retrograde(self) -> bool:
        return self.lon_speed < 0.0


class Ephemeris:
    """One engine per process. ``ephe_path`` defaults to the repo data dir."""

    def __init__(self, ephe_path: str | Path | None = None, strict_files: bool = True):
        self.ephe_path = Path(ephe_path) if ephe_path else config.ephe_path()
        swe.set_ephe_path(str(self.ephe_path))
        self.se_version: str = swe.version
        self.strict_files = strict_files
        if strict_files:
            self._assert_data_files()

    # -- internals -----------------------------------------------------------
    def _assert_data_files(self) -> None:
        # The Moon requires semo_*.se1; a fallback shows up in the flag word.
        xx, retflags = swe.calc_ut(2451545.0, swe.MOON, BASE_FLAGS)
        if not retflags & swe.FLG_SWIEPH:
            raise EphemerisDataMissing(
                f"Swiss Ephemeris data files not found under {self.ephe_path} "
                f"(computation fell back to Moshier). Run `make vendor`."
            )

    def _calc(self, jd_ut: float, se_id: int, flags: int) -> tuple[float, ...]:
        xx, retflags = swe.calc_ut(jd_ut, se_id, flags)
        if self.strict_files and not retflags & swe.FLG_SWIEPH:
            raise EphemerisDataMissing(
                f"fell back to Moshier for body {se_id} at JD {jd_ut} "
                f"(outside data-file range {config.EPHE_RANGE_YEARS}?)"
            )
        return xx

    # -- public --------------------------------------------------------------
    def state(self, jd_ut: float, key: str) -> BodyState:
        """Compute a point by registry key (Swiss-Ephemeris-backed keys only;
        derived points like SOUTH_NODE_* are assembled in the core layer)."""
        p = get_point(key)
        if p.se_id is None:
            raise ValueError(f"{key} is a derived point; compute {p.derived_from} instead")
        ecl = self._calc(jd_ut, p.se_id, BASE_FLAGS)
        equ = self._calc(jd_ut, p.se_id, BASE_FLAGS | swe.FLG_EQUATORIAL)
        return BodyState(
            key=key, jd_ut=jd_ut,
            lon=ecl[0], lat=ecl[1], dist_au=ecl[2],
            lon_speed=ecl[3], lat_speed=ecl[4], dist_speed=ecl[5],
            ra=equ[0], dec=equ[1], ra_speed=equ[3], dec_speed=equ[4],
        )

    def states(self, jd_ut: float, keys: tuple[str, ...] = SE_POINTS) -> dict[str, BodyState]:
        return {k: self.state(jd_ut, k) for k in keys}

    def houses(self, jd_ut: float, lat: float, lon: float, hsys: str = "P"
               ) -> tuple[tuple[float, ...], dict[str, float]]:
        """House cusps (1..12) and named angles for a house system letter.

        Raises on polar failure (Placidus/Koch beyond polar circles); the
        core layer decides the fallback policy.
        """
        cusps, ascmc = swe.houses_ex(jd_ut, lat, lon, hsys.encode("ascii"))
        angles = {
            "ASC": ascmc[0], "MC": ascmc[1], "ARMC": ascmc[2],
            "VERTEX": ascmc[3], "EQUATORIAL_ASC": ascmc[4],
        }
        return tuple(cusps), angles

    def delta_t_sec(self, jd_ut: float) -> float:
        return swe.deltat(jd_ut) * 86400.0

    def info(self) -> dict[str, str]:
        files = sorted(f.name for f in self.ephe_path.glob("*.se1"))
        return {
            "engine": "swisseph",
            "se_version": self.se_version,
            "ephe_path": str(self.ephe_path),
            "ephe_files": ",".join(files) or "(none)",
        }
