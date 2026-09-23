Produce one generated slide per selected source slide for a whole-deck Instant Deck pass.
Treat the deck as a venture narrative system: improve sequence, evidence hierarchy, and diligence readiness across the entire deck.
Use instantDeckContext.promptRecipe, vcAiStackModules, and contextVigilancePatterns as additive guidance for structure and scrutiny, never as founder fact sources.
Infer the company's product gist and brand gist from the uploaded deck, then carry that understanding consistently across every redesigned slide.
Use subjectContext.userPrompt as the redesign direction for the whole deck: it should influence the narrative, emphasis, and visual tone of the finished investor deck, not just one slide.
Return a whole-deck variant choice by populating root variantId and variantRationale using one of instantDeckContext.launchVariants.
For every slide, return archetypeId and narrativeRole that reflect the redesigned job of that slide in the deck, not just the uploaded title.
Return a whole-deck variant choice by populating root variantId and variantRationale using one of instantDeckContext.launchVariants.
For every slide, return archetypeId and narrativeRole that reflect the redesigned job of that slide in the deck, not just the uploaded title.
Return render-schema JSON that matches smart-deck-render-schema.v1 and carries analytics, sourceFactIds, missingInputs, and confidence.
Follow outputContract.rootShape and outputContract.renderSchemaJsonSchema exactly. Every element requires id, type, x, y, width, and height.
Use visionDesignAnalysis as the visual art-direction contract and keep presentation-scale typography: primary headlines 44-72px, subheadlines and body 28-36px, supporting labels 20-24px.
If the source deck lacks proof for a stronger claim, keep the wording honest and route the gap into missingInputs, designRationale, or source-backed caution rather than inventing evidence.
For color, token, or gradient backgrounds populate background.value; background.fill is only the layered-background fallback field.
Redesign the whole deck as if an investor will read it cold: make the product clearer, make the evidence hierarchy sharper, and make the brand feel more intentional and fundable while preserving the company's underlying identity.
Use renderSchema.analytics to persist deckVariantId, deckVariantLabel, deckVariantRationale, slideArchetypeId, slideArchetypeLabel, and narrativeRole for review surfaces.
Use renderSchema.analytics to persist deckVariantId, deckVariantLabel, deckVariantRationale, slideArchetypeId, slideArchetypeLabel, and narrativeRole for review surfaces.
Redesign the whole deck as if an investor will read it cold: make the product clearer, make the evidence hierarchy sharper, and make the brand feel more intentional and fundable while preserving the company's underlying identity.
Apply EventCut-inspired editorial principles without copying a fixed template: establish clear, non-overlapping zones; use deliberate asymmetry; keep text measures bounded; make headline, support, and evidence hierarchy unmistakable; preserve generous whitespace; and use only a few restrained accents.
You remain the composition owner. Adapt those principles to each slide's story and archetype, leave breathing room between text boxes, and shorten copy before a text box would overflow; do not mechanically fill a static layout.
