PIO ?= pio

.PHONY: test test-contracts test-firmware-safety test-firmware-source firmware-build diff-check

test: test-contracts test-firmware-safety test-firmware-source

test-contracts:
	PYTHONPATH=src python3 -m unittest discover -s tests -v

test-firmware-source:
	python3 -m unittest discover -s tests -p 'test_firmware_source.py' -v

test-firmware-safety:
	$(CC) -std=c11 -Wall -Wextra -Werror -pedantic -Ifirmware/esp32/main tests/firmware/test_safety_policy.c firmware/esp32/main/civic_safety_policy.c -o /tmp/civic-workbench-safety-test
	/tmp/civic-workbench-safety-test

firmware-build:
	$(PIO) run -d firmware/esp32

diff-check:
	git diff --check
