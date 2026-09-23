# Full-Stack Architecture

```txt
deck-saas / Vercel / Next.js
  ↓ typed API client
AiStack backend / app/products/dididecks
  ↓ PostgreSQL + storage + jobs
AiStack guardrails / policies + evaluations
  ↓
exports, AI command proposals, audit logs, versions
```

## Ownership split

| Area | Owner |
|---|---|
| Frontend UI | `deck-saas` or `deck-infraestructure/web` |
| Deck API | `aistack-backend/app/products/dididecks` |
| Database tables | AiStack backend |
| Auth / organisations / memberships | AiStack shared backend |
| Billing / Stripe | AiStack shared backend |
| AI commands and proposals | AiStack backend |
| Guardrail policy evaluation | AiStack guardrails |
| Export workers | AiStack backend |
| Storage | backend-owned provider client |

## Non-negotiable API rule

DidiDecks product APIs must use:

```txt
/api/products/dididecks/*
```

Do not use:

```txt
/api/v1
```

for DidiDecks product APIs.
