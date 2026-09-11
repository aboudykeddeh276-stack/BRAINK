.PHONY: install test run seed package
install:
	python -m pip install -e .
test:
	PYTHONPATH=src pytest -q
run:
	PYTHONPATH=src uvicorn braink_runtime.app:app --host 127.0.0.1 --port 8000
seed:
	PYTHONPATH=src python scripts/seed_registry.py
package:
	tar -czf ../braink-runtime-publish.tar.gz .
