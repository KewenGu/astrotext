"""Geographic places.

M0 baseline: caller supplies latitude/longitude and a timezone directly.
M1 adds an offline gazetteer (name -> lat/lon/tz, with Chinese aliases); this
dataclass is already the resolution target for it.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Place:
    """A point on Earth.

    lat: geographic latitude, degrees, north positive, [-90, +90]
    lon: geographic longitude, degrees, EAST positive, [-180, +180]
    tz:  IANA zone name ("Asia/Shanghai"), "LMT" (local mean time derived
         from ``lon``), or a fixed offset like "UTC+8", "+08:00", "UTC-3:30".
         May be None if a tz is always passed explicitly at resolve time.
    """

    lat: float
    lon: float
    name: str | None = None
    tz: str | None = None
    elevation_m: float = 0.0

    def __post_init__(self) -> None:
        if not (-90.0 <= self.lat <= 90.0):
            raise ValueError(f"latitude out of range [-90, 90]: {self.lat}")
        if not (-180.0 <= self.lon <= 180.0):
            raise ValueError(f"longitude out of range [-180, 180]: {self.lon}")

    def label(self) -> str:
        ns = "N" if self.lat >= 0 else "S"
        ew = "E" if self.lon >= 0 else "W"
        core = f"{abs(self.lat):.4f}{ns} {abs(self.lon):.4f}{ew}"
        return f"{self.name} ({core})" if self.name else core
