PYTHON ?= python3
PIO ?= pio
BENCH_FRAMES ?= 20000
WHEEL_DIR ?= /tmp/civic-workbench-wheels

PYFLAKES ?= $(PYTHON) -m pyflakes

.PHONY: lint run test test-contracts test-firmware-safety test-firmware-source test-firmware-can-mock test-firmware-serial test-storage test-api test-analysis test-simulator test-proteus compile-check schema-check yaml-check diff-check package-check design-source benchmark verify firmware-build clean-local

run:
	PYTHONPATH=src $(PYTHON) -m civic_workbench --host 127.0.0.1 --port 8765

test: test-contracts test-firmware-safety

test-contracts:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -v

test-firmware-safety:
	$(CC) -std=c11 -Wall -Wextra -Werror -pedantic -Ifirmware/esp32/main tests/firmware/test_safety_policy.c firmware/esp32/main/civic_safety_policy.c -o /tmp/civic-workbench-safety-test
	/tmp/civic-workbench-safety-test

test-firmware-source:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -p 'test_firmware_source.py' -v

test-firmware-can-mock:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -p 'test_firmware_can_core.py' -v

test-firmware-serial:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -p 'test_firmware_serial_transport.py' -v

test-storage:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -p 'test_storage_and_import_export.py' -v

test-api:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -p 'test_api_*.py' -v

test-analysis:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -p 'test_analysis.py' -v

test-simulator:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -p 'test_simulator_tx.py' -v

test-proteus:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -p 'test_proteus_generator.py' -v

lint:
	$(PYFLAKES) src tests tools

compile-check:
	PYTHONPATH=src $(PYTHON) -m compileall -q src tests tools

schema-check:
	$(PYTHON) -c "import json; from pathlib import Path; from jsonschema import Draft202012Validator; [Draft202012Validator.check_schema(json.loads(p.read_text())) for p in Path('schemas/v1').glob('*.schema.json')]; print('All versioned JSON Schemas are valid.')"
	$(PYTHON) tools/check_schema_sync.py

yaml-check:
	$(PYTHON) -c "import yaml; from pathlib import Path; [yaml.safe_load(p.read_text()) for p in Path('.').rglob('*.yaml') if not any(part.startswith('.') for part in p.parts)]; print('All project YAML files parse.')"

diff-check:
	git diff --check

package-check:
	mkdir -p $(WHEEL_DIR)
	$(PYTHON) -m pip wheel . --no-deps -w $(WHEEL_DIR)
	$(PYTHON) tools/check_built_wheel.py $(WHEEL_DIR)

design-source:
	$(PYTHON) tools/generate_proteus_reference.py --output hardware/proteus/generated
	$(PYTHON) tools/generate_eagle_schematic.py --output hardware/proteus/generated/civic-workbench-rev-b.sch

benchmark:
	PYTHONPATH=src $(PYTHON) tools/benchmark.py --frames $(BENCH_FRAMES)

verify: test compile-check schema-check yaml-check diff-check package-check design-source

firmware-build:
	cd firmware/esp32 && $(PIO) run

clean-local:
	rm -rf .pytest_cache build dist *.egg-info src/*.egg-info
