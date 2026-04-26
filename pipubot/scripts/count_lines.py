from pathlib import Path

root = Path("../..")
total = 0

for path in root.rglob("*.py"):
    if ".venv" in path.parts:
        continue
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        total += sum(1 for _ in f)

print("Total lines:", total)