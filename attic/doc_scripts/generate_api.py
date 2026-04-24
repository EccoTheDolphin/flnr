import ast
from pathlib import Path

tree = ast.parse(Path("src/flnr/__init__.py").read_text())

names = []
for node in tree.body:
    if isinstance(node, ast.ImportFrom):
        names.extend([alias.asname or alias.name for alias in node.names])

# deduplicate, preserve order
seen = set()
for name in names:
    if name not in seen:
        seen.add(name)

with Path("docs/api.rst").open("w") as f:
    f.write("API\n===\n\n")
    f.write(".. autosummary::\n   :toctree: none\n   :nosignatures:\n\n")
    f.writelines(f"   flnr.{n}\n" for n in seen)
