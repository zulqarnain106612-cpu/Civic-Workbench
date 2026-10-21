.PHONY: test test-contracts diff-check

test: test-contracts

test-contracts:
	PYTHONPATH=src python3 -m unittest discover -s tests -v

diff-check:
	git diff --check
