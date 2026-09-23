# Slide Instruction Generator Prompt

Generate slide-level implementation instructions for the Due Diligence report.

Each instruction must be actionable, audience-specific, and evidence-safe.

## Required fields per slide instruction

- slideId
- slideTitle
- currentRole
- targetRole
- action
- audienceProblem
- audienceReason
- implementationInstruction
- headlineDirection
- bodyCopyDirection
- layoutDirection
- visualDirection
- evidenceNeeded
- factsToPreserve
- claimsToSoften
- smartEditInstruction
- smartDeckInstruction
- priority
- confidence
- requiresReview

## Action types

Allowed actions:

- keep
- rewrite
- redesign
- rewrite_and_redesign
- reorder
- merge
- delete
- add
- split
- request_evidence

## Instruction quality standard

Weak instruction:

"Improve the slide for investors."

Strong instruction:

"Rewrite this product feature slide into a VC Partner wedge slide. Preserve the current product capability claims, but change the headline to communicate why this capability creates a defensible workflow advantage. Use a two-column layout: left side shows the current broken workflow, right side shows the proprietary intelligence layer. Do not add traction metrics unless provided. Request usage frequency or time-saved evidence."

## Audience-specific adaptation

For VC Partner:
- prioritize fund-return logic, market scale, traction, defensibility, why now.

For VC Associate:
- prioritize scannability, extractable facts, diligence questions, metrics.

For Investment Committee:
- prioritize decision case, risks, assumptions, mitigations.

For Strategic Corporate Buyer:
- prioritize strategic fit, integration, build/buy/partner logic.

For Board Member:
- prioritize decisions, milestones, risks, resource allocation.

For Advisor Client:
- prioritize practical fix instructions and missing client inputs.

## Evidence handling

If evidence is missing, do not invent it. The slide instruction should say:

- what evidence is missing
- where it should appear
- how to rewrite the slide safely until evidence is available

## Output purpose

These instructions are review artifacts. They may guide a human operator, but must
not be serialized into Smart Deck render-schema text or Smart Edit replacement
copy. Keep evidence requests, risk notes, and implementation advice in the Due
Diligence report.
