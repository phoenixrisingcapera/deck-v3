# Deck AIStack LLM Knowledge Base Implementation

## Current Implementation Status

This document started as the target architecture for an excellent Deck AIStack LLM knowledge base. The backend now implements the first production-shaped phase inside:

```text
backend/llm_knowledge/deck_archetype_knowledge
```

### Implemented Now

* `manifest.yaml` defines the Smart Deck runtime contract, module list, retrieval priorities, and rules for backend-validated `render_schema_json`; current compiled version is `0.3.0`.
* `taxonomy/deck_types.yaml` defines startup pitch and VC fund pitch deck types, audiences, canonical flows, and quality bars.
* `deck_recipes/recipes.yaml` defines stage-aware startup and VC fund pitch sequences.
* `narrative/flows.yaml` defines investor, LP, and problem-solution-impact narrative arcs.
* `visual_language/render_schema_rules.yaml` defines the Svelte renderer contract, allowed schema output, element bounds, layout patterns, and visual quality bar.
* `writing/copy_rules.yaml` defines headline, evidence, tone, and slide-copy rules.
* `rubrics/quality_rubrics.yaml` defines Smart Deck, Smart Edit, and deck-sequence quality checks.
* `diagnostics/diagnostic_rules.yaml` defines Smart Deck and Smart Edit diagnostic rules for hallucination, missing evidence, and risky edits.
* `constraints/hallucination_constraints.yaml` defines hard limits on unsupported metrics, customers, investors, financials, and regulatory claims.
* `generation/slide_output_contracts.yaml` defines source facts, assumptions, missing inputs, warnings, and confidence fields for generated slides.
* `examples/example_cases.yaml` and `evals/eval_cases.yaml` provide the first strong/weak examples and regression-style expectations.
* `retrieval/routing_rules.yaml` defines which modules are always retrieved for Smart Deck generation, Smart Edit, critique, and repair.
* `scripts/compile_deck_archetypes.py` compiles Markdown archetypes and YAML modules into runtime JSON.
* `compiled_json/archetypes.index.json` is now the backend entrypoint for archetypes, deck types, knowledge modules, runtime contract, and routing metadata.
* `app/ai/slide_archetypes_context.py` loads the compiled index and exposes `knowledgeModules`, `runtimeContract`, per-archetype operating-manual fields, `renderContract`, `qualityRubric`, and `outputContract`.
* Smart Deck generation prompts now instruct the LLM to use deck recipes, diagnostics, render-schema rules, generation contracts, writing rules, quality rubrics, and hallucination constraints.
* Smart Edit now receives the same `slideArchetypeContext` knowledge and uses diagnostics and rewrite modes for reviewable rewrite suggestions.
* `RenderSchemaAnalytics` now accepts `sourceFactsUsed`, `assumptions`, `missingInputs`, `qualityWarnings`, and `confidence`.

### Current Runtime Rule

Deck AIStack does **not** ask the LLM to generate raw Svelte. The LLM must generate backend-validated `render_schema_json`; `GeneratedSlideRenderer.svelte` renders that JSON in the Smart Deck page. The knowledge base should therefore teach the model how to produce excellent render schemas for Svelte rendering, not uncontrolled Svelte components or Tailwind class strings.

### Docs And Knowledge Files Created

```text
backend/llm_knowledge/deck_archetype_knowledge/manifest.yaml
backend/llm_knowledge/deck_archetype_knowledge/deck_recipes/recipes.yaml
backend/llm_knowledge/deck_archetype_knowledge/taxonomy/deck_types.yaml
backend/llm_knowledge/deck_archetype_knowledge/narrative/flows.yaml
backend/llm_knowledge/deck_archetype_knowledge/visual_language/render_schema_rules.yaml
backend/llm_knowledge/deck_archetype_knowledge/writing/copy_rules.yaml
backend/llm_knowledge/deck_archetype_knowledge/rubrics/quality_rubrics.yaml
backend/llm_knowledge/deck_archetype_knowledge/diagnostics/diagnostic_rules.yaml
backend/llm_knowledge/deck_archetype_knowledge/constraints/hallucination_constraints.yaml
backend/llm_knowledge/deck_archetype_knowledge/generation/slide_output_contracts.yaml
backend/llm_knowledge/deck_archetype_knowledge/retrieval/routing_rules.yaml
backend/llm_knowledge/deck_archetype_knowledge/examples/example_cases.yaml
backend/llm_knowledge/deck_archetype_knowledge/evals/eval_cases.yaml
backend/llm_knowledge/deck_archetype_knowledge/compiled_json/modules/*.json
```

### Needs Further Expansion

* Each source archetype in `source_md/*.md` now compiles into a rich operating-manual record, but most rich fields are compiler defaults; they still need custom per-archetype playbooks.
* The current `render_contract`, `quality_rubric`, evidence hierarchy, rewrite modes, and output contract are useful defaults, but they are not yet customized per archetype.
* The examples and evals are seed examples only; they need real accepted/rejected Smart Deck and Smart Edit outputs from tester runs.
* The backend does not yet have an admin refresh endpoint for reloading compiled knowledge without deploy.
* The backend does not yet persist knowledge-version metadata on each `GenerationJob`, `AiRun`, or generated slide artifact.
* The frontend does not yet show knowledge-version/debug metadata to admins.
* Smart Edit uses the knowledge context, but it still needs a stronger per-archetype edit rubric and regression tests.

### Next Phases

1. Expand the top 10 archetypes used in tester decks with custom evidence rules and layout patterns.
2. Add knowledge-version metadata to Smart Deck generation jobs and generated slides.
3. Add a backend knowledge validation script that checks schema, module presence, and archetype completeness.
4. Promote accepted/rejected Smart Deck and Smart Edit examples into a future examples module.
5. Add admin-only knowledge health/readiness endpoint.

---

Assuming **ddeck** is your AI deck-building product, I would structure the backend so the LLM is guided by a **versioned knowledge/control system**, not just prompts.

The folder should answer these questions for the LLM:

> What type of deck is this?
> What is the user trying to achieve?
> What slide archetypes are valid?
> What sequence should the deck follow?
> What should each slide contain?
> What layout/visual rules apply?
> How do we critique and repair the result?
> What gets remembered for future improvements?

A strong backend structure would look like this.

---

# 1. Recommended backend architecture

```txt
backend/
  app/
    api/
      v1/
        routes/
          deck_agent_routes.py
          deck_routes.py
          knowledge_routes.py
          feedback_routes.py

    agents/
      deck_builder/
        graph.py
        state.py
        planner.py
        executor.py

        nodes/
          brief_normalizer.py
          deck_classifier.py
          knowledge_router.py
          deck_strategist.py
          outline_builder.py
          slide_planner.py
          slide_writer.py
          layout_director.py
          visual_director.py
          critic.py
          repair.py
          finalizer.py

        tools/
          retrieve_knowledge.py
          search_examples.py
          inspect_existing_deck.py
          create_slide.py
          update_slide.py
          validate_slide.py
          validate_deck.py
          export_deck.py

        prompts/
          system/
            deck_builder_system.md
            critic_system.md
            layout_system.md

          tasks/
            classify_deck.md
            create_outline.md
            write_slide.md
            improve_slide.md
            critique_deck.md
            repair_deck.md

        schemas/
          deck_brief.schema.json
          deck_plan.schema.json
          slide_plan.schema.json
          slide_content.schema.json
          layout_decision.schema.json
          critique.schema.json
          repair_action.schema.json
          agent_state.schema.json

        policies/
          retrieval_policy.yaml
          generation_policy.yaml
          validation_policy.yaml
          memory_policy.yaml
          safety_policy.yaml

        evaluators/
          deck_quality_evaluator.py
          slide_quality_evaluator.py
          narrative_evaluator.py
          visual_evaluator.py
          hallucination_evaluator.py

    knowledge_base/
      deck/
        manifest.yaml

        taxonomy/
          deck_types.yaml
          audiences.yaml
          business_stages.yaml
          communication_goals.yaml
          slide_archetypes.yaml
          narrative_patterns.yaml
          design_patterns.yaml

        deck_types/
          investor_pitch.yaml
          sales_deck.yaml
          product_deck.yaml
          strategy_deck.yaml
          board_deck.yaml
          marketing_deck.yaml
          case_study_deck.yaml
          one_pager.yaml

        slide_archetypes/
          title_slide.yaml
          problem_slide.yaml
          solution_slide.yaml
          market_slide.yaml
          product_demo_slide.yaml
          traction_slide.yaml
          business_model_slide.yaml
          competitive_landscape_slide.yaml
          roadmap_slide.yaml
          team_slide.yaml
          ask_slide.yaml
          summary_slide.yaml
          data_story_slide.yaml
          process_slide.yaml
          comparison_slide.yaml

        narrative/
          investor_pitch_flow.yaml
          sales_narrative_flow.yaml
          before_after_bridge.yaml
          problem_solution_impact.yaml
          strategic_memo_flow.yaml

        visual_language/
          layout_principles.yaml
          hierarchy_rules.yaml
          spacing_rules.yaml
          chart_rules.yaml
          image_usage_rules.yaml
          typography_rules.yaml
          color_rules.yaml
          iconography_rules.yaml

        writing/
          executive_tone.yaml
          investor_tone.yaml
          sales_tone.yaml
          concise_copy_rules.yaml
          headline_patterns.yaml
          anti_patterns.yaml

        examples/
          investor_pitch/
            good_problem_slide.yaml
            good_traction_slide.yaml
            good_market_slide.yaml

          sales_deck/
            good_roi_slide.yaml
            good_case_study_slide.yaml

        rubrics/
          deck_quality_rubric.yaml
          slide_quality_rubric.yaml
          narrative_quality_rubric.yaml
          layout_quality_rubric.yaml
          investor_readiness_rubric.yaml

        retrieval/
          routing_rules.yaml
          chunking_rules.yaml
          embedding_manifest.yaml
          search_boosts.yaml

        constraints/
          brand_constraints.yaml
          hallucination_constraints.yaml
          data_integrity_constraints.yaml
          export_constraints.yaml

    services/
      llm_provider_service.py
      knowledge_retrieval_service.py
      deck_generation_service.py
      deck_validation_service.py
      deck_export_service.py
      memory_service.py
      feedback_service.py
      agent_telemetry_service.py

    models/
      deck.py
      slide.py
      deck_version.py
      agent_run.py
      agent_event.py
      knowledge_document.py
      user_feedback.py

    repositories/
      deck_repository.py
      slide_repository.py
      knowledge_repository.py
      telemetry_repository.py
      feedback_repository.py

    workers/
      generate_deck_worker.py
      index_knowledge_worker.py
      evaluate_deck_worker.py
      export_deck_worker.py

    db/
      migrations/
      seed/
        default_knowledge_seed.py

    config/
      settings.py
      llm_models.yaml
      feature_flags.yaml

  tests/
    unit/
      agents/
      services/
      validators/

    integration/
      deck_generation/
      knowledge_retrieval/
      export/

    evals/
      golden_decks/
      expected_outputs/
      regression_tests/

  scripts/
    index_knowledge_base.py
    validate_knowledge_base.py
    run_deck_evals.py
```

---

# 2. The most important folder: `knowledge_base/deck/`

This is the folder that actually teaches the LLM how to build decks.

It should not be one giant markdown file. It should be broken into **structured, retrievable, versioned knowledge modules**.

A good structure:

```txt
knowledge_base/
  deck/
    manifest.yaml

    taxonomy/
    deck_types/
    slide_archetypes/
    narrative/
    visual_language/
    writing/
    examples/
    rubrics/
    retrieval/
    constraints/
```

Each section has a different job.

---

## `manifest.yaml`

This is the control file. It tells the backend what knowledge exists, what version it is, and how the LLM should retrieve it.

```yaml
version: "1.0.0"
domain: "deck_building"

default_deck_type: "investor_pitch"

knowledge_modules:
  - id: "deck_types"
    path: "deck_types/"
    retrieval_priority: high

  - id: "slide_archetypes"
    path: "slide_archetypes/"
    retrieval_priority: high

  - id: "narrative_patterns"
    path: "narrative/"
    retrieval_priority: high

  - id: "visual_language"
    path: "visual_language/"
    retrieval_priority: medium

  - id: "writing_rules"
    path: "writing/"
    retrieval_priority: medium

  - id: "quality_rubrics"
    path: "rubrics/"
    retrieval_priority: high

  - id: "examples"
    path: "examples/"
    retrieval_priority: medium

runtime_rules:
  always_retrieve:
    - "taxonomy/deck_types.yaml"
    - "taxonomy/slide_archetypes.yaml"
    - "constraints/hallucination_constraints.yaml"

  retrieve_by_deck_type: true
  retrieve_by_slide_archetype: true
  retrieve_examples: true
  retrieve_rubrics_before_critique: true
```

The backend reads this file before every agent run or when indexing the knowledge base.

---

# 3. `taxonomy/`

This defines the vocabulary of the product.

The LLM needs a controlled vocabulary. Otherwise, it will invent inconsistent deck types, slide types, and strategy labels.

Example:

```txt
taxonomy/
  deck_types.yaml
  audiences.yaml
  business_stages.yaml
  communication_goals.yaml
  slide_archetypes.yaml
  narrative_patterns.yaml
  design_patterns.yaml
```

Example `deck_types.yaml`:

```yaml
deck_types:
  investor_pitch:
    name: "Investor Pitch Deck"
    purpose: "Raise capital by explaining the opportunity, business, traction, and ask."
    common_audiences:
      - angel_investors
      - seed_vcs
      - series_a_vcs
    common_slide_sequence:
      - title_slide
      - problem_slide
      - solution_slide
      - market_slide
      - product_slide
      - traction_slide
      - business_model_slide
      - go_to_market_slide
      - competition_slide
      - team_slide
      - ask_slide

  sales_deck:
    name: "Sales Deck"
    purpose: "Persuade a buyer that the product solves a costly business problem."
    common_audiences:
      - enterprise_buyer
      - smb_buyer
      - department_head
    common_slide_sequence:
      - title_slide
      - customer_problem_slide
      - cost_of_inaction_slide
      - solution_slide
      - product_demo_slide
      - roi_slide
      - proof_slide
      - next_steps_slide
```

