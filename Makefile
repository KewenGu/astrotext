PY      := python3
ROOT    := $(shell pwd)
export PYTHONPATH := $(ROOT)/src:$(ROOT)/vendor/py:$(ROOT)/vendor/lib
export SE_EPHE_PATH := $(ROOT)/data/ephe
export PYTHONHASHSEED := 0

.PHONY: vendor vendor-swiss test verify smoke check-license clean

# Default profile: de440 kernel only, no Swiss Ephemeris (this is what ships).
vendor:
	bash tools/vendor.sh

# Dev/verify profile: adds the AGPL pyswisseph + swetest reference.
vendor-swiss:
	bash tools/vendor.sh --with-swiss

test:
	$(PY) -m pytest tests -q

smoke:
	$(PY) -m pytest tests -q -m smoke

# Cross-implementation reference gate (requires `make vendor-swiss`).
verify:
	$(PY) tools/verify_report.py

# Relicense gate: prove the default distribution is Swiss-Ephemeris-free.
check-license:
	$(PY) tools/check_no_swiss.py

clean:
	find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null; true
