# we use 3.11 because of tomlib dependency
uv run --python 3.11 sphinx-build -b html docs docs/_build -v
