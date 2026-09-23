# Codex Prompt: Data Assets Layer

Goal: Add the DidiDecks data assets frontend shell.


Important rules:
- Do not move backend logic into the frontend.
- Do not expose secrets.
- Do not use /api/v1 for DidiDecks.
- DidiDecks APIs use /api/products/dididecks/*.
- Do not copy legacy Michael repo code.
- Run build/typecheck and report results.


Routes:

- /decks/[deckId]/data-assets
- /decks/[deckId]/data-assets/people
- /decks/[deckId]/data-assets/companies

Components:

- DeckStatsPanel
- DataAssetsLayout
- CompaniesAuditTable
- PeopleAuditTable
- AssetCompletenessCard
- AssetStatusBadge
- MissingAssetWarnings
- AssetLinkPills
- AssetImageCell

Data assets should cover:

- people
- companies
- logos
- headshots
- URLs
- bios
- sectors
- used-in-slide mappings
- audit findings
