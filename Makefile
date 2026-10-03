.PHONY: install test lint demo build
install:
	python -m pip install -e '.[dev]'
test:
	pytest -q
lint:
	ruff check .
	ruff format --check .
demo:
	forgeiac request --blueprint local-demo --set name=hello-platform
build:
	python -m build
