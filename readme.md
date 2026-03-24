# `flnr`

<!-- markdownlint-disable link-fragments -->

<!-- mdformat-toc start --slug=gitlab --no-anchors --maxlevel=6 --minlevel=1 -->

- [`flnr`](#flnr)
  - [Development](#development)
    - [Using uv](#using-uv)
      - [Common Commands](#common-commands)

<!-- mdformat-toc end -->

<!-- markdownlint-enable link-fragments -->

## Development

Development infrastructur is shamelessly stolen
from https://github.com/rudenkornk/python_experiments .
It facilitates **uv**-based development workflow (I ditched the nix part, since
it is an overkill).

### Using uv

[uv](https://docs.astral.sh/uv/) is the only prerequisite for this workflow.

#### Common Commands

```bash
uv run pytest
uv run ./repo.py format         # Format code.
uv run ./repo.py format --check # Check formatting without changes.
uv run ./repo.py lint           # Run linters.
uv sync                         # Install dependencies (automatic on first run).
```

**Note:** The uv workflow provides full testing support and includes formatting
and linting tools available on PyPI.
