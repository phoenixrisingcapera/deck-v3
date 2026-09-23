# Deck AIStack LLM Knowledge Bitacora

This file records the implementation work for the backend LLM knowledge base that supports Smart Deck generation and Smart Edit suggestions.

## 2026-06-19 - Phase 0: Backend Knowledge Mount

### Purpose

Make `backend/llm_knowledge` a backend-owned knowledge mount instead of a loose drop-in folder.

### Completed

* Added `DECK_KNOWLEDGE_INDEX_PATH` to backend config and `.env.example`.
* Added `PyYAML` to backend dependency files because the compiler reads YAML frontmatter and knowledge modules.
* Added a Nixpacks build phase so Railway compiles the knowledge base during backend build.
* Wired `app/ai/slide_archetypes_context.py` to load:
  * `backend/llm_knowledge/deck_archetype_knowledge/compiled_json/archetypes.index.json`
  * fallback static archetypes if the compiled knowledge file is unavailable.
* Preserved the backend rule that Smart Deck should produce backend-validated `render_schema_json`, not raw Svelte, HTML, CSS, Tailwind classes, or arbitrary JavaScript.

### Code Paths

```text
backend/app/core/config.py
backend/app/ai/slide_archetypes_context.py
backend/nixpacks.toml
backend/requirements.txt
backend/pyproject.toml
backend/.env.example
```

### Runtime Entry Point

```text
backend/llm_knowledge/deck_archetype_knowledge/compiled_json/archetypes.index.json
```

### Validation

* Loader smoke confirmed the backend reads compiled JSON knowledge.
* Compiler smoke confirmed 27 archetypes compile successfully.

---

## 2026-06-19 - Phase 1: Structured Knowledge Modules

### Purpose

Move beyond a basic archetype catalogue and create the first structured knowledge-base layer for Smart Deck generation.

### Source Files Created

```text
backend/llm_knowledge/deck_archetype_knowledge/manifest.yaml
backend/llm_knowledge/deck_archetype_knowledge/taxonomy/deck_types.yaml
backend/llm_knowledge/deck_archetype_knowledge/narrative/flows.yaml
backend/llm_knowledge/deck_archetype_knowledge/visual_language/render_schema_rules.yaml
backend/llm_knowledge/deck_archetype_knowledge/writing/copy_rules.yaml
backend/llm_knowledge/deck_archetype_knowledge/rubrics/quality_rubrics.yaml
backend/llm_knowledge/deck_archetype_knowledge/constraints/hallucination_constraints.yaml
backend/llm_knowledge/deck_archetype_knowledge/retrieval/routing_rules.yaml
```

### Completed

* Added a versioned `manifest.yaml` for the Smart Deck knowledge base.
* Added deck-type taxonomy for startup pitch and VC fund pitch decks.
* Added narrative arcs for investor conviction, LP conviction, and problem-solution-impact flow.
* Added render-schema rules for the Svelte renderer contract.
* Added writing rules for claims, proof points, tone, evidence, and caveats.
* Added quality rubrics for Smart Deck generation, Smart Edit, and deck sequence.
* Added hallucination constraints so the model treats the knowledge base as structure, not user facts.
* Added retrieval routing rules for Smart Deck generation, Smart Edit, critique, and repair.

### Compiler Changes

`compile_deck_archetypes.py` was extended so it compiles:

* Markdown archetype source files from `source_md/*.md`.
* YAML knowledge modules listed in `manifest.yaml`.
* Runtime module JSON into `compiled_json/modules/*.json`.
* A combined runtime entrypoint at `compiled_json/archetypes.index.json`.

### Runtime Wiring

`slide_archetypes_context.py` now exposes:

* `knowledgeModules`
* `runtimeContract`
* `renderContract`
* `qualityRubric`
* `llmContract`

Smart Deck and Smart Edit both receive this context through `slideArchetypeContext`.

### Prompt Wiring

Smart Deck generation now instructs the model to use:

* render-schema rules
* writing rules
* quality rubrics
* hallucination constraints