This helps the agent classify the task before writing.

---

# 4. `deck_types/`

Each deck type should have its own playbook.

Example:

```txt
deck_types/
  investor_pitch.yaml
  sales_deck.yaml
  product_deck.yaml
  board_deck.yaml
  strategy_deck.yaml
```

Example `investor_pitch.yaml`:

```yaml
id: investor_pitch
name: Investor Pitch Deck

primary_goal:
  - "Create belief in the company’s opportunity."
  - "Make the investor want a meeting or follow-up."
  - "Explain why now, why this team, and why this market."

required_inputs:
  - company_name
  - product_description
  - target_customer
  - problem
  - solution
  - market
  - traction
  - business_model
  - fundraising_ask

recommended_structure:
  - slide_type: title_slide
    purpose: "Orient the reader."
  - slide_type: problem_slide
    purpose: "Make the pain obvious and important."
  - slide_type: solution_slide
    purpose: "Show how the company solves the pain."
  - slide_type: market_slide
    purpose: "Show the scale of the opportunity."
  - slide_type: traction_slide
    purpose: "Prove momentum."
  - slide_type: team_slide
    purpose: "Show why this team can win."
  - slide_type: ask_slide
    purpose: "Clarify the fundraising request."

common_failures:
  - "Too much product detail before establishing the problem."
  - "Market slide uses vague top-down numbers without relevance."
  - "Traction slide lists metrics without interpretation."
  - "Ask slide does not explain use of funds."

quality_bar:
  narrative:
    - "The deck should feel like one argument, not separate slides."
    - "Every slide should move the investor toward conviction."
  writing:
    - "Headlines should be claims, not labels."
    - "Bullets should be specific and evidence-backed."
  design:
    - "Each slide should have one primary message."
```

This is one of the files the LLM should retrieve after classifying the deck.

---

# 5. `slide_archetypes/`

This is the core of the system.

Every slide type should have a structured YAML file that tells the LLM:

1. When to use this slide.
2. What inputs it needs.
3. What the slide should communicate.
4. What layout patterns work.
5. What mistakes to avoid.
6. How to judge quality.
7. What JSON output should look like.

Example structure:

```txt
slide_archetypes/
  problem_slide.yaml
  solution_slide.yaml
  market_slide.yaml
  traction_slide.yaml
  competitive_landscape_slide.yaml
  team_slide.yaml
  ask_slide.yaml
```

Example `problem_slide.yaml`:

```yaml
id: problem_slide
name: Problem Slide

purpose:
  primary: "Make the audience understand and care about the problem."
  secondary: "Create urgency for the solution."

use_when:
  - "The deck needs to establish pain before introducing the product."
  - "The audience may not fully understand the customer’s current struggle."
  - "The user is building an investor, sales, or product deck."

do_not_use_when:
  - "The deck is only an internal status update."
  - "The problem has already been established in a previous slide."

required_inputs:
  - target_customer
  - current_pain
  - consequence_of_pain
  - evidence

optional_inputs:
  - market_data
  - customer_quote
  - workflow_example
  - before_after_comparison

recommended_structure:
  headline:
    rule: "State the problem as a clear business claim."
    examples:
      - "Finance teams still lose days reconciling fragmented payment data."
      - "Sales leaders cannot see pipeline risk until it is too late."

  body:
    preferred_patterns:
      - "Three pain points"
      - "Before/after workflow"
      - "Cost of inaction"
      - "Customer quote plus evidence"

  visual:
    preferred_layouts:
      - "three_column_pain_points"
      - "workflow_breakdown"
      - "metric_plus_explanation"

copy_rules:
  - "Avoid generic statements like 'X is broken'."
  - "Name the customer."
  - "Explain the consequence."
  - "Use evidence where available."

visual_rules:
  - "Do not overload with more than three primary pain points."
  - "Use contrast to separate current state from desired state."
  - "Keep the headline as the main argument."

common_failures:
  - "Problem is too vague."
  - "Problem describes the product gap rather than customer pain."
  - "Slide has no evidence."
  - "Too many pain points with no hierarchy."

quality_rubric:
  excellent:
    - "The problem is specific, urgent, and audience-relevant."
    - "The consequence of the problem is clear."
    - "The slide naturally creates demand for the solution."
  weak:
    - "The problem could apply to any company."
    - "The slide lists issues but does not explain why they matter."

output_contract:
  slide_type: "problem_slide"
  required_fields:
    - headline
    - main_message
    - content_blocks
    - speaker_notes
    - layout_recommendation
```

This gives the LLM a repeatable, product-specific way to create a slide.

---

# 6. `narrative/`

The LLM should not only generate individual slides. It needs to understand the **story arc**.

Example:

```txt
narrative/
  investor_pitch_flow.yaml
  sales_narrative_flow.yaml
  strategy_deck_flow.yaml
  before_after_bridge.yaml
  problem_solution_impact.yaml
```

Example:

```yaml
id: problem_solution_impact
name: Problem → Solution → Impact

sequence:
  - stage: "establish_problem"
    goal: "Make the pain real and costly."
    slide_archetypes:
      - problem_slide
      - customer_pain_slide
      - cost_of_inaction_slide

  - stage: "introduce_solution"
    goal: "Show the new way forward."
    slide_archetypes:
      - solution_slide
      - product_slide
      - demo_slide

  - stage: "prove_impact"
    goal: "Show why the solution matters."
    slide_archetypes:
      - traction_slide
      - roi_slide
      - case_study_slide

rules:
  - "Do not introduce detailed product features before the audience understands the problem."
  - "Do not present impact claims without evidence."
  - "Each stage should make the next stage feel necessary."
```

This is what guides the **deck outline builder**.

---

# 7. `visual_language/`

This helps the LLM make layout and design decisions.

```txt
visual_language/
  layout_principles.yaml
  hierarchy_rules.yaml
  spacing_rules.yaml
  chart_rules.yaml
  image_usage_rules.yaml
  typography_rules.yaml
  color_rules.yaml
  iconography_rules.yaml
```

Example:

```yaml
layout_principles:
  one_message_per_slide:
    rule: "Each slide should communicate one dominant message."
    validation:
      - "There is one clear headline."
      - "The layout supports the headline."
      - "Secondary content does not compete with the main point."

  hierarchy:
    rule: "The viewer should understand the slide in under five seconds."
    guidance:
      - "Use headline as the main claim."
      - "Use visual emphasis for the most important data."
      - "Group related elements."

  density:
    rule: "Avoid excessive text density."
    max_recommended_blocks: 4
    max_recommended_bullets_per_block: 3
```

This should be used by the `layout_director` node.

---

# 8. `writing/`

The LLM needs guidance for copy style.

```txt
writing/
  executive_tone.yaml
  investor_tone.yaml
  sales_tone.yaml
  concise_copy_rules.yaml
  headline_patterns.yaml
  anti_patterns.yaml
```

Example:

```yaml
headline_patterns:
  claim_headline:
    description: "A headline that makes a specific argument."
    examples:
      - "Manual reconciliation is costing finance teams days every month."
      - "Our platform reduces onboarding time from weeks to hours."

  contrast_headline:
    description: "Shows a before/after or old/new contrast."
    examples:
      - "From fragmented workflows to one operating system."
      - "What used to take three tools now happens in one place."

avoid:
  - "Overview"
  - "Our Solution"
  - "Market Opportunity"
  - "Key Benefits"
```

This prevents generic slide titles.

---

# 9. `rubrics/`

Rubrics are used by the critic and repair nodes.

```txt
rubrics/
  deck_quality_rubric.yaml
  slide_quality_rubric.yaml
  narrative_quality_rubric.yaml
  layout_quality_rubric.yaml
  investor_readiness_rubric.yaml
```

Example:

```yaml
id: slide_quality_rubric

criteria:
  clarity:
    weight: 0.25
    checks:
      - "The slide has one main message."
      - "The headline is understandable without presenter explanation."

  specificity:
    weight: 0.20
    checks:
      - "Claims are specific."
      - "Vague words are minimized."

  evidence:
    weight: 0.20
    checks:
      - "Important claims are supported by facts, examples, or user-provided information."
      - "The model does not invent unsupported numbers."

  visual_structure:
    weight: 0.20
    checks:
      - "The layout matches the slide purpose."
      - "The visual hierarchy is clear."

  narrative_fit:
    weight: 0.15
    checks:
      - "The slide fits the deck sequence."
      - "It advances the story instead of repeating earlier content."

score_bands:
  excellent: "0.85-1.00"
  acceptable: "0.70-0.84"
  weak: "0.50-0.69"
  failed: "0.00-0.49"
```

The LLM should critique against rubrics before finalizing.

---

# 10. `examples/`

Examples should be structured, not just pasted decks.

```txt
examples/
  investor_pitch/
    good_problem_slide.yaml
    weak_problem_slide.yaml
    good_traction_slide.yaml

  sales_deck/
    good_roi_slide.yaml
    good_case_study_slide.yaml
```

Example:

```yaml
id: good_problem_slide_b2b_saas
deck_type: investor_pitch
slide_archetype: problem_slide

input_context:
  company: "B2B SaaS finance automation company"
  customer: "mid-market finance teams"
  problem: "manual reconciliation across payment systems"

good_output:
  headline: "Finance teams still lose days reconciling fragmented payment data."

  content_blocks:
    - title: "Data lives in too many systems"
      body: "Payments, invoices, refunds, and bank records are rarely synchronized."

    - title: "Manual checks create delays"
      body: "Teams spend hours comparing exports instead of closing books."

    - title: "Errors compound as volume grows"
      body: "More transactions mean more exceptions, rework, and audit risk."

why_it_works:
  - "The customer is specific."
  - "The pain is operational and measurable."
  - "The problem naturally leads to an automation solution."
```

Use examples for retrieval, not as rigid templates.

---

# 11. `retrieval/`

This controls what knowledge is retrieved at each stage.

```txt
retrieval/
  routing_rules.yaml
  chunking_rules.yaml
  embedding_manifest.yaml
  search_boosts.yaml
```

Example `routing_rules.yaml`:

```yaml
routing_rules:
  classify_deck:
    retrieve:
      - "taxonomy/deck_types.yaml"
      - "taxonomy/communication_goals.yaml"

  build_outline:
    retrieve:
      - "deck_types/{deck_type}.yaml"
      - "narrative/{narrative_pattern}.yaml"
      - "taxonomy/slide_archetypes.yaml"

  plan_slide:
    retrieve:
      - "slide_archetypes/{slide_type}.yaml"
      - "visual_language/layout_principles.yaml"
      - "writing/headline_patterns.yaml"

  write_slide:
    retrieve:
      - "slide_archetypes/{slide_type}.yaml"
      - "writing/{tone}.yaml"
      - "examples/{deck_type}/"

  critique_slide:
    retrieve:
      - "rubrics/slide_quality_rubric.yaml"
      - "slide_archetypes/{slide_type}.yaml"

  critique_deck:
    retrieve:
      - "rubrics/deck_quality_rubric.yaml"
      - "rubrics/narrative_quality_rubric.yaml"
      - "deck_types/{deck_type}.yaml"
```

This is very important. It keeps the LLM from receiving too much irrelevant context.

---

# 12. `constraints/`

This folder protects quality and safety.

```txt
constraints/
  hallucination_constraints.yaml
  data_integrity_constraints.yaml
  brand_constraints.yaml
  export_constraints.yaml
```

Example:

```yaml
hallucination_constraints:
  rules:
    - "Do not invent revenue, growth, customer names, market size, funding, or usage metrics."
    - "If a number is missing, ask for it or mark it as unknown."
    - "Clearly distinguish user-provided facts from inferred recommendations."

data_integrity:
  protected_fields:
    - revenue
    - customer_count
    - fundraising_amount
    - market_size
    - valuation
    - growth_rate

  allowed_transformations:
    - "summarize"
    - "rephrase"
    - "convert to percentage if source data supports it"
    - "group related facts"

  forbidden_transformations:
    - "invent missing data"
    - "exaggerate traction"
    - "claim customer proof without source"
```

This is especially important for investor decks.

---

# 13. Agent flow in the backend

Your LLM should not just receive: “make me a deck.”

It should run through a controlled pipeline.

```txt
User request
   ↓
Brief normalizer
   ↓
Deck classifier
   ↓
Knowledge router
   ↓
Deck strategist
   ↓
Outline builder
   ↓
Slide planner
   ↓
Slide writer
   ↓
Layout director
   ↓
Critic
   ↓
Repair
   ↓
Validation
   ↓
Deck save/export
   ↓
Telemetry + feedback memory
```

In code, your agent state may look like this:

```python
class DeckAgentState(BaseModel):
    request_id: str
    user_id: str
    deck_id: str | None = None

    raw_user_request: str
    normalized_brief: DeckBrief | None = None

    deck_type: str | None = None
    audience: str | None = None
    goal: str | None = None
    tone: str | None = None

    retrieved_knowledge: list[KnowledgeChunk] = []
    deck_plan: DeckPlan | None = None
    slide_plans: list[SlidePlan] = []

    generated_slides: list[SlideContent] = []
    layout_decisions: list[LayoutDecision] = []

    critiques: list[Critique] = []
    repair_actions: list[RepairAction] = []

    validation_results: list[ValidationResult] = []
    final_deck_id: str | None = None
```

---

# 14. Backend services

Your backend should separate **agent orchestration** from **business services**.

```txt
services/
  llm_provider_service.py
  knowledge_retrieval_service.py
  deck_generation_service.py
  deck_validation_service.py
  deck_export_service.py
  memory_service.py
  feedback_service.py
  agent_telemetry_service.py
```

## `knowledge_retrieval_service.py`

Responsible for:

```txt
- Loading YAML/Markdown knowledge files
- Chunking knowledge
- Creating embeddings
- Searching relevant knowledge
- Applying retrieval routing rules
- Returning source-linked knowledge chunks
```

## `deck_generation_service.py`

Responsible for:

```txt
- Starting an agent run
- Passing user brief into the agent
- Managing deck generation lifecycle
- Saving generated slides
- Returning progress/status
```

