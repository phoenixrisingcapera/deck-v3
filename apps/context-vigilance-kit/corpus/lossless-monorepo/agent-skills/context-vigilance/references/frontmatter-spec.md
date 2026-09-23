---
source_root: /Users/mpstaton/code/lossless-monorepo/context-v
source_relative_path: agent-skills/context-vigilance/references/frontmatter-spec.md
source_repo_slug: lossless-monorepo
collated_at: '2026-08-24'
source_path: "context-v/agent-skills/context-vigilance/references/frontmatter-spec.md"
---

# Frontmatter Spec for `context-v/` Documents

> **In practice, frontmatter is scattered.** Some files are richly tagged with status, supersedes, related, aliases. Others have only `title` and `date_created`. Both are fine. This document describes the *aspirational* baseline for new files — not a validator's checklist.

Most Markdown files under `context-v/` start with YAML frontmatter delimited by `---` lines. Be generous reading; be thoughtful writing.

## Property names: always `snake_case`

**All frontmatter property names in `context-v/` are `snake_case`.** This is not a stylistic preference — **Obsidian's frontmatter rendering and property indexing enforce it**, and most Lossless `context-v/` directories are symlinked into Obsidian vaults. camelCase and kebab-case keys break Obsidian's property panel and graph indexing.

- ✅ `date_created`, `augmented_with`, `semantic_version`, `superseded_by`, `implements_spec`, `related_blueprint`
- ❌ `dateCreated`, `augmented-with`, `SemanticVersion`, `supersededBy`

The rule applies to **keys only.** Values are governed separately:

- `tags` values → **Train-Case** (e.g., `Markdown-Rendering`)
- `status` values → **Train-Case** (e.g., `In-Discussion`, `Signed-Off`) — see the `status` row below
- `authors`, `augmented_with` values → free-form human-readable strings
- Dates → `YYYY-MM-DD`

When introducing a new property anywhere in the tree (in a doc, a template, a tool, a script): name the key in `snake_case`, no exceptions. When you encounter an existing file with a non-`snake_case` key, surface it to the user rather than silently renaming — some sites' build tooling or content collections may be reading the field by its current name.

## Canonical example

```yaml
---
title: "Maintain an Extended Markdown Render Pipeline"
lede: "Why our markdown pipeline is the asset — and where it's heading next."
date_created: 2026-03-30
date_modified: 2026-05-03
authors:
  - Michael Staton
augmented_with:
  - Pi on Claude Sonnet 4.5
semantic_version: 0.1.2.0
tags:
  - Markdown
  - Rendering
  - Astro
---
```

## Baseline fields (recommended for new files)

| Field | Type | Notes |
|---|---|---|
| `title` | string | Human-readable. Quote it if it contains a colon. Title Case. |
| `lede` *(or `description`)* | string | **A rendering field: the one line under the title on a card, list view, or social preview.** It exists because `title` says *what a thing is* and `description` is always too long and too boring to read on a card — `lede` says *why you'd care*, in a glance. **Optional on any `context-v/` doc-type** — spec, prompt, blueprint, exploration, reminder, issue. Newsroom-style hook that makes a reader want to keep reading. **Keep it subtitle-length: 140 characters maximum, target 90–130 — two rendered lines, never three.** That is a hard budget, not a guideline: an OpenGraph unfurl truncates around 200 characters and a list card wraps sooner, so a longer lede clips mid-sentence on exactly the surfaces the field exists to serve. **Write ONE clause that lands**, not a sentence with a subordinate clause trailing off it. Prose guidance like "a few sentences" is too vague to hold — a 2026-08-17 sweep briefed against the old wording produced 55 ledes averaging 370 characters, all of which had to be rewritten. Never trade specificity for brevity, though: a short generic lede ("A profile of Qdrant, a vector database") is the worst outcome, worse than none at all. If a document genuinely cannot be hooked in 140 characters, that is worth surfacing rather than papering over — it's the single line shown in a list view / preview card / OG snippet before a reader decides to click, so a lede that runs long has stopped being a hook. When the lede wants to grow, that material belongs in a `## Why Care?` (or context) section in the body, not the frontmatter. **`lede` is preferred** over `description` because the word itself signals the job (*grab attention*); both are accepted. Many `context-v/` docs render publicly through Astro Knots sites, so the lede also doubles as the OpenGraph / preview-card / list-view summary. See the `context-vigilance` skill's *Lede length discipline* and the `changelog-conventions` skill for the deeper rationale and concrete examples. |
| `publish` | boolean | **A decision, not a measurement — and a *website* gate, not a retrieval gate.** See *`publish` gates the website* below: on a context-v doc, `false` does **not** remove it from Chroma or Graphiti; only `private: true` does. `true` if there's real content a reader would get value from; `false` for a stub, a title with nothing under it, an empty placeholder, or a doc whose every section is `[awaits discussion]` / `<!-- developing -->`. **If the key already exists, never flip it** — especially never `false` → `true`. Judge it by *reading*: a stale "Stub" banner over a fully-developed body is `true`; a polished title and lede over twelve placeholder sections is `false`. Word counts get both backwards. |
| `date_created` | YYYY-MM-DD | **Filesystem.** When the bytes appeared. Set once. Never change — and never overwrite an existing value with `stat` (see *Filesystem dates lie* below). Legacy spelling `created:` renames to this, value verbatim. |
| `date_modified` | YYYY-MM-DD | **Filesystem.** Update on every meaningful edit. Obsidian bumps this on mere *open*, so it is not the field a timeline should read — that's `date_authored_current_draft`. Never stamp it with today as a side effect of an automated pass; read it before editing. |
| `date_authored_initial_draft` | YYYY-MM-DD | **Editorial.** When the content was first *set* — real, coherent, not a stub. Not when the file was created empty. Set once. Legacy spelling `date:` renames to this. |
| `date_authored_current_draft` | YYYY-MM-DD | **Editorial.** When the doc last received a **substantive** revision. Never earlier than `initial_draft`; if the best source would be, set them equal. Moves together with `at_semantic_version`. |
| `authors` | list of strings | **Humans only.** Always a list, even with one entry. |
| `augmented_with` | list of strings | AI tools used. Format: `<tool> on <model name version>`. Include whenever an AI agent contributed materially. |
| `at_semantic_version` | string `e.M.m.p` | Four-part. See `versioning.md`. New docs start at `0.0.0.1`. **This is the standard spelling** (~4,140 files). `semantic_version` (~330 files) is a **permanently-accepted alias for the same property and value** — not a legacy form awaiting migration. Write `at_`, read either, and never rewrite an existing file just to change which name it uses. Consumers resolve the field as `at_semantic_version ?? semantic_version`. |
| `tags` | list of strings | **Train-Case** (e.g., `Markdown-Rendering`). At least one tag. |

