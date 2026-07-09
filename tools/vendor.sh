#!/usr/bin/env bash
# Fetch + build third-party components from pinned sources.
#
# Two profiles (KERNEL.md §11):
#
#   bash tools/vendor.sh                 # DEFAULT — de440 kernel only.
#       Permissively-licensed stack: kernel Python deps (numpy, jplephem
#       MIT, pyerfa BSD-3), the DE440 excerpt, and pure-python pytest.
#       NO Swiss Ephemeris code or data — this is what ships.
#
#   bash tools/vendor.sh --with-swiss    # DEV/VERIFY — adds the AGPL
#       reference: builds pyswisseph + swetest and fetches the .se1
#       ephemeris data.  Enables `backend="swiss"` and tests/cross/.
#       Never included in wheels/releases.
#
# The dev environment's network policy blocks PyPI/npm but reaches GitHub
# and JPL/VizieR, so third-party code is built from source; Python deps
# come from vendor/sdists/ when present, else pip.  Run from repo root.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$PWD"

WITH_SWISS=0
for arg in "$@"; do
  case "$arg" in
    --with-swiss) WITH_SWISS=1 ;;
    *) echo "unknown flag: $arg (use --with-swiss)"; exit 2 ;;
  esac
done

mkdir -p vendor/src vendor/py vendor/lib vendor/sdists data/ephe data/kernel

# ---- pinned versions --------------------------------------------------------
PYSWISSEPH_REPO=https://github.com/astrorigin/pyswisseph
PYSWISSEPH_COMMIT=91ec65631badc7faf4a4b913570c944a4c1b101d   # v2.10.3.2 + master
SWISSEPH_REPO=https://github.com/aloistr/swisseph
SWISSEPH_COMMIT=59ac051b5a5812c684973ca0fcedb1c8c3e9c5dc     # SE 2.10.03 official
PYTEST_TAG=8.4.2
PLUGGY_TAG=1.6.0
INICONFIG_TAG=v2.1.0

# ---- kernel Python deps (permissive): numpy, jplephem, pyerfa ---------------
# Prefer vendored sdists/wheels (offline); fall back to pip.  These are the
# only runtime deps of the default de440 backend.
echo "== default profile: kernel deps + data =="
if ls vendor/sdists/pyerfa* vendor/sdists/jplephem* >/dev/null 2>&1; then
  python3 -m pip install --no-index --find-links vendor/sdists \
      numpy jplephem pyerfa 2>/dev/null \
    || python3 -m pip install vendor/sdists/pyerfa*.whl vendor/sdists/jplephem*.tar.gz \
    || echo "WARN: vendored kernel deps not installed; try: pip install numpy jplephem pyerfa"
else
  python3 -m pip install numpy jplephem pyerfa \
    || echo "WARN: could not pip install numpy jplephem pyerfa (offline?)"
fi

# ---- DE440 excerpt (JPL, public domain) -------------------------------------
if [ ! -f data/kernel/de440_1799_2400.bsp ]; then
  echo "fetching DE440 excerpt (~65 MB) ..."
  python3 tools/fetch_kernel_data.py \
    || echo "WARN: DE440 excerpt not fetched; run tools/fetch_kernel_data.py on a networked machine"
fi
# chiron_horizons.npz, hipparcos_22.json, se_deltat_parity.csv are committed
# (small, public-domain / free-use, cited).  Regenerate with the fetch_*.py
# tools only when refreshing solutions.

# ---- pytest + deps, vendored as pure-python sources (no pip needed) ---------
clone_tag () { [ -d "vendor/src/$2" ] || git clone --depth 1 --branch "$3" "https://github.com/$1/$2" "vendor/src/$2"; }
clone_tag pytest-dev pytest    "$PYTEST_TAG"
clone_tag pytest-dev pluggy    "$PLUGGY_TAG"
clone_tag pytest-dev iniconfig "$INICONFIG_TAG"
cp -r vendor/src/pytest/src/pytest vendor/src/pytest/src/_pytest vendor/src/pytest/src/py.py \
      vendor/src/pluggy/src/pluggy vendor/src/iniconfig/src/iniconfig vendor/py/
printf '__version__ = version = "%s"\nversion_tuple = (%s)\n' "$PYTEST_TAG" "$(echo "$PYTEST_TAG" | tr . ,)" > vendor/py/_pytest/_version.py
printf '__version__ = version = "%s"\nversion_tuple = (%s)\n' "$PLUGGY_TAG" "$(echo "$PLUGGY_TAG" | tr . ,)" > vendor/py/pluggy/_version.py
printf '__version__ = version = "2.1.0"\n' > vendor/py/iniconfig/_version.py

