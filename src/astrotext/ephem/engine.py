"""L0 ephemeris engine — backend-dispatched.

Backends (KERNEL.md; selectable per instance or via ASTROTEXT_BACKEND):

* ``de440`` (default since engine 2.0): the in-repo kernel — DE440
  excerpt via jplephem, ERFA reductions, own houses/sidereal/star/
  rise-set implementations.  Permissively licensed end to end; needs no
  Swiss Ephemeris code or data.  Parity vs SE is verified module by
  module in tools/verify_kernel.py with measured, attributed gates.
* ``swiss``: the original Swiss Ephemeris wrapper (AGPL; dev/verify
  profile only — requires the vendored pyswisseph and .se1 data files).
  Kept as a cross-implementation reference, excluded from wheels.

Conventions (both backends): apparent geocentric positions on the
ecliptic of date with speeds — astro.com defaults.  Sidereal is a flag,
not a fork.  Time scales and calendars always come from
kernel.timescales (SE-parity ≤0.25 ms, K1); house mathematics is the
kernel's for de440 and Swiss Ephemeris' own for swiss.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .. import config
from .points import REGISTRY, SE_POINTS, get as get_point

__all__ = ["BodyState", "Ephemeris", "EphemerisDataMissing"]


class EphemerisDataMissing(RuntimeError):
    """Required ephemeris data files are absent (de440: the DE440
    excerpt; swiss: .se1 files would silently degrade to Moshier)."""


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


#: registry key → kernel dispatch ("body"/"point", kernel name)
_KERNEL_MAP = {
    "SUN": ("body", "sun"), "MOON": ("body", "moon"),
    "MERCURY": ("body", "mercury"), "VENUS": ("body", "venus"),
    "MARS": ("body", "mars"), "JUPITER": ("body", "jupiter"),
    "SATURN": ("body", "saturn"), "URANUS": ("body", "uranus"),
    "NEPTUNE": ("body", "neptune"), "PLUTO": ("body", "pluto"),
    "CHIRON": ("body", "chiron"),
    "MEAN_NODE": ("point", "mean_node"),
    "TRUE_NODE": ("point", "true_node"),
    "MEAN_APOGEE": ("point", "mean_apogee"),
}

_AYANAMSA_MAP = {"lahiri": "lahiri", "krishnamurti": "krishnamurti",
                 "raman": "raman", "fagan-bradley": "fagan_bradley"}


class Ephemeris:
    """One engine per process.  ``backend`` defaults to
    ``$ASTROTEXT_BACKEND`` or "de440"."""

    SIDEREAL_MODES = _AYANAMSA_MAP          # name -> kernel mode key

    def __init__(self, ephe_path: str | Path | None = None,
                 strict_files: bool = True, backend: str | None = None):
        self.backend = (backend or os.environ.get("ASTROTEXT_BACKEND")
                        or "de440").lower()
        if self.backend not in ("de440", "swiss"):
            raise ValueError(f"unknown backend {self.backend!r}")
        self.strict_files = strict_files
        self.sidereal_mode: str | None = None
        if self.backend == "swiss":
            import swisseph as swe
            self._swe = swe
            self.ephe_path = Path(ephe_path) if ephe_path else config.ephe_path()
            swe.set_ephe_path(str(self.ephe_path))
            self.se_version = f"swisseph {swe.version}"
            if strict_files:
                xx, retflags = swe.calc_ut(2451545.0, swe.MOON,
                                           swe.FLG_SWIEPH | swe.FLG_SPEED)
                if not retflags & swe.FLG_SWIEPH:
                    raise EphemerisDataMissing(
                        f"Swiss Ephemeris data files not found under "
                        f"{self.ephe_path} (fell back to Moshier). "
                        f"Run `make vendor`.")
        else:
            self._swe = None
            self.ephe_path = config.kernel_data_path()
            bsp = self.ephe_path / "de440_1799_2400.bsp"
            if strict_files and not bsp.exists():
                raise EphemerisDataMissing(
                    f"DE440 excerpt not found: {bsp} — run "
                    f"tools/fetch_kernel_data.py")
            self.se_version = "kernel de440 (jplephem+erfa)"

    # -- sidereal ------------------------------------------------------------
    def configure_sidereal(self, mode: str = "lahiri") -> None:
        """Select the ayanamsa for all subsequent sidereal=True calls."""
        key = mode.lower()
        if key not in _AYANAMSA_MAP:
            raise ValueError(f"unknown ayanamsa {mode!r}; "
                             f"known: {', '.join(_AYANAMSA_MAP)}")
        if self.backend == "swiss":
            sidm = {"lahiri": self._swe.SIDM_LAHIRI,
                    "krishnamurti": self._swe.SIDM_KRISHNAMURTI,
                    "raman": self._swe.SIDM_RAMAN,
                    "fagan-bradley": self._swe.SIDM_FAGAN_BRADLEY}[key]
            self._swe.set_sid_mode(sidm, 0.0, 0.0)
        self.sidereal_mode = key

    def _require_sid(self) -> str:
        if self.sidereal_mode is None:
            raise RuntimeError("sidereal computation requested before "
                               "configure_sidereal()")
        return _AYANAMSA_MAP[self.sidereal_mode]

    def ayanamsa(self, jd_ut: float) -> float:
        """Ayanamsa (degrees) of the configured mode — swe_get_ayanamsa_ut
        parity, i.e. the MEAN (no-nutation) flavour."""
        mode = self._require_sid()
        if self.backend == "swiss":
            return self._swe.get_ayanamsa_ut(jd_ut)
        from ..kernel import sidereal as ks
        from ..kernel import timescales as ts
        return ks.ayanamsa_deg(ts.ut1_to_tt(jd_ut, "swieph"), mode, False)

    # -- states ----------------------------------------------------------
    def state(self, jd_ut: float, key: str, frame: str = "of-date",
              sidereal: bool = False) -> BodyState:
        """Compute a point by registry key (derived points like
        SOUTH_NODE_* are assembled in the core layer).

        ``frame="fixed"`` gives mean-J2000, nutation-free longitudes
        (precession-corrected returns).  ``sidereal=True`` subtracts
        the configured ayanamsa natively (never mix flavours by hand)."""
        p = get_point(key)
        if p.se_id is None:
            raise ValueError(
                f"{key} is a derived point; compute {p.derived_from} instead")
        if self.backend == "swiss":
            return self._state_swiss(jd_ut, key, p.se_id, frame, sidereal)
        return self._state_de440(jd_ut, key, frame, sidereal)

    def _state_swiss(self, jd_ut, key, se_id, frame, sidereal) -> BodyState:
        swe = self._swe
        flags = swe.FLG_SWIEPH | swe.FLG_SPEED
        if frame == "fixed":
            flags |= swe.FLG_J2000 | swe.FLG_NONUT
        if sidereal:
            self._require_sid()
            flags |= swe.FLG_SIDEREAL
        ecl, rf = swe.calc_ut(jd_ut, se_id, flags)
        if self.strict_files and not rf & swe.FLG_SWIEPH:
            raise EphemerisDataMissing(
                f"fell back to Moshier for body {se_id} at JD {jd_ut} "
                f"(outside data-file range {config.EPHE_RANGE_YEARS}?)")
        equ, _ = swe.calc_ut(jd_ut, se_id, flags | swe.FLG_EQUATORIAL)
        return BodyState(
            key=key, jd_ut=jd_ut,
            lon=ecl[0], lat=ecl[1], dist_au=ecl[2],
            lon_speed=ecl[3], lat_speed=ecl[4], dist_speed=ecl[5],
            ra=equ[0], dec=equ[1], ra_speed=equ[3], dec_speed=equ[4])

    def _state_de440(self, jd_ut, key, frame, sidereal) -> BodyState:
        from ..kernel import bodies as kb
        from ..kernel import points as kp
        from ..kernel import timescales as ts
        jd_tt = ts.ut1_to_tt(jd_ut, "swieph")
        kind, name = _KERNEL_MAP[key]
        if kind == "body":
            kf = "j2000" if frame == "fixed" else "of-date"
            a = kb.apparent_with_speed(name, jd_tt, frame=kf)
        else:
            if frame == "fixed":
                raise ValueError(
                    f"fixed-frame not supported for derived point {key}")
            a = kp.apparent_with_speed(name, jd_tt)
        lon, lon_speed = a.lon, a.lon_speed
        if sidereal:
            from ..kernel import sidereal as ks
            mode = self._require_sid()
            lon = ks.sidereal_lon(lon, jd_tt, mode)
            lon_speed = lon_speed - ks.ayanamsa_speed(jd_tt, mode)
        return BodyState(
            key=key, jd_ut=jd_ut,
            lon=float(lon), lat=float(a.lat), dist_au=float(a.dist),
            lon_speed=float(lon_speed), lat_speed=float(a.lat_speed),
            dist_speed=float(a.dist_speed),
            ra=float(a.ra), dec=float(a.dec),
            ra_speed=float(a.ra_speed), dec_speed=float(a.dec_speed))

    def states(self, jd_ut: float, keys: tuple[str, ...] = SE_POINTS
               ) -> dict[str, BodyState]:
        return {k: self.state(jd_ut, k) for k in keys}

    def lon(self, jd_ut: float, key: str, frame: str = "of-date",
            sidereal: bool = False) -> float:
        """Longitude-only fast path for root-finding loops (skips the
        five-sample speed stencil: ~5x cheaper under de440; swiss falls
        back to state())."""
        if self.backend == "swiss":
            return self.state(jd_ut, key, frame, sidereal).lon
        from ..kernel import bodies as kb
        from ..kernel import points as kp
        from ..kernel import timescales as ts
        jd_tt = ts.ut1_to_tt(jd_ut, "swieph")
        kind, name = _KERNEL_MAP[key]
        if kind == "body":
            kf = "j2000" if frame == "fixed" else "of-date"
            lon = float(np.atleast_1d(kb.apparent(name, jd_tt, frame=kf).lon)[0])
        else:
            lon = float(np.atleast_1d(kp.apparent(name, jd_tt).lon)[0])
        if sidereal:
            from ..kernel import sidereal as ks
            lon = float(ks.sidereal_lon(lon, jd_tt, self._require_sid()))
        return lon

    # -- houses ------------------------------------------------------------
    def houses(self, jd_ut: float, lat: float, lon: float, hsys: str = "P",
               sidereal: bool = False
               ) -> tuple[tuple[float, ...], dict[str, float]]:
        """House cusps (1..12) and named angles.  Raises on polar failure
        (Placidus/Koch beyond the polar circles); the core layer decides
        the fallback policy."""
        if self.backend == "swiss":
            swe = self._swe
            flag = 0
            if sidereal:
                self._require_sid()
                flag = swe.FLG_SIDEREAL
            cusps, ascmc = swe.houses_ex(jd_ut, lat, lon,
                                         hsys.encode("ascii"), flag)
            angles = {"ASC": ascmc[0], "MC": ascmc[1], "ARMC": ascmc[2],
                      "VERTEX": ascmc[3], "EQUATORIAL_ASC": ascmc[4]}
            return tuple(cusps), angles
        from ..kernel import frames as kfr
        from ..kernel import houses as kh
        from ..kernel import timescales as ts
        import numpy as np
        jd_tt = ts.ut1_to_tt(jd_ut, "swieph")
        armc = kh.armc_deg(jd_ut, jd_tt, lon)
        eps = float(np.degrees(kfr.true_obliquity(jd_tt)))
        cusps = kh.cusps(armc, eps, lat, hsys)
        ang = kh.angles(armc, eps, lat)
        if hsys in ("R", "C"):
            ang["MC"] = cusps[9]        # measured SE per-system convention
        if sidereal:
            from ..kernel import sidereal as ks
            mode = self._require_sid()
            ay = ks.ayanamsa_deg(jd_tt, mode, True)
            cusps = tuple((c - ay) % 360.0 for c in cusps)
            for k in ("ASC", "MC", "VERTEX", "EQUATORIAL_ASC"):
                ang[k] = (ang[k] - ay) % 360.0
        return tuple(cusps), ang

    # -- observing ---------------------------------------------------------
    def star_lons(self, jd_ut: float, names: tuple[str, ...]
                  ) -> dict[str, float]:
        """Apparent ecliptic longitudes of fixed stars."""
        if self.backend == "swiss":
            out = {}
            for name in names:
                xx, _rn, _fl = self._swe.fixstar_ut(name, jd_ut,
                                                    self._swe.FLG_SWIEPH)
                out[name] = xx[0]
            return out
        from ..kernel import observing as ko
        from ..kernel import timescales as ts
        jd_tt = ts.ut1_to_tt(jd_ut, "swieph")
        return {name: float(ko.star_apparent(name, jd_tt).lon)
                for name in names}

    def next_sun_event(self, jd_ut: float, lat: float, lon: float,
                       kind: str, elevation_m: float = 0.0) -> float | None:
        """Next sunrise/sunset after jd_ut; None in circumpolar regimes."""
        if self.backend == "swiss":
            swe = self._swe
            rsmi = swe.CALC_RISE if kind == "rise" else swe.CALC_SET
            try:
                ret, tret = swe.rise_trans(jd_ut, swe.SUN, rsmi,
                                           (lon, lat, elevation_m))
            except Exception:
                return None
            return tret[0] if ret == 0 else None
        from ..kernel import observing as ko
        return ko.next_sun_event(jd_ut, lat, lon, kind)

    def true_altitude(self, jd_ut: float, ecl_lon: float, ecl_lat: float,
                      lat: float, lon: float, elevation_m: float = 0.0,
                      dist_au: float = 1.0) -> float:
        """Geocentric true altitude of an ecliptic position (sect check)."""
        if self.backend == "swiss":
            az = self._swe.azalt(jd_ut, self._swe.ECL2HOR,
                                 (lon, lat, elevation_m), 0.0, 0.0,
                                 (ecl_lon, ecl_lat, dist_au))
            return az[1]
        from ..kernel import observing as ko
        return ko.true_altitude(jd_ut, ecl_lon, ecl_lat, lat, lon)

    # -- time & frames -------------------------------------------------------
    def obliquity_true(self, jd_ut: float) -> float:
        """True obliquity of date, degrees (swe ECL_NUT[0] parity)."""
        if self.backend == "swiss":
            ecl, _ = self._swe.calc_ut(jd_ut, self._swe.ECL_NUT, 0)
            return ecl[0]
        import numpy as np
        from ..kernel import frames as kfr
        from ..kernel import timescales as ts
        return float(np.degrees(kfr.true_obliquity(
            ts.ut1_to_tt(jd_ut, "swieph"))))

    def delta_t_sec(self, jd_ut: float) -> float:
        from ..kernel import timescales as ts
        return ts.deltat_sec(jd_ut, "swieph")

    def info(self) -> dict[str, str]:
        if self.backend == "swiss":
            files = sorted(f.name for f in self.ephe_path.glob("*.se1"))
            return {"engine": "swiss", "se_version": self.se_version,
                    "ephe_path": str(self.ephe_path),
                    "ephe_files": ",".join(files) or "(none)"}
        files = sorted(f.name for f in self.ephe_path.glob("*")
                       if f.suffix in (".bsp", ".npz", ".json", ".csv"))
        return {"engine": "de440", "se_version": self.se_version,
                "ephe_path": str(self.ephe_path),
                "ephe_files": ",".join(files) or "(none)"}
