PY      := python3
ROOT    := $(shell pwd)
export PYTHONPATH := $(ROOT)/src:$(ROOT)/vendor/py:$(ROOT)/vendor/lib
export SE_EPHE_PATH := $(ROOT)/data/ephe
export PYTHONHASHSEED := 0

.PHONY: vendor test verify smoke clean

vendor:
	bash tools/vendor.sh

test:
	$(PY) -m pytest tests -q

smoke:
	$(PY) -m pytest tests -q -m smoke

verify:
	$(PY) tools/verify_report.py

clean:
	find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null; true
