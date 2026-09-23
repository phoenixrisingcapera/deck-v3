# Backend production queue

Already solved in main:

- #52 persist background worker failures. This is merged in main, so future worker-failure work should build on that implementation instead of reopening the older queue item.

Existing backend PRs:

- #30 recover Smart Deck retry when processing state exists
- #17 auto-map Railway bucket and database env aliases

New backend issues:

- #59 product lifecycle route contract
- #60 brand loader idempotency and palette provenance
- #61 Workspace AI Provider backend resilience

Suggested order:

1. Smart Deck retry recovery
2. Railway env alias mapping
3. Provider safe default response
4. Product lifecycle route contract
5. Brand loader provenance and idempotency