## `deck_validation_service.py`

Responsible for:

```txt
- Checking JSON schema compliance
- Checking deck completeness
- Checking slide quality
- Checking hallucination risks
- Checking layout constraints
```

## `agent_telemetry_service.py`

Responsible for:

```txt
- Agent run started
- Node completed
- Retrieval performed
- LLM call made
- Validation failed
- Repair attempted
- User accepted/rejected output
```

Since the LLM will become more autonomous, telemetry should be treated as a core system, not a nice-to-have.

---

# 15. Database tables you likely need

The knowledge base folder contains static/versioned product intelligence, but runtime data should live in the database.

A practical schema:

```txt
users
decks
deck_versions
slides
slide_versions
agent_runs
agent_events
llm_provider_calls
knowledge_documents
knowledge_chunks
knowledge_embeddings
deck_feedback
slide_feedback
validation_results
user_memory
organization_memory
```

Important distinction:

| Belongs in repo folder | Belongs in database/vector store |
| ---------------------- | -------------------------------- |
| Slide archetypes       | Embedded chunks                  |
| Deck type playbooks    | User decks                       |
| Narrative rules        | Agent runs                       |
| Rubrics                | Telemetry                        |
| Prompt templates       | Feedback                         |
| Retrieval policies     | User preferences                 |
| Validation schemas     | Long-term memory                 |
| Static examples        | Deck-specific context            |

Do **not** store all knowledge only in the vector database. Keep the source of truth as files in the repo, then index those files into the vector store.

---

# 16. Prompt folder

The prompt folder should be separate from the knowledge base.

```txt
agents/
  deck_builder/
    prompts/
      system/
        deck_builder_system.md
        critic_system.md
        layout_system.md

      tasks/
        classify_deck.md
        create_outline.md
        write_slide.md
        improve_slide.md
        critique_deck.md
```

The prompts should tell the model **how to behave**.

The knowledge base should tell the model **what good deck-building means**.

Example system prompt:

```md
You are the deck-building agent for ddeck.

Your job is to help users create, improve, and critique professional slide decks.

You must:
- Use retrieved knowledge before making deck-structure decisions.
- Follow the deck type playbook.
- Use valid slide archetypes only.
- Preserve user-provided facts.
- Never invent metrics, customers, revenue, fundraising details, or market numbers.
- Return outputs using the required JSON schema.
- Critique and repair your work before finalizing.
```

---

# 17. Schemas are mandatory

Every major LLM output should use a schema.

```txt
schemas/
  deck_brief.schema.json
  deck_plan.schema.json
  slide_plan.schema.json
  slide_content.schema.json
  layout_decision.schema.json
  critique.schema.json
  repair_action.schema.json
```

Example `slide_content.schema.json`:

```json
{
  "type": "object",
  "required": [
    "slide_type",
    "headline",
    "main_message",
    "content_blocks",
    "layout_recommendation",
    "speaker_notes"
  ],
  "properties": {
    "slide_type": {
      "type": "string"
    },
    "headline": {
      "type": "string"
    },
    "main_message": {
      "type": "string"
    },
    "content_blocks": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["title", "body"],
        "properties": {
          "title": {
            "type": "string"
          },
          "body": {
            "type": "string"
          }
        }
      }
    },
    "layout_recommendation": {
      "type": "object",
      "required": ["layout_type", "rationale"],
      "properties": {
        "layout_type": {
          "type": "string"
        },
        "rationale": {
          "type": "string"
        }
      }
    },
    "speaker_notes": {
      "type": "string"
    }
  }
}
```

This prevents the LLM from giving you pretty text that the backend cannot reliably render.

---

# 18. The actual generation loop

A good deck-generation flow should look like this internally:

```python
async def generate_deck(request: GenerateDeckRequest) -> DeckResult:
    state = await brief_normalizer.run(request)

    state = await deck_classifier.run(state)

    state.retrieved_knowledge = await knowledge_router.retrieve(
        task="build_outline",
        deck_type=state.deck_type,
        audience=state.audience,
        goal=state.goal,
    )

    state = await deck_strategist.run(state)

    state = await outline_builder.run(state)

    for slide_plan in state.slide_plans:
        slide_knowledge = await knowledge_router.retrieve(
            task="write_slide",
            deck_type=state.deck_type,
            slide_type=slide_plan.slide_type,
            tone=state.tone,
        )

        slide = await slide_writer.run(
            state=state,
            slide_plan=slide_plan,
            knowledge=slide_knowledge,
        )

        layout = await layout_director.run(
            slide=slide,
            deck_context=state.deck_plan,
        )

        critique = await critic.run(
            slide=slide,
            layout=layout,
            rubric="slide_quality_rubric",
        )

        if critique.requires_repair:
            slide = await repair.run(
                slide=slide,
                critique=critique,
            )

        state.generated_slides.append(slide)

    deck_critique = await critic.run_deck_review(state)

    if deck_critique.requires_repair:
        state = await repair.run_deck_repair(state, deck_critique)

    validation = await deck_validation_service.validate(state)

    final_deck = await deck_repository.save_generated_deck(state)

    await agent_telemetry_service.record_completed_run(state)

    return DeckResult(deck_id=final_deck.id)
```

This creates a controlled, observable agent instead of a black-box prompt.

---

# 19. API routes

You probably want endpoints like this:

```txt
POST   /api/v1/deck-agent/generate
POST   /api/v1/deck-agent/improve
POST   /api/v1/deck-agent/critique
POST   /api/v1/deck-agent/continue
GET    /api/v1/deck-agent/runs/{run_id}
GET    /api/v1/deck-agent/runs/{run_id}/events

POST   /api/v1/decks/{deck_id}/slides
PATCH  /api/v1/decks/{deck_id}/slides/{slide_id}
POST   /api/v1/decks/{deck_id}/export

POST   /api/v1/knowledge/reindex
GET    /api/v1/knowledge/status
POST   /api/v1/feedback/deck
POST   /api/v1/feedback/slide
```

For long deck generation, avoid making the frontend wait on a single request. Use a job/worker model:

```txt
Frontend starts generation
   ↓
Backend creates agent_run
   ↓
Worker processes deck
   ↓
Frontend streams or polls progress
   ↓
Generated deck appears when ready
```

---

# 20. What the LLM should retrieve at each step

| Agent step       | Knowledge needed                              |
| ---------------- | --------------------------------------------- |
| Brief normalizer | Communication goals, deck types               |
| Deck classifier  | Deck type taxonomy                            |
| Deck strategist  | Deck type playbook, audience rules            |
| Outline builder  | Narrative patterns, slide sequences           |
| Slide planner    | Slide archetype definitions                   |
| Slide writer     | Slide archetype, writing rules, examples      |
| Layout director  | Layout rules, visual language, chart rules    |
| Critic           | Rubrics, constraints                          |
| Repair           | Rubric failure reasons, slide archetype rules |
| Finalizer        | Export constraints, deck quality rubric       |

This prevents context overload.

---

# 21. Naming convention for knowledge files

Use predictable IDs.

Good:

```txt
problem_slide.yaml
investor_pitch.yaml
deck_quality_rubric.yaml
problem_solution_impact.yaml
```

Avoid:

```txt
deck ideas.md
good stuff.md
prompt 7 final final.md
new logic.md
```

Each knowledge file should include:

```yaml
id:
name:
description:
applies_to:
inputs:
rules:
examples:
common_failures:
quality_checks:
output_contract:
```

---

# 22. Minimal version to build first

The first production-ready version does not need hundreds of files.

Start with this:

```txt
knowledge_base/
  deck/
    manifest.yaml

    taxonomy/
      deck_types.yaml
      slide_archetypes.yaml

    deck_types/
      investor_pitch.yaml
      sales_deck.yaml
      product_deck.yaml

    slide_archetypes/
      title_slide.yaml
      problem_slide.yaml
      solution_slide.yaml
      market_slide.yaml
      traction_slide.yaml
      business_model_slide.yaml
      team_slide.yaml
      ask_slide.yaml

    narrative/
      investor_pitch_flow.yaml
      sales_narrative_flow.yaml

    visual_language/
      layout_principles.yaml
      chart_rules.yaml

    writing/
      headline_patterns.yaml
      concise_copy_rules.yaml

    rubrics/
      deck_quality_rubric.yaml
      slide_quality_rubric.yaml

    constraints/
      hallucination_constraints.yaml
      data_integrity_constraints.yaml
```

Then add examples and more slide archetypes over time.

---

# 23. How this connects to the frontend

The frontend should not need to know all this complexity.

Frontend sends:

```json
{
  "user_request": "Create an investor deck for my AI finance automation startup",
  "company_context": {
    "name": "Acme AI",
    "customer": "mid-market finance teams",
    "problem": "manual reconciliation",
    "solution": "AI-powered reconciliation workflow"
  },
  "deck_preferences": {
    "tone": "confident and concise",
    "slide_count": 10
  }
}
```

Backend returns:

```json
{
  "run_id": "run_123",
  "status": "processing",
  "deck_id": null
}
```

Then frontend polls or streams:

```json
{
  "run_id": "run_123",
  "status": "completed",
  "deck_id": "deck_456",
  "summary": {
    "deck_type": "investor_pitch",
    "slides_created": 10,
    "quality_score": 0.86
  }
}
```

The frontend should receive finished deck data like:

```json
{
  "deck_id": "deck_456",
  "slides": [
    {
      "slide_id": "slide_1",
      "slide_type": "problem_slide",
      "headline": "Finance teams still lose days reconciling fragmented payment data.",
      "blocks": [],
      "layout": {
        "type": "three_column_pain_points"
      }
    }
  ]
}
```

---

# 24. The key design principle

The LLM should not be the product brain by itself.

The product brain should be:

```txt
Knowledge base
+ retrieval rules
+ schemas
+ validators
+ rubrics
+ telemetry
+ feedback memory
+ LLM reasoning
```

The LLM is the reasoning engine.
The backend knowledge folder is the operating manual.
The schemas are the contract.
The validators are the guardrails.
The telemetry is how you improve the system.

---

# 25. Best practical structure for ddeck

For your ddeck backend, I would organize it like this:

```txt
backend/
  app/
    agents/
      deck_builder/
        graph.py
        state.py
        nodes/
        tools/
        prompts/
        schemas/
        policies/
        evaluators/

    knowledge_base/
      deck/
        manifest.yaml
        taxonomy/
        deck_types/
        slide_archetypes/
        narrative/
        visual_language/
        writing/
        examples/
        rubrics/
        retrieval/
        constraints/

    services/
      knowledge_retrieval_service.py
      deck_generation_service.py
      deck_validation_service.py
      deck_export_service.py
      memory_service.py
      feedback_service.py
      agent_telemetry_service.py

    models/
    repositories/
    workers/
    db/
```

That gives you a backend where the LLM can:

1. Understand the user’s deck goal.
2. Classify the deck type.
3. Retrieve the right deck-building knowledge.
4. Build a narrative outline.
5. Generate slide plans.
6. Write slide content.
7. Recommend layouts.
8. Critique itself.
9. Repair weak outputs.
10. Save the final deck.
11. Learn from feedback without corrupting the core knowledge base.

For the actual ddeck product, the most important first folders are:

```txt
knowledge_base/deck/deck_types/
knowledge_base/deck/slide_archetypes/
knowledge_base/deck/narrative/
knowledge_base/deck/rubrics/
knowledge_base/deck/constraints/
agents/deck_builder/schemas/
agents/deck_builder/nodes/
services/knowledge_retrieval_service.py
services/deck_generation_service.py
```

Those are the pieces that will make the LLM feel like it understands deck building instead of just generating generic slides.
You’re right. A folder that only has `slug`, `title`, `tags`, and maybe a short description is **not an LLM knowledge base**. That is only a catalogue.

For the Smart Deck and Smart Edits pages, the LLM needs something much closer to a **deck operating manual**: structured, validated, explicit, and rich enough that the backend can use it to generate, critique, rewrite, sequence, and validate decks.

# What an excellent LLM deck knowledge base should be

An excellent knowledge base should answer these questions for the LLM:

```text
What kind of deck is this?
Who is the audience?
What decision is the deck trying to create?
Which slides are needed?
What is each slide responsible for?
What evidence is required?
What should the slide never claim without proof?
What does a strong version look like?
What does a weak version look like?
How should the slide be rewritten?
How should the backend validate the result?
How should the frontend render/edit the result?
```

So the knowledge base should not be:

```json
{
  "slug": "problem",
  "tags": ["startup", "pitch"]
}
```

It should be closer to:

```json
{
  "id": "startup_pitch.problem.v1",
  "archetype": "problem",
  "deck_families": ["startup_pitch"],
  "narrative_role": "Makes the pain obvious, urgent, and economically meaningful before the solution appears.",
  "required_inputs": ["target_customer", "pain_point", "current_alternative", "cost_of_inaction"],
  "evidence_rules": "...",
  "generation_rules": "...",
  "critique_rules": "...",
  "rewrite_rules": "...",
  "output_schema": "...",
  "quality_rubric": "...",
  "examples": "..."
}
```

The important distinction:

```text
Slug/tags help humans find a file.
A real LLM knowledge base teaches the model how to think, decide, generate, and critique.
```

---

# 1. The knowledge base needs multiple layers

A strong structure should look like this:

```text
backend/
  llm_knowledge/
    deck_knowledge_base/
      manifest.json

      taxonomy/
        deck_families.json
        audiences.json
        company_stages.json
        fund_stages.json
        sectors.json
        tone_profiles.json
        evidence_types.json

      deck_recipes/
        startup_pitch.json
        pre_seed_pitch.json
        seed_pitch.json
        series_a_pitch.json
        vc_fund_pitch.json
        investor_update.json
        sales_deck.json
        product_launch_deck.json

      archetypes/
        problem.json
        solution.json
        product.json
        market.json
        traction.json
        business_model.json
        competition.json
        team.json
        ask.json
        use_of_funds.json
        fund_thesis.json
        portfolio_construction.json
        lp_terms.json

      diagnostics/
        startup_pitch_diagnostics.json
        vc_fund_diagnostics.json
        smart_edits_rules.json
        hallucination_rules.json
        missing_evidence_rules.json

      generation/
        slide_output_contracts.json
        layout_guidance.json
        visual_patterns.json
        speaker_notes_rules.json

      examples/
        startup_pitch/
          problem.strong.json
          problem.weak.json
          traction.strong.json
          traction.weak.json

      evals/
        startup_pitch_eval_cases.json
        smart_edits_eval_cases.json
```

