"""M4: the dossier generator — completeness and determinism."""
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fixtures import TIMED_NOW_UTC, TIMED_PLACE  # noqa: E402

from astrotext.dossier import Subject, generate_dossier  # noqa: E402
from astrotext.timespace import Place  # noqa: E402

SUBJECT = Subject(
    name="Dossier Test 1988",
    local=dt.datetime(1988, 6, 15, 14, 30),
    place=Place(39.9042, 116.4074, "Beijing", "Asia/Shanghai"),
)

EXPECTED = [
    "index.txt", "00_meta.txt", "10_natal.txt", "11_natal_hellenistic.txt",
    "20_transits.txt", "21_secondary.txt", "22_tertiary.txt",
    "23_solar_arc.txt", "30_solar_return.txt", "31_lunar_return.txt",
    "40_firdaria.txt", "41_profections.txt",
]


def _generate(tmp: Path, sub: Subject = SUBJECT) -> Path:
    return generate_dossier(sub, TIMED_NOW_UTC, TIMED_PLACE, tmp)


def test_dossier_complete_and_terminated(tmp_path):
    out = _generate(tmp_path / "a")
    names = sorted(p.name for p in out.glob("*.txt"))
    assert names == sorted(EXPECTED)
    for p in out.glob("*.txt"):
        text = p.read_text(encoding="utf-8")
        assert text.endswith("== END ==\n"), p.name
        assert "ASTROTEXT" in text.splitlines()[0]


def test_dossier_byte_deterministic(tmp_path):
    a = _generate(tmp_path / "a")
    b = _generate(tmp_path / "b")
    for name in EXPECTED:
        assert (a / name).read_bytes() == (b / name).read_bytes(), name


def test_dossier_unknown_time_drops_time_dependent_files(tmp_path):
    sub = Subject(
        name="Unknown Time", local=dt.datetime(1985, 10, 10, 12, 0),
        place=Place(31.2304, 121.4737, "Shanghai", "Asia/Shanghai"),
        unknown_time=True,
    )
    out = _generate(tmp_path / "u", sub)
    names = {p.name for p in out.glob("*.txt")}
    assert "40_firdaria.txt" not in names      # no sect without birth time
    assert "41_profections.txt" not in names   # no ASC without birth time
    assert "10_natal.txt" in names and "20_transits.txt" in names
    meta = (out / "00_meta.txt").read_text(encoding="utf-8")
    assert "unknown-birth-time" in meta
