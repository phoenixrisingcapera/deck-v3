---
title: Graphiti Over the Lossless Corpus
lede: Chroma cannot answer "what changed, and when." Graphiti's bi-temporal graph
  can — pointed at the changelog rollup until the bet proves out.
date_created: 2026-08-14
date_modified: 2026-08-21
authors:
- Michael Staton
augmented_with:
- Claude Code on Claude Opus 5 (1M context)
semantic_version: 0.0.2.0
status: Draft
tags:
- Graphiti
- Knowledge-Graph
- Temporal-Reasoning
- Neo4j
- ChromaDB
- Retrieval
- Context-Engineering
- Ollama
- LM-Studio
- Visualization
publish: true
site_uuid: 7ad275e3-f8dd-4488-a7eb-e6b7ca7a663d
hex_code: 0amtbg
date_authored_initial_draft: 2026-08-14
date_authored_current_draft: 2026-08-21
source_root: /Users/mpstaton/code/lossless-monorepo/ai-labs/context-vigilance-kit/context-v
source_relative_path: explorations/Graphiti-Over-The-Lossless-Corpus.md
source_repo_slug: context-vigilance-kit
collated_at: '2026-08-24'
source_path: "ai-labs/context-vigilance-kit/context-v/explorations/Graphiti-Over-The-Lossless-Corpus.md"
---

# Graphiti Over the Lossless Corpus

## Why care?

The kit already has retrieval. Four Chroma collections, ~28,000 chunks, wired
into every session through an MCP server. It works, and the root `CLAUDE.md`
tells every agent to reach for it before answering from training data.

But Chroma is answering exactly one kind of question: *what did we write that
sounds like this?* Similarity over a bag of chunks. Ask it "when did we ship the
Chroma corpus" and it returns five chunks that talk about shipping and Chroma,
ordered by cosine distance, and you read them and work it out yourself. Ask it
"what changed about our OG image approach between May and August" and it has no
mechanism at all — there is no *between* in a vector index.

The [Graphiti profile](../../../studies/memory-layers-for-agents/context-v/profiles/Profile__Graphiti.md)
in the memory-layers study called this out before we ever tried it:

