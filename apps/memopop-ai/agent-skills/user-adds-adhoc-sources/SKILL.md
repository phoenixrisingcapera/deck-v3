---
name: user-adds-adhoc-sources
description: "The \"I saw the output and I'm annoyed\" workflow. User comes back from a Google search with 1-5 URLs they want incorporated without re-running the whole pipeline. Three moves: add the URLs to the deal's `inputs/Sources.md`, then Claude reads the existing per-section `1-research/<NN>-section-research.md` files and inserts the new source content + `[^N]` citations directly using its own judgment about fit (no codified-researcher re-run, no version bump, no copying — edit the research files in place), then trigger the writer agent so it regenerates the section files from the now-enhanced research. Use whenever the user pastes 1-5 URLs after reviewing a memo draft and says \"add these,\" \"work these in,\" \"I found these — redo with these,\" or similar. Different from `sources-md-curation` (which is the general authoring skill); this is the **end-to-end orchestrated workflow** for the impatient-with-output case. Composes with sources-md-curation for the tagging step."
---

# User-Triggered Adhoc Source Addition

> The analyst is reading a generated memo. Something's missing — a fact, an angle, a source they expected to see. They google, find 1-5 URLs that fix it. This skill is the workflow that gets those URLs into the memo without re-running the whole pipeline.

## When this skill activates

The signal pattern is **post-output dissatisfaction + URLs**:

- "Read this memo, it's missing X — add these: <URL1>, <URL2>, <URL3>"
- "I just found <URL>, work it into the Series A section"
- "These 4 sources should be in the team section — add them and re-run"
- "Section 5 is thin — I found these three, redo with them"

If the user just wants to add to Sources.md without re-running anything, that's plain **sources-md-curation** territory. If they want a full broad-search re-run from scratch, that's the normal pipeline. This skill is specifically the **add-and-regenerate-from-the-writer-down** orchestration.

## The shape of the work

Three moves. No version games, no copies, no temp directories, no codified-researcher re-run. Claude is the one inserting the new sources into the existing research files — judgment about fit, in place. Then the writer re-runs against the enhanced research.

```
1. Sources.md     ← add new URLs (delegate to sources-md-curation)
2. 1-research/*   ← Claude reads each affected file, inserts source content + [^N] inline, in place
3. writer         ← re-run; it produces fresh 2-sections/ from the enhanced research
```

## Step 1 — Add the URLs to Sources.md

Delegate to **sources-md-curation** for the file mechanics. The short version of what that skill does for each URL the user pasted:

1. `fetch_url_markdown(url)` to confirm it reaches and get the real title + body.
2. Read the title + first ~500 chars; pick section tags by cross-referencing `deal.json` → outline → `templates/outlines/<name>.yaml`. If ambiguous, ask the user.
3. Add as a `sources:` entry at the bottom of any "Analyst-added" block in `inputs/Sources.md`, with `note:` recording date and intent.
4. Round-trip parse-test (`load_sources_md()` must succeed and the new entry must appear in `sm.sources`).

Confirm to the user the count + the affected research files:

> Added 4 URLs to inputs/Sources.md, tagged to [team, fundraising-round, fundraising-round, situation--market-overview]. Affected files: 04-team-research.md, 06-fundraising-round-research.md, 03-situation-and-market-overview-research.md.

Keep the fetched markdown for each URL in working memory — Step 2 needs it.

## Step 2 — Claude inserts each new source into the affected 1-research/ files (in place)

This is the load-bearing step and it's done by Claude directly — no separate agent, no prompt template ceremony, no copy of the research file. Edit the existing file in the latest version's `1-research/` directory in place.

For each new source, for each affected research file:

1. **Read the existing research file** (`1-research/<NN>-<section>-research.md`).
2. **Read what the source actually says** — the markdown you fetched in Step 1. Don't work from the title alone.
3. **Find the next local `[^N]` number** for this research file (scan its existing `[^N]` markers; new local number = `max(existing) + 1`).
4. **Use judgment about where the new source fits.** Where in the narrative does it support an existing claim? Where does it add a new fact the narrative should mention? Either is fine — this is enhancement, not strict citation-additive coverage promotion. Light additive edits to the narrative are OK if the new source genuinely adds substance.
5. **Insert.** Drop `[^N]` markers inline next to the relevant sentences. If the source adds a new fact, add a short sentence (one to two sentences max, matching the surrounding voice) with the citation. Stack with existing `[^M]` citations when multiple sources back the same claim.
6. **Append the source appendix block** at the end of the file's source list (following the existing `### Source [^N] (rank N): <title>` pattern the codified researcher uses):

   ```markdown
   ### Source [^N] (rank N): {title}
   URL: {url}
   Fetched: {fetched_at}
   Publisher: {publisher}

   {first ~2KB of clean markdown}
   ```