Smart Edit now receives the same knowledge context for reviewable rewrite suggestions.

### Validation

* Compiler generated 27 archetypes.
* Loader smoke confirmed `compiled_json`, version `0.2.0`, 27 archetypes.
* JSON validation passed for the compiled index and an individual archetype file.

### Boundary

This phase made the knowledge base real and used by backend prompts, but most archetype-specific knowledge was still generic.

---

## 2026-06-19 - Phase 2: Operating-Manual Knowledge Contract

### Purpose

Implement the pasted requirement that the knowledge base must be a deck operating manual, not just slug/title/tag metadata.

The target was to teach the LLM how to decide, generate, critique, rewrite, validate, and render Smart Deck slides.

### Source Files Created

```text
backend/llm_knowledge/deck_archetype_knowledge/deck_recipes/recipes.yaml
backend/llm_knowledge/deck_archetype_knowledge/diagnostics/diagnostic_rules.yaml
backend/llm_knowledge/deck_archetype_knowledge/generation/slide_output_contracts.yaml
backend/llm_knowledge/deck_archetype_knowledge/examples/example_cases.yaml
backend/llm_knowledge/deck_archetype_knowledge/evals/eval_cases.yaml
```

### Manifest Update

`manifest.yaml` was upgraded to:

```text
version: 0.3.0
```

It now registers 12 runtime modules:

```text
deck_types
narrative_flows
render_schema_rules
writing_rules
quality_rubrics
hallucination_constraints
retrieval_routing
deck_recipes
diagnostics
generation_contracts
examples
eval_cases
```

### Compiled Runtime Outputs

The compiler now produces:

```text
compiled_json/archetypes.index.json
compiled_json/archetypes/*.json
compiled_json/modules/deck_recipes.json
compiled_json/modules/deck_types.json
compiled_json/modules/diagnostics.json
compiled_json/modules/eval_cases.json
compiled_json/modules/examples.json
compiled_json/modules/generation_contracts.json
compiled_json/modules/hallucination_constraints.json
compiled_json/modules/narrative_flows.json
compiled_json/modules/quality_rubrics.json
compiled_json/modules/render_schema_rules.json
compiled_json/modules/retrieval_routing.json
compiled_json/modules/writing_rules.json
```

### Archetype Contract Upgrade

Every compiled archetype now includes:

* `id`
* `slug`
* `title`
* `description`
* `deck_types`
* `deck_families`
* `sequence`
* `body_md`
* `narrative_role`
* `use_when`
* `do_not_use_when`
* `required_inputs`
* `optional_inputs`
* `evidence_hierarchy`
* `generation_rules`
* `critique_rules`
* `rewrite_modes`
* `visual_guidance`
* `llm_contract`
* `render_contract`
* `quality_rubric`
* `output_contract`
* `validation_rules`
* `frontend_render_hints`

This means a compiled archetype is now an operating-manual record, not a catalogue record.

### Schema Enforcement

`deck_archetype.schema.json` now requires the operating-manual fields. A minimal slug/title/tags record is no longer a valid compiled archetype.

### Smart Deck Runtime Changes

Smart Deck prompt rules now instruct the LLM to use:

* deck recipes
* diagnostics
* generation contracts
* render-schema rules
* writing rules
* quality rubrics
* hallucination constraints

The expected render schema now includes analytics fields for:

* `sourceFactsUsed`
* `assumptions`
* `missingInputs`
* `qualityWarnings`
* `confidence`

### Smart Edit Runtime Changes

Smart Edit now receives `slideArchetypeContext` and is instructed to use:

* diagnostics
* hallucination constraints
* archetype rewrite modes
* Smart Edit quality rubrics

Smart Edit remains reviewable. It does not silently apply edits.

### Backend Render Schema Change

`RenderSchemaAnalytics` now accepts:

```text
sourceFactsUsed: list[str]
assumptions: list[str]
missingInputs: list[str]
qualityWarnings: list[str]
confidence: float | None
```

