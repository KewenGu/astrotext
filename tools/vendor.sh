#!/usr/bin/env bash
# Fetch + build all third-party components from pinned sources.
# Network policy of the dev environment blocks PyPI/npm; GitHub is reachable,
# so everything is built from source. Run from repo root:  bash tools/vendor.sh
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$PWD"
mkdir -p vendor/src vendor/py vendor/lib data/ephe

# ---- pinned versions --------------------------------------------------------
PYSWISSEPH_REPO=https://github.com/astrorigin/pyswisseph
PYSWISSEPH_COMMIT=91ec65631badc7faf4a4b913570c944a4c1b101d   # v2.10.3.2 + master
SWISSEPH_REPO=https://github.com/aloistr/swisseph
SWISSEPH_COMMIT=59ac051b5a5812c684973ca0fcedb1c8c3e9c5dc     # SE 2.10.03 official
PYTEST_TAG=8.4.2
PLUGGY_TAG=1.6.0
INICONFIG_TAG=v2.1.0

# ---- pyswisseph (C extension, built with system gcc) ------------------------
if [ ! -d vendor/src/pyswisseph ]; then
  git clone --depth 1 "$PYSWISSEPH_REPO" vendor/src/pyswisseph
  (cd vendor/src/pyswisseph && git submodule update --init --depth 1)
fi
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
cp vendor/src/swisseph/ephe/* data/ephe/
# extended range 1200-1799 (optional; some proxies block large blob fetches)
(cd vendor/src/swisseph \
  && git sparse-checkout add '/ephe/sepl_12.se1' '/ephe/semo_12.se1' '/ephe/seas_12.se1' \
  && cp ephe/*_12.se1 ../../../data/ephe/) \
  || echo "WARN: extended ephemeris (1200-1799) not fetched; engine range stays 1800-2399"

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

# ---- record provenance -------------------------------------------------------
{
  echo "# Vendored components (pinned)"
  echo "pyswisseph  $PYSWISSEPH_REPO @ $(cd vendor/src/pyswisseph && git rev-parse HEAD)"
  echo "  libswe    $(cd vendor/src/pyswisseph/libswe && git rev-parse HEAD)"
  echo "  swephelp  $(cd vendor/src/pyswisseph/swephelp && git rev-parse HEAD)"
  echo "swisseph    $SWISSEPH_REPO @ $(cd vendor/src/swisseph && git rev-parse HEAD)"
  echo "pytest      $PYTEST_TAG | pluggy $PLUGGY_TAG | iniconfig $INICONFIG_TAG"
  echo "ephemeris   data/ephe/{sepl_18,semo_18,seas_18}.se1 + sefstars.txt (SE 2.10.03, 1800-2399)"
} > vendor/PINS.txt
echo "vendor OK"; PYTHONPATH=vendor/py:vendor/lib python3 -m pytest --version
