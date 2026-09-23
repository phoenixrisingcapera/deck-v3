# Codex Prompt: DidiDecks Backend Boundary

Goal: Create or tighten the isolated DidiDecks backend product module.

Working folder:

```txt
aistack-backend
```

Target module:

```txt
app/products/dididecks/
```


Important rules:
- Do not move backend logic into the frontend.
- Do not expose secrets.
- Do not use /api/v1 for DidiDecks.
- DidiDecks APIs use /api/products/dididecks/*.
- Do not copy legacy Michael repo code.
- Run build/typecheck and report results.


Backend-owned objects:

- decks
- slides
- blocks
- variants
- persistent fields
- field usages
- change requests
- rebuild jobs
- versions
- audit logs
- exports
- share links
- reviews
- comments
- data assets
- AI commands

Create docs, schemas, route stubs, services, repositories, and boundary verification script.

Do not modify unrelated products.