### Filesystem dates lie — which is why the editorial pair exists

`context-v/` documents constantly evolve, so "when did this last really change?" is the question the directory has to answer. The filesystem cannot answer it:

- **`date_modified` overstates recency.** Obsidian's templater bumps mtime when you merely open a file. A spec untouched in substance for three months can show yesterday's date.
- **`date_created` can overstate age-of-origin.** A machine recovery in this tree reset birthtime on a batch of files to the recovery date. Where frontmatter already records an *earlier* `date_created` than `stat` reports, **the frontmatter is the more accurate record.** Never overwrite it.
- **Deriving a missing `date_created`?** Prefer `date_authored_initial_draft` over filesystem birthtime. A document cannot have been created after its own first draft.

#### Source precedence when a date must be derived

Use the first one that resolves. **`stat` is last, not first.**

1. **An existing frontmatter date** on the same file (`date_authored_initial_draft`, `date_created`, `date_modified`).
2. **A date encoded in the filename** — `2025-11-26_03.md` → `2025-11-26`. Changelog entries always carry this.
3. **A date stated in the document's own body** — release notes often name their ship date.
4. **Git first-commit date:** `git log --diff-filter=A --follow --format=%ad --date=short -- <file> | tail -1`. This is the strongest *derived* source and beats the filesystem outright, because git records when the content actually entered the repo.
5. **Filesystem `stat`** — only when everything above fails, and treat the result as suspect.

**Why `stat` is last.** Whole directories in this tree carry a birthtime from a bulk copy or machine recovery rather than from authorship. Observed cases: a hundred changelog entries spanning Nov 2025 – Mar 2026 all reporting `created=2026-05-06 modified=2026-05-06`, and a set of release-notes files reporting a birthtime of *the day the sweep ran* while git dated them nine months earlier. A uniform birthtime across files of obviously different ages is the tell. When you see it, drop to git.

If an existing file is missing any baseline field, **don't silently add them while doing unrelated edits** — surface the gap to the user first. Frontmatter changes are a separate concern from content changes. (The exception is an operator-directed sweep — see *Validation philosophy* at the bottom.)

## Optional fields

Add as needed; do not invent fields without precedent in the project. Common ones seen in the wild:

