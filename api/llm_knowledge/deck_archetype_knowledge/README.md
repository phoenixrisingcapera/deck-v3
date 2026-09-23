# Deck Archetype Knowledge Base

This folder replaces the rough `slide-archetypes` seed with an infrastructure-ready knowledge base named:

```text
deck_archetype_knowledge
```

The goal is to make deck knowledge available to the backend as read-only LLM context and as strict JSON contracts for classification, critique, outline generation, and slide generation.

## Runtime layout

```text
backend/llm_knowledge/deck_archetype_knowledge/
  source_md/                 # Human-editable Markdown source files
  compiled_json/
    archetypes.index.json    # Load this first in the backend
    archetypes/*.json        # One runtime JSON file per archetype
  schema/
    deck_archetype.schema.json
  scripts/
    compile_deck_archetypes.py
```

## Runtime rule

The backend should treat this folder as deck knowledge, not as user facts.

The LLM may use it to answer:

- What kind of slide is this?
- What should come before or after this slide?
- What inputs are required before generating this slide?
- What mistakes should be flagged?
- What JSON shape should the frontend receive?

The LLM must not use it to invent:

- traction numbers
- customers
- investors
- team credentials
- regulatory claims
- financial projections

Those facts must come from the active project, user input, source files, or verified data.

## Backend mount path

Recommended runtime path:

```bash
DECK_KNOWLEDGE_INDEX_PATH=/app/backend/llm_knowledge/deck_archetype_knowledge/compiled_json/archetypes.index.json
```

For Railway, mount persistent editable knowledge under the app path if the service needs to update it at runtime:

```bash
/app/backend/llm_knowledge
```

If the knowledge base is committed to git and only read at runtime, a Railway volume is optional. If you want to edit/upload knowledge files independently of deploys, use a volume and point the backend to `RAILWAY_VOLUME_MOUNT_PATH` or to the explicit `DECK_KNOWLEDGE_INDEX_PATH`.

## Compile Markdown to JSON

```bash
python backend/llm_knowledge/deck_archetype_knowledge/scripts/compile_deck_archetypes.py   --src backend/llm_knowledge/deck_archetype_knowledge/source_md   --out backend/llm_knowledge/deck_archetype_knowledge/compiled_json
```

## Backend loading contract

Pseudo-code:

```ts
const indexPath = process.env.DECK_KNOWLEDGE_INDEX_PATH
  ?? path.join(process.cwd(), "backend/llm_knowledge/deck_archetype_knowledge/compiled_json/archetypes.index.json");

const deckKnowledge = JSON.parse(await fs.readFile(indexPath, "utf8"));
```

Cache the parsed index in memory. Reload it on deploy, server start, or an explicit admin refresh endpoint.

## First backend endpoints to expose

```text
GET  /api/llm/deck/archetypes
POST /api/llm/deck/analyze
POST /api/llm/deck/outline
POST /api/llm/deck/generate-slide
POST /api/llm/deck/rewrite-slide
POST /api/llm/deck/chat
```