> You wouldn't replace `context-vigilance` with Graphiti — the human-readable
> markdown layer is irreplaceable for human review. But if we ever needed to
> make wikilink relationships first-class to an agent (e.g., "find every spec
> that depends on a blueprint that was superseded after 2025-Q1"), Graphiti's
> data model is the shape that question wants.

This exploration is the first attempt to cash that in.

## The bet

Graphiti stores **typed entities and typed, bi-temporally versioned edges**.
Every fact carries four time fields, and the split between two of them is the
whole point:

- `valid_at` / `invalid_at` — *valid time*. When the fact became, and stopped
  being, true in the world.
- `created_at` / `expired_at` — *system time*. When the graph learned it, and
  when the graph retired it.

Those can differ, and the difference is the interesting part. "We moved
calmstorm-decks under dididecks-ai" became true on one date and was recorded on
another. A vector index flattens both into "a chunk that mentions the move."

So the bet is: **a graph over dated events answers questions about change that a
vector index structurally cannot.**

## Why the changelog, and not the whole corpus

The instinct is to point it at `context-vigilance-corpus` — 9,453 chunks of
specs, plans, and explorations, the place "what did we decide about X" actually
lives. Two reasons we did not.

**Cost.** Graphiti is not Chroma. Chroma costs one cheap local embedding per
chunk; the whole ingest runs in minutes on a laptop. Graphiti runs an LLM
extraction call plus dedup calls *per episode*. Extrapolating across ~28,000
chunks is a serious bill and many hours of wall clock. That is not a reason
never to do it — it is a reason not to do it first.

**Fit.** Changelog entries are *dated events*, which is exactly the data shape
the bi-temporal model was designed for. Specs and explorations are mostly
atemporal by comparison — a spec describes a desired end state, not a thing that
happened on a date. If the temporal graph is going to earn its keep anywhere, it
earns it here first. If it *doesn't* pay off on 479 dated ship records, that is
a strong signal not to spend 20× more on the atemporal material.

Current slice: **479 changelog entries across the tree, 2025-01-02 → 2026-08-14.**

## The stack, and why each piece

| Layer | Choice | Why |
|---|---|---|
| Graph store | Neo4j 5.26 (Docker) | Reference backend for graphiti-core; Lucene fulltext; we already know it |
| Extraction | Anthropic `claude-haiku-4-5-latest` | graphiti-core's own default for the Anthropic client; right tier for high-volume structured output |
| Embeddings | Ollama `all-minilm` (384-dim) | Local, no API key, same MiniLM family the Chroma collections already use |
| Reranking | Passthrough | Reranking is search-time only; RRF/MMR recipes don't use it. Keeps us off a third API |

### Why not FalkorDB

Upstream's MCP server defaults to FalkorDB and bundles it in a single container,
which is genuinely simpler. We took Neo4j anyway, for one concrete reason
visible in the pinned source: **the FalkorDB driver degrades fulltext search.**

Graphiti's Neo4j path (`driver/neo4j/operations/search_ops.py:54-73`) runs
`lucene_sanitize` and preserves Lucene semantics with `max_query_length=8000`.
The FalkorDB path (`driver/falkordb_driver.py:344-425`) has to paper over
RediSearch: it translates ~30 punctuation characters to whitespace, strips
stopwords, joins the survivors with `' | '` — pure OR — and caps at 128 tokens.
Hybrid search fuses BM25 with cosine and BFS, so the other two legs carry you,
but the keyword leg is measurably weaker. That, plus zero learning cost, decided
it. FalkorDB's sparse-matrix traversal story gets more interesting if this ever
scales to the full corpus.

### Two upstream gotchas worth writing down

**1. There is no sentence-transformers embedder in graphiti-core.** The MCP
server README advertises `provider: "sentence_transformers"` for local setups.
That value is not implemented — `mcp_server/src/services/factories.py` handles
`openai`, `azure_openai`, `gemini`, `voyage`, then falls through to
`raise ValueError(f'Unsupported Embedder provider: {provider}')`. Local
embeddings therefore go through Ollama's OpenAI-compatible `/v1/embeddings`
endpoint using the `openai` provider. This works because `OpenAIEmbedder`
truncates dimensions client-side rather than sending a `dimensions` request
parameter Ollama would reject.

**2. The cross-encoder is constructed eagerly.** `graphiti.py:227` does a bare
`OpenAIRerankerClient()` when you pass `cross_encoder=None` — which raises on a
missing `OPENAI_API_KEY` even though reranking never runs during ingest. Passing
an explicit passthrough is what keeps an Anthropic-plus-local stack from
demanding an OpenAI key it will never use.

## The ontology

Custom Pydantic entity types are Graphiti's ontology surface, and the profile is
blunt that retrofitting them is painful — so they are defined up front, tuned to
what Lossless changelogs actually talk about:

- **Repo** — a repository or project in the tree
- **Capability** — a feature, surface, script, or command that shipped or changed
- **Convention** — a practice, standard, or rule adopted (skills, schemas, tiers)
- **Tool** — a third-party dependency, service, framework, or model
- **Person** — a named human

The `Capability` / `Convention` split is the one doing real work. A changelog
entry usually announces both — a thing built, and a rule adopted about how such
things get built — and they age differently. Capabilities get replaced;
conventions get superseded.

## Seeing the graph — `scripts/graph-viz.py`

**Graphiti ships no UI.** The installed `graphiti-core` package contains only
library internals (`driver`, `embedder`, `llm_client`, `prompts`, `search`,
`utils`, …) — no `server/`, no `ui/`, and nothing in the venv that would serve
one. Neo4j Bloom would be the rich viewer, but the compose file pins
`neo4j:5.26-community` and Bloom is Enterprise. So there are exactly two ways to
look at this graph, and one of them we had to build.

### Where the source lives

```
ai-labs/context-vigilance-kit/
├── scripts/graph-viz.py            ← the generator (tracked, this is the one)
└── .graphiti-state/graph.html      ← the output (gitignored, regenerate freely)
```

```bash
.venv/bin/python scripts/graph-viz.py                      # default: top 300 by degree
.venv/bin/python scripts/graph-viz.py --limit 400 --open   # bigger, and open it
.venv/bin/python scripts/graph-viz.py --group-id lossless-changelog
```

### Why it is a tracked script and not a scratch heredoc

A working version of this existed on **2026-08-15** and was shown once. It was
built as two ad-hoc heredocs writing into a session scratchpad — a `graph.json`
dump and an `mkhtml.py`. When the scratchpad was cleaned, the artifact *and its
generator* went with it, and five days later the honest answer to "where's that
viz?" was "it doesn't exist." That is precisely the failure the root
`CLAUDE.md` names about browser drives: **a thing that lives only in a session
transcript is not codified.** The rewrite is a tracked script for that reason
alone.

### How it works

Two Cypher reads, then one string of HTML:

1. **Node query** — every `:Entity` in the partition, ranked by degree, capped
   at `--limit`. Degree ranking is what makes a truncated view useful: it keeps
   hubs and drops one-off leaves, rather than taking an arbitrary 300.
2. **Edge query** — `RELATES_TO` edges *among the surviving nodes only*
   (`WHERE a.uuid IN $uuids AND b.uuid IN $uuids`), so no edge dangles.
3. **Render** — nodes, edges and the color map are serialised into one `<script>`
   block and written as a single self-contained file.

Visual encoding, all of it deliberate:

| Encoding | Meaning |
|---|---|
| Node color | Ontology label — Repo / Capability / Convention / Tool / Person |
| Node radius | `sqrt(degree)` — hubs are visibly bigger, without swamping the canvas |
| **Red dashed edge** | `invalid_at IS NOT NULL` — a fact recorded true, later learned false |
| Hover node | Entity summary, type, degree |
| Hover edge | The fact, plus its `valid_at` → `invalid_at` window |
| Legend click | Filter that entity type in or out |

**The red dashed edges are the entire point.** They are the bi-temporal model
made visible, and they are the one thing a vector index structurally cannot
represent. If this graph ever justifies its cost, that is where the
justification shows up.

Two implementation choices worth not re-litigating:

- **No CDN.** The force simulation is ~60 lines of hand-rolled vanilla JS rather
  than a d3 import. "Self-contained" is the whole point — the file has to still
  work emailed, archived, or opened offline.
- **`--limit` defaults to 300.** The full graph is thousands of nodes and does
  not lay out usefully in a browser; past ~600 the force sim stops being
  readable. Raise it knowingly.

Every query is read-only, so it is safe to run while an ingest is in flight.

## Running extraction on a local model

The hosted path costs real money — measured at **$0.759/episode** on
`claude-haiku-4-5` (a 50-episode batch took a $117 balance to $79.04). Pointing
extraction at a local OpenAI-compatible endpoint makes it free, and
`scripts/graphiti_clients.py` grew a `GRAPHITI_LLM_PROVIDER` switch for it:

```bash
export GRAPHITI_LLM_PROVIDER=lmstudio          # or ollama / local / openai-generic
export GRAPHITI_LLM_BASE_URL=http://localhost:1234/v1
export GRAPHITI_LLM_MODEL=gemma-3-12b-it-qat
export SEMAPHORE_LIMIT=1
```

It routes to graphiti's *generic* OpenAI client, which — unlike the hosted
clients — does not assume strict structured-output support.

### Five things that bite, in the order they bit

**1. Concurrency overflows the KV cache.** `SEMAPHORE_LIMIT` defaults to 8. Two
concurrent 30k-token prompts against a 65536-token context collide and return
`exceed_context_size_error`. Set it to **1** for local runs. Serial is also no
slower in practice, since a single-GPU engine serialises anyway.

**2. LM Studio rejects `response_format: {"type":"json_object"}`** — it requires
`json_schema` or `text`. Graphiti sends `json_object` only when no
`response_model` is passed (`openai_generic_client.py:111`); the normal
extraction paths do pass a Pydantic model and take the `json_schema` branch,
which works. It is a latent failure on any call that omits the model, not a
blanket blocker.

**3. Non-primitive attributes fail the write.** This is the real one. The entity
types above declare a docstring and **no fields**, so Graphiti's
attribute-extraction step is unconstrained — the model returns whatever shape it
likes. Neo4j properties accept only primitives or arrays of primitives, so a
nested object dies at write time:

```
CypherTypeError: Property values can only be of primitive types or arrays
thereof. Encountered: Map{tree_path -> ..., supports -> List{...}, role -> ...}
```

Hosted Haiku happened to return flat primitives across 150 episodes, zero
failures. `gemma-3-12b-it-qat` returns nested objects and failed on episode 1.
The guard lives in **`scripts/run-ingest-local-safe.py`**, a thin wrapper that
monkeypatches `graphiti_core.graphiti.extract_attributes_from_nodes` to coerce
any non-primitive attribute to a JSON string before the write. Flat values pass
through untouched, so a Haiku run through the wrapper is identical to running
the script directly.

It patches the name bound *inside* `graphiti_core.graphiti`, not the defining
module — `graphiti.py:102` does `from ...node_operations import
extract_attributes_from_nodes` at import time, so patching the source module
would leave the already-bound reference untouched. That detail is easy to get
wrong and silent when you do.

**4. Empty keys and labels fail the write too.** A second, distinct Neo4j
rejection, found only after the first fix let the run get far enough to hit it:

```
Neo.ClientError.Schema.TokenNameError: '' is not a valid token name.
Token names cannot be empty or contain any null-bytes.
```

Neo4j calls labels, relationship types and property keys **tokens**, and none of
them may be empty. gemma emits `{"": "..."}` attributes and blank entity types
often enough to matter: **2 failures in 12 episodes (17%)** before the fix, **0
in 30** after. The same wrapper now also drops unusable attribute keys — an
empty key cannot be repaired, because the name was the meaning — and strips
blank labels, falling back to `["Entity"]` so a node is never left label-less
and therefore unfindable.

The pattern worth internalizing: **a fix that lets the run go further will
surface the next bug, not finish the job.** Both failures were invisible until
the one before them was solved.

**5. `APIConnectionError` means the EMBEDDER at least as often as the LLM.**
This stack depends on two local services, and the OpenAI client wraps a failure
in either into the identical opaque line:

```
APIConnectionError: Connection error.
```

On 2026-08-20 Ollama died mid-run while LM Studio stayed perfectly healthy —
verified serving a 35,206-token prompt in 202s *while every episode was
failing*. Hours went into a wrong theory (poisoned HTTP connection pool)
before anyone checked port 11434.

The diagnostic tell: **failures arriving every ~33 seconds.** A slow model or a
bad connection pool does not fail that fast. Immediate refusal means something
is not listening. A fast reply to a *small* test prompt proves only that the
server is up, which is rarely the thing in doubt.

`run-ingest-local-safe.py` now runs a **preflight** that pings both endpoints
and round-trips a real embedding before starting — a reachable Ollama that has
forgotten `all-minilm` is as fatal as a dead one — and exits 3 naming the
culprit rather than discovering it an hour in.

For unattended runs, `.graphiti-state/supervise.sh` wraps this in 25-episode
slices, each a fresh process, stalling out after 5 consecutive no-progress
slices instead of grinding forever. **It lives under a gitignored directory and
should be moved to `scripts/`** — the same "exists only in a scratchpad"
mistake documented above, one directory over.

```bash
.venv/bin/python scripts/run-ingest-local-safe.py --limit 1   # smoke
nohup caffeinate -is .venv/bin/python -u scripts/run-ingest-local-safe.py &
nohup caffeinate -is bash .graphiti-state/supervise.sh "$LOG" &   # unattended
```

`caffeinate` is not optional: this laptop sleeps after **1 minute idle on AC**,
and macOS Low Power Mode (`pmset -g custom` → `powermode 1`) throttles inference
hard enough to turn a 3-second call into a 600-second engine timeout.

### The economics, measured

| Path | Rate | Cost for the remaining ~200 |
|---|---|---|
| `claude-haiku-4-5` (hosted) | ~46s/episode | ~$150 |
| `gemma-3-12b-it-qat` (local) | ~1,050s/episode | $0, but ~60 hours |

**The local rate degrades as the graph grows** — 831s/episode at 5 done,
1,061s at 30 — because dedup prompts carry more existing graph as context each
time. Haiku shows the same curve, but each extra prompt token costs ~7× less
there, so it flattens instead of compounding. A single early measurement will
badly underestimate the total: the first smoke test read 335s/episode, which is
a third of the settled rate.

Local is **~20× slower in practice** and free. The unpriced cost is consistency: episodes
extracted by different models produce different entity naming and typing, so a
half-Haiku, half-gemma graph has a seam in it. Whether that seam matters is
still open.

## What this does not replace

Chroma stays. The two indexes answer different questions and the honest posture
is that this is **additive, not a migration**:

- *"What have we written about X?"* → Chroma. Broad recall over the whole corpus,
  cheap, already covers all 28,000 chunks.
- *"When did X happen, what changed, what superseded what?"* → Graphiti. Narrow,
  expensive, currently covers only the changelog.

An agent that reaches for the graph to answer a similarity question will get
worse results than Chroma gives, because the graph has seen 479 documents and
Chroma has seen thousands.

## Open questions

1. **Does the extraction actually produce useful entities over Lossless prose?**
   Our changelogs are dense with proper nouns that are also common words
   (`splash`, `corpus`, `studies`, `knots`). Entity resolution could smear
   `splash` the Astro site into `splash` the generic noun. Unmeasured.

2. **Does supersession work without explicit pointers?** The profile flags this
   as the thing to be skeptical about — Graphiti has no `superseded_by` pointer
   pair, and depends on dedup quality at ingest to set `invalid_at` correctly.
   The tree has real supersession events (repo relocations, convention changes,
   the eight-folder taxonomy replacing the older one). Whether the graph
   represents them correctly is the sharpest test available.

3. **Is a haiku-tier model good enough for extraction?** graphiti-core defaults
   to it, but the profile warns that smaller models produce schema-mismatched
   JSON and extraction failures. The ingester counts failures per run; if that
   number is non-trivial, the next lever is a larger extraction model, not a
   different graph.

4. **77 of 479 entries have no date in frontmatter** and fall back to file
   mtime, which is a poor temporal anchor — a reformatting pass rewrites it.
   That is a `changelog-conventions` compliance gap the graph surfaced as a side
   effect. Worth fixing at the source regardless of what happens to Graphiti.

5. **Is MCP the right delivery surface, or is a script enough?** Every MCP
   server costs context in every session. Adding one for a 479-document graph
   needs to earn that. `scripts/query-graphiti.py` deliberately exists so the
   graph can be judged before the MCP server is wired.

## Status

**As of 2026-08-20 — extraction is running, roughly half done.**

| | |
|---|---|
| Episodes ingested | **285 of 525** |
| Entities | ~2,156 |
| Fact edges | ~4,272 |
| Superseded edges (`invalid_at`) | **941** |
| Communities | **0** — never built |

The first 284 were extracted by hosted `claude-haiku-4-5` across three
50-episode batches, zero failures. The remainder is grinding on local
`gemma-3-12b-it-qat` through `run-ingest-local-safe.py`.

Two things a future session should not have to rediscover:

- **`communities` is 0 because nothing ever called it.** Community detection is
  a separate `build_communities()` pass; `add_episode(update_communities=...)`
  defaults off and the ingester never sets it. The "which projects cluster
  together" view does not exist yet — do not go hunting for `:Community` nodes.
- **The state file and the graph disagree by 9 episodes.** `.graphiti-state/`
  tracked 284 while the graph held 293. The extras are orphans from early
  local-model attempts that wrote episodes without recording their hashes. They
  will re-ingest as duplicates. Reconciling is a read-only Cypher query plus a
  state-file patch, and it has not been done.

Open question 2 — *does supersession work without explicit pointers?* — now has
a number against it: **941 edges carry an `invalid_at`**, up from 17 when the
graph held 10 episodes. Whether those 941 are *correct* is unmeasured, and
`scripts/graph-viz.py` exists partly to make them inspectable by eye.

## See also

- [[Profile__Graphiti]] — the study profile this exploration cashes in
- [[Systematizing-Chroma-as-Loading-Mechanism-for-Context-v]] — the vector-index
  counterpart this sits beside
- [[Chroma-and-Graphiti-Gotchas]] — the reminders counterpart

### Source map — every file this exploration describes

All paths relative to `ai-labs/context-vigilance-kit/`:

| Path | What it is |
|---|---|
| `docker-compose.graphiti.yml` | Neo4j 5.26 + APOC. Browser on **:7474**, Bolt on **:7687**, `neo4j` / `losslessgraph` |
| `scripts/graphiti_clients.py` | Shared config — LLM/embedder/reranker construction, `GRAPHITI_LLM_PROVIDER` switch, `.env` chain walk |
| `scripts/ingest-changelogs-to-graphiti.py` | The ingester. Ontology, discovery, per-file hash state, `--limit` / `--reset` |
| `scripts/run-ingest-local-safe.py` | Local-model wrapper — coerces non-primitive attribute *values*, drops empty attribute *keys* and blank *labels*, so the Neo4j write survives unconstrained model output |
| `scripts/graph-viz.py` | **The visualization generator** → writes `.graphiti-state/graph.html` |
| `scripts/query-graphiti.py` | CLI search — `--stats`, plus natural-language queries. No LLM, so free |
| `.graphiti-state/changelog-ingest.json` | Resume state, `source_path` → `sha256`. Deleting it means paying for extraction twice |
| `.graphiti-state/logs/` | Ingest run logs, gitignored |