| Field | Purpose |
|---|---|
| `summary` | **The agent-facing counterpart to `lede`.** Where `lede` competes for a human's attention pre-click, `summary` answers what an agent asks before opening the file: *what is this document for, where does it sit in the workflow, and what logic downstream should care about it?* Optional everywhere, but worth writing on any doc another agent will have to triage — an agent can produce it in the same pass as the lede. **Not a longer lede.** `lede` flows into OpenGraph automatically and is length-constrained by an unfurl card; `summary` renders nowhere, so it can be as long as the orientation needs. See *`lede` vs. `summary`* below — including the legacy-alias trap. |
| `status` | **Train-Case display string** (e.g., `Draft`, `In-Review`, `Signed-Off`, `Implementing`, `Shipped`, `Partially-Shipped`, `Deferred`, `Stale`, `Superseded`, `Archived`). Treat as a rendering string for humans, **not a machine enum** — don't switch on these values in code, since spelling and casing drift across files. The Train-Case casing is the signal: "this property exists for display, not for build/render-pipeline branching." Update status as work lands; don't let it rot at `Draft`. Companion fields are required for `Shipped`, `Partially-Shipped`, `Deferred`, and `Superseded` — see `status-discipline.md` for the full lifecycle, companion-field rules, and the `## Remaining work` section convention. Spec-specific progression lives in `developing-a-spec.md`. |
| `date_authored_final_draft` | `YYYY-MM-DD`, or **present-but-empty**. Empty is meaningful: "not final yet." **Do not delete the empty key** — its presence is the signal that finality is being tracked. |
| `date_first_published` | `YYYY-MM-DD`. The ship date, set when `status:` first becomes `Shipped` or `Partially-Shipped`. Never updated after — it anchors when the work first landed. |
| `date_work_started` | `YYYY-MM-DD`. **When the work this document describes began** — not when the document was written. A separate axis from the editorial pair; see *Work dates vs. document dates* below. Optional; omit rather than guess. |
| `date_work_completed` | `YYYY-MM-DD`. When that work finished. Independent of `date_work_started` — recording only the completion is fine. Must not precede it. |
| `date_last_updated` | `YYYY-MM-DD`. Any touch, substantive or not. Contrast `date_authored_current_draft`, which moves only on substantive revision. Having both is intentional: one tracks activity, the other tracks meaning. |
| `post_ship_note` | Multiline string. Things learned after `Shipped`. Useful when later work invalidates or sharpens a claim the plan made. See `status-discipline.md`. |
| `deferral_note` | Multiline string. Required when `status: Deferred`. Names the reason and (where known) the expected unblocker. |
| `supersedes` | wikilink or filename of the doc this one replaces |
| `superseded_by` | reverse of above |
| `related` | list of `[[wikilinks]]` to related docs |
| `aliases` | alternate titles for Obsidian linking |

### `lede` vs. `summary` — two audiences, two jobs

They are not long and short versions of each other. Different readers, different consuming surfaces.

| | `lede` | `summary` |
|---|---|---|
| **Audience** | humans, pre-click | agents, and humans orienting mid-workflow |
| **Job** | grab attention; convert interest into a click and time on page | situate the document: purpose, workflow position, what consumes it |
| **Voice** | newsroom hook; specific, surprising | plain and declarative; no salesmanship |
| **Consumed by** | list views, preview cards, search results, **OpenGraph/social unfurls** | agent retrieval, Chroma/Graphiti ingest, roll-up logic, an agent deciding whether to open the file |
| **Length** | **140 chars max, target 90–130** — two rendered lines. A hard budget. | a few sentences; may exceed the lede freely, since nothing renders it in a card |

**The rendering split is the practical reason to keep them separate.** `lede` (or `description`) is what flows into OpenGraph automatically, so it is constrained by an unfurl card — stuffing workflow context into it degrades the surface the field exists to serve. `summary` has no such constraint. Each field gets to be good at one thing.

**What belongs in a `summary`:**

- What the document is *for* — the purpose behind it, not a restatement of the title.
- Where it sits in a workflow — what it unblocks, what it supersedes, what has to happen before or after it.
- How pseudomonorepo or `context-vigilance` logic might use it — which repo tier it affects, whether it defines a convention other repos inherit, whether it's roll-up-worthy or purely local, which doc-type conventions apply.
- What an agent should do with the knowledge — "read this before touching X," "the spec it points at is the authority, not this file."

This is most valuable on the doc-types an agent has to *triage* rather than read: specs, blueprints, handoffs, and issues, where the cost of opening the wrong file is a wasted context window.

#### `summary` is a claimed name — check before you write one

**Some repos historically used `summary` as a spelling of `lede`.** `astro-knots/sites/fullstack-vc` is the known case: 22 changelog entries carry human-facing subtitle prose under `summary`, predating this definition.

- **Never assume an existing `summary` means what this section describes.** On a file with `summary` and no `lede`, the value is almost certainly a legacy lede.
- **A renderer doing `lede ?? summary` will render agent prose in a human slot** on any file written to this spec that lacks a `lede`. The fix is to write a real `lede`, not to shorten the `summary`.
- **Migrating a legacy `summary` is a content edit, not a normalization** — a directed pass, outside an additive-only sweep. Same rule as repairing a broken lede.

