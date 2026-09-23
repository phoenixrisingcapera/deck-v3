#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT = Path.cwd()
MODULE = ROOT / "app" / "products" / "dididecks"
errors = []
warnings = []

if not MODULE.exists():
    errors.append("Missing app/products/dididecks module.")

for p in ROOT.rglob("*.py"):
    if any(part in {".venv", "venv", "__pycache__"} for part in p.parts):
        continue
    text = p.read_text(errors="ignore")
    if "/api/v1" in text and "dididecks" in text.lower():
        errors.append(f"DidiDecks /api/v1 usage found in {p}")
    if "dididecks_" in text and "app/products/dididecks" not in str(p):
        warnings.append(f"DidiDecks table reference outside product module: {p}")

if MODULE.exists():
    router = MODULE / "api" / "router.py"
    if not router.exists():
        errors.append("Missing app/products/dididecks/api/router.py")
    elif "/api/products/dididecks" not in router.read_text(errors="ignore"):
        errors.append("DidiDecks router does not expose /api/products/dididecks prefix.")

print("DidiDecks Backend Boundary Report")
print({"errors": errors, "warnings": warnings})
if errors:
    sys.exit(1)
