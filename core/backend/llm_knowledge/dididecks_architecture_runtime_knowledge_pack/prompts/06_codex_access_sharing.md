# Codex Prompt: Access and Sharing

Goal: Add the DidiDecks access and private deck safety shell.


Important rules:
- Do not move backend logic into the frontend.
- Do not expose secrets.
- Do not use /api/v1 for DidiDecks.
- DidiDecks APIs use /api/products/dididecks/*.
- Do not copy legacy Michael repo code.
- Run build/typecheck and report results.


Route:

```txt
/decks/[deckId]/access
```

Components:

- DeckAccessPanel
- AccessModeCard
- MembersAccessTable
- ShareLinksTable
- AccessEventLog
- PermissionBadge
- PermissionMatrix

Mock data:

- organisation
- members
- share links
- permissions
- allowed/denied access events

Backend API placeholders:

```txt
GET /api/products/dididecks/decks/{deckId}/access
GET /api/products/dididecks/decks/{deckId}/members
GET /api/products/dididecks/decks/{deckId}/share-links
POST /api/products/dididecks/decks/{deckId}/share-links
GET /api/products/dididecks/decks/{deckId}/access-events
```