### Work dates vs. document dates — two different timelines

Every other date on a `context-v/` document is about the **document**:
`date_created` when the file appeared, the editorial pair when the content was
set and last revised. `date_work_started` / `date_work_completed` are about the
**work the document describes**.

For a spec or a plan those come apart hard. A plan is written *before* the work,
revised *during* it, and the work finishes long after the last edit:

```yaml
date_authored_initial_draft: 2026-04-02   # plan written
date_authored_current_draft: 2026-04-28   # revised as scope moved
date_work_started: 2026-04-08             # implementation began
date_work_completed: 2026-06-11           # shipped
```

None of those four is derivable from another. A document whose editorial dates
sit in April is not a document about April's work.

**Why capture it.** Rendered surfaces build timelines, and a timeline keyed on
authorship shows when someone sat down to type — not when anything happened. For
`context-v/` this is worse than for changelog, because the gap between writing a
plan and finishing the work it plans is routinely months. Any tooling that helps
a developer fold `context-vigilance-kit` into their own workflow — how long did
this actually take, what was in flight in Q2, where are the plans that were
written and never worked — is asking about the work axis. It cannot ask until
the data exists.

**Rules.**

- **Optional, and independently so.** `date_work_completed` on its own is a
  useful record. Write what is known.
- **`date_work_completed` must not precede `date_work_started`.**
- **Do not derive either from the filesystem.** `date_created` is a fact about
  the file. If the work dates are not known, omit them — an absent field is
  honest, an inferred one quietly corrupts the timeline it was added to serve.
- **Do not backfill.** Nobody reliably remembers when work started six months
  ago, and a guessed timeline is worse than no timeline.
- **They pair naturally with `status`.** `date_work_completed` is normally set in
  the same edit that moves `status` to `Shipped`, and sits alongside
  `date_first_published`. Where `date_first_published` records when the *result*
  went out, `date_work_completed` records when the *effort* ended — those differ
  whenever something is finished but held.

The convention is already live on eleven entries in
`content-farm/plugin-modules/perplexed`, which is why it is being written down
rather than invented.

## Identity fields — `site_uuid` and `hex_code`

Two stable identifiers, both cheap to generate and both **write-once**. Neither does much on its own today; together they are what lets the corpus be addressed by something other than its filename. **Start writing them on new files now** — retrofitting identity onto a corpus is far more expensive than minting it at creation, and the corpus is already past 1,850 `context-v/` documents and 930 changelog entries.

| Field | Shape | Set |
|---|---|---|
| `site_uuid` | UUID v4, lowercase, canonical hyphenated form | once, at file creation — never regenerated |
| `hex_code` | 6 chars, `[a-z0-9]` | once, at file creation — never regenerated |

### Why the filename is not enough

`[[Filename-to-Reference]]` with no path works today because everything is on one filesystem and the resolver can walk the tree. It is also **already ambiguous**. A single blueprint in this tree resolves to eight files:

```
lfm/context-v/Maintain-Embeddable-Slides.md
content/lost-in-public/blueprints/Maintain-Embeddable-Slides.md
astro-knots/context-v/blueprints/Maintain-Embeddable-Slides.md
astro-knots/sites/mpstaton-site/src/content/context-v/astro-knots/blueprints/…
ai-labs/context-vigilance-kit/corpus/lfm/…
ai-labs/context-vigilance-kit/corpus/astro-knots/blueprints/…
ai-labs/context-vigilance-kit/corpus/lost-in-public/blueprints/…
site/src/generated-content/lost-in-public/blueprints/…
```

Same document, one original plus roll-ups and generated copies. **`site_uuid` is the only thing that distinguishes "eight copies of one document" from "eight different documents"** when the filename matches too. That distinction is invisible to a wikilink and to a filename-keyed index — and it is exactly what a retrieval layer gets wrong.

This is why the identifier **travels with the document into every roll-up**. Copies sharing a `site_uuid` is correct behavior, not a duplicate to clean up. In this tree 3,129 values are currently shared across 6,599 files for precisely this reason.

### Why it earns its keep as the corpus grows

- **Stable keys across re-ingest.** Chroma and Graphiti are already reading this corpus, and more stores are coming. Without a document-stable ID, every re-ingest mints new nodes and the history of a document through the graph is unrecoverable — you can't ask "how did this spec change" because nothing connects the versions. A `site_uuid` in the frontmatter survives re-ingest, file moves, and renames.
- **Rename survival.** Filenames change; `context-v/` documents get retitled as their scope sharpens. A filename-keyed reference breaks silently. A UUID-keyed one does not.
- **Disambiguation across pseudomonorepos.** Two repos can hold same-named documents that are genuinely different things.
- **Live-sync to a multi-modal store (SurrealDB is the current favourite)** needs a primary key that the source of truth owns. That is what `site_uuid` is.