That is much better than one folder of basic Markdown files.

---

# 2. Core components

## A. `manifest.json`

This tells the backend what version of the knowledge base is loaded.

```json
{
  "knowledge_base_id": "deck_knowledge_base",
  "version": "1.0.0",
  "description": "Central LLM knowledge base for Smart Deck and Smart Edits.",
  "default_language": "en",
  "supported_deck_families": [
    "startup_pitch",
    "vc_fund_pitch",
    "investor_update",
    "sales_deck"
  ],
  "entrypoints": {
    "deck_recipes": "deck_recipes/",
    "archetypes": "archetypes/",
    "diagnostics": "diagnostics/",
    "generation_contracts": "generation/"
  }
}
```

This matters because the backend should know exactly what it is loading.

---

## B. Deck family taxonomy

The LLM must know the difference between deck types.

A **startup pitch deck** is not the same as a **fundraising deck for a VC fund**, an **investor update**, or a **sales deck**.

Example:

```json
{
  "id": "startup_pitch",
  "name": "Startup Pitch Deck",
  "primary_audience": ["angel_investors", "seed_investors", "venture_capitalists"],
  "primary_goal": "Convince investors that the company is a venture-scale opportunity worth a meeting, diligence, or investment.",
  "common_decision": "Should the investor take the next meeting or invest?",
  "typical_sections": [
    "problem",
    "solution",
    "product",
    "market",
    "traction",
    "business_model",
    "competition",
    "team",
    "ask"
  ],
  "must_not_do": [
    "Overstate traction without proof",
    "Use generic market claims without segmentation",
    "Describe features before explaining pain",
    "Confuse customer problem with founder inconvenience"
  ]
}
```

For a VC fund deck:

```json
{
  "id": "vc_fund_pitch",
  "name": "VC Fund Pitch Deck",
  "primary_audience": ["limited_partners", "family_offices", "fund_of_funds"],
  "primary_goal": "Convince LPs that the fund has a differentiated strategy, credible access, disciplined construction, and return potential.",
  "typical_sections": [
    "fund_thesis",
    "market_opportunity",
    "track_record",
    "sourcing_advantage",
    "portfolio_construction",
    "team",
    "terms",
    "lp_ask"
  ],
  "must_not_do": [
    "Sound like a startup pitch deck",
    "Claim proprietary deal flow without evidence",
    "Show returns without explaining attribution",
    "Avoid portfolio construction details"
  ]
}
```

This is necessary because Smart Deck needs to know what kind of deck it is building.

---

# 3. Deck recipes

A deck recipe defines the **recommended sequence**.

This is what Smart Deck should use when generating an outline.

Example:

```json
{
  "id": "startup_pitch.pre_seed.v1",
  "deck_family": "startup_pitch",
  "stage": "pre_seed",
  "audience": "seed_investors",
  "recommended_length": {
    "min_slides": 8,
    "max_slides": 12
  },
  "sequence": [
    {
      "position": 1,
      "archetype": "cover",
      "purpose": "Establish company identity and one-line promise."
    },
    {
      "position": 2,
      "archetype": "problem",
      "purpose": "Make the pain clear and urgent."
    },
    {
      "position": 3,
      "archetype": "solution",
      "purpose": "Show the company’s answer to the problem."
    },
    {
      "position": 4,
      "archetype": "product",
      "purpose": "Demonstrate how the solution works."
    },
    {
      "position": 5,
      "archetype": "market",
      "purpose": "Show the opportunity is large and reachable."
    },
    {
      "position": 6,
      "archetype": "traction",
      "purpose": "Show proof of demand, even if early."
    },
    {
      "position": 7,
      "archetype": "business_model",
      "purpose": "Explain how the company captures value."
    },
    {
      "position": 8,
      "archetype": "competition",
      "purpose": "Show why this company can win."
    },
    {
      "position": 9,
      "archetype": "team",
      "purpose": "Explain why this team is credible."
    },
    {
      "position": 10,
      "archetype": "ask",
      "purpose": "Make the fundraising request clear."
    }
  ],
  "conditional_rules": [
    {
      "condition": "no_revenue_or_usage",
      "action": "Do not fabricate traction. Use milestones, pilots, LOIs, waitlist, or learning velocity if provided."
    },
    {
      "condition": "deep_tech_company",
      "action": "Add technical defensibility after product or before competition."
    }
  ]
}
```

This lets the backend generate deck outlines without guessing.

---

# 4. Archetype knowledge

Each archetype needs to be much richer than slug and tags.

A good archetype file should contain:

```text
Identity
Purpose
When to use it
When not to use it
Narrative role
Required inputs
Optional inputs
Evidence hierarchy
Generation rules
Critique rules
Rewrite rules
Visual/layout guidance
Quality rubric
Common mistakes
Weak examples
Strong examples
Output schema
Validation rules
Frontend render hints
```

## Example: `problem.json`

```json
{
  "id": "startup_pitch.problem.v1",
  "slug": "problem",
  "name": "Problem",
  "deck_families": ["startup_pitch"],
  "description": "Explains the customer pain, why it matters now, and why current alternatives are inadequate.",
  "narrative_role": {
    "primary_job": "Create urgency before introducing the solution.",
    "emotional_effect": "The audience should feel that the problem is real, specific, and costly.",
    "business_effect": "The audience should understand why solving this problem can create economic value.",
    "comes_before": ["solution", "product"],
    "comes_after": ["cover"]
  },
  "use_when": [
    "The deck needs to establish a painful customer or market inefficiency.",
    "The solution is not obvious without understanding the current workflow."
  ],
  "do_not_use_when": [
    "The slide is mainly about product features.",
    "The problem is only a vague macro trend with no specific user pain."
  ],
  "required_inputs": [
    {
      "field": "target_customer",
      "description": "The specific user, buyer, or organization experiencing the problem.",
      "required": true
    },
    {
      "field": "pain_point",
      "description": "The painful workflow, unmet need, or costly friction.",
      "required": true
    },
    {
      "field": "current_alternative",
      "description": "What the customer does today instead.",
      "required": false
    },
    {
      "field": "cost_of_inaction",
      "description": "Time, money, risk, churn, inefficiency, or lost revenue caused by the problem.",
      "required": false
    }
  ],
  "evidence_hierarchy": [
    {
      "level": 1,
      "name": "Strong evidence",
      "examples": [
        "Customer interviews",
        "Usage data",
        "Revenue leakage",
        "Time wasted",
        "Compliance risk",
        "Churn or retention data"
      ]
    },
    {
      "level": 2,
      "name": "Moderate evidence",
      "examples": [
        "Industry benchmark",
        "Survey",
        "Public research",
        "Anecdotal customer quotes"
      ]
    },
    {
      "level": 3,
      "name": "Weak evidence",
      "examples": [
        "Generic market trend",
        "Founder opinion",
        "Unverified claim"
      ]
    }
  ],
  "generation_rules": {
    "headline": {
      "goal": "Name the painful current reality in one direct sentence.",
      "patterns": [
        "{target_customer} still rely on {broken_current_alternative}",
        "{target_customer} lose {cost} because {pain_point}",
        "{workflow} remains manual, fragmented, and expensive"
      ],
      "avoid": [
        "Generic statements like 'The market is broken'",
        "Feature language",
        "Overly dramatic claims"
      ]
    },
    "body": {
      "recommended_structure": [
        "Who has the pain",
        "What causes the pain",
        "Why existing alternatives fail",
        "Why the pain matters economically"
      ],
      "max_bullets": 4
    },
    "speaker_notes": {
      "goal": "Explain the pain clearly without pitching the product too early."
    }
  },
  "critique_rules": [
    {
      "rule": "specific_customer_required",
      "description": "Flag the slide if the customer/user is vague.",
      "severity": "high"
    },
    {
      "rule": "cost_or_urgency_needed",
      "description": "Flag the slide if it describes inconvenience but not urgency or cost.",
      "severity": "medium"
    },
    {
      "rule": "solution_too_early",
      "description": "Flag the slide if it sells product features before establishing pain.",
      "severity": "medium"
    }
  ],
  "rewrite_modes": {
    "clearer": {
      "instruction": "Remove vague language and make the customer pain more specific."
    },
    "more_investor_grade": {
      "instruction": "Tie the problem to urgency, market pull, and economic value without exaggeration."
    },
    "shorter": {
      "instruction": "Reduce to one headline and three concise bullets."
    },
    "more_visual": {
      "instruction": "Convert the problem into a workflow, before/after, cost stack, or fragmentation diagram."
    }
  },
  "visual_guidance": [
    {
      "type": "broken_workflow",
      "best_when": "The problem involves fragmented tools or manual process.",
      "description": "Show the current process as disconnected steps, handoffs, or scattered tools."
    },
    {
      "type": "cost_stack",
      "best_when": "The problem has measurable time, money, or risk cost.",
      "description": "Show the accumulated cost of the current approach."
    }
  ],
  "quality_rubric": {
    "score_5": "Specific customer, painful current workflow, credible evidence, clear urgency, no premature product pitch.",
    "score_3": "Problem is understandable but lacks strong evidence or economic urgency.",
    "score_1": "Generic, vague, trend-based, or mostly about the product instead of the pain."
  },
  "common_mistakes": [
    "Starting with a broad market trend instead of a user pain.",
    "Using buzzwords instead of concrete workflow friction.",
    "Claiming the problem is huge without showing who feels it.",
    "Solving the problem on the same slide before the audience understands it."
  ],
  "output_contract": {
    "type": "object",
    "required": [
      "archetype",
      "headline",
      "supporting_points",
      "missing_inputs",
      "quality_warnings",
      "visual_suggestion"
    ],
    "properties": {
      "archetype": { "type": "string" },
      "headline": { "type": "string" },
      "subheadline": { "type": "string" },
      "supporting_points": {
        "type": "array",
        "items": { "type": "string" },
        "maxItems": 4
      },
      "missing_inputs": {
        "type": "array",
        "items": { "type": "string" }
      },
      "quality_warnings": {
        "type": "array",
        "items": { "type": "string" }
      },
      "visual_suggestion": {
        "type": "object",
        "properties": {
          "type": { "type": "string" },
          "description": { "type": "string" }
        }
      }
    }
  },
  "frontend_render_hints": {
    "editable_fields": [
      "headline",
      "subheadline",
      "supporting_points",
      "speaker_notes"
    ],
    "show_missing_inputs_panel": true,
    "show_quality_warnings": true
  }
}
```

That is the level of detail the LLM layer needs.

---

# 5. Smart Deck needs generation knowledge

Smart Deck is not only “generate some text.”

It needs knowledge for:

```text
Deck type selection
Audience selection
Stage-specific sequencing
Slide archetype selection
Missing input detection
Outline generation
Slide generation
Visual recommendation
Speaker notes
JSON validation
```

The knowledge base should include rules like:

```json
{
  "rule_id": "do_not_generate_fake_traction",
  "applies_to": ["traction", "market", "business_model", "ask"],
  "rule": "If traction metrics are missing, do not invent revenue, users, customers, pilots, LOIs, growth rate, retention, or pipeline.",
  "fallback": "Return missing_inputs and suggest acceptable proof types."
}
```

For Smart Deck, every generated slide should include:

```json
{
  "slide_id": "generated-id",
  "archetype": "problem",
  "headline": "...",
  "subheadline": "...",
  "supporting_points": ["...", "..."],
  "visual_suggestion": {
    "type": "...",
    "description": "..."
  },
  "speaker_notes": "...",
  "missing_inputs": [],
  "quality_warnings": [],
  "source_facts_used": ["..."],
  "assumptions": [],
  "confidence": 0.82
}
```

The fields `source_facts_used` and `assumptions` are important. They help prevent the LLM from silently inventing content.

---

# 6. Smart Edits needs diagnostic knowledge

Smart Edits is even more demanding than Smart Deck.

It needs to look at an existing slide and answer:

```text
What archetype is this slide?
Is it doing the job of that archetype?
Is it in the right order?
Is it too vague?
Is it unsupported?
Is it too long?
Is it visually weak?
What exactly should change?
```

So the knowledge base needs diagnostic rules.

Example:

```json
{
  "id": "smart_edits.startup_pitch.problem_diagnostics.v1",
  "target_archetype": "problem",
  "diagnostic_checks": [
    {
      "check_id": "customer_specificity",
      "question": "Does the slide identify a specific customer, user, or buyer?",
      "pass_condition": "A specific segment, role, or organization type is named.",
      "fail_message": "The problem is too broad because the affected customer is unclear.",
      "rewrite_action": "Add a specific customer segment to the headline or first bullet."
    },
    {
      "check_id": "pain_urgency",
      "question": "Does the slide explain why the pain matters now?",
      "pass_condition": "The slide mentions time, money, risk, growth blocker, compliance, churn, or operational urgency.",
      "fail_message": "The slide describes inconvenience but not urgency.",
      "rewrite_action": "Tie the pain to a measurable or strategic cost."
    },
    {
      "check_id": "solution_leakage",
      "question": "Is the slide prematurely pitching the product?",
      "pass_condition": "The slide focuses on the customer pain, not product features.",
      "fail_message": "The slide introduces the solution before the problem is fully established.",
      "rewrite_action": "Move product claims to the solution or product slide."
    }
  ]
}
```

This allows Smart Edits to produce useful critique rather than generic feedback.

Bad Smart Edits output:

```text
Make this clearer and more concise.
```

Good Smart Edits output:

```json
{
  "slide_id": "s2",
  "detected_archetype": "problem",
  "score": 3,
  "issues": [
    {
      "severity": "high",
      "issue": "The target customer is unclear.",
      "why_it_matters": "Investors need to know who feels the pain and who might pay.",
      "suggested_fix": "Name the buyer or user segment in the headline."
    }
  ],
  "rewrite": {
    "headline": "...",
    "supporting_points": ["...", "..."]
  }
}
```

