"""Kernel v2 — permissively-licensed computation core (KERNEL.md).

DE440 (public domain) read via jplephem (MIT), reduced with ERFA routines
via pyerfa (BSD-3).  Replaces Swiss Ephemeris as the production backend at
K7; until then this package is exercised only by its own tests and the
verify harness.

Modules
-------
timescales : UTC/TAI/TT/UT1 conversions, ΔT (SE-2.10.03 parity), calendars.
frames     : bias-precession-nutation, true obliquity, ecliptic-of-date.
bodies     : SPK-backed apparent geocentric positions (K2).

Clean-room note: written from published sources (SE manual as description,
IERS/USNO tables, IAU/ERFA documentation, Meeus) plus black-box outputs of
the vendored swetest/pyswisseph — the SE source tree stays closed
(KERNEL.md §11).
"""
from __future__ import annotations