### `site_uuid` — and why not just `uuid`

**The name is deliberate.** Databases issue their own `uuid` primary keys; a document synced into one would then carry two different meanings under the same key name. `site_uuid` names the identity that is **valid local to the project** — the authoring vault, wherever it renders on the web, and the pseudomonorepo / `context-vigilance` context — and leaves `uuid` free for whatever store the document lands in. Sync layers map `site_uuid` → their own `uuid` without a collision.

~6,650 files across the tree already carry it, overwhelmingly as lowercase v4.

### `hex_code` — the document's own citation ID

**This is what makes the corpus self-citing.** The `lossless-flavored-markdown` skill already specifies hex-code citations and says to *reuse a source's existing hex ID* so the same citation renders identically across documents. `hex_code` is where that ID lives when the source is **one of our own documents**.

Using it: inline footnote markers, definitions collected in a `## References` section at the bottom.

```markdown
The sweep found the standard was being restated inconsistently between batches.[^a4f2c1]
Filesystem birthtime is not a reliable authorship date.[^9de07b]

## References

[^a4f2c1]: [[Frontmatter-Normalization-Remaining-Repos]]
[^9de07b]: [[Context-Vigilance-Frontmatter-Spec]]
```

This is native Obsidian footnote syntax, so it renders in the vault with hover previews and works as an aggregation surface across every pseudomonorepo. It also gives LFM a real render target on Astro Knots sites — the citation resolver already handles hex-code footnotes; pointing one at a wikilink instead of an external URL is the same mechanism.

**Never sequential `[^1]`.** Sequential markers collide the moment a paragraph is copied between documents — the failure the hex-code convention exists to prevent. See `lossless-flavored-markdown/references/syntax-and-directives.md`.

### Generating them — a command, never the model

**An agent must shell out for these. It must never type an identifier from its own head.** A language model producing a "random" UUID emits something UUID-*shaped* drawn from training-data frequency: biased, repetition-prone, and not actually unique.

This has already happened here. Seven `site_uuid` values in the tree contain characters that are not hex digits at all:

```
1n870f09-5578-4a74-a05d-a2f98752z7b9      ← n, z
a0354223-396h-4rb4-a6ca-97afbe5cff17      ← h, r
aad9a307-5897-418b-a822-f02gdbf6cb48      ← g
y8f59v34-aa5b-4f79-b8a7-93c3fc99a89f      ← v, y
```

Every one is a model that typed a plausible-looking string instead of calling a generator. They are not valid UUIDs and will fail any strict parser downstream.

```bash
# site_uuid — any of these
uuidgen | tr 'A-Z' 'a-z'
python3 -c "import uuid; print(uuid.uuid4())"
node -e "console.log(crypto.randomUUID())"

# hex_code — 6 chars of [a-z0-9]
LC_ALL=C tr -dc 'a-z0-9' </dev/urandom | head -c6; echo
python3 -c "import secrets,string; a=string.ascii_lowercase+string.digits; print(''.join(secrets.choice(a) for _ in range(6)))"
```

#### The charset matters more than the name suggests

**`hex_code` is a slight misnomer — the charset is `[a-z0-9]` (base36), not `[0-9a-f]`.** Keep the established name; do *not* narrow the charset to true hex. The difference is the whole ballgame at corpus scale:

| Documents | 6 chars of true hex (16⁶ ≈ 16.8M) | 6 chars of `[a-z0-9]` (36⁶ ≈ 2.18B) |
|---|---|---|
| 2,784 (today) | **20.6%** chance of a collision | 0.18% |
| 10,000 | **94.9%** | 2.3% |
| 25,000 | ~100% | 13.4% |

`openssl rand -hex 3` is therefore the **wrong** generator here despite being the obvious one — it draws from 16 characters and collides at today's corpus size one time in five. Use the `tr -dc 'a-z0-9'` form above.

#### Check before you commit

Cheap, and definitive — the corpus is the registry:

```bash
grep -rl "<the-new-code>" --include='*.md' /Users/mpstaton/code/lossless-monorepo
```

No output means it's free. Regenerate on a hit. Worth doing for `hex_code` every time; unnecessary for `site_uuid`, where v4 collision is not a real-world risk.

### Retrofitting is a directed pass, not a side effect

Both fields are **additive and safe** — nothing reads them yet, so adding one cannot break a render. That does not make a sweep free: minting identity for 2,700 existing documents is an operator-directed decision, and the roll-up copies mean a naive `find` would assign *different* `site_uuid`s to copies of the same document, permanently breaking the dedup property. **Edit originals, never roll-ups** — resolve paths through `sources.md` or the changelog walker. Until that pass is directed, write these on new files and leave existing ones alone.