---

# 7. The knowledge base needs evidence rules

This is one of the most important parts.

The LLM must know what it is allowed to claim.

For example:

```json
{
  "claim_type": "traction",
  "requires_evidence": true,
  "allowed_sources": [
    "user_provided_metrics",
    "uploaded_deck_data",
    "CRM_data",
    "analytics_data",
    "manual_user_input"
  ],
  "forbidden_without_evidence": [
    "ARR",
    "MRR",
    "user growth percentage",
    "retention",
    "revenue pipeline",
    "customer logos",
    "signed LOIs",
    "pilot count"
  ],
  "fallback_when_missing": {
    "action": "ask_for_input",
    "missing_inputs": [
      "current revenue",
      "active users",
      "growth rate",
      "customer proof",
      "retention data"
    ]
  }
}
```

Without this layer, the LLM will produce confident nonsense.

A good knowledge base should make the backend enforce:

```text
No evidence → no claim.
Missing facts → ask or mark missing.
Weak proof → use careful wording.
Strong proof → allow stronger slide copy.
```

---

# 8. It needs examples, but examples must be structured

Examples should not be random Markdown paragraphs.

They should be labeled:

```json
{
  "id": "example.problem.strong.001",
  "archetype": "problem",
  "quality": "strong",
  "why_it_works": [
    "Names the customer",
    "Shows the painful workflow",
    "Explains business cost",
    "Does not pitch the solution too early"
  ],
  "input_context": {
    "target_customer": "finance teams at growing SaaS companies",
    "pain_point": "manual revenue reporting across spreadsheets and billing systems",
    "cost_of_inaction": "slow board reporting and poor forecast visibility"
  },
  "slide_output": {
    "headline": "Finance teams still build revenue visibility by hand",
    "supporting_points": [
      "Billing, CRM, and spreadsheet data rarely match without manual cleanup.",
      "Board reporting depends on fragile recurring workflows.",
      "Forecast decisions are delayed because teams do not trust the numbers."
    ]
  }
}
```

Weak examples are useful too:

```json
{
  "id": "example.problem.weak.001",
  "archetype": "problem",
  "quality": "weak",
  "slide_output": {
    "headline": "The market is broken",
    "supporting_points": [
      "Companies need better tools.",
      "AI can solve this.",
      "The opportunity is massive."
    ]
  },
  "why_it_fails": [
    "No specific customer",
    "No concrete pain",
    "No current alternative",
    "Solution appears before problem is explained"
  ]
}
```

This helps the LLM learn what “good” and “bad” mean inside your product.

---

# 9. It needs output contracts, not just prompts

The backend should not accept arbitrary text from the model.

Every endpoint needs a strict response contract.

For example, `generate-slide` should always return:

```json
{
  "status": "ready | needs_context | blocked",
  "archetype": "string",
  "headline": "string",
  "subheadline": "string",
  "supporting_points": ["string"],
  "visual_suggestion": {
    "type": "string",
    "description": "string",
    "data_needed": ["string"]
  },
  "speaker_notes": "string",
  "missing_inputs": ["string"],
  "quality_warnings": ["string"],
  "source_facts_used": ["string"],
  "assumptions": ["string"]
}
```

For `analyze-deck`, the contract should be different:

```json
{
  "deck_type": "startup_pitch",
  "overall_score": 0,
  "slide_diagnostics": [],
  "missing_archetypes": [],
  "sequence_issues": [],
  "evidence_gaps": [],
  "recommended_next_actions": []
}
```

For `rewrite-slide`:

```json
{
  "status": "ready | needs_context",
  "original_slide_id": "string",
  "detected_archetype": "string",
  "rewrite_mode": "string",
  "before_summary": "string",
  "after": {
    "headline": "string",
    "subheadline": "string",
    "supporting_points": ["string"],
    "speaker_notes": "string",
    "visual_suggestion": {}
  },
  "changes_made": [],
  "risks_remaining": [],
  "missing_inputs": []
}
```

This is what makes the LLM usable inside software.

---

# 10. It needs a graph, not just a list

Deck knowledge is sequential.

A problem slide leads to a solution slide.
A solution slide leads to product.
Traction should usually appear before ask.
Competition should not appear before the audience understands the product.

So the knowledge base needs a graph:

```json
{
  "archetype_graph": {
    "problem": {
      "usually_before": ["solution", "product"],
      "usually_after": ["cover"],
      "depends_on": [],
      "bad_if_missing_before": []
    },
    "solution": {
      "usually_before": ["product", "market"],
      "usually_after": ["problem"],
      "depends_on": ["problem"],
      "bad_if_missing_before": ["problem"]
    },
    "traction": {
      "usually_before": ["business_model", "ask"],
      "usually_after": ["product", "market"],
      "depends_on": ["evidence"]
    },
    "ask": {
      "usually_before": [],
      "usually_after": ["team", "traction", "business_model"],
      "depends_on": ["fundraising_amount", "use_of_funds"]
    }
  }
}
```

Smart Deck uses this to generate a good order.

Smart Edits uses this to detect bad order.

---

# 11. It needs audience and stage modifiers

A pre-seed pitch is not a Series A pitch.

The knowledge base should include modifiers like:

```json
{
  "stage": "pre_seed",
  "investor_expectations": [
    "Clear problem",
    "Founder-market fit",
    "Early product insight",
    "Early validation",
    "Large market potential"
  ],
  "traction_expectation": "Can be qualitative or early quantitative proof.",
  "avoid": [
    "Over-modeling financial projections",
    "Pretending early pilots are repeatable enterprise traction"
  ]
}
```

For Series A:

```json
{
  "stage": "series_a",
  "investor_expectations": [
    "Repeatable growth motion",
    "Clear ICP",
    "Revenue quality",
    "Retention",
    "Sales efficiency",
    "Scalable go-to-market"
  ],
  "traction_expectation": "Must include credible metrics.",
  "avoid": [
    "Only showing anecdotes",
    "Vague market sizing",
    "No cohort or retention evidence"
  ]
}
```

This makes the same archetype behave differently depending on context.

A traction slide for pre-seed:

```text
Show early signal.
```

A traction slide for Series A:

```text
Show repeatable growth quality.
```

The knowledge base should encode that difference.

---

# 12. It needs visual intelligence

For decks, words are not enough.

Each archetype should define visual patterns.

Example:

```json
{
  "archetype": "market",
  "visual_patterns": [
    {
      "type": "tam_sam_som",
      "best_when": "The market can be segmented from broad to reachable.",
      "required_data": ["TAM", "SAM", "SOM"],
      "risk": "Often weak if numbers are generic or sourced poorly."
    },
    {
      "type": "wedge_expansion",
      "best_when": "The company starts in a narrow ICP and expands over time.",
      "required_data": ["initial_segment", "adjacent_segments"],
      "risk": "Must explain why the wedge is credible."
    }
  ]
}
```

For traction:

```json
{
  "archetype": "traction",
  "visual_patterns": [
    {
      "type": "growth_chart",
      "required_data": ["time_period", "metric_name", "metric_values"],
      "best_when": "There is real month-over-month or quarter-over-quarter growth."
    },
    {
      "type": "customer_logo_strip",
      "required_data": ["approved_customer_names"],
      "best_when": "Customer names are allowed and recognizable."
    },
    {
      "type": "milestone_timeline",
      "required_data": ["milestones"],
      "best_when": "Quantitative traction is still early."
    }
  ]
}
```

This lets the backend tell the frontend:

```text
This slide should probably be a before/after diagram.
This one needs a chart.
This one should not be a chart because there is no data.
```

---

# 13. It needs frontend render hints

The LLM knowledge base should also help the app know how to render the result.

For example:

```json
{
  "frontend_render_hints": {
    "preferred_layouts": [
      "headline_with_three_bullets",
      "before_after",
      "workflow_diagram"
    ],
    "editable_fields": [
      "headline",
      "subheadline",
      "supporting_points",
      "speaker_notes"
    ],
    "requires_data_visualization": false,
    "show_missing_inputs_panel": true,
    "show_source_facts": true
  }
}
```

This bridges the LLM output to the Smart Deck UI.

---

# 14. It needs prompt recipes, but prompts should not be the whole knowledge base

A common mistake is to put everything into one giant prompt.

Better structure:

```text
Knowledge base = stable rules, archetypes, examples, schemas
Prompt builder = selects the relevant pieces at runtime
LLM call = receives only the relevant knowledge for the task
```

The prompt builder should assemble:

```text
System rules
Deck family rules
Audience/stage modifiers
Selected archetype knowledge
User/project context
Required output schema
Validation constraints
```

Example runtime prompt ingredients:

```json
{
  "task": "generate_slide",
  "deck_family": "startup_pitch",
  "stage": "pre_seed",
  "audience": "seed_investors",
  "archetype": "problem",
  "knowledge_refs": [
    "deck_recipes/startup_pitch.pre_seed.v1",
    "archetypes/problem",
    "diagnostics/hallucination_rules",
    "generation/slide_output_contracts"
  ],
  "project_context": {},
  "output_contract": "GeneratedSlideResponse"
}
```

This makes the LLM behavior consistent.

---

# 15. It needs validation and scoring

A serious knowledge base should support automatic checks.

Example scoring rubric:

```json
{
  "archetype": "problem",
  "rubric": [
    {
      "criterion": "customer_specificity",
      "weight": 0.25,
      "score_1": "No customer is named.",
      "score_3": "A broad customer category is named.",
      "score_5": "A specific user, buyer, or segment is named."
    },
    {
      "criterion": "pain_clarity",
      "weight": 0.25,
      "score_1": "Pain is vague.",
      "score_3": "Pain is understandable but generic.",
      "score_5": "Pain is concrete, specific, and easy to repeat."
    },
    {
      "criterion": "urgency",
      "weight": 0.25,
      "score_1": "No urgency or cost.",
      "score_3": "Some urgency but weak evidence.",
      "score_5": "Clear cost, risk, inefficiency, or timing pressure."
    },
    {
      "criterion": "focus",
      "weight": 0.25,
      "score_1": "Mostly talks about product.",
      "score_3": "Some problem focus, some solution leakage.",
      "score_5": "Pure problem framing with no premature product pitch."
    }
  ]
}
```

Smart Edits can then say:

```json
{
  "slide_id": "s1",
  "archetype": "problem",
  "score": 3.2,
  "weakest_criteria": ["urgency", "customer_specificity"],
  "recommended_action": "Make the customer and cost of the problem more specific."
}
```

That is much better than vague LLM feedback.

---

# 16. It needs “missing input” logic

The LLM should know when it does not have enough information.

Example:

```json
{
  "archetype": "ask",
  "required_inputs": [
    "fundraising_amount",
    "round_type",
    "runway_target",
    "use_of_funds",
    "milestones_to_reach"
  ],
  "if_missing": {
    "fundraising_amount": {
      "severity": "blocking",
      "message": "Cannot generate a credible ask slide without the fundraising amount."
    },
    "use_of_funds": {
      "severity": "blocking",
      "message": "Cannot explain why the amount is needed without use of funds."
    },
    "milestones_to_reach": {
      "severity": "medium",
      "message": "The ask will be weaker without milestones."
    }
  }
}
```

Then the backend can return:

```json
{
  "status": "needs_context",
  "missing_inputs": [
    "fundraising_amount",
    "use_of_funds",
    "milestones_to_reach"
  ],
  "question_to_user": "How much are you raising, and what milestones should this round achieve?"
}
```

This is essential for professional output.

---

# 17. It needs transformation rules for Smart Edits

Smart Edits should support edit modes.

Examples:

```json
{
  "rewrite_modes": {
    "shorter": {
      "goal": "Reduce length while preserving the main claim.",
      "rules": [
        "Keep one headline",
        "Use no more than three bullets",
        "Remove repeated claims",
        "Do not remove required evidence"
      ]
    },
    "more_investor_grade": {
      "goal": "Make the slide more precise, evidence-aware, and decision-oriented.",
      "rules": [
        "Replace vague benefits with specific outcomes",
        "Reduce hype",
        "Tie claims to proof",
        "Surface missing evidence instead of inventing it"
      ]
    },
    "more_visual": {
      "goal": "Recommend a layout or visual structure instead of adding more text.",
      "rules": [
        "Prefer diagrams, charts, timelines, matrices, or before/after structures",
        "Identify what data is needed for the visual",
        "Do not recommend a chart without data"
      ]
    },
    "less_hype": {
      "goal": "Remove exaggerated language.",
      "rules": [
        "Replace absolute claims with supportable claims",
        "Avoid words like revolutionary, game-changing, massive, inevitable unless proven",
        "Preserve ambition but reduce overclaiming"
      ]
    }
  }
}
```

This makes rewrite buttons predictable.

---

# 18. The knowledge base should support both retrieval and direct loading

There are two use cases:

## Direct loading

For small, critical files:

```text
deck recipe
selected archetype
output contract
hallucination rules
```

The backend should load these directly.

## Retrieval

For larger examples and guidance:

```text
strong examples
weak examples
sector-specific guidance
visual examples
diagnostic examples
```

The backend can retrieve only the relevant chunks.

The compiled structure should therefore include:

```text
compiled_json/
  manifest.json
  recipes.index.json
  archetypes.index.json
  diagnostics.index.json
  examples.index.json

retrieval_chunks/
  problem.examples.jsonl
  traction.examples.jsonl
  market.examples.jsonl
```

A JSONL retrieval chunk might look like:

```json
{
  "chunk_id": "problem.strong_example.001",
  "archetype": "problem",
  "deck_family": "startup_pitch",
  "stage": "pre_seed",
  "content_type": "strong_example",
  "text": "A strong problem slide names the specific customer, explains the broken current workflow, and shows why the pain creates urgency.",
  "metadata": {
    "quality": "strong",
    "use_for": ["generate_slide", "rewrite_slide", "critique_slide"]
  }
}
```

This is useful later if you add embeddings or vector search.

---

# 19. What the backend should load for each endpoint

## `GET /api/llm/deck/archetypes`

Loads:

```text
manifest
archetype summaries
deck family taxonomy
```

