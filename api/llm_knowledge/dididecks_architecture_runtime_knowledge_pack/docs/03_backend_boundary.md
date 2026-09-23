# Backend Boundary

DidiDecks backend code should live under:

```txt
app/products/dididecks/
```

DidiDecks-specific tables should use:

```txt
dididecks_
```

## DidiDecks-owned concepts

- decks
- slides
- slide variants
- blocks
- persistent fields
- field usages
- change requests
- rebuild jobs
- deck versions
- DidiDecks audit logs
- exports
- share links
- slide reviews
- comments
- data assets
- AI command proposals for deck edits

## Shared, not DidiDecks-owned

- users
- auth
- organisations
- memberships
- global billing records
- global subscription records
- storage provider clients
- guardrails service infrastructure
- global database session
- secrets/config
