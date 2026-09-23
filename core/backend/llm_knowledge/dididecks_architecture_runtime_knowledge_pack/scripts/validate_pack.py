#!/usr/bin/env python3
from pathlib import Path
import json

root = Path(__file__).resolve().parents[1]
errors = []
for path in list((root / "json").glob("*.json")) + list((root / "schemas").glob("*.json")) + list((root / "examples").glob("*.json")):
    try:
        json.loads(path.read_text())
    except Exception as exc:
        errors.append(f"{path}: {exc}")

if errors:
    print("JSON validation failed")
    for e in errors:
        print("-", e)
    raise SystemExit(1)
print("Knowledge pack JSON files are valid.")
