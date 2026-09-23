# Smart Deck Audience Selector

Status: mounted and wired

## Intended Behavior

The audience selector determines the audience context persisted for later Smart
Deck generation requests. A user may change it while viewing either the current
deck or a generated preview. The selector is disabled only while an AI generation
job is actively running, which prevents its context from changing mid-request.

The selected value must:

- update local selector state immediately;
- persist as the deck's Smart Deck `audience` preference;
- survive a workspace reload;
- be included in the next generation request;
- remain editable while a generated version is in preview.

## Mounted Surfaces

The pasted selector values (`VC investor`, `Angel`, `Strategic`, `LP`, `Internal
review`, and `Sample day`) identify the diagnostics implementation mounted at:

- `/admin/decks/[deckId]/smart-deck`
- `src/routes/(admin)/admin/decks/[deckId]/smart-deck/+page.svelte`
- `src/lib/components/smart-deck/SmartDeckWorkspace.svelte`
- `src/lib/components/smart-deck/LlmChatCard.svelte`

The canonical user product route remains `/decks/[deckId]/smart-deck`. It mounts
`src/lib/features/smart-deck/user/UserSmartDeckWorkspace.svelte` and uses
`SmartDeckAIAssistantPanel.svelte`, whose audience selector was already enabled
and uses the same persisted preference endpoint. The two route roles must not be
merged or replaced with a parallel page.

## Wiring

```text
Audience select change
-> LlmChatCard audience state
-> SmartDeckWorkspace.persistTopicPreferences
-> patchSmartDeckPreferences
-> PATCH /api/decks/[deckId]/smart-deck/preferences
-> frontend authenticated product proxy
-> PATCH /api/products/deck-aistack-codes/decks/{deck_id}/smart-deck/preferences
-> smart_deck_update_preferences
-> update_smart_deck_preferences
-> SmartDeckPreference.audience
-> next Smart Deck generation request audience
```

## Affected Files

- `src/lib/components/smart-deck/LlmChatCard.svelte`: renders the identified
  selector, emits persisted context changes, and includes audience in generation.
- `src/lib/components/smart-deck/SmartDeckWorkspace.svelte`: owns persistence and
  generation handlers for the diagnostics workspace.
- `src/lib/api/smartDeckWorkspace.ts`: frontend preference client.
- `src/routes/api/decks/[deckId]/smart-deck/preferences/+server.ts`: authenticated
  frontend-to-backend proxy.
- Backend `app/api/routes/smart_deck.py`: ownership-checked PATCH route.
- Backend `app/schemas/smart_deck.py`: accepts `audience` up to 120 characters.
- Backend `app/services/llm/generation_service.py`: persists the audience field.
- `scripts/verify-smart-deck-audience-selector-contract.mjs`: guards mounted
  component, enablement, persistence, proxy, and generation wiring.

## Blocker And Solution

The selector used `disabled={previewMode || isAgentRunning}`. Preview mode is a
review state, not an active mutation, so the control remained disabled for as
long as an unapplied generated version existed.

The selector now uses `disabled={isAgentRunning}`. Generation remains protected,
while preview review no longer blocks preference changes. No new endpoint,
service, schema, route, or fallback was introduced.

## Legacy And Absorption Review

No runtime file or current document needed movement to `legacy/` for this fix.
Historical documents describe broader Smart Deck concepts or preview generation
locking; none owns this selector contract, and moving them would not be a proven
safe absorption. This document is the focused source for this element.

## Verification

Run:

```bash
node scripts/verify-smart-deck-audience-selector-contract.mjs
npm run check
npm run build
```