## Avoid disclosing what could be considered sensitive

Most `context-v/` work is publishable and *should* be published — it's how the practice spreads. The goal here is not secrecy. It is a light habit: **write generically about specifics that aren't yours to share.**

### `publish` gates the website. It does **not** gate retrieval.

**This is the single most misread field in the tree, so read this before reaching for it as a safety control.**

On a `context-v/` document, `publish: false` keeps the document off the published website. That is all it does. **It does not remove the document from the Chroma corpus or the Graphiti graph.**

```
scripts/ingest-to-chroma.py          (context-v)  → skips `private: true` ONLY
scripts/ingest-changelogs-to-chroma.py            → skips `private: true` OR `publish: false`
scripts/ingest-changelogs-to-graphiti.py          → skips `private: true` OR `publish: false`
```

`publish` appears **zero times** in `ingest-to-chroma.py`. Verified 2026-08-17.

**This asymmetry is intentional and was ratified on 2026-08-17.** `context-v/` is internal-by-nature — its whole job is shared memory across the tree — so our own retrieval layer deliberately reads everything, including the documents we chose not to publish. Those are frequently the *most* useful ones to retrieve. Do not "fix" the ingester to honour `publish`; doing so would silently shrink the corpus by hundreds of documents, most of them the substantive ones.

Two consequences that bind:

1. **`private: true` is the only retrieval control.** If a document genuinely must not be retrievable — not merely unpublished — it needs `private: true`. Reaching for `publish: false` to hide something will not do what it looks like it does.
2. **The two tiers now mean different things by the same key.** On a changelog entry `publish: false` *does* remove it from retrieval. On a context-v document it does not. Anything reasoning across both tiers has to know that.

The corollary is that a confidentiality problem in `context-v/` is **not** solved by a `publish` flag. It is solved by genericizing the sentence, or by `private: true`, or — where the exposure is a live credential — by rotating the credential, since the value is in git history regardless of what the working tree says.

### Genericize first; `publish: false` is the fallback

When a document is useful but names something it shouldn't, **the fix is almost always to genericize the sentence, not to hide the document.** A plan about lifting shared navigation into a package is worth publishing; it just doesn't need the client's name in it.

| Instead of | Write |
|---|---|
| "chroma-decks was built before the carve-out" | "the first client site was built before the carve-out" |
| "Humain's three scroll-deck variants" | "one engagement's three scroll-deck variants" |
| "Jane Chen, formerly of Acme, 18% IRR" | "a partner with a prior fund track record" |
| "the round is mostly committed at $12M" | *(cut it — the fact adds nothing to an engineering doc)* |
| a client's 12-dimension rubric reproduced verbatim | "the client's scoring framework has ~12 weighted dimensions" |

### The decision order — the document's job comes first

Never damage a useful internal document to make it publishable. Ask in this order:

1. **Does it do its job just as well genericized?** Almost always yes for engineering docs. Genericize the sentence, keep `publish: true`.
2. **Is it materially better at its job *with* the specifics?** Then **keep the specifics and set `publish: false`.** A plan that names the actual client, deck, and slide is easier for the next agent to act on; a data model whose example rows are real is easier to reason about. That value is real, and it's the whole point of `context-v/` — internal shared memory across the pseudomonorepo tree. Keep it for us.

`publish: false` is **not a demotion.** A large share of the corpus is legitimately internal. The failure mode to avoid is not "too many `false`" — it's a vague document that helps nobody *and* still names a client, having been watered down for a publication that was never going to happen.

So: genericize when it costs nothing, and go internal when it costs something.

### What actually wants genericizing

- **PII.** Named individuals with biography, performance, judgment, or behavior attached. Roles and generic descriptions are fine.
- **A client's trade secrets.** Proprietary frameworks, rubrics, and taxonomies reproduced verbatim; brand tokens and design IP lifted from their production assets.
- **Confidential deal terms.** Raise amounts, round status, valuations, cap-table splits, LP commitments — on identifiable companies.
- **Third-party confidential documents.** Don't reproduce a doc marked Confidential, including its structure or table of contents.
- **Client names**, where naming them adds nothing. Usually it doesn't.

### What is fine — don't over-screen

Being over-cautious makes the practice useless. These are **not** sensitive:

- **Variable and env-var names** (`SESSION_SECRET`, `TURSO_AUTH_TOKEN`). A name is not a secret. Actual values obviously are.
- **Architecture, schemas, file layouts, component contracts, keyboard maps, route tables.** This is ordinary engineering writing.
- **The fact that client work happened**, described generically.
- **Our own conventions, practices, and post-mortems.** Candour about what we got wrong is a feature of this corpus, not a liability.
- **Illustrative figures and placeholder data** that aren't tied to a real party.

