---
source_root: /Users/mpstaton/code/lossless-monorepo/context-v
source_relative_path: agent-skills/changelog-conventions/references/frontmatter-spec.md
source_repo_slug: lossless-monorepo
collated_at: '2026-08-24'
source_path: "context-v/agent-skills/changelog-conventions/references/frontmatter-spec.md"
---

# Changelog Frontmatter Spec

The complete frontmatter contract for `changelog/` entries.

## Mandatory (hardcoded for last few months and forward)

```yaml
---
title: "Title in title case"
lede: "Attention-grabbing one-line subtitle"
publish: true
date_authored_initial_draft: YYYY-MM-DD
date_authored_current_draft: YYYY-MM-DD
authors:
  - Firstname Lastname
augmented_with:
  - Pi on Claude Sonnet 4.5
---
```

### Field-by-field

#### `date_authored_initial_draft`
- ISO date with dashes (`2026-05-04`)
- **When the content was first *set*** — real, coherent, not a stub, not embarrassing. Not when the file was created empty.
- Set once. Never change it after the fact.
- For a changelog entry the filename usually encodes this (`2026-05-12_01.md`); the filename beats filesystem birthtime when they disagree.
- **Legacy spelling: `date:`.** Rename to this key, preserving the value verbatim.

#### `date_authored_current_draft`
- ISO date with dashes
- **When the entry last received a SUBSTANTIVE revision.** Opening a file, reformatting, or an automated frontmatter pass do not count.
- Must never be earlier than `date_authored_initial_draft`. If the best available source would be, set them equal.
- Bump it when you'd also bump `at_semantic_version` — the two move together.

#### `date_created` — *filesystem, optional on changelog entries*
- ISO date with dashes
- The birth of the bytes, per `stat`. Distinct from when the content was authored.
- **Where frontmatter already records a date_created EARLIER than filesystem birthtime, the frontmatter wins.** A machine recovery in this tree reset birthtime on a batch of files to the recovery date. Never overwrite an existing value with `stat`.
- When deriving a missing one, prefer `date_authored_initial_draft` over filesystem birthtime — a document cannot be created after its own first draft.
- **Legacy spelling: `created:`.** Rename to this key, preserving the value verbatim.
- Required on `context-v/` documents (the Obsidian standard); merely recognized on changelog entries, where the editorial pair carries the meaning.

#### `date_modified` — *filesystem, optional on changelog entries*
- ISO date with dashes
- Obsidian's templater updates this on file *open*, without real changes — a known artifact. **This is exactly why it is not the timeline field**; use `date_authored_current_draft` for "when did this last really change."
- Never stamp it with today's date as a side effect of an automated pass. Read it before editing.

#### `title`
- Human-readable. Title case.
- Quote it if it contains a colon, leading number, or special YAML characters
- Aim for clarity over cleverness — but not at the expense of being readable

#### `lede`
- The most distinctive field
- **Purpose:** grab attention. The reader should want to keep reading.

##### Why the field exists at all

`title` and `description` each fail at a different half of the job:

- **`title` says what the thing *is*.** Necessary, but knowing what something is rarely makes anyone open it.
- **`description` is always too long and too boring.** It's a summary written for completeness; on a card it wraps to five lines and nobody reads past the second.
- **`lede` says why you'd care, in a glance.** Short enough to render, interesting enough to earn the click.

That's why the field is named `lede` and not `description` — the word is a newsroom instruction: *write something that grabs attention.*

**It is a rendering field first.** Changelog entries surface on index pages, content cards, the cross-repo changelog aggregator, search results, and OpenGraph/social previews. Every one of those needs a single good line under the title. An entry with a strong body and no lede renders as a bare title everywhere it appears; an entry whose lede is a truncated summary renders as noise. Both are avoidable for the cost of one sentence.
- **Subtitle-length: 140 characters maximum, target 90–130 — two rendered lines, never three.** A hard budget, not a guideline; prose guidance like "a few sentences" does not constrain a writer, human or agent. It has to do its job in two seconds — a paragraph can't. When the lede wants to grow, move the long version into the `## Why Care?` section. Lede = the hook; `Why Care?` = the paragraph that earns the scroll. *(Tightened 2026-08-17 from "~3 rendered lines". Existing entries written to the looser rule are not defects — this is the aspiration for new ones.)*
- Avoid generic ledes ("Updates to the project") — make it specific
- Examples:
  - ✅ `"From zero to four shipped skills in one Claude session — and a backlog longer than the shipped list."`
  - ❌ `"Various improvements and changes."`

