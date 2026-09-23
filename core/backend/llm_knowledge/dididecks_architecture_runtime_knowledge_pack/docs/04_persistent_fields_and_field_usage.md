# Persistent Fields and Field Usage

A persistent field is stored once and can appear across many slide blocks.

Example:

```txt
founder.ceo_name = Andrea Capera
```

Used by:

- Cover slide / founder subtitle
- Team slide / founder card
- Contact slide / signature
- Appendix / leadership profile

When updated:

1. Update the persistent field record.
2. Find all field usages.
3. Preview affected slides and blocks.
4. Apply the change.
5. Mark affected blocks stale or update them directly.
6. Create rebuild job if needed.
7. Create version snapshot.
8. Write audit record.

## Why this matters

Without persistent fields, the product becomes a local visual editor. With persistent fields, it becomes a business-data-aware deck system.
