import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / "src", ROOT / "vendor" / "py", ROOT / "vendor" / "lib"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
os.environ.setdefault("SE_EPHE_PATH", str(ROOT / "data" / "ephe"))


@pytest.fixture(scope="session")
def eph():
    from astrotext.ephem import Ephemeris
    return Ephemeris()