##### A lede is written, never extracted

**You cannot generate a lede by taking the first N characters of anything.** It is the one frontmatter field that requires having read the document and understood what is interesting about it. Everything else in the block can be derived; this cannot.

A generated-then-abandoned lede is worse than no lede, because it renders as garbage on the surfaces the field exists to serve — list views, preview cards, OG unfurls. Known failure signatures from a real extraction pass in this tree:

| Symptom | What went wrong |
|---|---|
| `lede: "---"` | Grabbed a horizontal rule instead of prose |
| `lede: "…allows each firm (e.g."` | Sentence-splitter broke on the period inside `e.g.` |
| `lede: "…5-scorecard/12Ps-scorecard."` | Split on a period inside a filename |
| `lede: "Added a set of CLI tools to tighten the workflow end-to-end:"` | Lifted a sentence that introduces a bullet list, trailing colon and all |
| `title: "Summary"` / `title: "Overview"` | Took the first `##` heading rather than the document's real subject — four entries ended up sharing one meaningless title |

**Repairing one is a content edit, not a normalization.** It falls outside an additive-only sweep and needs its own directed pass. To do it: read the document, find the single most interesting or surprising thing in it, and write one to three sentences that make someone want the rest. The raw material is almost always already in the body — a `## Summary` opener, a problem statement, a concrete number. Prefer the specific over the categorical: *"a $19M Series A that belonged to a different company with the same name"* beats *"fixed entity disambiguation."*

**If the document is a genuine stub, leave the lede empty.** An empty lede on an empty document is accurate. Inventing a hook for content that does not exist is fabrication, and it will read as a promise the page cannot keep.

#### `publish`
- **Always `true`** for new entries you are writing — if it's worth logging, it's worth publishing
- Obsidian publisher uses this field to decide what goes to the published site
- This is the most strictly enforced field on the platform
- `publish: false` is reserved for explicit reasons: sensitive content, or **a stub** — a title with nothing under it, an empty placeholder, or a doc whose every section is `[awaits discussion]` / `<!-- developing -->`
- **An existing value is a decision. Never flip it.** Especially never flip an explicit `false` to `true` because a document "looks long enough."
- Judging it on an existing file means **reading the file**, not measuring it. A stale "Stub" banner above a fully-developed body is `true`. A polished title and lede above twelve placeholder sections is `false`. Word counts get both backwards.
- **Avoid disclosing what could be considered sensitive** — see *Avoid disclosing what could be considered sensitive* in `context-vigilance/references/frontmatter-spec.md`. Changelog entries are the easy case: they're written outward-facing by design and the tree runs 364 `true` to 1 `false`. The habit that matters is **genericizing, not hiding** — say "a client engagement" rather than naming the firm, keep PII and confidential deal terms out, and never paste a live credential value. Variable names, architecture, and candid accounts of what we got wrong are all fine and worth publishing. And if an entry is genuinely better at its job naming the specifics — a post-mortem that only makes sense with the real names in it — keep them and set `publish: false`. It stays in the repo for us. Never water an entry down for a publication that was never going to happen.

#### `authors`
- **Humans only.** AI agents are tracked separately under `augmented_with` (see below).
- Always a YAML list, even with one author
- **Preferred form:** ul list (one author per line)
  ```yaml
  authors:
    - Michael Staton
  ```
- **Tolerated form:** inline list (`[Michael Staton, Other Person]`) — works but harder to diff and read
- Use the human's full preferred name

