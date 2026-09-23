# Deck Diagnosis Prompt

Diagnose the current deck against the selected audience.

You receive:

- canonical Deck Map
- selected audience
- conversion goal
- optional market research artifact
- optional brand profile
- optional user instruction

## Required diagnostic steps

1. Identify the current deck type.
2. Identify the current narrative arc.
3. Identify what the deck currently makes clear.
4. Identify what the selected audience will still doubt.
5. Identify missing evidence.
6. Identify where the deck is too product-led, too vague, too dense, or too unsupported.
7. Identify whether the deck order supports audience belief formation.
8. Identify which slides are strong, adequate, weak, duplicated, or unnecessary.
9. Identify the highest-impact changes.
10. Produce a current deck fit score for the selected audience.

## Fit score rubric

Use 0-100.

- 90-100: audience-ready, minor sharpening only.
- 75-89: strong but missing some evidence or narrative polish.
- 60-74: usable but requires targeted slide rewrites.
- 40-59: important investor/advisor questions remain unanswered.
- 20-39: deck needs major restructuring before audience use.
- 0-19: deck is not fit for this audience.

## Diagnosis output principles

The diagnosis must be specific. Reference slide IDs and slide titles from the deck map.

Do not say only:

"The deck lacks evidence."

Say:

"Slide 5 claims enterprise adoption but does not show customer names, usage metrics, case studies, or pipeline conversion. For a VC Partner audience, this weakens traction credibility."

## Required diagnosis fields

Return content for:

- currentDeckFit
- mainAudienceProblem
- narrativeGap
- evidenceGap
- strongestSlides
- weakestSlides
- duplicatedSlides
- missingSlides
- highestImpactChanges