Returns a lightweight frontend-safe catalogue.

## `POST /api/llm/deck/outline`

Loads:

```text
deck recipe
deck family rules
stage modifier
audience modifier
sequence graph
missing input rules
```

Returns a recommended deck outline.

## `POST /api/llm/deck/generate-slide`

Loads:

```text
selected archetype
deck recipe context
generation rules
evidence rules
visual rules
output contract
examples
```

Returns one structured slide.

## `POST /api/llm/deck/analyze`

Loads:

```text
deck diagnostics
archetype detection rules
sequence graph
quality rubrics
evidence rules
missing archetype rules
```

Returns a diagnosis.

## `POST /api/llm/deck/rewrite-slide`

Loads:

```text
detected archetype
rewrite mode rules
quality rubric
visual guidance
evidence rules
output contract
```

Returns a proposed edit.

---

# 20. The ideal architecture

The knowledge base should be designed like this:

```text
Human-editable source
  ↓
Validated canonical JSON
  ↓
Compiled indexes
  ↓
Backend loader
  ↓
Prompt builder
  ↓
LLM provider
  ↓
JSON validator
  ↓
Smart Deck / Smart Edits UI
```

So the source files can be Markdown or YAML for humans, but the backend should consume compiled JSON.

Recommended source structure:

```text
source/
  archetypes/problem.md
  archetypes/traction.md
  deck_recipes/startup_pitch.md
  diagnostics/smart_edits.md

compiled/
  archetypes/problem.json
  deck_recipes/startup_pitch.json
  indexes/*.json
```

But the compiled JSON must be rich. Not just extracted headings.

---

# 21. Minimum standard for your product

For your Smart Deck and Smart Edits pages, the minimum serious knowledge base should include:

| Layer                               |    Required |
| ----------------------------------- | ----------: |
| Deck families                       |         Yes |
| Deck recipes                        |         Yes |
| Archetype definitions               |         Yes |
| Sequence graph                      |         Yes |
| Required input rules                |         Yes |
| Evidence / anti-hallucination rules |         Yes |
| Generation rules                    |         Yes |
| Critique rules                      |         Yes |
| Rewrite modes                       |         Yes |
| Visual guidance                     |         Yes |
| Output schemas                      |         Yes |
| Strong/weak examples                |         Yes |
| Quality rubrics                     |         Yes |
| Frontend render hints               |         Yes |
| Versioned manifest                  |         Yes |
| Eval cases                          | Ideally yes |

Without these, the LLM layer will feel generic.

---

# 22. What was wrong with the current version

The current version sounds like it is doing this:

```text
Read files
Extract title
Extract slug
Extract tags
Save JSON
```

That produces a list of files, not a knowledge system.

The correct version should do this:

```text
Define the deck universe
Define deck types
Define archetype jobs
Define sequencing logic
Define required facts
Define what claims are allowed
Define generation rules
Define critique rules
Define rewrite rules
Define output contracts
Define validation
Define examples
Compile everything into backend-usable JSON
```

That is the difference between:

```text
“Here are some slide names”
```

and:

```text
“Here is how a deck expert should reason about this deck.”
```

---

# 23. Target standard

An excellent LLM knowledge base should make the LLM behave like:

```text
A deck strategist
A pitch editor
A narrative architect
A slide critic
A formatting-aware product assistant
A fact-constrained writer
```

not like:

```text
A text generator with a list of slide names
```

The next version should replace the shallow archetype catalogue with a **versioned, schema-validated deck intelligence system**. It should contain enough knowledge for the backend to generate, critique, rewrite, sequence, and validate deck content without relying on vague prompts.

---

# 24. Current implementation status

As of 2026-06-19, the backend has the first operational knowledge-base layer implemented.

Implemented:

* Versioned knowledge manifest at `backend/llm_knowledge/deck_archetype_knowledge/manifest.yaml`.
* Human-editable archetype source in `source_md/`.
* Rich compiled archetype JSON in `compiled_json/archetypes/`.
* Compiled master index at `compiled_json/archetypes.index.json`.
* Knowledge modules for deck types, narrative flows, render schema rules, writing rules, quality rubrics, hallucination constraints, retrieval routing, deck recipes, diagnostics, generation contracts, examples, and eval cases.
* Backend loader in `app/ai/slide_archetypes_context.py`.
* Smart Deck prompt context uses the compiled knowledge modules and archetype contracts.
* Smart Edit context uses the same knowledge layer.
* Render schema analytics can store source facts, assumptions, missing inputs, quality warnings, and confidence.
* Validation script at `backend/scripts/validate_llm_knowledge.py`.
* Admin readiness endpoint at `GET /api/admin/llm-knowledge/health`.
* Runtime `knowledgeMetadata` is persisted into Smart Deck generation context, LLM artifacts, render-schema artifacts, design manifests, and telemetry.
* Smart Edit telemetry records the knowledge version/source used.
* Smart Deck now creates a `smart_deck_generation_plan` artifact before the provider call.
* Smart Deck now creates a `smart_deck_generation_critique` artifact after backend render-schema validation.
* Smart Deck design manifests and telemetry include critique status and warning/missing-input counts.
* Smart Deck now performs one bounded repair provider call when critique status is `review`.
* Smart Deck now validates and critiques repaired output before persistence.
* Smart Deck now creates a `smart_deck_generation_repair` artifact when repair is performed.
* Smart Deck now builds a deterministic `sourceFactPackage` before the provider call.
* Smart Deck now persists `smart_deck_source_facts` artifacts for each generation job.
* Smart Deck critique now checks whether generated `analytics.sourceFactsUsed` entries match approved source facts.
* Smart Deck manifests and telemetry now include source-fact coverage counts.
* Smart Deck render schema analytics now supports `sourceFactIds`.
* Smart Deck provider prompts now require explicit source fact IDs plus readable source fact labels.
* Smart Deck critique now rejects missing or unknown `analytics.sourceFactIds`.
* Frontend Smart Deck render schema types now include `analytics.sourceFactIds`.
* Smart Deck critique artifacts can now be promoted to sanitized regression cases through an admin endpoint.
* Regression replay now checks that source fact IDs are preserved when the fixture requires it.
* Smart Edit now has source facts, plan artifacts, critique artifacts, and bounded repair artifacts.
* Smart Edit completion telemetry now includes source-fact and critique metadata.
* Smart Deck and Smart Edit source facts now include fact type, evidence strength, and safety flags.
* Smart Deck and Smart Edit prompts now instruct providers to respect fact safety metadata.
* Regression fixtures now preserve sanitized fact metadata without raw fact text.
* Smart Deck and Smart Edit now use a shared critique decision contract with severity, dimensions, and specific repair actions.
* Smart Deck and Smart Edit repair contexts now receive structured repair actions.

This means the current platform can load and use the knowledge base for Smart Deck and Smart Edit generation, and admin operators can confirm whether the compiled knowledge is ready.

---

# 25. What is still required for the full LLM implementation

The knowledge base is working as an input layer, but the full LLM implementation still needs the complete agent pipeline.

Next required stages:

1. Critique stage: expand the new shared critique decision service into full fact, narrative, visual, render-contract, and audience-fit critique.
2. Repair stage: improve the current one-pass repair with richer repair actions per slide/element and artifact-visible repair results.
3. Validation stage: enforce knowledge-base validation and source-fact validation before and after repair.
4. Persistence stage: store final pass/fail decisions alongside the existing plan, source facts, prompt context, critique, repair artifact, final render schema, knowledge version, provider, and model.
5. Learning stage: convert accepted/rejected edits and failed generations into examples, eval cases, and admin learning memory.
6. Evaluation stage: export promoted regression fixtures into `eval_cases` and run repeatable backend tests before deploy.
7. Admin review stage: show critique dimensions, repair actions, and repeated failure patterns in admin artifact views.
8. Live smoke stage: sign in as seeded tester, upload a deck, generate Smart Deck slides, run Smart Edit, and confirm artifacts/telemetry on Railway.

Until these stages are implemented, the LLM system is not complete. The current state is a working knowledge-base foundation plus Smart Deck and Smart Edit source facts, source-fact IDs, planning, critique decisions, and bounded repair pipeline artifacts.


You’re right. A folder that only has `slug`, `title`, `tags`, and maybe a short description is **not an LLM knowledge base**. That is only a catalogue.

For the Smart Deck and Smart Edits pages, the LLM needs something much closer to a **deck operating manual**: structured, validated, explicit, and rich enough that the backend can use it to generate, critique, rewrite, sequence, and validate decks.

# What an excellent LLM deck knowledge base should be

An excellent knowledge base should answer these questions for the LLM:

```text
What kind of deck is this?
Who is the audience?
What decision is the deck trying to create?
Which slides are needed?
What is each slide responsible for?
What evidence is required?
What should the slide never claim without proof?
What does a strong version look like?
What does a weak version look like?
How should the slide be rewritten?
How should the backend validate the result?
How should the frontend render/edit the result?
```

So the knowledge base should not be:

```json
{
  "slug": "problem",
  "tags": ["startup", "pitch"]
}
```

It should be closer to:

```json
{
  "id": "startup_pitch.problem.v1",
  "archetype": "problem",
  "deck_families": ["startup_pitch"],
  "narrative_role": "Makes the pain obvious, urgent, and economically meaningful before the solution appears.",
  "required_inputs": ["target_customer", "pain_point", "current_alternative", "cost_of_inaction"],
  "evidence_rules": "...",
  "generation_rules": "...",
  "critique_rules": "...",
  "rewrite_rules": "...",
  "output_schema": "...",
  "quality_rubric": "...",
  "examples": "..."
}
```

The important distinction:

```text
Slug/tags help humans find a file.
A real LLM knowledge base teaches the model how to think, decide, generate, and critique.
```

---

# 1. The knowledge base needs multiple layers

A strong structure should look like this:

```text
backend/
  llm_knowledge/
    deck_knowledge_base/
      manifest.json

      taxonomy/
        deck_families.json
        audiences.json
        company_stages.json
        fund_stages.json
        sectors.json
        tone_profiles.json
        evidence_types.json

      deck_recipes/
        startup_pitch.json
        pre_seed_pitch.json
        seed_pitch.json
        series_a_pitch.json
        vc_fund_pitch.json
        investor_update.json
        sales_deck.json
        product_launch_deck.json

      archetypes/
        problem.json
        solution.json
        product.json
        market.json
        traction.json
        business_model.json
        competition.json
        team.json
        ask.json
        use_of_funds.json
        fund_thesis.json
        portfolio_construction.json
        lp_terms.json

      diagnostics/
        startup_pitch_diagnostics.json
        vc_fund_diagnostics.json
        smart_edits_rules.json
        hallucination_rules.json
        missing_evidence_rules.json

      generation/
        slide_output_contracts.json
        layout_guidance.json
        visual_patterns.json
        speaker_notes_rules.json

      examples/
        startup_pitch/
          problem.strong.json
          problem.weak.json
          traction.strong.json
          traction.weak.json

      evals/
        startup_pitch_eval_cases.json
        smart_edits_eval_cases.json
```

That is much better than one folder of basic Markdown files.

---

# 2. Core components

## A. `manifest.json`

This tells the backend what version of the knowledge base is loaded.

```json
{
  "knowledge_base_id": "deck_knowledge_base",
  "version": "1.0.0",
  "description": "Central LLM knowledge base for Smart Deck and Smart Edits.",
  "default_language": "en",
  "supported_deck_families": [
    "startup_pitch",
    "vc_fund_pitch",
    "investor_update",
    "sales_deck"
  ],
  "entrypoints": {
    "deck_recipes": "deck_recipes/",
    "archetypes": "archetypes/",
    "diagnostics": "diagnostics/",
    "generation_contracts": "generation/"
  }
}
```

This matters because the backend should know exactly what it is loading.

---

## B. Deck family taxonomy

The LLM must know the difference between deck types.

A **startup pitch deck** is not the same as a **fundraising deck for a VC fund**, an **investor update**, or a **sales deck**.

Example:

```json
{
  "id": "startup_pitch",
  "name": "Startup Pitch Deck",
  "primary_audience": ["angel_investors", "seed_investors", "venture_capitalists"],
  "primary_goal": "Convince investors that the company is a venture-scale opportunity worth a meeting, diligence, or investment.",
  "common_decision": "Should the investor take the next meeting or invest?",
  "typical_sections": [
    "problem",
    "solution",
    "product",
    "market",
    "traction",
    "business_model",
    "competition",
    "team",
    "ask"
  ],
  "must_not_do": [
    "Overstate traction without proof",
    "Use generic market claims without segmentation",
    "Describe features before explaining pain",
    "Confuse customer problem with founder inconvenience"
  ]
}
```

For a VC fund deck:

```json
{
  "id": "vc_fund_pitch",
  "name": "VC Fund Pitch Deck",
  "primary_audience": ["limited_partners", "family_offices", "fund_of_funds"],
  "primary_goal": "Convince LPs that the fund has a differentiated strategy, credible access, disciplined construction, and return potential.",
  "typical_sections": [
    "fund_thesis",
    "market_opportunity",
    "track_record",
    "sourcing_advantage",
    "portfolio_construction",
    "team",
    "terms",
    "lp_ask"
  ],
  "must_not_do": [
    "Sound like a startup pitch deck",
    "Claim proprietary deal flow without evidence",
    "Show returns without explaining attribution",
    "Avoid portfolio construction details"
  ]
}
```

This is necessary because Smart Deck needs to know what kind of deck it is building.

---

# 3. Deck recipes

A deck recipe defines the **recommended sequence**.

This is what Smart Deck should use when generating an outline.

Example:

