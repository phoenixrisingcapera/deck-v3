# Audience Diligence Prompt Package

## Product definition

Audience Diligence is the VC/advisor knowledge layer for DeckAiStack.

It is not primarily a static report generator. Its job is to review an uploaded deck through the lens of a selected audience and produce a concrete implementation plan that Smart Deck and Smart Edit can execute.

## Workflow

```text
Deck Map
  -> selected audience
  -> audience profile
  -> VC judgment rules
  -> deck diagnosis
  -> audience-specific conversion plan
  -> slide-level implementation instructions
  -> Smart Deck / Smart Edit execution
```

## Package files

- `manifest.json` — package metadata, audience list, expected inputs, outputs, and routing.
- `system.md` — core system prompt.
- `audience_profile.md` — audience-specific VC/advisory judgment profiles.
- `vc_judgment_rules.md` — experienced VC reasoning rules.
- `deck_diagnosis.md` — how to diagnose the current deck against the selected audience.
- `conversion_planner.md` — how to produce whole-deck implementation plans.
- `slide_instruction_generator.md` — how to produce slide-level implementation instructions for Smart Deck and Smart Edit.
- `output_schema.json` — required structured JSON output.

## Required inputs

```json
{
  "deckId": "string",
  "deckMap": "canonical deck map object",
  "selectedAudience": "VC Partner | VC Associate | Investment Committee | LP | Strategic Corporate Buyer | Accelerator Judge | Board Member | Fundraising Advisor Client | Portfolio Founder",
  "conversionGoal": "fundraising | IC prep | advisory client version | portfolio support | corporate review | board review",
  "brandProfile": "optional brand profile",
  "marketResearch": "optional market research artifact",
  "userInstruction": "optional user instruction"
}
```

## Required output

The model must return a JSON object matching `output_schema.json`. The result should be persisted as a DeckLlmArtifact and used as an execution input for Smart Deck and Smart Edit.

## Non-negotiable product rule

Due Diligence must answer:

> How should this deck change for the selected audience to believe, evaluate, and act on it?

It must not stop at:

> What risks are in this deck?