#### `augmented_with`
- The AI tool(s) used to produce the entry. Tracked separately from `authors` because **AI agents augment human authorship; they don't co-author.**
- Format: `<tool> on <model name and version>`
  - ul-list, one entry per tool/model pair
- Examples:
  ```yaml
  augmented_with:
    - Pi on Claude Sonnet 4.5
    - Claude Code on Claude Opus 4
    - Cursor on GPT-5
  ```
- Include this field whenever an AI agent contributed meaningfully — even (especially) when it produced most of the words. Honesty about augmentation matters more than authorship credit.
- Avoid generic strings like `"AI Assistant"` or `"ChatGPT"`. Specify the tool *and* the model.

## Strongly recommended optional fields

### `summary`

- **String.** Optional, but write one going forward — an agent can produce it in the same pass that writes the lede, so the marginal cost is near zero.
- **Purpose: the agent-facing counterpart to `lede`.** Where `lede` competes for a human's attention, `summary` answers the questions an agent asks before opening a file: *what is this entry for, where does it sit in the workflow, and what downstream logic should care about it?*

#### `lede` vs. `summary` — two audiences, two jobs

They are not long and short versions of each other. They are written for different readers and consumed by different surfaces.

| | `lede` | `summary` |
|---|---|---|
| **Audience** | humans, pre-click | agents, and humans orienting mid-workflow |
| **Job** | grab attention; convert interest into a click and time on page | situate the entry: purpose, workflow position, what consumes it |
| **Voice** | newsroom hook; specific, surprising | plain and declarative; no salesmanship |
| **Consumed by** | index pages, preview cards, search results, **OpenGraph/social unfurls** | agent retrieval, corpus ingest, roll-up logic, an agent deciding whether to open the file |
| **Length** | **140 chars max, target 90–130** — two rendered lines. A hard budget. | a few sentences; may exceed the lede without penalty, since nothing renders it in a card |

**The rendering split is the practical reason to keep them separate.** `lede` (or `description`) is what flows into OpenGraph automatically — so it is length-constrained by an unfurl card, and stuffing workflow context into it degrades a surface that exists to earn clicks. `summary` has no such constraint because no card renders it. Each field gets to be good at one thing.

**What belongs in a `summary`:**

- What the entry is *for* — the purpose behind the ship, not a restatement of the title.
- Where it sits in a workflow — what it unblocks, what it supersedes, what has to happen next.
- How pseudomonorepo or `context-vigilance` logic might use it — which repo tier it affects, whether it changes a convention other repos inherit, whether it's roll-up-worthy or purely local.
- What an agent should do with the knowledge — "read this before touching X," "this supersedes the approach in Y."

```yaml
lede: "Four repos and 256 files are done; 652 across 47 are not — and three traps will bite anyone who assumes the standard applies uniformly."
summary: "Hands off an in-flight tree-wide frontmatter sweep. Records what the completed repos proved and what the remaining ones still need, so a fresh session can resume without re-deriving the rules. Read before starting any frontmatter normalization work; the two frontmatter-spec references it points at are the authority, not this file. Consumed by whoever picks up the sweep, and by the pseudomonorepo branch-tier logic deciding which repos are already conformant."
```

#### `summary` is a claimed name — check before you write one

**Some repos in this tree historically used `summary` as a spelling of `lede`.** `astro-knots/sites/fullstack-vc` is the known case: 22 changelog entries carry human-facing subtitle prose under `summary`, predating this definition.

Consequences to respect:

- **Never assume an existing `summary` means what this section describes.** On a file that has `summary` but no `lede`, the value is almost certainly a legacy lede.
- **A renderer doing `lede ?? summary` will render agent prose in a human slot** on any file where `summary` was written to this spec and `lede` is missing. If a repo carries that fallback, the fix is to write a real `lede` — not to shorten the `summary`.
- **Migrating a legacy `summary` is a content edit, not a normalization.** It moves human prose into `lede` and leaves `summary` free for its real job. That is a directed pass, outside an additive-only sweep — same rule as repairing a broken lede.

