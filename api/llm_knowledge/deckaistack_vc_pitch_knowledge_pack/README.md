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
