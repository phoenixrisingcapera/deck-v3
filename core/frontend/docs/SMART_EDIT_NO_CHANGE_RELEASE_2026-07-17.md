# Smart Edit No-Change Contract Release

Date: 2026-07-17

## Canonical Behavior

Smart Edit may return `no_change` when the configured model finds no safe,
source-grounded improvement for the selected text block. This is a successful,
terminal, non-mutating result rather than a failed generation or pending review.

The mounted product route is `/decks/[deckId]/smart-edit`. Its user and
super-admin surfaces preserve `no_change`, show truthful copy, and do not enable
Accept or Dismiss actions for unchanged text.

## Contract Chain

```text
Smart Edit instruction
-> authenticated frontend patch proxy
-> backend reviewable Smart Edit service
-> source-grounded patch validation
-> SmartEditSuggestion(status=no_change)
-> SmartEditWorkflowRunResponse(status=no_change)
-> mounted Smart Edit UI
-> no deck mutation
```

## Canonical Owners

- Backend generation and persistence: `app/services/llm/smart_edit_service.py`
- Backend response schema: `app/schemas/smart_edit_workflow.py`
- Shared frontend status contract: `src/lib/contracts/types.ts`
- Product Smart Edit surface: `src/routes/(product)/decks/[deckId]/smart-edit/+page.svelte`
- Super-admin Smart Edit surface: `src/routes/(admin)/super-admin/decks/[deckId]/smart-edit/+page.svelte`
- Static contract verification: `scripts/verify-smart-edit-no-change-contract.mjs`

## Safety Rules

- Unchanged provider output must not be rewritten with synthetic punctuation or truncation.
- `no_change` must never be normalized back to `pending`.
- Accept and Dismiss remain available only for pending suggestions.
- Existing deck text remains unchanged and no revision is applied.
- Provider failures and provider-capacity failures remain separate error states.

## Verification

Run:

```bash
npm run test:smart-edit-no-change
npm run check
```

Backend verification covers schema acceptance, persisted no-change runs, source
targeting, provider repair behavior, route contracts, and authorization.