### Credentials: the cases that don't look like credentials

"Never paste a live credential value" is the rule. The failure mode is that the
things which actually leak **do not look like values**, so a screen aimed at
high-entropy secrets walks straight past them. Treat every one of these as a
credential:

| Looks like | Actually is | Why it matters |
|---|---|---|
| **Access Key ID** (`AKIA…`, R2/S3 key IDs) | half a credential | It is called an *ID*, so it reads as a name. It is not. It is one half of a key pair, and it names the account to attack. |
| **A salt** (`*_SALT=`) | half a credential | Salts are "public by design" in the abstract. Committed **next to the hash they salt**, they hand over an offline cracking job. |
| **A password/passcode hash** (`*_HASH=`) | crackable secret | A hash is not a one-way door when the salt is on the adjacent line and the passcode is human-chosen. |
| **An account ID inside an endpoint URL** | not secret, but identifying | `https://<32-hex>.r2.cloudflarestorage.com` is public by design — but it pins the exact account, so it converts a stray key ID into a targeted one. Redact for hygiene; do not panic-rotate. |
| **A token's *ID*** as distinct from its value | half a credential | Some providers derive the S3 secret from the token value (`SHA-256(token)`), which means ID and secret are two faces of one token. Rotating once invalidates both. |

The test is not "does this look secret." It is: **would this value, plus one
more thing an attacker might get, grant access?** If yes, it is a credential.

Corollary worth internalising: a provider **Account ID cannot be rotated.** It
is permanent. So it must never be the thing you were relying on to stay quiet —
and equally, its exposure is not an incident on its own.

### Write hot, redact at the commit boundary

The docs that leak credentials are almost never written carelessly. They are
written **during** the work — an exploration narrating an hour of getting auth
to work, with the real values pasted in because you are using them in that
moment. Forbidding that would make the notes worse.

So the rule is a **boundary**, not a prohibition:

1. **While working:** paste whatever you need. The working tree is not the risk.
2. **Before `git add`:** sweep the diff for credential shapes. One command:

   ```bash
   git diff --cached -U0 | grep -nE '\b[0-9a-f]{32,64}\b|(KEY|TOKEN|SECRET|SALT|HASH|PASSCODE)[A-Z_]*\s*[:=]'
   ```

3. **Replace with the retrieval path, not a blank.** `<CLOUDFLARE_ACCOUNT_ID>`
   or "in `~/.secrets` as `R2_ACCESS_KEY_ID`" keeps the doc's procedural value.
   A deleted line makes the doc worse and teaches nobody where to look.
4. **If it is already pushed: rotate.** Redacting the working tree does nothing
   about history. Rotation is the fix; redaction is the cleanup.

The boundary is the commit, because that is where the value stops being yours.

### One document is several files

`context-v/` documents are mirrored. Redacting the source is not the job —
finding every copy is. A single exploration can exist as:

- the source in `<repo>/context-v/`
- a Chroma **`corpus/` mirror** (tracked, and in at least one **public** repo)
- a splash **`src/rollup/` copy**
- a site's `src/content/context-v/` copy
- a vendored `agent-skills/` copy

Grep the **whole tree** for the value, not the file. Regenerating the mirrors
afterward is not sufficient on its own — the stale copy is already committed.

### The one reliable tell

The documents that most often need genericizing are the ones *about* handling confidential material — a doc explaining a private-data submodule pattern, or a corpus data model, tends to quote the very filenames and paths it exists to protect. Worth a second look when the title mentions private data, datarooms, substantiation, or auth.
| Not reader-ready | raw session transcript, duplicated half-sentences, trailing "Rewriting the entry now." |

**Borderline resolves to `false`.** Internal-by-default is a recoverable error; publishing a client's scorecard is not.

### Check the repo's own convention first

Before deciding anything, count what the repo already does:

```bash
grep -rh '^publish:' --include='*.md' context-v/ | sort | uniq -c
```

A repo running 47 `false` to 5 `true` has made a decision. Respect it, and treat a `true` there as the exception that needs justifying. Tree-wide the split is roughly 2:1 in favour of `true`, so **there is no safe global default** — you have to look.

## Author conventions

**Strong Lossless preference: `authors` is for humans only.** Even when an AI agent produced most of the prose, the human directing the work is the author. AI tooling is tracked separately under `augmented_with`.

### `authors`

- Use the human's full preferred name (not a handle)
- Always a list, even with one entry
- Order: alphabetical or by contribution — team's call, no hard rule

### `augmented_with`

