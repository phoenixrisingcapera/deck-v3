---
title: "memopop-native Character Cast"
version: 1
characters:
  - id: financial-analyst
    name: "Financial-Analyst"
    image: "/characters/financial-analyst.png"
    role: "Reads the pitch deck — extracts numbers, slides, and structure"
    stages:
      - deck_analysis
    default_caption: "Reading the deck"
    agents:
      - id: deck_analyst
        caption: "Parsing the pitch deck"
      - id: inject_deck_images
        caption: "Embedding deck slides"

  - id: researcher
    name: "Researcher"
    image: "/characters/researcher.png"
    role: "External research — Perplexity searches and competitive landscape"
    stages:
      - research
      - competitive
    default_caption: "Out gathering sources"
    agents:
      - id: research
        caption: "Initial research sweep"
      - id: section_research
        caption: "Researching by section"
      - id: cite
        caption: "Adding citations"
      - id: cleanup_research
        caption: "Tidying research notes"
      - id: competitive_research
        caption: "Mapping the landscape"

  - id: writer
    name: "Writer"
    image: "/characters/writer.png"
    role: "Drafts memo sections and revises summaries"
    stages:
      - writing
    default_caption: "At the typewriter"
    agents:
      - id: draft
        caption: "Drafting sections"
      - id: revise_summaries
        caption: "Revising summaries"

  - id: editor
    name: "Editor"
    image: "/characters/editor.png"
    role: "Polishes the draft into a deliverable"
    stages:
      - enrichment
      - assembly
    default_caption: "Polishing the draft"
    agents:
      - id: enrich_trademark
        caption: "Adding trademarks"
      - id: enrich_socials
        caption: "Hunting LinkedIn profiles"
      - id: enrich_links
        caption: "Wiring up references"
      - id: enrich_visualizations
        caption: "Drawing the diagrams"
      - id: toc
        caption: "Building the table of contents"
      - id: cleanup_sections
        caption: "Removing dead sources"
      - id: assemble_citations
        caption: "Compiling final draft"

  - id: fact-checker
    name: "Fact-Checker"
    image: "/characters/fact-checker.png"
    role: "Citation validity and claim verification"
    stages:
      - validation
    default_caption: "Verifying claims"
    agents:
      - id: validate_citations
        caption: "Validating citations"
      - id: fact_check
        caption: "Fact-checking claims"
      - id: validate
        caption: "Final validation"

  - id: scorecard-generator
    name: "Scorecard-Generator"
    image: "/characters/scorecard-generator.png"
    role: "Quality scoring and the scorecard navigator"
    stages:
      - validation
    default_caption: "Scoring the memo"
    agents:
      - id: scorecard
        caption: "Running the scorecard"
      - id: integrate_scorecard
        caption: "Integrating the scorecard"
---

# memopop-native Character Cast

This file is the source of truth for the row of characters that appears above the JobView's
3-column grid during a memo run. The frontmatter above is the manifest the app reads at build
time. Edit `name`, `default_caption`, or any `agents[].caption` to change what users see —
no code changes required, just a dev-server reload.

## Field guide

- `id` — kebab-case identifier. Stable across edits; never displayed.
- `name` — the label shown under the portrait. Keep it short (≤14 chars).
- `image` — path served by SvelteKit's static handler. PNGs live under `static/characters/`.
- `role` — longer description, surfaced as a tooltip when implemented.
- `stages` — `MilestoneStage` values the character claims. Used for v1 active-state derivation.
  Multiple stages OK; multiple characters claiming the same stage is OK (both glow).
- `default_caption` — the line under the name when the character is active and no specific
  milestone has fired yet.
- `agents` — per-agent captions. Forward-compat for v2 (server emits `agent` field on
  milestone events, client uses it to pick a precise caption). v1 ignores this list and
  uses the most recent matching milestone's `label` as the caption.

## v1 → v2

In v1 the cast is wired against the `MilestoneStage` enum the orchestrator already emits.
That means during the validation stage **both** Fact-Checker and Scorecard-Generator glow
together, even though only one of them is technically running at any instant. That's
honest given the data we have. v2 will tag milestone events with `agent` and the captions
above will become precise — same file, no schema changes.