This lets generated slides preserve evidence, assumptions, missing inputs, and confidence inside validated backend JSON.

### Frontend Type Change

`Frontend-clean/src/lib/api/smartDeckWorkspace.ts` now includes the same analytics fields in the TypeScript `RenderSchema` type.

### Code Paths Changed

```text
backend/app/agents/smart_edit_agent.py
backend/app/ai/slide_archetypes_context.py
backend/app/schemas/smart_deck.py
backend/app/services/smart_deck_llm_service.py
backend/app/services/smart_edit_service.py
Frontend-clean/src/lib/api/smartDeckWorkspace.ts
```

### Validation

Ran compiler:

```text
Compiled 27 archetypes into llm_knowledge/deck_archetype_knowledge/compiled_json
```

Ran structural validation:

```text
ok modules=12 archetypes=27 version=0.3.0 operating_manual_fields=true
```

Confirmed loader output:

```text
12 modules exposed through slideArchetypeContext
inferred archetype has evidenceHierarchy=true
inferred archetype has rewriteModes=true
inferred archetype has outputContract=true
```

Ran JSON validation:

```text
archetypes.index.json valid JSON
problem.json valid JSON
```

Ran Python syntax checks for:

```text
compile_deck_archetypes.py
slide_archetypes_context.py
smart_deck.py
smart_deck_llm_service.py
smart_edit_agent.py
```

### Validation Limitation

System Python in this shell does not have backend dependencies installed, so the full Pydantic runtime smoke could not execute here. The compile and syntax checks passed.

### Deployment Note

`backend/llm_knowledge/` is currently untracked in the backend git repo. It must be added and committed before Railway can deploy this knowledge base.

### Remaining Work

* Customize each `source_md/*.md` archetype with specific evidence rules, visual patterns, and examples.
* Promote accepted and rejected tester outputs into examples and eval cases.
* Add regression tests for Smart Deck generation and Smart Edit suggestions using the `eval_cases` module.
* Add the full multi-step LLM agent loop: planner, generator, critic, repair pass, and final renderer validation.
* Add live Vercel/Railway smoke coverage with a seeded tester account and a real uploaded deck.

## Phase 3 - Runtime Knowledge Readiness

Date: 2026-06-19

Purpose: make the knowledge base operationally visible and versioned at runtime, so Smart Deck and Smart Edit outputs can be traced back to the exact LLM knowledge release.

### Backend Validation Script

Added:

```text
backend/scripts/validate_llm_knowledge.py
```

The script validates:

* `manifest.yaml`
* compiled index version alignment
* required module IDs
* compiled module files
* compiled archetype detail files
* duplicate archetype IDs/slugs
* required operating-manual fields
* Smart Deck render schema contract
* relationship graph coverage

Expected success output:

```text
LLM knowledge validation passed: version=0.3.0 archetypes=27 modules=12
```

### Runtime Knowledge Service

Added:

```text
backend/app/services/llm_knowledge_service.py
```

This exposes:

```text
build_llm_knowledge_metadata()
get_llm_knowledge_health()
```

The metadata includes:

* knowledge name
* version
* source
* archetype count
* module count
* module IDs
* runtime contract

### Admin Health Endpoint

Added an admin-only route:

```text
GET /api/admin/llm-knowledge/health
```

The endpoint returns readiness status, loaded knowledge metadata, required module coverage, and archetype field validation errors.

### Smart Deck Metadata Persistence

Smart Deck generation now writes `knowledgeMetadata` into:

* `GenerationJob.llm_context_json`
* `smart_deck_generation_context` LLM artifact
* generated slide render-schema artifact payloads
* design version manifest artifact payload
* Smart Deck telemetry metadata

This means every generated Smart Deck run can be traced back to the knowledge base version used at generation time without adding a database migration.

### Smart Edit Metadata Persistence

Smart Edit now includes `knowledgeMetadata` in the deck context sent to the Smart Edit agent and records knowledge version/source in Smart Edit telemetry.