Adding a `summary` to a file that already has a *legacy* `summary` is the one case where this field needs a decision rather than a fill-in. Resolve the legacy value first.

### `date_work_started` and `date_work_completed`

- **ISO dates with dashes.** Both optional, and independent of each other —
  `date_work_completed` alone is a perfectly good record.
- **Purpose: when the WORK happened.** Every other date on the entry is about
  the *document*. These are about the thing the document describes.

#### Why this is a separate axis, not a duplicate

The editorial pair answers *when was this written*. The work pair answers *when
did this happen*. Those are different questions and the answers routinely differ:

```yaml
date_work_started: 2026-05-09              # sat down to it Saturday
date_work_completed: 2026-05-10            # finished Sunday
date_authored_initial_draft: 2026-05-10    # wrote it up the same evening
date_authored_current_draft: 2026-05-17    # corrected a claim a week later
```

One entry, three distinct facts. Collapsing them loses information that cannot
be recovered later — nobody remembers in November which Saturday a thing started.

**This matters for rendering, which is the point.** A timeline built on
`date_authored_*` is a timeline of *writing*, and it will show a burst of
activity on the day someone sat down to document a fortnight of work. A timeline
built on the work pair shows the work. Sites that render a project history want
the second one, and today they cannot have it because the data was never
captured.

It matters for tooling too. Any feature that helps a developer integrate
`context-vigilance-kit` into their own workflow — "what did this repo actually do
last quarter", "how long do these tasks really take", "show me the gaps" — is
asking about work, not about authorship. The fields have to exist before a
feature can read them.

#### Rules

- **`date_work_completed` must not precede `date_work_started`.** If only one is
  known, write that one; do not invent the other.
- **`date_work_completed` is normally on or before `date_authored_initial_draft`** —
  you write the entry up after doing the work. A later value is not an error, but
  it usually means the entry was drafted mid-flight and finished afterwards.
- **Multi-day work is the case these exist for.** For a single-session change all
  four dates collapse to the same day, and the pair adds nothing; skip it.
- **Never derive them from the filesystem.** `date_created` is when the file
  appeared, which is a fact about the writeup. If the work dates are not known,
  leave them out — an absent field is honest, an inferred one is not.
- **Optional means optional.** Do not backfill across old entries; there is no
  reliable source for when work started three months ago, and guessing would
  poison exactly the timelines these are meant to serve.

#### Precedent

`content-farm/plugin-modules/perplexed` has been running this convention on
eleven entries since April 2026, and it is the reason the fields are being
written down rather than invented. On those entries `date_work_completed` and
`date_created` agree, which is what you would expect from same-day work — the
convention pays off on the entries where they diverge.

When both are present, **prefer `date_work_completed` over `date_created`** as
the derivation source for a missing `date_authored_initial_draft`: it is a
human-authored statement about when the work landed, where `date_created` is a
filesystem fact.

### `site_uuid` and `hex_code` — stable identity

Two write-once identifiers. Cheap to generate, near-useless in isolation, and increasingly load-bearing as the corpus grows — **write them on new entries starting now.** Retrofitting identity onto 930 existing entries is far more expensive than minting it at creation.

| Field | Shape | Set |
|---|---|---|
| `site_uuid` | UUID v4, lowercase, canonical hyphenated form | once, at creation — never regenerated |
| `hex_code` | 6 chars, `[a-z0-9]` | once, at creation — never regenerated |

#### Why a changelog entry in particular needs one

**Changelog entries are the most-copied documents in the tree.** Every entry is read in at least three aggregations — the repo's own list, the parent pseudomonorepo's roll-up, and the cross-repo Lossless Changelog — and the roll-ups are literal file copies. Filenames make this worse rather than better: entry filenames are dates (`2026-04-27_01.md`), so **two unrelated entries in two repos routinely share a filename**. A date-shaped filename is not an identifier.

`site_uuid` is what tells an aggregator that four files are one entry rolled up four times, versus four different entries that happen to be named alike. **The identifier travels with the copy** — that is the point, not a duplicate to clean up.

