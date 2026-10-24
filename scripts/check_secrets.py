"""Scan publishable Git files without printing possible secret values."""
from pathlib import Path
import re
import subprocess

root = Path(__file__).resolve().parents[1]
names = subprocess.check_output(
    ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=root,
).decode().split("\0")
bad = []
for name in filter(None, names):
    path = Path(name)
    if path.name == ".env" or ".venv" in path.parts or ".uv-cache" in path.parts:
        bad.append(name)
        continue
    data = (root / path).read_bytes()
    if re.search(rb"sk-[A-Za-z0-9_-]{16,}", data):
        bad.append(name)
if bad:
    raise SystemExit("Publication blocked; inspect possible secrets locally in: " + ", ".join(bad))
print("Publishable Git files contain no matching API key pattern or local credential file.")