### Code Paths Changed In This Phase

```text
backend/app/api/routes/admin_operations.py
backend/app/services/llm_knowledge_service.py
backend/app/services/smart_deck_llm_service.py
backend/app/services/smart_edit_service.py
backend/scripts/validate_llm_knowledge.py
```

### Current Status

The LLM knowledge layer is now compiled, validated, loaded by Smart Deck/Smart Edit, visible to admin operators, and versioned in generated artifacts/telemetry.

It is not yet the complete full LLM product architecture. The next stage is the agentic generation loop: plan, retrieve, draft, critique, repair, validate, persist, and learn from user feedback.

## Phase 4 - Smart Deck Generation Plan And Critique Artifacts

Date: 2026-06-19

Purpose: start converting Smart Deck generation from a single prompt call into a traceable backend agent pipeline.

### Generation Plan

Added a deterministic planning layer in:

```text
backend/app/services/smart_deck_llm_service.py
```

The new plan artifact uses:

```text
schemaVersion: smart-deck-generation-plan.v1
artifact_type: smart_deck_generation_plan
artifact_key: GenerationJob.id
```

The plan records:

* knowledge metadata
* selected slide count
* recommended archetype sequence
* primary inferred archetype
* required inputs
* render contract
* output contract
* pipeline steps: classify, retrieve, draft, critique, persist

### Generation Critique

Added a deterministic critique layer after model output is validated by the backend render schema.

The critique artifact uses:

```text
schemaVersion: smart-deck-generation-critique.v1
artifact_type: smart_deck_generation_critique
artifact_key: GenerationJob.id
```

The critique checks:

* missing `sourceFactsUsed`
* declared assumptions
* declared missing inputs
* declared quality warnings
* non-numeric confidence
* high confidence when assumptions are still present

The critique summary is added to the Smart Deck design version manifest and completion telemetry.

### Current Pipeline Shape

Smart Deck generation now follows this backend flow:

```text
load knowledge
build LLM context
build generation plan
persist generation plan artifact
call provider
validate render_schema_json
build critique
persist critique artifact
persist generated slides/elements/code versions
persist design manifest
record telemetry
```

### Remaining Pipeline Work

The next stage should add:

* failed-critique promotion into regression/eval cases
* Smart Edit equivalent planning, critique, and repair artifacts
* live smoke with real provider credentials and a seeded tester deck

## Phase 5 - Bounded Smart Deck Repair Pass

Date: 2026-06-19

Purpose: move Smart Deck from critique-only diagnostics to a first repair loop that can automatically correct weak model output before generated slides are persisted.

### Repair Trigger

Smart Deck now performs one repair pass when:

```text
generation_critique.status == review
```

The repair is bounded to a single retry. There is no open-ended loop.

### Repair Context

The repair provider call receives:

* original Smart Deck LLM context
* original render payload
* deterministic critique
* instruction to preserve `sourceSlideId` values
* instruction to fix only critique issues
* instruction to keep unsupported claims conservative
* instruction to populate `analytics.missingInputs` and `analytics.qualityWarnings` instead of inventing data

### Repair Validation

The repaired payload is validated through the same backend path:

```text
_validate_generated_render_payload()
RenderSchema.model_validate()
_critique_generated_render_payload()
```

If the repaired critique still returns `review`, the generated output is still persisted as reviewable output with critique metadata. The backend does not loop or silently ignore the remaining warnings.

### Repair Artifact

Added artifact:

```text
artifact_type: smart_deck_generation_repair
artifact_key: GenerationJob.id
schemaVersion: smart-deck-generation-repair.v1
```

The artifact records:

* knowledge metadata
* original critique
* repaired critique
* original design version name
* repaired design version name
* repaired slide count

### Manifest And Telemetry

The Smart Deck design manifest and completion telemetry now record:

* whether repair was performed
* final critique status
* final warning count
* final missing-input count
* repair artifact type when present

### Current Pipeline Shape

Smart Deck generation now follows:

```text
load knowledge
build LLM context
build generation plan
persist generation plan artifact
call provider
validate render_schema_json
build critique
persist critique artifact
if critique requires review:
  call provider once for repair
  validate repaired render_schema_json
  critique repaired output
  persist repair artifact
persist generated slides/elements/code versions
persist design manifest
record telemetry
```

## Phase 6 - Source Fact Package For Smart Deck

Date: 2026-06-19

Purpose: make Smart Deck generation fact-constrained before the provider call, so the model has a bounded evidence object instead of relying on broad prompt context.

### Source Fact Package

Added deterministic source-fact extraction in:

```text
backend/app/services/smart_deck_llm_service.py
```

The package uses:

```text
schemaVersion: smart-deck-source-facts.v1
artifact_type: smart_deck_source_facts
artifact_key: GenerationJob.id
```

Source facts are extracted from:

* deck title, audience, purpose, and summary
* user prompt and additional context
* brand profile name and visual direction
* selected source slide title, role, semantic type, and raw text
* existing prompt-context LLM artifact summaries

### Provider Contract

The Smart Deck provider prompt now tells the model:

* use `sourceFactPackage.facts` as the only allowed source for factual claims
* populate `analytics.sourceFactsUsed` with exact or clearly matching source facts
* put missing evidence into `analytics.missingInputs` or `analytics.qualityWarnings`
* do not invent unsupported traction, customer, investor, financial, regulatory, or legal claims

### Plan And Context Wiring

`sourceFactPackage` is now included in:

* `GenerationJob.llm_context_json`
* Smart Deck LLM context artifact
* generation plan source-fact summary
* repair context

### Critique Enforcement

The deterministic critique now checks whether generated `analytics.sourceFactsUsed` entries match the approved `sourceFactPackage.facts`.

If a generated fact does not match the approved source fact package, critique adds:

```text
Some analytics.sourceFactsUsed entries do not match sourceFactPackage facts.
```

The critique also records unsupported source facts per slide.

### Manifest And Telemetry

The Smart Deck design manifest and completion telemetry now include:

* `sourceFactCount`
* `missingSlideFactCount`
* `sourceFactsArtifactType`

### Current Pipeline Shape

Smart Deck generation now follows:

```text
load knowledge
extract source facts
build LLM context with sourceFactPackage
build generation plan
persist source facts artifact
persist generation plan artifact
call provider
validate render_schema_json
critique source-fact usage and render analytics
repair once if critique requires review
validate and critique repaired output
persist generated slides/elements/code versions
persist design manifest
record telemetry
```

### Remaining Pipeline Work

The source-fact package is deterministic and bounded, but it is still a first version. The next improvements should:

* promote failed source-fact critiques into eval cases
* add Smart Edit source-fact packages
* run live smoke with real provider credentials and a seeded tester deck

## Phase 7 - Explicit Source Fact IDs

Date: 2026-06-19

Purpose: stop relying only on fuzzy text matching for source facts and make Smart Deck cite explicit fact IDs in the render schema.

### Render Schema Analytics

Added:

```text
renderSchema.analytics.sourceFactIds: list[str]
```

`sourceFactsUsed` remains available as readable labels or excerpts, but `sourceFactIds` is now the authoritative citation field.

### Frontend Type Support

Updated:

```text
Frontend-clean/src/lib/api/smartDeckWorkspace.ts
```

The frontend Smart Deck render schema type now accepts:

```text
analytics.sourceFactIds?: string[]
```

### Provider Contract

The Smart Deck provider prompt now requires:

* `analytics.sourceFactIds` with IDs such as `fact_1`
* `analytics.sourceFactsUsed` with short readable labels or excerpts for those same facts
* missing evidence to remain in `missingInputs` or `qualityWarnings`

### Critique Enforcement

The deterministic critique now checks:

* `analytics.sourceFactIds` exists when source facts are available
* every source fact ID exists in `sourceFactPackage.facts`
* readable `sourceFactsUsed` still matches approved fact text where possible

