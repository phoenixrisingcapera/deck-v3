---
name: source-with-extracts-md
description: The assumed (evolving-toward-canonical) structure of a single per-source markdown file that preserves ONE web source plus the analyst's extracts — quotes, claims, stats, references — pulled from it. Use whenever the user saves a search result or pasted URL as its own .md file, captures or pastes an extract (a quote / stat / claim / reference) from a source, asks "what should this source file look like", promotes a preview-only candidate to full fetched content, or wraps pasted rich text into the extract format. Encodes the frontmatter schema (mapped to Jina Reader results), the hard rule that extracts live in the BODY as Lossless Flavored Markdown directives (NOT YAML, which breaks on quote/stat punctuation), the `:::quote` / `:::claim` / `:::stat` directive vocabulary, references as hex-code citations, the two-tier fetch lifecycle (cheap preview → full-on-promote), and where the file sits inside a per-search folder. Distinct from `sources-md-curation`, which manages the per-deal Sources.md LIST; this skill is about ONE source's own file. The structure is deliberately marked ASSUMED — it is still converging; treat the directive syntax as the current best guess, not a frozen contract.
---

# A Source-with-Extracts Markdown File

> This is the file shape that preserves **one** web source — its fetched content plus the extracts an analyst pulls from it. One source, one `.md` file. It is the per-item artifact behind the [[Source-Curation-Gate]] (see `../../context-v/blueprints/Source-Curation-Gate.md` in the ai-labs parent). The structure here is **assumed and evolving** — we expect it to be messy before it's canonical. Treat the schema as the current working agreement, document deviations, and let it converge.

## When this skill activates

- The user saves a SearXNG result or a pasted URL as its own markdown file.
- The user pastes a **quote, claim, stat, or reference** lifted from a source and wants it preserved.
- The user asks what a saved source file should contain, or how extracts should be formatted.
- The user **promotes** a preview-only candidate (metadata + first 200 chars) to full fetched content or a downloaded PDF.
- The user asks why extracts aren't (or shouldn't be) in the YAML frontmatter.

## The behavioral core

1. **One source = one file.** Never merge two sources into one file. The unit is the source.
2. **Frontmatter is for short scalars; the body is for content and extracts.** The dangerous, punctuation-heavy text (quotes with `: " $ % [ ]`, stat strings, reference citations) goes in the **body as directives**, never as YAML values — YAML breaks on exactly that content.
3. **Two-tier fetch.** On save, pull cheap metadata + a ~200-char excerpt (Jina Reader). Only on **promote** pull the full body or download the PDF. Don't fetch full content for a candidate that may be rejected.
4. **Extracts are LFM directives, and the parse IS the extraction.** Wrap pasted text in the right `:::` directive. Because it's machine-parseable, there is no separate structured copy to keep in sync — do not also write the extract into YAML.
5. **References are hex-code citations**, never sequential `[^1]`.
6. **Flag the assumption.** When the structure is ambiguous, say so and pick the current best guess rather than inventing a parallel convention; note the deviation so it can be folded into the canonical shape later.

## Where the file lives

Inside a per-search folder (the gate's capture layout). The search owns a manifest; each saved source is a file under `relevant_results/`:

```
<gate-root>/
  2026-06-27_ocean-energy-market-size/        # ISO date + slugified query
    _search.md                                # the search manifest (query, raw candidates, notes)
    relevant_results/
      ocean-energy-systems-annual-report.md   # ⭐ ONE source-with-extracts file (this skill)
      irena-2025-offshore-outlook.md
```

The folder name is a **slug**; the verbatim query lives in `_search.md`'s frontmatter (filenames can't hold `/ : ? " *`).

## File anatomy

A complete file = **frontmatter (scalars) → optional verbatim content → `# Extracts` (directives)**.

