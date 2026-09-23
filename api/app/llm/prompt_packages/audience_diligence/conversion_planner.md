# Conversion Planner Prompt

Produce a concrete deck implementation plan for the selected audience.

This is not a report. This is an execution plan.

## Planning objective

Convert the current deck into a version that better serves the selected audience's decision process.

For this product mode, adapt the existing deck only. Do not recommend net-new slides or net-new financial sections. If evidence is missing, use rewrites, reordering, softening, or explicit evidence requests instead.

## Required planning dimensions

### 1. Narrative shift

State the main narrative change needed.

Examples:

- Product-led to investment-thesis-led.
- Feature explanation to strategic value.
- Founder story to evidence-backed fundraising story.
- Generic market claim to bottom-up market conviction.
- Demo-day pitch to IC-ready decision material.

### 2. Deck structure changes

Classify each structural change as:

- keep
- rewrite
- redesign
- reorder
- merge
- delete
- add

Each action must include:

- slideId when applicable
- slide title when available
- reason
- selected audience relevance
- priority: critical | high | medium | low
- implementation note

### 3. Slides to add

In this mode, do not recommend new slides. Leave `slidesToAdd` empty and convert missing-slide needs into evidence requests, rewrite guidance, or reordering notes for the current deck.

Common slide types:

- Why Now
- Market Size Assumptions
- Customer Evidence
- Traction Quality
- Competitive Wedge
- Defensibility
- Use of Funds and Milestones
- Risk and Mitigation
- Strategic Fit
- Integration Logic
- Board Decision Required

### 4. Slides to rewrite

For each rewrite, give:

- current issue
- audience problem
- new direction
- suggested headline direction
- evidence needed

### 5. Slides to reorder

Explain how the new order improves audience belief formation.

### 6. Slides to merge/delete

Recommend merge/delete when slides are duplicative, too tactical, or not decision-relevant.

### 7. Smart Deck execution instruction

Produce one concise instruction object that Smart Deck can consume to generate the audience version.

It must include:

- target audience
- narrative shift
- slide actions
- brand constraints
- evidence constraints
- anti-hallucination rules

## Implementation quality bar

The plan must be specific enough that another service can execute it without asking, except when missing evidence is required.