Unknown fact IDs produce:

```text
Some analytics.sourceFactIds entries do not exist in sourceFactPackage facts.
```

Missing fact IDs produce:

```text
No fact IDs were declared in renderSchema.analytics.sourceFactIds.
```

The critique payload now records:

* `allowedSourceFactIds`
* per-slide `sourceFactIds`
* per-slide `unsupportedSourceFactIds`
* per-slide readable unsupported source facts

### Validation

Ran:

```text
python3 -m py_compile app/services/smart_deck_llm_service.py app/schemas/smart_deck.py app/services/llm_knowledge_service.py app/api/routes/admin_operations.py app/services/smart_edit_service.py scripts/validate_llm_knowledge.py
python3 scripts/validate_llm_knowledge.py
PYTHONPATH=. python3 -c "from app.services.llm_knowledge_service import get_llm_knowledge_health; ..."
```

Results:

```text
LLM knowledge validation passed: version=0.3.0 archetypes=27 modules=12
ready 0.3.0 27 12 0
```

Pydantic runtime schema smoke could not run in this shell because the checkout does not have a backend `.venv` and system Python is missing `pydantic`.

### Remaining Pipeline Work

Next improvements should:

* add Smart Edit source-fact packages
* add Smart Edit plan, critique, and repair artifacts
* run live smoke with real provider credentials and a seeded tester deck

## Phase 8 - Smart Deck Critique Regression Promotion

Date: 2026-06-19

Purpose: convert failed or review-status Smart Deck critique artifacts into sanitized regression cases that preserve source fact IDs without exposing raw deck content.

### Service Implementation

Extended:

```text
backend/app/services/agent_regression_service.py
```

Added:

```text
promote_smart_deck_critique_to_regression_case()
```

The service accepts a `smart_deck_generation_critique` artifact ID, loads the real artifact payload even when the artifact is stored through the upload-storage abstraction, finds the matching `smart_deck_source_facts` artifact, and builds a sanitized regression fixture.

Because `AgentRegressionCase` is keyed to a telemetry event, the service creates a sanitized synthetic telemetry event:

```text
event_name: ai.smart_deck_generation.critique_regression
run_type: smart_deck_generation
status: failed
event_level: error
error_category: smart_deck_source_fact_critique
```

### Admin Endpoint

Added:

```text
POST /api/admin/llm-artifacts/{artifact_id}/promote-regression
```

The endpoint is `super_admin` gated and accepts an optional operator note.

### Fixture Shape

The regression fixture preserves:

* source telemetry event ID
* source critique artifact ID
* generation run ID
* provider/model when available
* critique status
* warning count
* missing-input count
* allowed source fact IDs
* per-slide cited source fact IDs
* per-slide unsupported source fact IDs
* sanitized source fact metadata

The fixture does not preserve raw slide text, raw prompts, provider secrets, cookies, or full generated output.

### Replay Check

`replay_agent_regression_fixture()` now checks:

```text
expected.shouldPreserveSourceFactIds
```

When enabled, replay fails if source fact IDs are missing or if cited IDs are not present in the fixture source facts.

### Validation

Ran:

```text
python3 -m py_compile app/services/agent_regression_service.py app/api/routes/admin_operations.py app/services/smart_deck_llm_service.py app/schemas/smart_deck.py scripts/validate_llm_knowledge.py
python3 scripts/validate_llm_knowledge.py
PYTHONPATH=. python3 -c "from app.services.llm_knowledge_service import get_llm_knowledge_health; ..."
```

Results:

```text
LLM knowledge validation passed: version=0.3.0 archetypes=27 modules=12
ready 0.3.0 27 12 0
```

### Remaining Work

Next improvements should:

* add admin UI action for promoting critique artifacts
* export promoted fixtures into the knowledge eval folder
* add Smart Edit critique promotion into regression cases
* run live smoke with real provider credentials and a seeded tester deck

## Phase 9 - Smart Edit Knowledge Parity

Date: 2026-06-19