It also gives Chroma, Graphiti, and any future live-sync (SurrealDB is the current favourite) a key that survives re-ingest. Without one, every ingest mints fresh nodes and an entry's history through the graph is unrecoverable.

#### Why `site_uuid` and not `uuid`

Databases issue their own `uuid` primary keys. `site_uuid` names the identity that is **valid local to the project** — the authoring vault, wherever it renders on the web, and the pseudomonorepo / `context-vigilance` context — leaving `uuid` free for whatever store the entry syncs into. Sync layers map `site_uuid` → their `uuid` with no collision. ~6,650 files across the tree already carry it.

#### `hex_code` — citing our own prior art

`hex_code` is the entry's own citation ID, which is what lets **other** documents cite it. The `lossless-flavored-markdown` skill already specifies hex-code citations and says to reuse a source's existing hex ID so the citation renders identically everywhere; this is where that ID lives when the source is one of ours.

```markdown
This supersedes the ingester fix shipped in April.[^7c1e0a]

## References

[^7c1e0a]: [[2026-04-29_03]]
```

Native Obsidian footnote syntax — so it renders in the vault with hover previews, aggregates across pseudomonorepos, and gives LFM a real render target on Astro Knots sites.

**Never sequential `[^1]`.** Sequential markers collide the instant a paragraph is copied between documents — and changelog entries get copied constantly.

#### Generate with a command — never let the model type one

A model asked for a "random" UUID emits a UUID-*shaped* string drawn from training-data frequency: biased and repetition-prone. **Seven `site_uuid` values already in this tree contain non-hex characters** (`…a2f98752z7b9`, `…396h-4rb4…`, `y8f59v34-…`) — each one a model typing instead of calling a generator. They are invalid and will fail a strict parser.

```bash
# site_uuid
uuidgen | tr 'A-Z' 'a-z'

# hex_code — 6 chars of [a-z0-9]
LC_ALL=C tr -dc 'a-z0-9' </dev/urandom | head -c6; echo
```

**Use that charset, not `openssl rand -hex 3`.** Despite the field's name the charset is base36, not true hex — and the difference decides whether it works at scale. Six true-hex characters (16⁶) collide with **20.6% probability at today's corpus size and 94.9% at 10,000 documents**; six `[a-z0-9]` characters (36⁶) collide at 0.18% and 2.3%. Check a new code before committing — the corpus is the registry:

```bash
grep -rl "<the-new-code>" --include='*.md' /Users/mpstaton/code/lossless-monorepo
```

No output means it's free. (Worth doing for `hex_code`; unnecessary for `site_uuid`.)

#### Retrofitting is a directed pass

Both fields are additive and safe — nothing reads them yet, so adding one cannot break a render. A *sweep* is still an operator decision, and a careless one is destructive: roll-up copies mean a naive `find` would assign **different** `site_uuid`s to copies of the same entry, permanently breaking the dedup property that justifies the field. **Edit originals, never roll-ups.** Until such a pass is directed, write these on new entries and leave existing ones alone.

### `files_changed`
- **List of paths**, project-root-relative
- Format: ul-list, one path per line
  ```yaml
  files_changed:
    - src/components/NameOfComponent.astro
    - src/styles/global.css
    - context-v/blueprints/Component-Pattern.md
  ```
- Why include it: makes seeing what actually moved trivial — for readers, for diffs across rendered changelogs, for the future "Lossless Changelog" aggregator
- Not required, but include it whenever the entry is about file-level changes (almost always)
- Paths are from the **project root** (the repo containing the changelog), not from the changelog file itself

## Optional fields (use as needed)

### The extended date family — never strip these

Applied unevenly across the tree, **on purpose**. Different surfaces read different ones, and the cost of an agent writing one is near zero — which is why the vocabulary is broad rather than minimal. Fill one when you genuinely know the answer; otherwise leave it exactly as found.

