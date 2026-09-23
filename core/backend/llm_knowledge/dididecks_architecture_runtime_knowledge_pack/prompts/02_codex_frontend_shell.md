# Codex Prompt: Frontend Shell

Goal: Build or tighten the DidiDecks frontend shell.


Important rules:
- Do not move backend logic into the frontend.
- Do not expose secrets.
- Do not use /api/v1 for DidiDecks.
- DidiDecks APIs use /api/products/dididecks/*.
- Do not copy legacy Michael repo code.
- Run build/typecheck and report results.


Routes to support:

- /
- /dashboard
- /decks
- /decks/new
- /decks/[deckId]
- /decks/[deckId]/editor
- /decks/[deckId]/map
- /decks/[deckId]/smart-edit
- /decks/[deckId]/rebuild
- /decks/[deckId]/review-matrix
- /decks/[deckId]/scroll
- /decks/[deckId]/play
- /decks/[deckId]/print
- /decks/[deckId]/versions
- /decks/[deckId]/exports
- /decks/[deckId]/access
- /billing
- /auth/sign-in
- /legal/privacy
- /legal/terms

Create mock data in local files. Do not hardcode large mock objects inside pages.

Completion criteria:

- app builds
- typecheck passes
- navigation works
- route/status docs are honest about shell-only versus backend-connected