Purpose: bring Smart Edit closer to the Smart Deck LLM architecture by adding source facts, planning, critique, bounded repair, artifacts, and telemetry.

### Agent Contract

Updated:

```text
backend/app/agents/smart_edit_agent.py
```

The Smart Edit agent now asks for:

```text
original_text
suggested_text
reason
risk_level
source_fact_ids
source_facts_used
missing_inputs
quality_warnings
```

The prompt instructs the model to use `deck_context.sourceFactPackage.facts` as the only factual source and to cite fact IDs such as `fact_1`.

### Source Facts

Added deterministic source-fact extraction in:

```text
backend/app/services/smart_edit_service.py
```

The source fact package uses:

```text
schemaVersion: smart-edit-source-facts.v1
artifact_type: smart_edit_source_facts
artifact_key: SmartEditRun.id
```

Source facts are extracted from:

* deck title, audience, and purpose
* Smart Edit instruction and audience type
* selected slide title, role, and raw text
* selected block type and raw/normalized text

### Plan Artifact

Added:

```text
artifact_type: smart_edit_plan
schemaVersion: smart-edit-plan.v1
```

The plan records the source fact summary, knowledge metadata, and the Smart Edit steps: retrieve, draft, critique, repair, and persist.

### Critique Artifact

Added:

```text
artifact_type: smart_edit_critique
schemaVersion: smart-edit-critique-artifact.v1
```

The critique checks:

* missing source fact IDs
* unknown source fact IDs
* missing inputs
* quality warnings
* unchanged suggested text

### Bounded Repair

Smart Edit now performs one repair pass when critique status is `review`.

The repair artifact uses:

```text
artifact_type: smart_edit_repair
schemaVersion: smart-edit-repair.v1
```

The repair pass is bounded to one retry and the suggestion remains reviewable after persistence.

### Telemetry

Smart Edit completion telemetry now records:

* source fact count
* critique status
* critique warning count
* critique missing-input count
* repair performed
* knowledge version/source

### Validation

Ran:

```text
python3 -m py_compile app/services/smart_edit_service.py app/agents/smart_edit_agent.py app/services/agent_regression_service.py app/api/routes/admin_operations.py app/services/smart_deck_llm_service.py app/schemas/smart_deck.py scripts/validate_llm_knowledge.py
python3 scripts/validate_llm_knowledge.py
PYTHONPATH=. python3 -c "from app.services.llm_knowledge_service import get_llm_knowledge_health; ..."
```

Results:

```text
LLM knowledge validation passed: version=0.3.0 archetypes=27 modules=12
ready 0.3.0 27 12 0
```

### Remaining Work

Next improvements should:

* add Smart Edit critique promotion into regression cases
* extract shared source-fact helpers into a dedicated service after behavior stabilizes
* run live smoke with real provider credentials and a seeded tester deck

## Phase 10 - Fact Types And Evidence Strength

Date: 2026-06-19

Purpose: make Smart Deck and Smart Edit source facts safer and more useful by classifying facts before the provider call.

### Shared Classifier

Added:

```text
backend/app/services/source_fact_service.py
```

The classifier adds:

```text
factType
evidenceStrength
safetyFlags
```

Supported fact types include:

```text
instruction
brand
context
positioning
metric
financial
customer
team
market
regulatory
product
timeline
ask
assumption
general
```

Safety flags include:

```text
requires_source
requires_user_confirmation
do_not_strengthen
avoid_superlative
```

### Smart Deck Wiring

Updated:

```text
backend/app/services/smart_deck_llm_service.py
```

Smart Deck source facts now include fact type, evidence strength, and safety flags. The provider prompt tells the model to respect these fields and not strengthen facts marked `do_not_strengthen`.

Smart Deck critique now records:

* cited fact types
* cited safety flags
* whether cited facts requiring source labels are missing readable source labels

Smart Deck source-fact artifact metrics now include:

* `factTypeCounts`
* `safetyFlagCounts`

### Smart Edit Wiring

Updated:

```text
backend/app/services/smart_edit_service.py
backend/app/agents/smart_edit_agent.py
```

Smart Edit source facts now include fact type, evidence strength, and safety flags. The Smart Edit prompt tells the model to respect the metadata and treat financial, regulatory, customer, and metric facts carefully.

Smart Edit critique now records:

* cited fact types
* cited safety flags
* missing readable source labels when cited facts require source labels

Smart Edit source-fact artifact metrics now include:

* `factTypeCounts`
* `safetyFlagCounts`

### Regression Fixture Wiring

Updated:

```text
backend/app/services/agent_regression_service.py
```

Sanitized regression fixtures now preserve:

* fact type
* evidence strength
* safety flags

They still do not preserve raw fact text.

### Validation

Ran:

```text
python3 -m py_compile app/services/source_fact_service.py app/services/smart_deck_llm_service.py app/services/smart_edit_service.py app/agents/smart_edit_agent.py app/services/agent_regression_service.py app/api/routes/admin_operations.py app/schemas/smart_deck.py scripts/validate_llm_knowledge.py
python3 scripts/validate_llm_knowledge.py
PYTHONPATH=. python3 -c "from app.services.llm_knowledge_service import get_llm_knowledge_health; ..."
```

Results:

```text
LLM knowledge validation passed: version=0.3.0 archetypes=27 modules=12
ready 0.3.0 27 12 0
```

### Remaining Work

Next improvements should:

* add Smart Edit critique promotion into regression cases
* add a stronger critique service with dimensions and repair actions
* add source-fact classifier tests when the backend test folder is available
* run live smoke with real provider credentials and a seeded tester deck

## Phase 11 - Stronger Critique Decisions

Date: 2026-06-19

Purpose: make Smart Deck and Smart Edit critique results operationally useful by adding a shared decision contract with severity, dimensions, and repair actions.

### Shared Critique Service

Added:

```text
backend/app/services/critique_service.py
```

The service produces:

* `schemaVersion: critique-decision.v1`
* `status`: `passed`, `review`, or `blocking`
* `blockingCount`
* `warningCount`
* critique `dimensions`
* structured `repairActions`

The first implemented dimensions cover:

* factuality
* evidence
* claim safety
* edit quality
* confidence
* general warnings
* overall pass state

### Smart Deck Wiring

Updated:

```text
backend/app/services/smart_deck_llm_service.py
```

Smart Deck generation critique now includes:

* per-slide critique decisions
* top-level critique summary decision
* flattened dimensions for artifact review
* repair actions for bounded repair prompts
* blocking counts and repair-action counts in artifacts, design manifests, and telemetry

Blocking decisions are still routed through the existing review/repair status path so the current runtime contract remains stable while the richer critique structure is added.

### Smart Edit Wiring

Updated:

```text
backend/app/services/smart_edit_service.py
```

Smart Edit critique now includes:

* shared critique decisions
* dimensions
* repair actions
* blocking counts and repair-action counts in artifacts and telemetry
* repair context that passes structured actions back to the bounded repair prompt

### Validation

Ran:

```text
python3 -m py_compile app/services/critique_service.py app/services/source_fact_service.py app/services/smart_deck_llm_service.py app/services/smart_edit_service.py app/agents/smart_edit_agent.py app/services/agent_regression_service.py app/api/routes/admin_operations.py app/schemas/smart_deck.py scripts/validate_llm_knowledge.py
python3 scripts/validate_llm_knowledge.py
PYTHONPATH=. python3 -c "from app.services.llm_knowledge_service import get_llm_knowledge_health; ..."
```

Results:

```text
LLM knowledge validation passed: version=0.3.0 archetypes=27 modules=12
ready 0.3.0 27 12 0
```

### Remaining Work

Next improvements should:

* add deterministic narrative-fit, visual-density, render-validity, and audience-fit critique dimensions
* add admin UI display for dimensions and repair actions
* promote repeated critique decisions into eval/regression cases
* add tests for `critique_service.py` when the backend test folder is available