7. **Write the file back.** In place. Same path, same version directory.

Quality bar: every `[^N]` reflects content Claude actually read in the source. No guessing, no contriving cites. If the source doesn't fit a section it was tagged for, leave it uncited in that file's narrative (the appendix entry stands alone as record).

Report to the user what got inserted where: *"04-team-research.md: added [^15] (Bloomberg Beta partner page) at 3 sentences in the Advisors paragraph plus one new sentence at the end of that paragraph. 06-fundraising-round-research.md: added [^9] (Series A blog post) at 2 sentences alongside [^4]."*

## Step 3 — Re-run the writer (and everything downstream)

Delete the writer's output and everything after it in the same version directory, then resume. The resume CLI's auto-detect picks up at `draft`.

```bash
cd apps/memopop-orchestrator
VDIR=io/<firm>/deals/<deal>/outputs/<deal>-v0.0.N

rm -rf "$VDIR"/2-sections \
       "$VDIR"/2-tables \
       "$VDIR"/3-source-catalog \
       "$VDIR"/3-validation.* \
       "$VDIR"/4-* \
       "$VDIR"/5-* \
       "$VDIR"/7-* \
       "$VDIR"/8-* \
       "$VDIR"/header.md \
       "$VDIR"/redacted-hallucinations.md \
       "$VDIR"/source-validation-log-*.json

source .venv/bin/activate
python -m src.main "<deal>" --firm "<firm>" --resume --version v0.0.N
```

The auto-detect sees 1-research/ populated and 2-sections/ missing → picks up at the writer. The writer reads the enhanced research files; the new `[^N]` markers and source-appendix blocks flow through naturally because they're in its input. Enrichments, cleanup_sections, assemble_citations, validate, fact-check, scorecard, finalize all run normally.

Cost: one writer pass ($3–5) + enrichments + validators. No researcher work, no broad search.

## What this skill does NOT do

- **Does not copy or temp the research files.** Editing them in place is correct. The prior version directory is not preserved as a historical artifact for this enhancement step — if the user wants that, they can take a snapshot before invoking this skill.
- **Does not re-run the codified researcher.** The whole point is that the research narrative is already drafted; we're enhancing it directly, not regenerating it.
- **Does not bump the version.** Same version directory throughout. The resume re-creates 2-sections/ and everything after.
- **Does not invoke a separate insertion agent or prompt template.** Claude does the writing directly using its judgment, in conversation. No templated rules, no word-count delta checks, no temperature ceremony.
- **Does not run a fresh broad search.** That's a different workflow (start from scratch, let aggregator halt, edit Sources-aggregated.md, codify).

## Common failure modes

1. **Resume auto-detect picks the wrong node.** If 2-sections/ or downstream artifacts didn't get fully cleaned, the detector may pick up downstream of `draft` and skip the writer. Re-check the `rm -rf` list and the version directory.

2. **New URL is bad** (404, paywalled non-allow-listed publisher, hallucination-pattern). The fetch in Step 1 catches hard failures; the downstream `cleanup_sections` gate catches the rest via the verdict ladder.

3. **Claude duplicates an existing `[^N]` number** when inserting. Always scan the file for max existing N before assigning. Per-file local numbering, not global.

4. **User-tagged section doesn't exist in the outline.** Sources.md will accept the entry but it won't match any research file in Step 2. Cross-check tags against the outline YAML during Step 1 — sources-md-curation knows the canonical names.

5. **User adds a URL that's already in Sources.md.** Don't create a duplicate entry. Update the existing entry's tags/rank if needed and add a new `[^N]` to the affected research files only if the original `[^N]` for that URL isn't already serving the relevant sentences.

6. **Outline changed between when the research was generated and now.** Don't switch outlines mid-workflow. Follow `sources-md-curation`'s *Outline-switch caveat* first if applicable.

## Compose with

- **`sources-md-curation`** — Step 1 of this skill delegates URL-tagging mechanics there. This skill orchestrates the wider workflow; that skill knows the file's grammar.
- **`changelog-conventions`** — when the addition was substantive (multiple URLs, materially changed the memo's argument), a short changelog entry under `apps/memopop-orchestrator/changelog/` is warranted.
- **`context-vigilance`** — Sources.md follows the convention; the enhanced research files do too.

## See also

- `apps/memopop-orchestrator/cli/resume_from_interruption.py` — the auto-detect logic; read it to know which artifacts trigger which resume point
- `apps/memopop-orchestrator/src/agents/codified_section_researcher.py` — the agent whose output Claude is editing in place (NOT calling)
- `apps/memopop-orchestrator/src/curation/fetch.py` — the fetcher used in Step 1
- `apps/memopop-orchestrator/context-v/plans/Citation-Coverage-Promoter.md` — the structural version of upstream coverage discipline; this skill's human-triggered counterpart
