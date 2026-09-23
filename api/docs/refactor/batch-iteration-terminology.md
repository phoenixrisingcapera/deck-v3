# Batch / Iteration Terminology

## Canonical Product Language

Use `iteration` for all user-facing product concepts.

- `iteration`
- `iterationId`
- `iterationName`
- `iterationNumber`
- `iterations`

## Internal Storage Compatibility

The persistence layer still uses `batch` in model and table names.

- `design_batches`
- `DesignBatch`
- `batch_slide_decisions`
- `CompiledDeck.batch_id`

These internal names should be read as persisted iteration storage.

## Compatibility Rule

Where older callers still send or expect batch-shaped payloads:

- accept `batchId` as an alias for `iterationId`
- accept `batchName` as an alias for `iterationName`
- accept `batchNumber` as an alias for `iterationNumber`
- accept `batches` as an alias for `iterations`
- accept `batch` as an alias for `iteration`

New code should emit `iteration*` fields first.
