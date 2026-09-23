# DeckAiStack VC & Entrepreneurial Pitch Knowledge Pack

Purpose: backend/LLM classifier knowledge for ingesting investor decks, classifying slides and blocks, and mapping ambiguous deck content into diligence-ready structure.

This pack is designed for decks that may not use canonical slide titles. It relies on semantic signals, block patterns, evidence clues, and investor-intent mapping rather than only title matching.

Suggested use:
1. Load all JSON files into backend/llm_knowledge.
2. Compile into a single index at build time.
3. Use the classifier in two stages:
   - slide_archetype classification
   - block_role classification inside each slide
4. Store confidence, alternatives, and evidence signals for explainability.

Core output idea:
{
  "slide_id": "...",
  "predicted_slide_archetype": "problem",
  "confidence": 0.82,
  "evidence": ["pain language", "current workaround", "user segment named"],
  "blocks": [
    {"block_id": "...", "role": "problem_statement", "confidence": 0.88}
  ],
  "alternative_archetypes": ["customer_insight", "market_context"]
}


## Market Research Vigilance Add-on

Files 09-15 add a market intelligence layer for investor decks. This layer classifies and audits market-size, competitor, growth, regulation, buyer, and trend claims. It is designed for conservative investor-grade checking: when evidence is missing, the system should mark the claim as `needs_research`, not invent sources.

Recommended flow:

1. Intake slide text and visual blocks.
2. Classify slide archetype and block roles.
3. Detect market claims.
4. Normalise numbers: currency, year, geography, unit.
5. Check whether the claim is cited and current.
6. Trigger live research only when enabled.
7. Return investor risk and suggested slide fixes.

This should power a DeckAiStack UI panel such as: Market Accuracy, Competitor Check, Claim Risk, Missing Sources, Suggested Evidence.