**These earn their keep in `context-v/`, not here.** `context-v/` documents constantly evolve — a spec revised across months, a plan accumulating phases — so tracking initial vs. current vs. final draft is load-bearing there. A changelog entry is normally write-once: expect `date_authored_initial_draft` and `date_authored_current_draft` to be the same date permanently, and expect `date_authored_final_draft` / `date_first_published` to sit empty. None of that is a defect. The fields are carried for uniform shape (one aggregator reads both trees) and for the occasional entry that *does* get revised — a correction, a folded-in follow-up, a post-ship addendum. **Redundant unused fields cost nothing; do not prune them.**

```yaml
date_authored_final_draft:      # Present-but-EMPTY is meaningful: "not final yet." Do not delete the empty key.
date_first_published: YYYY-MM-DD  # When it went out. Distinct from when it was written.
date_last_updated: YYYY-MM-DD     # Any touch, substantive or not. Contrast date_authored_current_draft.
at_semantic_version: 0.0.1.0      # Four-part epoch.major.minor.patch. Moves with current_draft.
```

**Deleting an unrecognized frontmatter key is always wrong.** If you don't know what it does, that is a reason to leave it, not a reason to remove it. Ask.

### `tags`
- Train-Case (e.g., `Skills`, `Pseudomonorepo-Pattern`)
- At least one tag is recommended for taxonomy/filtering on rendered sites

### `at_semantic_version`
- Four-part `epoch.major.minor.patch` (see `context-vigilance/references/versioning.md`)
- **`semantic_version` is a permanently-accepted alias** for the same property and value. Write `at_`, read either, and never rewrite an existing file just to change which name it uses — no migration is planned. Consumers resolve `at_semantic_version ?? semantic_version`.
- For release entries, this is essentially the version being announced
- For standard changelog entries, optional — a changelog entry isn't itself a versioned doc, and being write-once it rarely moves

### `release_version`
- Used in `releases/` subfolder. The version string the entry announces.
- Example: `release_version: "1.2.0"` or `release_version: "0.0.0.1"`

### `related`
- List of `[[wikilinks]]` to related context-v/ docs (the spec this implements, the blueprint this codifies)
- Helps the aggregator render entries with context

### `aliases`
- Obsidian convention for alternate titles
- Useful for SEO when the title is internal-flavored but a public reader would search differently

### `image` / `cover_image`
- For changelog entries that get rendered prominently on Astro Knots sites
- Path or URL

## Validation philosophy

- **Be lenient reading.** Older entries (more than a few months back) often have fewer or different fields. They are not bugs.
- **Be careful writing.** New entries should have every mandatory field.
- **Don't auto-migrate incidentally.** Don't go through old entries adding `lede` or normalizing `authors` as a side effect of unrelated work. Show, don't enforce.
- If a frontmatter is genuinely broken (malformed YAML), fix it in a small dedicated edit, not as a side effect of unrelated work.

### When a normalization sweep *is* directed

An operator can explicitly ask for a repo to be brought up to standard. That is not a violation of "show, don't enforce" — it's the deliberate case the rule was never about. Under a sweep:

- **Additive only.** Add missing keys; rename `date:` → `date_authored_initial_draft` and `created:` → `date_created`, values verbatim. Change nothing else.
- **No YAML round-trips.** Serializing frontmatter through a YAML library reorders hand-authored keys and collapses multi-line `lede:` / `authors:` / `files_changed:` blocks. Edit the key's line in place; append new keys at the end of the block.
- **Never touch the body.** The diff should be frontmatter lines and nothing else.
- **Read to judge `publish`.** See the `publish` section above — this is the one field a sweep cannot mechanize.
- **Edit originals, never rollups.** Collated copies (`context-vigilance-kit/corpus/`, `splash/src/rollup/`) and vendored skill copies (`context-v/agent-skills/`) regenerate from source. Editing them is wasted work that gets overwritten.
- **Grep for consumers before a rename lands.** The `date:` → `date_authored_initial_draft` migration silently broke two changelog ingesters — one lifted `date` into its metadata allowlist, the other used it as a temporal anchor. Renaming a key in 85 files is easy; noticing what read it is the actual work.
