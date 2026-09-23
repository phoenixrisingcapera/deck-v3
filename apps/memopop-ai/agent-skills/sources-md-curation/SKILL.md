---
name: sources-md-curation
description: Help the user author, edit, and codify the per-deal `inputs/Sources.md` file that drives MemoPop's codified-source research path. Use whenever the user asks to add URLs to a Sources.md, curate (reorder/prune) an existing one, fetch a URL and figure out where it belongs, promote an `outputs/<v>/Sources-aggregated.md` draft to `inputs/Sources.md`, change outlines on a deal that already has a curated source list, or generally anything involving the file at `io/<firm>/deals/<deal>/inputs/Sources.md`. Encodes the URL→section tagging heuristic, the validator's verdict ladder, the rank/sensitivity semantics, the aggregator→curate→codify lifecycle, and the common pitfalls (outline-switch breaks tags; bare-domain fetches return thin content; aggregator overwrites if codified mode isn't set).
---

# Authoring and Codifying MemoPop Sources.md

> The per-deal `inputs/Sources.md` is the analyst's hand-curated source list. When `mode: codified`, the MemoPop research pipeline skips broad search entirely and composes only from those URLs. This skill is how an agent helps a human author + maintain that file.

## When this skill activates

- The user pastes a URL and says "add this to Sources.md" or "add this one".
- The user is about to start, mid-, or finishing a curation pass on `Sources-aggregated.md`.
- The user wants to promote a `Sources-aggregated.md` draft into a working `inputs/Sources.md`.
- The user asks to change the outline on a deal that already has a curated Sources.md (high-risk operation — see *Outline-switch caveat*).
- The user is confused about why a URL isn't appearing in a section's research.
- The user wants to understand why a source was dropped, gated, or recovered.

## The behavioral core

When supporting the user on Sources.md, the agent's job is to:

1. **Know the current outline.** Section tags in Sources.md are only useful if they match the outline the orchestrator will read. Always check `deal.json`'s `outline:` field and load the corresponding `templates/outlines/<name>.yaml` (or `templates/outlines/custom/<name>.yaml`) to know the canonical section names.

2. **Fetch before adding.** Never add a URL blind. Run it through `src/curation/fetch.py` (`fetch_url_markdown(url)`) to confirm it reaches, get a real title, and see how much content comes back. A URL that fetches thin (<500 chars) or fails warrants a note — it'll be useless to the codified researcher.

3. **Tag sections deliberately.** The forgiving matcher helps but it's not magic. Tags must lexically match outline section names (after lowercase + hyphenate normalization). See *Section tagging* below.

4. **Surface the verdict ladder when discussing drops.** When a user asks "why was X dropped?", the answer is one of: hard 404, soft-404 body sniff, paywall stub (publisher not on allow-list), hallucination-pattern regex match, fetch failure. The agent should know these by name and which file implements them (`src/agents/remove_invalid_sources.py`).

5. **Don't auto-promote without explicit instruction.** Moving `outputs/<v>/Sources-aggregated.md` → `inputs/Sources.md` and flipping `mode: aggregated` → `mode: codified` are deliberate decisions. Confirm before doing them, OR clearly announce when promoting as-is.

## File anatomy

```
io/<firm>/deals/<deal>/
├── inputs/
│   ├── deal.json                 ← references outline, deck, mode flags
│   ├── Sources.md                ← ⭐ the codified source list (analyst-managed)
│   ├── <deck>.pdf                ← pitch deck the analyst added
│   └── <other-inputs>.md
└── outputs/
    └── ChromaDB-v0.0.N/
        └── Sources-aggregated.md ← pipeline output per run; analyst's worksheet
```

**`inputs/Sources.md`** is the canonical, lives-across-runs file. It survives version increments.

**`outputs/<v>/Sources-aggregated.md`** is the pipeline's per-run draft. Each broad-search run overwrites the one in its own version dir. The aggregator's first job per run.

## Frontmatter schema

```yaml
---
mode: codified           # "codified" activates the short-circuit; "aggregated" or "search" does not
deal: ChromaDB
firm: alpha-partners
date_curated_initial: 2026-05-22
date_curated_current: 2026-05-22
at_semantic_version: 0.0.0.1
curated_by:
  - Michael Staton
augmented_with: Claude Code (Opus 4.7)
sources:
  - url: https://example.com/article
    title: "Real Article Title"                       # required for good display + recovery
    publisher: "Example Publisher"                    # used for recovery's site:domain query
    published_date: 2024-03-15                        # YYYY-MM-DD; optional
    sections: [team, fundraising-round]               # see Section tagging below
    rank: 1                                           # 1=primary, higher=lower priority
    sensitivity: citable_externally                   # or internal_only
    note: "Free-form analyst comment."
---

# Optional analyst-facing body below the frontmatter.
# Conventional sections (not enforced):
## How this list was built
## Excluded — examined and rejected
## Open questions / coverage gaps
```

Only `url` is required per source. Everything else is best-effort; the codified researcher and validator degrade gracefully.

## The three modes (lifecycle)

| Mode | What it means | When set | Pipeline behavior |
|---|---|---|---|
| absent (no Sources.md) | First-ever run for this deal | First broad-search run | Broad search runs; aggregator writes a draft to `outputs/<v>/Sources-aggregated.md` with `mode: aggregated` and halts |
| `aggregated` | Pipeline's draft, awaiting curation | Aggregator sets this when writing the file | Codified short-circuit does NOT fire; if re-run, broad search runs again and aggregator halts again |
| `codified` | Analyst-approved; use ONLY these URLs | Analyst flips after curating | Codified short-circuit fires at `section_research`; aggregator passes through without halting; writer composes from these URLs only |

**Critical:** the codified short-circuit is in `src/agents/perplexity_section_researcher.py` (top of `perplexity_section_researcher_agent`). It checks `is_codified()` on the loaded `inputs/Sources.md`. If the file has `mode: aggregated` (or is at `outputs/<v>/Sources-aggregated.md` rather than `inputs/Sources.md`), the short-circuit does not fire.

## Section tagging — the heart of this skill

The `sections:` list on each source determines which per-section research file the codified researcher will use this source for. The matcher (`sources_for_section` in `src/curation/sources_md.py`) is forgiving but bounded:

- **Lowercase + hyphenate normalization.** "Market Context", "market-context", and "market_context" all collapse to `market-context` for matching.
- **Substring match both ways.** Tag `team` matches a section named "04-team", "team", or "Organization & Team". Tag `funding-terms` matches "Funding & Terms".
- **Section-number match.** If the outline has section #6 "Funding & Terms" and a source has `sections: [6]` or `sections: ["06"]`, it matches.
- **No fuzzy synonyms.** Tag `team` does NOT match `organization` (different words, no substring overlap). Tag `flags` does NOT match `risks`. The matcher won't bridge semantic gaps you'd need a thesaurus for.

### Section taxonomies by outline

The orchestrator has several outline templates. The section names differ. Always look up the current outline.

**`decile-group-deal-memo-template`** (currently default for alpha-partners):

| Section | Common content | Likely tags |
|---|---|---|
| Overview | Company snapshot, founders' pitch | `overview` |
| Why Invest | Investment thesis, momentum signals | `why-invest` |
| Situation – Market Overview | TAM, competitive landscape, trends | `situation--market-overview` (note the double hyphen!) |
| Team | Founders, advisors, key hires | `team` |
| Business Economics & Ethics | Unit economics, ARR, customer mix, governance | `business-economics--ethics` |
| Fundraising Round | Round size, lead, valuation, syndicate | `fundraising-round` |
| Flags | Risks, concerns, red flags | `flags` |

**`direct-early-stage-12Ps`** (Decile Group's 12Ps framework):

| Section | Common content | Likely tags |
|---|---|---|
| Executive Summary | One-pager-style overview | `executive-summary` |
| Origins | Founder story, why this company exists | `origins` |
| Opening | The investment opening (timing, momentum) | `opening` |
| Organization | Team, advisors, board | `organization` |
| Offering | The product/service, value prop | `offering` |
| Opportunity | Market sizing, TAM, growth | `opportunity` |
| Risks & What Could Go Wrong | Risk register | `risks` |
| 12Ps Scorecard Summary | Synthesis | `scorecard-summary` |
| Funding & Terms | Round details | `funding-terms` |
| Closing Assessment | Recommendation | `closing-assessment` |

**`alpha-partners-7-Cs-memo-template`**, **`hypernova-fund-commitment`**, **`four-factor-five-page`**, **`standard-direct-investment`** — read the YAML when needed.

### Choosing tags for a new URL

Rough heuristic, lowest friction first:

1. **What is the URL primarily about?** Read the title and the first few hundred chars of content if Jina returned it.
2. **Which outline section's *guiding questions* would this URL most directly answer?** Cross-check against the outline YAML's `guiding_questions:` fields if they exist for each section.
3. **Multi-section is fine but don't sprawl.** A source can legitimately support 2–3 sections (e.g., a founder interview supports Team AND Opportunity). It rarely supports 5+ honestly. If you'd tag it for 5+, you're probably tagging it for "Overview / Why Invest / Situation" — generic-fit signals; consider whether the source is really primary for any of them.
4. **VC firm homepages** → almost always `[team, funding-terms]` (or `[organization, fundraising-round]` depending on outline).
5. **Company blog / docs / GitHub** → `[overview, offering, technology-product]` or the outline's equivalents.
6. **News articles about a fundraise** → `[fundraising-round, opening]` or the equivalents.
7. **Founder interviews** → `[team, origins, opening]`.
8. **Market analyst reports** → `[opportunity, situation--market-overview, why-invest]`.
9. **Internal call notes / partner memos** → `[team, flags, closing-assessment]` with `sensitivity: internal_only`.

When in doubt, **ask the user which sections they're targeting** — they know the memo's argument better than the URL does.

## URL validation context (verdict ladder)

When the user asks "why was X dropped?" or "what happens to paywalled sources?", the answer comes from the verdict ladder in `src/agents/remove_invalid_sources.py`'s `validate_url()`:

| Verdict | Sentinel code | Meaning | Disposition |
|---|---|---|---|
| `verified-accessible` | real HTTP 200 (with `(body verified)` in status) | Real 2xx, body parses, no soft-404 or paywall phrases | **Kept** — counts as valid |
| `verified-gated` | `-4` | HTTP 200, paywall body, BUT publisher on `src/validation/gated_publishers.yaml` (31 publishers: WSJ, FT, NYT, Bloomberg, McKinsey, Gartner, etc.) | **Kept** — analyst verifies with their own subscription |
| `soft-404-graceful` | `-2` | HTTP 200, body contains "page not found"/"no longer available"/similar | **Dropped** — page is actually gone |
| `paywall-stub` | `-3` | HTTP 200, body is paywall/login wall, publisher NOT on allow-list | **Dropped** — not a reputable gated source |
| `hallucination-pattern` | `-1` | URL matches regex preflight for bare-doc-id IDs (Gartner `documents/\d+/?$`, Forrester `RES\d+$`, IDC bare-containerId), or generic placeholders (`example.com`, `XXXXX`, `placeholder`, `/path/to/`, `{template-var}`) | **Dropped** — LLM fabrication template |
| `hard-404` | 404, 410 | Real HTTP error | **Dropped** |
| `potentially-valid` | 401, 403, 429, 5xx, or connection error | URL might be valid but is currently unreachable | **Kept with warning** — analyst should spot-check |

Recovery (Step 5 of the Trustworthy-Citations rollout): when a citation hard-404s or hallucination-patterns AND has a known title/publisher, the recovery module attempts `"<title>" site:<publisher-domain>` via Tavily, validates each candidate through the same pipeline, accepts the first hit with title-Jaccard ≥ 0.6. McKinsey URL drift is the canonical case this rescues.

Redacted hallucinations log: dropped citations (post-recovery) get a card in `outputs/<v>/redacted-hallucinations.md` with the claimed title, publisher, verdict, files-it-appeared-in, and a clickable Google search link for the analyst to investigate manually.

## Operations the agent should support

### Adding a URL the user pasted

1. Fetch it via `fetch_url_markdown(url)` to confirm it reaches and get a real title.
2. Look at the title and first ~500 chars of body to infer what it's about.
3. Look at the current outline (`deal.json` → outline name → `templates/outlines/<name>.yaml`) for canonical section names.
4. Propose section tags based on title + content + outline section names. **Show the user the proposed tags before writing** if it's not obvious; otherwise add with best-guess tags and a note that re-tagging is welcome.
5. Insert the entry in the `sources:` list at the *bottom* of any existing analyst-added block (so the manual additions are grouped). Mark with a comment `# ─── Analyst-added below ───` on first addition.
6. Include a `note:` field with date, fetch-via signal, and any caveat (thin body, etc.).
7. **Round-trip parse-test** after writing: `load_sources_md()` should return non-None and the new entry should appear in `sm.sources[-1]`.

### Reordering / pruning during a curation pass

- **Rank semantics:** `rank: 1` = primary source for the section, `rank: 2` = secondary, `rank: 3+` = tertiary. Writer uses rank to calibrate hedging — declarative voice for rank-1, attributed/hedged for lower-rank.
- **Pruning:** delete entries the analyst x-es out. Don't comment them out — the YAML parser will keep them as data. Either delete or add a meaningful note in the `excluded` body section.
- **Sort within rank:** by topical relevance to the section, not by URL or alphabetically. Primary publisher voices first, then trade press, then aggregators.

### Promoting `outputs/<v>/Sources-aggregated.md` → `inputs/Sources.md`

This is a three-step deliberate operation:

```bash
# 1. Copy (don't move — the outputs/<v>/ artifact stays as the run's record)
cp io/<firm>/deals/<deal>/outputs/<deal>-v<X>/Sources-aggregated.md \
   io/<firm>/deals/<deal>/inputs/Sources.md

# 2. Flip mode in the new inputs/ copy
sed -i '' 's/^mode: aggregated$/mode: codified/' io/<firm>/deals/<deal>/inputs/Sources.md
# Or use a Python re.sub with MULTILINE — the file has TWO `mode: aggregated` mentions
# (one in a comment example, one in the actual YAML key). Only flip the key line.

# 3. Confirm
python3 -c "from src.curation.sources_md import load_sources_md, is_codified; from pathlib import Path; \
  sm = load_sources_md(Path('io/<firm>/deals/<deal>/inputs')); \
  print(f'mode={sm.mode}, is_codified={is_codified(sm)}, sources={len(sm.sources)}')"
```

If `is_codified=True` and source count matches expectations, codified mode is active. The next pipeline run will short-circuit broad search.

### Outline-switch caveat (the trap)

**Switching `deal.json`'s `outline:` field on a deal with an existing curated Sources.md is a high-risk operation.** Section tags in Sources.md are tied to the OLD outline's section names. The new outline almost always has different names (e.g., `team` in decile-group → `organization` in 12Ps).

When the user asks to switch outlines on a curated deal:

1. **Flag the consequence.** Tagged sources won't match the new outline's section names. Most sources will become `<needs-source>` stubs on the next run.
2. **Offer three options** before doing the switch:
   - **A.** Re-run aggregation under the new outline. Costs another broad-search run (~$5–10 in Perplexity calls) but produces a fresh Sources-aggregated.md with correctly-tagged sections. Cleanest.
   - **B.** Bulk re-tag the existing file using a best-guess mapping (old → new section name). Free; preserves the URL set and analyst-added entries. Heuristic; the analyst should spot-check.
   - **C.** Re-tag during the next curation pass manually. Free; most analyst-correct; more work for the human.
3. **Recommend B** unless the user has time for A, or knows the file is mostly junk anyway and A would be cleaner.

If the user reverses course mid-decision (as has happened — "switch back, sorry"), confirm both: deal.json reverted AND no in-flight tag remapping happened.

## Common pitfalls

1. **Forgetting to flip `mode: aggregated` → `mode: codified`** when promoting from `outputs/<v>/Sources-aggregated.md` to `inputs/Sources.md`. The codified researcher checks `mode == "codified"` exactly. Without the flip, the pipeline re-does broad search and overwrites the aggregated file in the new version's output dir.

2. **Two `mode:` occurrences in the file.** The aggregator's frontmatter includes a comment block that mentions "change `mode: aggregated` to `mode: codified`" as instructions. A naive string replace might hit the comment string before the YAML key. Always use a line-anchored regex (`^mode: aggregated$` with `MULTILINE`) or target the YAML key with awareness that comments contain the same string.

3. **Bare-domain VC firm sites returning thin content via Jina.** Many VC homepages are JS-heavy SPAs that Jina Reader can't extract well (Bloomberg Beta, for example, returns ~370 chars). Note in the entry's `note:` field that the body is thin; the writer can still cite the firm by name + URL even without rich content.

4. **Adding deck PDFs as Sources.md entries.** Don't. The deck flows through `state.deck_analysis` via the `deck_analyst` agent, not through the citation system. Wire the deck via `deal.json`'s `deck:` field instead (path relative to deal directory).

5. **Setting `sections: []` empty.** A source with no section tags won't match any section in the codified researcher. It'll be in the corpus (fetched) but never cited. Either tag it or remove it.

6. **Using outline section names with single hyphens when the outline has doubles.** `decile-group` has `situation--market-overview` (two hyphens). The forgiving matcher accepts variants but exact match is most reliable.

7. **Running `python -m src.main` without `inputs/Sources.md` present and expecting codified behavior.** No file = no short-circuit. The pipeline does broad search and halts at the aggregator. Always check `ls inputs/` for the file before launching.

## Reference paths

The skill assumes the user is working inside `ai-labs/memopop-ai/apps/memopop-orchestrator/`. Key files:

| Path | What |
|---|---|
| `src/curation/sources_md.py` | Loader + `SourcesMd` / `SourceEntry` dataclasses + `sources_for_section` filter |
| `src/curation/fetch.py` | URL → markdown via Jina (with httpx + BeautifulSoup fallback) |
| `src/agents/codified_section_researcher.py` | The agent that consumes Sources.md and writes per-section research |
| `src/agents/perplexity_section_researcher.py` | Has the codified short-circuit at top of its agent function |
| `src/agents/source_aggregator.py` | Aggregator that writes Sources-aggregated.md and halts |
| `src/agents/remove_invalid_sources.py` | The URL-keyed validator + verdict ladder + recovery + redaction worksheet |
| `src/validation/gated_publishers.yaml` | 31-publisher allow-list — paywalled-but-reputable |
| `templates/Sources-template.md` | Annotated template if the analyst wants to hand-author from scratch |
| `templates/outlines/<name>.yaml` | Section taxonomies — read this to know what tags to use |

## Compose with

- **`context-vigilance`** — Sources.md follows the same frontmatter-for-machines / body-for-humans convention as other context-v files.
- **`pseudomonorepos`** — io/ submodules. Sources.md lives inside `io/<firm>/` which is a submodule; edits there don't auto-commit the parent.
- **`changelog-conventions`** — substantial Sources.md curation work (new tagging conventions, new mappings between outlines) warrants a changelog entry.

## See also

- `context-v/explorations/Human-Curated-Source-Sets-and-Per-Firm-RAG-for-Memo-Narrative.md` — the exploration this workflow implements
- `apps/memopop-orchestrator/context-v/plans/Trustworthy-Citations-Source-Harvester-Rollout.md` — Phase 1 validation work referenced by the verdict ladder above
- `apps/memopop-orchestrator/changelog/2026-05-22_02.md` — "The Analyst Gets the Pencil" — narrative of when this whole workflow shipped
