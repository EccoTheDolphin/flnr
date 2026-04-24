#uv run sphinx-apidoc -o docs src/flnr  -f -e
uv run sphinx-build -b html docs docs/_build -v
# uv run sphinx-build -b singlehtml docs docs/_build
