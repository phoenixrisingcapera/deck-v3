# PR summary: LLM source DB enrichment

This PR audits and fixes the gap between source V1 preparation and LLM-enriched DB state.

## Audit result

The backend already had enough schema to persist LLM source labels without migrations. Existing fields cover source slides, source blocks, semantic labels, run outputs, and artifacts.

## Fix

The source pipeline now:

1. builds deterministic labels;
2. builds an LLM enrichment prompt;
3. optionally calls the configured provider;
4. validates returned slide/block ids;
5. writes only validated labels into existing DB fields;
6. records provider/model/status in the source run and artifacts;
7. falls back safely to deterministic labels if the LLM is unavailable or invalid.

## Validation

Tests cover deterministic fallback, validated LLM persistence, and rejection of unknown slide/block ids.
