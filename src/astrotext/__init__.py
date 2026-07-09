"""AstroText — plain-text astrology chart engine for AI agents.

Layer map (see docs/PLAN.md):
  timespace  L0  local time -> UTC -> JD(UT/TT), places, timezones, LMT
  ephem      L0  backend-dispatched engine (default de440: DE440+ERFA
                 kernel; optional swiss reference) — positions, speeds,
                 declinations
  core       L1  charts: houses, angles, aspects, dignities
  techniques L2  transits, progressions, returns, time-lord systems
  profiles   L3  tradition presets (modern / hellenistic / vedic)
  render     L4  deterministic plain-text + JSON output, round-trip parser
  verify         cross-checks against the swetest reference CLI
"""

__version__ = "2.0.0"

ENGINE_NAME = "astrotext"