```json
{
  "id": "startup_pitch.pre_seed.v1",
  "deck_family": "startup_pitch",
  "stage": "pre_seed",
  "audience": "seed_investors",
  "recommended_length": {
    "min_slides": 8,
    "max_slides": 12
  },
  "sequence": [
    {
      "position": 1,
      "archetype": "cover",
      "purpose": "Establish company identity and one-line promise."
    },
    {
      "position": 2,
      "archetype": "problem",
      "purpose": "Make the pain clear and urgent."
    },
    {
      "position": 3,
      "archetype": "solution",
      "purpose": "Show the company’s answer to the problem."
    },
    {
      "position": 4,
      "archetype": "product",
      "purpose": "Demonstrate how the solution works."
    },
    {
      "position": 5,
      "archetype": "market",
      "purpose": "Show the opportunity is large and reachable."
    },
    {
      "position": 6,
      "archetype": "traction",
      "purpose": "Show proof of demand, even if early."
    },
    {
      "position": 7,
      "archetype": "business_model",
      "purpose": "Explain how the company captures value."
    },
    {
      "position": 8,
      "archetype": "competition",
      "purpose": "Show why this company can win."
    },
    {
      "position": 9,
      "archetype": "team",
      "purpose": "Explain why this team is credible."
    },
    {
      "position": 10,
      "archetype": "ask",
      "purpose": "Make the fundraising request clear."
    }
  ],
  "conditional_rules": [
    {
      "condition": "no_revenue_or_usage",
      "action": "Do not fabricate traction. Use milestones, pilots, LOIs, waitlist, or learning velocity if provided."
    },
    {
      "condition": "deep_tech_company",
      "action": "Add technical defensibility after product or before competition."
    }
  ]
}
```

This lets the backend generate deck outlines without guessing.

---

# 4. Archetype knowledge

Each archetype needs to be much richer than slug and tags.

A good archetype file should contain:

```text
Identity
Purpose
When to use it
When not to use it
Narrative role
Required inputs
Optional inputs
Evidence hierarchy
Generation rules
Critique rules
Rewrite rules
Visual/layout guidance
Quality rubric
Common mistakes
Weak examples
Strong examples
Output schema
Validation rules
Frontend render hints
```

## Example: `problem.json`

```json
{
  "id": "startup_pitch.problem.v1",
  "slug": "problem",
  "name": "Problem",
  "deck_families": ["startup_pitch"],
  "description": "Explains the customer pain, why it matters now, and why current alternatives are inadequate.",
  "narrative_role": {
    "primary_job": "Create urgency before introducing the solution.",
    "emotional_effect": "The audience should feel that the problem is real, specific, and costly.",
    "business_effect": "The audience should understand why solving this problem can create economic value.",
    "comes_before": ["solution", "product"],
    "comes_after": ["cover"]
  },
  "use_when": [
    "The deck needs to establish a painful customer or market inefficiency.",
    "The solution is not obvious without understanding the current workflow."
  ],
  "do_not_use_when": [
    "The slide is mainly about product features.",
    "The problem is only a vague macro trend with no specific user pain."
  ],
  "required_inputs": [
    {
      "field": "target_customer",
      "description": "The specific user, buyer, or organization experiencing the problem.",
      "required": true
    },
    {
      "field": "pain_point",
      "description": "The painful workflow, unmet need, or costly friction.",
      "required": true
    },
    {
      "field": "current_alternative",
      "description": "What the customer does today instead.",
      "required": false
    },
    {
      "field": "cost_of_inaction",
      "description": "Time, money, risk, churn, inefficiency, or lost revenue caused by the problem.",
      "required": false
    }
  ],
  "evidence_hierarchy": [
    {
      "level": 1,
      "name": "Strong evidence",
      "examples": [
        "Customer interviews",
        "Usage data",
        "Revenue leakage",
        "Time wasted",
        "Compliance risk",
        "Churn or retention data"
      ]
    },
    {
      "level": 2,
      "name": "Moderate evidence",
      "examples": [
        "Industry benchmark",
        "Survey",
        "Public research",
        "Anecdotal customer quotes"
      ]
    },
    {
      "level": 3,
      "name": "Weak evidence",
      "examples": [
        "Generic market trend",
        "Founder opinion",
        "Unverified claim"
      ]
    }
  ],
  "generation_rules": {
    "headline": {
      "goal": "Name the painful current reality in one direct sentence.",
      "patterns": [
        "{target_customer} still rely on {broken_current_alternative}",
        "{target_customer} lose {cost} because {pain_point}",
        "{workflow} remains manual, fragmented, and expensive"
      ],
      "avoid": [
        "Generic statements like 'The market is broken'",
        "Feature language",
        "Overly dramatic claims"
      ]
    },
    "body": {
      "recommended_structure": [
        "Who has the pain",
        "What causes the pain",
        "Why existing alternatives fail",
        "Why the pain matters economically"
      ],
      "max_bullets": 4
    },
    "speaker_notes": {
      "goal": "Explain the pain clearly without pitching the product too early."
    }
  },
  "critique_rules": [
    {
      "rule": "specific_customer_required",
      "description": "Flag the slide if the customer/user is vague.",
      "severity": "high"
    },
    {
      "rule": "cost_or_urgency_needed",
      "description": "Flag the slide if it describes inconvenience but not urgency or cost.",
      "severity": "medium"
    },
    {
      "rule": "solution_too_early",
      "description": "Flag the slide if it sells product features before establishing pain.",
      "severity": "medium"
    }
  ],
  "rewrite_modes": {
    "clearer": {
      "instruction": "Remove vague language and make the customer pain more specific."
    },
    "more_investor_grade": {
      "instruction": "Tie the problem to urgency, market pull, and economic value without exaggeration."
    },
    "shorter": {
      "instruction": "Reduce to one headline and three concise bullets."
    },
    "more_visual": {
      "instruction": "Convert the problem into a workflow, before/after, cost stack, or fragmentation diagram."
    }
  },
  "visual_guidance": [
    {
      "type": "broken_workflow",
      "best_when": "The problem involves fragmented tools or manual process.",
      "description": "Show the current process as disconnected steps, handoffs, or scattered tools."
    },
    {
      "type": "cost_stack",
      "best_when": "The problem has measurable time, money, or risk cost.",
      "description": "Show the accumulated cost of the current approach."
    }
  ],
  "quality_rubric": {
    "score_5": "Specific customer, painful current workflow, credible evidence, clear urgency, no premature product pitch.",
    "score_3": "Problem is understandable but lacks strong evidence or economic urgency.",
    "score_1": "Generic, vague, trend-based, or mostly about the product instead of the pain."
  },
  "common_mistakes": [
    "Starting with a broad market trend instead of a user pain.",
    "Using buzzwords instead of concrete workflow friction.",
    "Claiming the problem is huge without showing who feels it.",
    "Solving the problem on the same slide before the audience understands it."
  ],
  "output_contract": {
    "type": "object",
    "required": [
      "archetype",
      "headline",
      "supporting_points",
      "missing_inputs",
      "quality_warnings",
      "visual_suggestion"
    ],
    "properties": {
      "archetype": { "type": "string" },
      "headline": { "type": "string" },
      "subheadline": { "type": "string" },
      "supporting_points": {
        "type": "array",
        "items": { "type": "string" },
        "maxItems": 4
      },
      "missing_inputs": {
        "type": "array",
        "items": { "type": "string" }
      },
      "quality_warnings": {
        "type": "array",
        "items": { "type": "string" }
      },
      "visual_suggestion": {
        "type": "object",
        "properties": {
          "type": { "type": "string" },
          "description": { "type": "string" }
        }
      }
    }
  },
  "frontend_render_hints": {
    "editable_fields": [
      "headline",
      "subheadline",
      "supporting_points",
      "speaker_notes"
    ],
    "show_missing_inputs_panel": true,
    "show_quality_warnings": true
  }
}
```

That is the level of detail the LLM layer needs.

---

# 5. Smart Deck needs generation knowledge

Smart Deck is not only “generate some text.”

It needs knowledge for:

```text
Deck type selection
Audience selection
Stage-specific sequencing
Slide archetype selection
Missing input detection
Outline generation
Slide generation
Visual recommendation
Speaker notes
JSON validation
```

The knowledge base should include rules like:

```json
{
  "rule_id": "do_not_generate_fake_traction",
  "applies_to": ["traction", "market", "business_model", "ask"],
  "rule": "If traction metrics are missing, do not invent revenue, users, customers, pilots, LOIs, growth rate, retention, or pipeline.",
  "fallback": "Return missing_inputs and suggest acceptable proof types."
}
```

For Smart Deck, every generated slide should include:

```json
{
  "slide_id": "generated-id",
  "archetype": "problem",
  "headline": "...",
  "subheadline": "...",
  "supporting_points": ["...", "..."],
  "visual_suggestion": {
    "type": "...",
    "description": "..."
  },
  "speaker_notes": "...",
  "missing_inputs": [],
  "quality_warnings": [],
  "source_facts_used": ["..."],
  "assumptions": [],
  "confidence": 0.82
}
```

The fields `source_facts_used` and `assumptions` are important. They help prevent the LLM from silently inventing content.

---

# 6. Smart Edits needs diagnostic knowledge

Smart Edits is even more demanding than Smart Deck.

It needs to look at an existing slide and answer:

```text
What archetype is this slide?
Is it doing the job of that archetype?
Is it in the right order?
Is it too vague?
Is it unsupported?
Is it too long?
Is it visually weak?
What exactly should change?
```

So the knowledge base needs diagnostic rules.

Example:

```json
{
  "id": "smart_edits.startup_pitch.problem_diagnostics.v1",
  "target_archetype": "problem",
  "diagnostic_checks": [
    {
      "check_id": "customer_specificity",
      "question": "Does the slide identify a specific customer, user, or buyer?",
      "pass_condition": "A specific segment, role, or organization type is named.",
      "fail_message": "The problem is too broad because the affected customer is unclear.",
      "rewrite_action": "Add a specific customer segment to the headline or first bullet."
    },
    {
      "check_id": "pain_urgency",
      "question": "Does the slide explain why the pain matters now?",
      "pass_condition": "The slide mentions time, money, risk, growth blocker, compliance, churn, or operational urgency.",
      "fail_message": "The slide describes inconvenience but not urgency.",
      "rewrite_action": "Tie the pain to a measurable or strategic cost."
    },
    {
      "check_id": "solution_leakage",
      "question": "Is the slide prematurely pitching the product?",
      "pass_condition": "The slide focuses on the customer pain, not product features.",
      "fail_message": "The slide introduces the solution before the problem is fully established.",
      "rewrite_action": "Move product claims to the solution or product slide."
    }
  ]
}
```

This allows Smart Edits to produce useful critique rather than generic feedback.

Bad Smart Edits output:

```text
Make this clearer and more concise.
```

Good Smart Edits output:

```json
{
  "slide_id": "s2",
  "detected_archetype": "problem",
  "score": 3,
  "issues": [
    {
      "severity": "high",
      "issue": "The target customer is unclear.",
      "why_it_matters": "Investors need to know who feels the pain and who might pay.",
      "suggested_fix": "Name the buyer or user segment in the headline."
    }
  ],
  "rewrite": {
    "headline": "...",
    "supporting_points": ["...", "..."]
  }
}
```

---

# 7. The knowledge base needs evidence rules

This is one of the most important parts.

The LLM must know what it is allowed to claim.

For example:

```json
{
  "claim_type": "traction",
  "requires_evidence": true,
  "allowed_sources": [
    "user_provided_metrics",
    "uploaded_deck_data",
    "CRM_data",
    "analytics_data",
    "manual_user_input"
  ],
  "forbidden_without_evidence": [
    "ARR",
    "MRR",
    "user growth percentage",
    "retention",
    "revenue pipeline",
    "customer logos",
    "signed LOIs",
    "pilot count"
  ],
  "fallback_when_missing": {
    "action": "ask_for_input",
    "missing_inputs": [
      "current revenue",
      "active users",
      "growth rate",
      "customer proof",
      "retention data"
    ]
  }
}
```

Without this layer, the LLM will produce confident nonsense.

A good knowledge base should make the backend enforce:

```text
No evidence → no claim.
Missing facts → ask or mark missing.
Weak proof → use careful wording.
Strong proof → allow stronger slide copy.
```

---

# 8. It needs examples, but examples must be structured

Examples should not be random Markdown paragraphs.

They should be labeled:

```json
{
  "id": "example.problem.strong.001",
  "archetype": "problem",
  "quality": "strong",
  "why_it_works": [
    "Names the customer",
    "Shows the painful workflow",
    "Explains business cost",
    "Does not pitch the solution too early"
  ],
  "input_context": {
    "target_customer": "finance teams at growing SaaS companies",
    "pain_point": "manual revenue reporting across spreadsheets and billing systems",
    "cost_of_inaction": "slow board reporting and poor forecast visibility"
  },
  "slide_output": {
    "headline": "Finance teams still build revenue visibility by hand",
    "supporting_points": [
      "Billing, CRM, and spreadsheet data rarely match without manual cleanup.",
      "Board reporting depends on fragile recurring workflows.",
      "Forecast decisions are delayed because teams do not trust the numbers."
    ]
  }
}
```

Weak examples are useful too:

```json
{
  "id": "example.problem.weak.001",
  "archetype": "problem",
  "quality": "weak",
  "slide_output": {
    "headline": "The market is broken",
    "supporting_points": [
      "Companies need better tools.",
      "AI can solve this.",
      "The opportunity is massive."
    ]
  },
  "why_it_fails": [
    "No specific customer",
    "No concrete pain",
    "No current alternative",
    "Solution appears before problem is explained"
  ]
}
```

This helps the LLM learn what “good” and “bad” mean inside your product.

---

# 9. It needs output contracts, not just prompts

The backend should not accept arbitrary text from the model.

Every endpoint needs a strict response contract.

For example, `generate-slide` should always return:

```json
{
  "status": "ready | needs_context | blocked",
  "archetype": "string",
  "headline": "string",
  "subheadline": "string",
  "supporting_points": ["string"],
  "visual_suggestion": {
    "type": "string",
    "description": "string",
    "data_needed": ["string"]
  },
  "speaker_notes": "string",
  "missing_inputs": ["string"],
  "quality_warnings": ["string"],
  "source_facts_used": ["string"],
  "assumptions": ["string"]
}
```

For `analyze-deck`, the contract should be different:

```json
{
  "deck_type": "startup_pitch",
  "overall_score": 0,
  "slide_diagnostics": [],
  "missing_archetypes": [],
  "sequence_issues": [],
  "evidence_gaps": [],
  "recommended_next_actions": []
}
```

For `rewrite-slide`:

```json
{
  "status": "ready | needs_context",
  "original_slide_id": "string",
  "detected_archetype": "string",
  "rewrite_mode": "string",
  "before_summary": "string",
  "after": {
    "headline": "string",
    "subheadline": "string",
    "supporting_points": ["string"],
    "speaker_notes": "string",
    "visual_suggestion": {}
  },
  "changes_made": [],
  "risks_remaining": [],
  "missing_inputs": []
}
```

This is what makes the LLM usable inside software.

---

# 10. It needs a graph, not just a list

Deck knowledge is sequential.

A problem slide leads to a solution slide.
A solution slide leads to product.
Traction should usually appear before ask.
Competition should not appear before the audience understands the product.

So the knowledge base needs a graph:

```json
{
  "archetype_graph": {
    "problem": {
      "usually_before": ["solution", "product"],
      "usually_after": ["cover"],
      "depends_on": [],
      "bad_if_missing_before": []
    },
    "solution": {
      "usually_before": ["product", "market"],
      "usually_after": ["problem"],
      "depends_on": ["problem"],
      "bad_if_missing_before": ["problem"]
    },
    "traction": {
      "usually_before": ["business_model", "ask"],
      "usually_after": ["product", "market"],
      "depends_on": ["evidence"]
    },
    "ask": {
      "usually_before": [],
      "usually_after": ["team", "traction", "business_model"],
      "depends_on": ["fundraising_amount", "use_of_funds"]
    }
  }
}
```

Smart Deck uses this to generate a good order.

Smart Edits uses this to detect bad order.

---

# 11. It needs audience and stage modifiers

A pre-seed pitch is not a Series A pitch.

The knowledge base should include modifiers like:

```json
{
  "stage": "pre_seed",
  "investor_expectations": [
    "Clear problem",
    "Founder-market fit",
    "Early product insight",
    "Early validation",
    "Large market potential"
  ],
  "traction_expectation": "Can be qualitative or early quantitative proof.",
  "avoid": [
    "Over-modeling financial projections",
    "Pretending early pilots are repeatable enterprise traction"
  ]
}
```

For Series A:

```json
{
  "stage": "series_a",
  "investor_expectations": [
    "Repeatable growth motion",
    "Clear ICP",
    "Revenue quality",
    "Retention",
    "Sales efficiency",
    "Scalable go-to-market"
  ],
  "traction_expectation": "Must include credible metrics.",
  "avoid": [
    "Only showing anecdotes",
    "Vague market sizing",
    "No cohort or retention evidence"
  ]
}
```

This makes the same archetype behave differently depending on context.

A traction slide for pre-seed:

```text
Show early signal.
```

A traction slide for Series A:

```text
Show repeatable growth quality.
```

The knowledge base should encode that difference.

---

# 12. It needs visual intelligence

For decks, words are not enough.

Each archetype should define visual patterns.

Example:

```json
{
  "archetype": "market",
  "visual_patterns": [
    {
      "type": "tam_sam_som",
      "best_when": "The market can be segmented from broad to reachable.",
      "required_data": ["TAM", "SAM", "SOM"],
      "risk": "Often weak if numbers are generic or sourced poorly."
    },
    {
      "type": "wedge_expansion",
      "best_when": "The company starts in a narrow ICP and expands over time.",
      "required_data": ["initial_segment", "adjacent_segments"],
      "risk": "Must explain why the wedge is credible."
    }
  ]
}
```

For traction:

```json
{
  "archetype": "traction",
  "visual_patterns": [
    {
      "type": "growth_chart",
      "required_data": ["time_period", "metric_name", "metric_values"],
      "best_when": "There is real month-over-month or quarter-over-quarter growth."
    },
    {
      "type": "customer_logo_strip",
      "required_data": ["approved_customer_names"],
      "best_when": "Customer names are allowed and recognizable."
    },
    {
      "type": "milestone_timeline",
      "required_data": ["milestones"],
      "best_when": "Quantitative traction is still early."
    }
  ]
}
```

This lets the backend tell the frontend:

```text
This slide should probably be a before/after diagram.
This one needs a chart.
This one should not be a chart because there is no data.
```

---

# 13. It needs frontend render hints

The LLM knowledge base should also help the app know how to render the result.

For example:

```json
{
  "frontend_render_hints": {
    "preferred_layouts": [
      "headline_with_three_bullets",
      "before_after",
      "workflow_diagram"
    ],
    "editable_fields": [
      "headline",
      "subheadline",
      "supporting_points",
      "speaker_notes"
    ],
    "requires_data_visualization": false,
    "show_missing_inputs_panel": true,
    "show_source_facts": true
  }
}
```

This bridges the LLM output to the Smart Deck UI.

---

# 14. It needs prompt recipes, but prompts should not be the whole knowledge base

A common mistake is to put everything into one giant prompt.

Better structure:

```text
Knowledge base = stable rules, archetypes, examples, schemas
Prompt builder = selects the relevant pieces at runtime
LLM call = receives only the relevant knowledge for the task
```

The prompt builder should assemble:

```text
System rules
Deck family rules
Audience/stage modifiers
Selected archetype knowledge
User/project context
Required output schema
Validation constraints
```

Example runtime prompt ingredients:

```json
{
  "task": "generate_slide",
  "deck_family": "startup_pitch",
  "stage": "pre_seed",
  "audience": "seed_investors",
  "archetype": "problem",
  "knowledge_refs": [
    "deck_recipes/startup_pitch.pre_seed.v1",
    "archetypes/problem",
    "diagnostics/hallucination_rules",
    "generation/slide_output_contracts"
  ],
  "project_context": {},
  "output_contract": "GeneratedSlideResponse"
}
```

This makes the LLM behavior consistent.

---

# 15. It needs validation and scoring

A serious knowledge base should support automatic checks.

Example scoring rubric:

```json
{
  "archetype": "problem",
  "rubric": [
    {
      "criterion": "customer_specificity",
      "weight": 0.25,
      "score_1": "No customer is named.",
      "score_3": "A broad customer category is named.",
      "score_5": "A specific user, buyer, or segment is named."
    },
    {
      "criterion": "pain_clarity",
      "weight": 0.25,
      "score_1": "Pain is vague.",
      "score_3": "Pain is understandable but generic.",
      "score_5": "Pain is concrete, specific, and easy to repeat."
    },
    {
      "criterion": "urgency",
      "weight": 0.25,
      "score_1": "No urgency or cost.",
      "score_3": "Some urgency but weak evidence.",
      "score_5": "Clear cost, risk, inefficiency, or timing pressure."
    },
    {
      "criterion": "focus",
      "weight": 0.25,
      "score_1": "Mostly talks about product.",
      "score_3": "Some problem focus, some solution leakage.",
      "score_5": "Pure problem framing with no premature product pitch."
    }
  ]
}
```

Smart Edits can then say:

```json
{
  "slide_id": "s1",
  "archetype": "problem",
  "score": 3.2,
  "weakest_criteria": ["urgency", "customer_specificity"],
  "recommended_action": "Make the customer and cost of the problem more specific."
}
```

That is much better than vague LLM feedback.

---

# 16. It needs “missing input” logic

The LLM should know when it does not have enough information.

Example:

```json
{
  "archetype": "ask",
  "required_inputs": [
    "fundraising_amount",
    "round_type",
    "runway_target",
    "use_of_funds",
    "milestones_to_reach"
  ],
  "if_missing": {
    "fundraising_amount": {
      "severity": "blocking",
      "message": "Cannot generate a credible ask slide without the fundraising amount."
    },
    "use_of_funds": {
      "severity": "blocking",
      "message": "Cannot explain why the amount is needed without use of funds."
    },
    "milestones_to_reach": {
      "severity": "medium",
      "message": "The ask will be weaker without milestones."
    }
  }
}
```

Then the backend can return:

```json
{
  "status": "needs_context",
  "missing_inputs": [
    "fundraising_amount",
    "use_of_funds",
    "milestones_to_reach"
  ],
  "question_to_user": "How much are you raising, and what milestones should this round achieve?"
}
```

This is essential for professional output.

---

# 17. It needs transformation rules for Smart Edits

Smart Edits should support edit modes.

Examples:

```json
{
  "rewrite_modes": {
    "shorter": {
      "goal": "Reduce length while preserving the main claim.",
      "rules": [
        "Keep one headline",
        "Use no more than three bullets",
        "Remove repeated claims",
        "Do not remove required evidence"
      ]
    },
    "more_investor_grade": {
      "goal": "Make the slide more precise, evidence-aware, and decision-oriented.",
      "rules": [
        "Replace vague benefits with specific outcomes",
        "Reduce hype",
        "Tie claims to proof",
        "Surface missing evidence instead of inventing it"
      ]
    },
    "more_visual": {
      "goal": "Recommend a layout or visual structure instead of adding more text.",
      "rules": [
        "Prefer diagrams, charts, timelines, matrices, or before/after structures",
        "Identify what data is needed for the visual",
        "Do not recommend a chart without data"
      ]
    },
    "less_hype": {
      "goal": "Remove exaggerated language.",
      "rules": [
        "Replace absolute claims with supportable claims",
        "Avoid words like revolutionary, game-changing, massive, inevitable unless proven",
        "Preserve ambition but reduce overclaiming"
      ]
    }
  }
}
```

This makes rewrite buttons predictable.

---

# 18. The knowledge base should support both retrieval and direct loading

There are two use cases:

## Direct loading

For small, critical files:

```text
deck recipe
selected archetype
output contract
hallucination rules
```

The backend should load these directly.

## Retrieval

For larger examples and guidance:

```text
strong examples
weak examples
sector-specific guidance
visual examples
diagnostic examples
```

The backend can retrieve only the relevant chunks.

The compiled structure should therefore include:

```text
compiled_json/
  manifest.json
  recipes.index.json
  archetypes.index.json
  diagnostics.index.json
  examples.index.json

retrieval_chunks/
  problem.examples.jsonl
  traction.examples.jsonl
  market.examples.jsonl
```

A JSONL retrieval chunk might look like:

```json
{
  "chunk_id": "problem.strong_example.001",
  "archetype": "problem",
  "deck_family": "startup_pitch",
  "stage": "pre_seed",
  "content_type": "strong_example",
  "text": "A strong problem slide names the specific customer, explains the broken current workflow, and shows why the pain creates urgency.",
  "metadata": {
    "quality": "strong",
    "use_for": ["generate_slide", "rewrite_slide", "critique_slide"]
  }
}
```

This is useful later if you add embeddings or vector search.

---

# 19. What the backend should load for each endpoint

## `GET /api/llm/deck/archetypes`

Loads:

```text
manifest
archetype summaries
deck family taxonomy
```

Returns a lightweight frontend-safe catalogue.

## `POST /api/llm/deck/outline`

Loads:

```text
deck recipe
deck family rules
stage modifier
audience modifier
sequence graph
missing input rules
```

Returns a recommended deck outline.

## `POST /api/llm/deck/generate-slide`

Loads:

```text
selected archetype
deck recipe context
generation rules
evidence rules
visual rules
output contract
examples
```

Returns one structured slide.

## `POST /api/llm/deck/analyze`

Loads:

```text
deck diagnostics
archetype detection rules
sequence graph
quality rubrics
evidence rules
missing archetype rules
```

Returns a diagnosis.

## `POST /api/llm/deck/rewrite-slide`

Loads:

```text
detected archetype
rewrite mode rules
quality rubric
visual guidance
evidence rules
output contract
```

Returns a proposed edit.

---

# 20. The ideal architecture

The knowledge base should be designed like this:

```text
Human-editable source
  ↓
Validated canonical JSON
  ↓
Compiled indexes
  ↓
Backend loader
  ↓
Prompt builder
  ↓
LLM provider
  ↓
JSON validator
  ↓
Smart Deck / Smart Edits UI
```

So the source files can be Markdown or YAML for humans, but the backend should consume compiled JSON.

Recommended source structure:

```text
source/
  archetypes/problem.md
  archetypes/traction.md
  deck_recipes/startup_pitch.md
  diagnostics/smart_edits.md

compiled/
  archetypes/problem.json
  deck_recipes/startup_pitch.json
  indexes/*.json
```

But the compiled JSON must be rich. Not just extracted headings.

---

# 21. Minimum standard for your product

For your Smart Deck and Smart Edits pages, the minimum serious knowledge base should include:

| Layer                               |    Required |
| ----------------------------------- | ----------: |
| Deck families                       |         Yes |
| Deck recipes                        |         Yes |
| Archetype definitions               |         Yes |
| Sequence graph                      |         Yes |
| Required input rules                |         Yes |
| Evidence / anti-hallucination rules |         Yes |
| Generation rules                    |         Yes |
| Critique rules                      |         Yes |
| Rewrite modes                       |         Yes |
| Visual guidance                     |         Yes |
| Output schemas                      |         Yes |
| Strong/weak examples                |         Yes |
| Quality rubrics                     |         Yes |
| Frontend render hints               |         Yes |
| Versioned manifest                  |         Yes |
| Eval cases                          | Ideally yes |

Without these, the LLM layer will feel generic.

---

# 22. What was wrong with the current version

The current version sounds like it is doing this:

```text
Read files
Extract title
Extract slug
Extract tags
Save JSON
```

That produces a list of files, not a knowledge system.

The correct version should do this:

```text
Define the deck universe
Define deck types
Define archetype jobs
Define sequencing logic
Define required facts
Define what claims are allowed
Define generation rules
Define critique rules
Define rewrite rules
Define output contracts
Define validation
Define examples
Compile everything into backend-usable JSON
```

That is the difference between:

```text
“Here are some slide names”
```

and:

```text
“Here is how a deck expert should reason about this deck.”
```

---

# 23. Target standard

An excellent LLM knowledge base should make the LLM behave like:

```text
A deck strategist
A pitch editor
A narrative architect
A slide critic
A formatting-aware product assistant
A fact-constrained writer
```

not like:

```text
A text generator with a list of slide names
```

The next version should replace the shallow archetype catalogue with a **versioned, schema-validated deck intelligence system**. It should contain enough knowledge for the backend to generate, critique, rewrite, sequence, and validate deck content without relying on vague prompts.
