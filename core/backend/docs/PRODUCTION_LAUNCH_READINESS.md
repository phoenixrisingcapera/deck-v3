# Production Launch Readiness

- Contract-first routing is enforced in backend via `scripts/verify_production_contract.py`.
- Deployment target: `https://api.deck.aistack.codes/api`.
- Smart Deck is exposed on product namespace routes:
  - `/api/products/deck-aistack-codes/decks/{deck_id}/smart-deck`
  - `/api/products/deck-aistack-codes/decks/{deck_id}/smart-deck/generation-jobs`
  - `/api/products/deck-aistack-codes/decks/{deck_id}/smart-deck/generation-jobs/{job_id}`
- `/api/settings/workspace/ai-provider` is required and verified.
- `/api/v1` is explicitly forbidden from production route registration.
- Railway API/worker roles are documented and separated in `docs/RAILWAY_DEPLOYMENT_CONTRACT.md`.
