# Codex Prompt: GitHub Readiness

Goal: Prepare the DidiDecks frontend scaffold for a safe GitHub upload.


Important rules:
- Do not move backend logic into the frontend.
- Do not expose secrets.
- Do not use /api/v1 for DidiDecks.
- DidiDecks APIs use /api/products/dididecks/*.
- Do not copy legacy Michael repo code.
- Run build/typecheck and report results.


Check:

- no node_modules
- no .next
- no .env or real secrets
- .gitignore is safe
- .env.example contains only public placeholders
- README is honest about scaffold vs finished product
- build passes
- typecheck passes
- lint result documented
- API boundary uses /api/products/dididecks

Create or update:

- docs/GITHUB_READINESS.md
- docs/PRODUCT_STATUS.md
- docs/BACKEND_BOUNDARY.md
