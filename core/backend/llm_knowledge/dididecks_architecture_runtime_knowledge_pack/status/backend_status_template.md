# Backend Status

| Area | Status | Notes |
|---|---|---|
| DidiDecks product module | Draft | Should live under `app/products/dididecks`. |
| API prefix | Required | `/api/products/dididecks/*`; no `/api/v1`. |
| Deck persistence | Draft | Backend-owned. |
| Persistent fields | Draft | Required for Smart Edit/Rebuild. |
| Field usages | Draft | Required for affected slide preview. |
| Rebuild jobs | Draft | Required for safe apply workflow. |
| Versions/audit | Draft | Required for accepted/rejected AI changes. |
| Exports | Draft | PDF/PPTX workers backend-owned. |
| Access/share links | Draft | Backend must validate private deck surfaces. |