```markdown
---
title: "IEA-OES Annual Report (release announcement)"
url: https://www.ocean-energy-systems.org/news/iea-oes-releases-annual-report/
normalized_url: ocean-energy-systems.org/news/iea-oes-releases-annual-report
publisher: "IEA Ocean Energy Systems (OES)"
origin: searxng            # searxng | perplexity | analyst-paste | analyst-added
search_query: "ocean energy market size"     # verbatim query that surfaced it (if any)
engine: google             # which SearXNG engine returned it
fetched_at: 2026-06-27T14:31:00Z
published_at: 2025-03-01
description: "Annual stocktake of global ocean-energy capacity and outlook."   # Jina/OG metadata
excerpt: "The IEA-OES annual report finds installed ocean-energy capacity reached…"  # first ~200 chars
status: candidate          # candidate | promoted | archived | rejected
content_pulled: false      # flips true once the full body / PDF is pulled on promote
asset_path:                # path to a downloaded PDF, if any
verdict: verified-accessible   # the validator ladder; unchecked until validated
confidence: 0              # 0–100; set by url-shape + name + recency scoring
sections: [colossal-market-size, cagr]   # which deliverable sections this serves
rank: 1                    # 1 = primary; drives downstream hedge calibration
sensitivity: citable_externally    # or internal_only
note: "Analyst-added 2026-06-27. Authoritative annual stocktake."
# NOTE: extracts do NOT live here. They live in the body as LFM directives (below).
# Frontmatter holds short controlled scalars only; quote/stat/reference text breaks YAML.
---

# IEA-OES Annual Report (release announcement)

<!-- Verbatim fetched body goes here once status: promoted (content_pulled: true).
     While status: candidate, this is empty or holds only the excerpt. The body is
     SACROSANCT and quotable — do NOT LLM-summarize it; store it as fetched. -->

# Extracts

## Quotes
:::quote{page="12"}
"Installed ocean-energy capacity will reach 10 GW by 2030 — a 40% CAGR: unmatched in marine power."
:::

## Claims
:::claim{confidence="high"}
Ocean energy is structurally counter-cyclical to fossil-fuel price swings.
:::

## Stats
:::stat{metric="market-size" value="5B" unit="USD" year="2030"}
Global ocean energy TAM projected at $5B by 2030.
:::

## References
IEA-OES (2025). *Annual Report*.[^a1f9]

[^a1f9]: 2026-06-27. [IEA-OES Annual Report](https://www.ocean-energy-systems.org/news/iea-oes-releases-annual-report/). Publisher: IEA-OES. Published: 2025-03-01.
```

## Frontmatter schema

| Field | Required | Meaning |
|---|---|---|
| `url` | ✅ | The exact source URL. The only hard requirement. |
| `title` | — | As **fetched**, not as claimed by whatever listed it. |
| `normalized_url` | — | Dedup key — query/hash stripped, trailing slash removed. Lets the same source be detected across two searches. |
| `publisher` | — | Domain or named publisher; used for recovery `site:` queries. |
| `origin` | — | How it entered: `searxng` / `perplexity` / `analyst-paste` / `analyst-added`. |
| `search_query` | — | Verbatim query that surfaced it (mirrors the `_search.md` slug). |
| `engine` | — | Which underlying SearXNG engine returned it. Document it. |
| `fetched_at` / `published_at` | — | ISO timestamps (Jina/OG metadata). |
| `description` / `excerpt` | — | The cheap preview: metadata blurb + first ~200 chars. |
| `status` | — | `candidate` → `promoted` → (`archived` \| `rejected`). |
| `content_pulled` | — | `false` until the full body / PDF is pulled on promote. |
| `asset_path` | — | Path to a downloaded PDF, if any. |
| `verdict` | — | Validator ladder verdict (see `sources-md-curation` for the full ladder). |
| `confidence` | — | 0–100 score. |
| `sections` | — | Which deliverable sections this source serves (tags). |
| `rank` | — | 1 = primary; drives writer hedge calibration. |
| `sensitivity` | — | `citable_externally` (default for public web) or `internal_only`. |
| `note` | — | Free-form analyst rationale, dated. |

Only `url` is required. Everything degrades gracefully.

## The `# Extracts` body — LFM directives, not YAML

Extracts are pasted rich-text strings full of `: " $ % [ ] |` — every character that breaks YAML. So they live in the **body** as [Lossless Flavored Markdown](../../../../context-v/skills/lossless-flavored-markdown/SKILL.md) **container directives**, under a `# Extracts` heading, sectioned `## Quotes` / `## Claims` / `## Stats` / `## References`. The dangerous text is the directive **body** (plain markdown, zero escaping); only short controlled metadata is in **attributes**.

| Extract type | Directive | Body holds | Attributes (optional) |
|---|---|---|---|
| Quote | `:::quote{…}` | the verbatim quote | `page`, (`speaker`) |
| Claim | `:::claim{…}` | the asserted claim | `confidence` (`high`/`med`/`low`) |
| Stat | `:::stat{…}` | a human sentence of the stat | `metric`, `value`, `unit`, `year` |
| Reference | hex-code footnote | the citation line | — (use `[^hex]`) |

**Why this is the structure (not a workaround):**