- The AI tool(s) used. Format: `<tool> on <model name and version>`
- Examples: `Pi on Claude Sonnet 4.5`, `Claude Code on Claude Opus 4`, `Cursor on GPT-5`, `Aider on Claude Sonnet 3.7`
- ul-list form, one entry per tool/model pair
- Include this field whenever an AI agent contributed materially — the more, the more important to disclose
- Avoid generic strings (`"AI Assistant"`, `"ChatGPT"`) — always specify both tool and model
- The point: honesty about augmentation matters more than credit allocation

## Tag conventions

- **Train-Case**: `Markdown-Rendering`, not `markdown-rendering`, `MarkdownRendering`, or `markdown_rendering`
- This is an Obsidian convention — Obsidian treats `#Markdown-Rendering` as a single tag, while underscores and other separators behave inconsistently
- Single-word tags are still capitalized: `Spec`, `Astro`, `Markdown`
- Singular over plural when ambiguous: `Spec`, not `Specs`
- Reuse existing tags in the project before inventing new ones — survey with:
  ```bash
  grep -rhA20 '^---' context-v/ | grep -E '^  - [A-Z]' | sort -u
  ```

## Date format

Always `YYYY-MM-DD`. No timestamps. No timezones. If you genuinely need a timestamp, use a separate field like `last_run: 2026-05-03T14:32:00Z` rather than overloading the date fields.

## Title quoting

Quote when the title contains:
- a colon (`:`)
- a leading number (`2026 Plan`)
- special YAML characters (`#`, `&`, `*`, `!`, `|`, `>`, `'`, `"`, `%`, `@`, `` ` ``)

When in doubt, double-quote.

## Validation philosophy

The Lossless team **does not hard-validate** frontmatter (this is itself a reminder). Be lenient about reading existing files; be thoughtful when writing new ones. Files older than current conventions are not bugs.

If a file's frontmatter is genuinely broken (malformed YAML, missing `title`), fix it as a `patch` bump and note the fix in the body or a commit message. Don't auto-migrate property names or styles unless explicitly asked.

**Never delete a key you don't recognize.** The vocabulary here is deliberately broad and unevenly applied — different surfaces read different keys, and an unused key costs nothing to carry. Not knowing what a field does is a reason to leave it alone and ask, never a reason to remove it.

## When a normalization sweep *is* directed

"Don't auto-migrate" governs **incidental** edits — don't rewrite someone's frontmatter as a side effect of unrelated work. It does not forbid an operator explicitly asking for a directory or repo to be brought up to standard. Under such a sweep, these bind:

1. **Additive only.** Add missing keys; rename the legacy spellings (`created:` → `date_created:`, `date:` → `date_authored_initial_draft:`) preserving values verbatim. Change nothing else.
2. **No YAML round-trips.** Serializing frontmatter through a YAML library reorders hand-authored keys and collapses multi-line `lede:` / `authors:` / `post_ship_note:` blocks. Edit the key's line in place; append new keys at the end of the block.
3. **Never touch the body.** The diff should be frontmatter lines and nothing else. A sweep that changes one line of prose is a failed sweep.
4. **`publish` cannot be mechanized.** It requires reading the document — see the baseline table. And an existing value is a decision: never flip it.
5. **Don't stamp `date_modified` with today.** Read it before editing. Adding a frontmatter key is not a substantive edit, and neither is it a reason to move `date_authored_current_draft` or bump `at_semantic_version`.
6. **Edit originals, never rollups.** Collated copies (`context-vigilance-kit/corpus/`, `splash/src/rollup/`) and vendored skill copies (`context-v/agent-skills/`) are derived from source and regenerate. Editing them is work that gets overwritten. Fix the original.
7. **Grep for consumers before a rename lands.** Renaming a key across a few hundred files is easy; noticing what *read* the old key is the actual work. The `date:` → `date_authored_initial_draft` migration silently broke two changelog ingesters — one lifted `date` into a metadata allowlist, the other used it as a temporal anchor.
8. **`agent-skills/` is out of scope.** `SKILL.md` frontmatter is a machine contract — Claude Code parses `name` and `description` to decide whether a skill loads. Extra keys are ignored by the loader and safe to *add*, but they are never reordered around those two, and vendored skill copies are not the source of truth.
9. **`context-v/skills/` is out of scope too** — decided 2026-08-17, during the context-v tier sweep. The same reasoning as rule 8, one directory up: `context-v/skills/<name>/` holds `SKILL.md`, `references/*.md`, and `README.md` — **skill internals that happen to live under a `context-v/` path**, not `context-v/` documents. They are authored against the skill-authoring contract, not this spec, and the loader is their consumer rather than a rendered surface or a retrieval layer. An audit that counts them reports ~123 extra files and ~101 phantom gaps. **This exclusion is written down so no future audit re-surfaces it as an open question** — it was one, and it is now settled.
