# DeckAiStack Extended LLM Knowledge Pack

Purpose: make DeckAiStack classify, critique, and improve decks as a VC diligence workspace, not only as a slide editor.

## What this adds

- Audience profiles: seed VC, Series A, growth equity, corporate strategic, family office, LP.
- VC due diligence modules: team, market, product, technology, traction, financials, competition, legal/governance, risks.
- LP intelligence: fund-return logic, portfolio construction, DPI/TVPI/IRR framing.
- IC readiness: partner questions, decision states, memo sections.
- Scoring models and JSON output schema.
- Prompts for a structured classifier LLM.

## Important rule

The LLM must not invent evidence. If a claim lacks a source, mark it as `missing_evidence` or `needs_research`.

## Suggested backend path

Copy this folder into:

```text
backend/llm_knowledge/deckaistack_extended/
```

Then compile/load `pipeline/llm_knowledge_manifest.json` and pass selected module snippets into the classifier prompt.