- **The parse is the extraction.** `remark-directive` (LFM's parser) turns `:::stat{…}` into `{ name: 'stat', attributes: {…}, children: [text] }`. There is **no YAML mirror**, so **nothing drifts** — a structured consumer reads the directives directly. If a YAML/JSON mirror is ever needed, it is **generated** and marked `# generated — do not edit`.
- **The pasted string never touches YAML or even an attribute value** — it is the directive body.
- **References resolve to the tree's real citation system** (hex-code footnotes with build-time OG hover-popovers), so they are bindable handles a downstream grounded-generation writer can cite — the whole reason the gate exists.

### LFM rules to honor

- Directive props are **strings and must be quoted**: `value="5B"`, not `value=5B`.
- `type` and `format` are **reserved** attribute names — use `metric=` on `:::stat`, never `type=`.
- `:::` open/close pairs are **strict** (lint with `pnpm lfm:check` where available).
- References use **hex codes** (`[^a1f9]`), never sequential `[^1]` — sequential breaks on reorder.
- For pure storage the directives parse for free even with no component registered; register `quote`/`claim`/`stat` triggers only if a site/splash later *renders* them.

## Lifecycle (status field)

| status | Body content | content_pulled | Meaning |
|---|---|---|---|
| `candidate` | excerpt only | `false` | Saved from a search; cheap preview pulled; not yet committed. |
| `promoted` | full verbatim body (or PDF at `asset_path`) | `true` | Analyst committed it; Jina pulled all content. The citable artifact. |
| `archived` | preserved | — | Set aside but kept (provenance retained). |
| `rejected` | excerpt + `note` why | — | Discarded; the `note` is institutional memory so it isn't re-saved next run. |

## Operations the agent should support

### Save a search result as a candidate
1. Take the URL + title from the SearXNG result.
2. Jina-fetch **metadata + first ~200 chars** only (cheap preview).
3. Write the file under the search's `relevant_results/` with `status: candidate`, `content_pulled: false`, the `excerpt`, and `origin: searxng`.
4. Filename = slug of the title (filesystem-safe).

### Promote a candidate to full content
1. Flip `status: promoted`, set `content_pulled: true`.
2. Jina-fetch the **full** body (or download the PDF → set `asset_path`).
3. Write the **verbatim** body under the `# <title>` heading — do **not** LLM-summarize it (summarizing at ingest is where facts get corrupted).

### Capture a pasted extract
1. Identify type (quote / claim / stat / reference).
2. Wrap it in the matching directive under the right `## ` subheading, paste text into the **body**, put only short metadata in attributes.
3. For a reference, write a hex-code footnote definition + place the `[^hex]` marker where it's cited.
4. Do **not** also write it into YAML.

### Dedup across searches
If the source's `normalized_url` already exists in another search folder, prefer recording the **mention** in the new `_search.md` (per `sources-md-curation`'s pool discipline) over writing a duplicate file. One artifact, many mentions.

## Common pitfalls

1. **Putting extracts in YAML.** The single most common mistake. Quote/stat text breaks the parser. Extracts go in the body as directives. Always.
2. **LLM-summarizing the body on promote.** The promoted body must be the source text **as written** — it's what gets quoted and cited. Summarize and you've corrupted the only thing downstream can ground against.
3. **Sequential `[^1]` references.** Use hex codes; sequential breaks the moment a reference is reordered or copied.
4. **Unquoted directive props / using `type=` on `:::stat`.** Props are strings (`value="5B"`); `type` is reserved (use `metric=`).
5. **Verbatim query in the folder name.** Folder = slug; verbatim query lives in `_search.md`.
6. **Treating this structure as frozen.** It is **assumed/evolving**. If a real source needs a shape the schema doesn't cover, pick the closest current convention, note the deviation in `note:`, and surface it so the canonical shape can absorb it.

## Relationship to neighbors

- **`sources-md-curation`** — manages the per-deal `Sources.md` **list** (which sources, ranked, tagged to sections). This skill is about **one source's own file** with its extracts. The list points at sources; this file *is* a source.
- **`user-adds-adhoc-sources`** — the in-app-chat contract for the user adding a source ad hoc; the file it writes follows **this** structure.
- **`../../context-v/blueprints/Source-Curation-Gate.md`** (ai-labs) — the convergent pattern; this skill is its per-item file format made operational, delivered (per the gate's Slab-3 plan) as an evolving agent-skill.

## See also

- `../../context-v/plans/In-App-Chat-Surface-for-Memopop-Native.md` — the chat surface that will load this skill into Slab 3.
- `lossless-flavored-markdown` skill — the directive + hex-code-citation syntax this file uses.
- `context-vigilance` — the frontmatter-for-machines / body-for-humans convention this follows.