# ---- provenance (default) ---------------------------------------------------
{
  echo "# Vendored components (pinned)"
  echo "# --- kernel v2 (default profile; permissive) ---"
  echo "jplephem    2.24    (MIT)"
  echo "pyerfa      2.0.1.5 (BSD-3; bundles ERFA C)"
  echo "de440.bsp   excerpt 1799-2400 (JPL, public domain; tools/fetch_kernel_data.py)"
  echo "pytest      $PYTEST_TAG | pluggy $PLUGGY_TAG | iniconfig $INICONFIG_TAG (MIT)"
} > vendor/PINS.txt

if [ "$WITH_SWISS" -eq 0 ]; then
  echo
  echo "vendor OK (default / de440).  No Swiss Ephemeris code or data."
  echo "Verify:  python tools/check_no_swiss.py"
  PYTHONPATH=vendor/py python3 -m pytest --version
  exit 0
fi

# ============================================================================
#  --with-swiss : AGPL reference harness (dev/verify only; never shipped)
# ============================================================================
echo
echo "== --with-swiss: building the AGPL Swiss Ephemeris reference =="

# ---- pyswisseph (C extension, built with system gcc) ------------------------
if [ ! -d vendor/src/pyswisseph ]; then
  git clone --depth 1 "$PYSWISSEPH_REPO" vendor/src/pyswisseph
fi
# --recursive matters: swephelp nests a sqlite3 submodule. On systems
# without libsqlite3-dev (typical macOS), setup.py falls back to compiling
# swephelp/sqlite3/sqlite3.c — which only exists after a recursive init.
(cd vendor/src/pyswisseph && git submodule update --init --recursive --depth 1) \
  || { echo "WARN: recursive submodule fetch failed; falling back (needs system libsqlite3-dev)"; \
       (cd vendor/src/pyswisseph && git submodule update --init --depth 1) || true; }
(cd vendor/src/pyswisseph && python3 setup.py -q build_ext --inplace)
cp vendor/src/pyswisseph/swisseph.cpython-*.so vendor/lib/

# ---- official swisseph: ephemeris data files + swetest reference CLI --------
if [ ! -d vendor/src/swisseph ]; then
  git clone --filter=blob:none --no-checkout --depth 1 "$SWISSEPH_REPO" vendor/src/swisseph
  (cd vendor/src/swisseph \
    && git sparse-checkout init --no-cone \
    && git sparse-checkout set '/*.c' '/*.h' '/Makefile' \
         '/ephe/sepl_18.se1' '/ephe/semo_18.se1' '/ephe/seas_18.se1' '/ephe/sefstars.txt' \
    && git checkout -q)
fi
(cd vendor/src/swisseph && make -s swetest)
cp vendor/src/swisseph/swetest vendor/lib/
# macOS (esp. Apple Silicon) kills unsigned/invalidly-signed Mach-O binaries
# with SIGKILL at exec; ad-hoc re-sign and clear any quarantine so the freshly
# built swetest runs.  No-ops off macOS.
if command -v codesign >/dev/null 2>&1; then
  xattr -cr vendor/lib/swetest 2>/dev/null || true
  codesign --force --sign - vendor/lib/swetest 2>/dev/null \
    || echo "WARN: could not ad-hoc sign swetest; if it is SIGKILLed, run: codesign --force --sign - vendor/lib/swetest"
fi
cp vendor/src/swisseph/ephe/* data/ephe/
# extended range 1200-1799 (optional; some proxies block large blob fetches)
(cd vendor/src/swisseph \
  && git sparse-checkout add '/ephe/sepl_12.se1' '/ephe/semo_12.se1' '/ephe/seas_12.se1' \
  && cp ephe/*_12.se1 ../../../data/ephe/) \
  || echo "WARN: extended ephemeris (1200-1799) not fetched; swiss range stays 1800-2399"

# ---- append swiss provenance ------------------------------------------------
{
  echo "# --- swiss reference (--with-swiss; AGPL; dev/verify only, not shipped) ---"
  echo "pyswisseph  $PYSWISSEPH_REPO @ $(cd vendor/src/pyswisseph && git rev-parse HEAD)"
  echo "  libswe    $(cd vendor/src/pyswisseph/libswe && git rev-parse HEAD)"
  echo "  swephelp  $(cd vendor/src/pyswisseph/swephelp && git rev-parse HEAD)"
  echo "swisseph    $SWISSEPH_REPO @ $(cd vendor/src/swisseph && git rev-parse HEAD)"
  echo "ephemeris   data/ephe/{sepl_18,semo_18,seas_18}.se1 + sefstars.txt (SE 2.10.03, 1800-2399)"
} >> vendor/PINS.txt

echo
echo "vendor OK (--with-swiss).  Swiss Ephemeris is AGPL — dev/verify only,"
echo "excluded from wheels/releases.  Reference gate:  make verify"
PYTHONPATH=vendor/py:vendor/lib python3 -m pytest --version
