# Due Diligence Canonical Route Note 2026-07-15

This note records the route-ownership fix applied to the backend product API.

## Problem

The backend exposed both:

- the real canonical product Due Diligence contract in `deck_intake.py`
- a placeholder contract in `product_runtime_hardening.py`

Those routes shared the same canonical product path family, which made Due
Diligence ownership brittle and easy to regress.

## Change

The placeholder routes in `app/api/routes/product_runtime_hardening.py` were
kept for rollback and inspection, but moved off the canonical path onto
explicit placeholder endpoints:

- `GET /api/products/deck-aistack-codes/decks/{deck_id}/due-diligence-placeholder`
- `POST /api/products/deck-aistack-codes/decks/{deck_id}/due-diligence-placeholder/run`

The mounted product page can now rely on the canonical Due Diligence owner
without a duplicate competing route.

## Chat retry contract

`clientExchangeKey` is the exact-once retry identity. Modern clients retain it
across retries; legacy clients may omit it and receive a server-generated key.
Conversation writes lock the existing artifact row and rely on the existing
PostgreSQL unique artifact identity for simultaneous first-writer resolution.
Assistant provider/model metadata is persisted and replayed with the response.

## Verification

- `python3 -m compileall` succeeded for the edited backend route file.
- Targeted `pytest` collection is currently blocked by a pre-existing SQLAlchemy
  duplicate-table registration issue around `vector_chunks` in this repo state.
