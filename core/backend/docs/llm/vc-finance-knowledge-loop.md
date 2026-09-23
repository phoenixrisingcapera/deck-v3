# VC Finance Knowledge Loop

## Purpose

DeckAiStack needs a finance-aware VC knowledge base so Audience Diligence can challenge the numbers in a deck and convert that critique into Smart Deck and Smart Edit instructions.

This is a curated knowledge system. It should contain original rules, taxonomies, examples, and metadata. It should not contain copied book chapters or proprietary report text.

## Product problem

Investor decks often include numbers that need scrutiny:

- market size claims without TAM/SAM/SOM scope
- ROI claims without baseline, payback, or customer proof
- GMV presented as revenue
- ARR without churn or retention context
- use of funds without runway or milestones
- valuation language without support

DeckAiStack should identify these problems and produce safer slide implementation instructions.

## Loop

```text
Uploaded deck
  -> Deck Map extracts claims
  -> Finance claim extractor identifies market, revenue, ROI, unit economics, fundraising, and valuation claims
  -> VC finance knowledge pack validates assumptions
  -> Audience Diligence applies audience-specific finance lens
  -> Output flags unsupported, inconsistent, or overstated claims
  -> Smart Deck and Smart Edit receive safe implementation instructions
  -> Accepted edits become future retrieval examples
```

## Allowed knowledge sources

- original checklists
- founder/advisor notes written by the team
- public source metadata and citation pointers
- manually derived frameworks
- synthetic examples
- user-approved accepted edits
- anonymised before/after examples where permitted

## Not allowed

- copied book chapters
- copied proprietary reports
- unlicensed benchmark datasets
- source text the project does not have permission to store

## Knowledge DB evolution

### Phase 1: Static JSON

Use:

```text
llm_knowledge/deckaistack_vc_finance_knowledge_pack/*.json
```

### Phase 2: Vector chunks

Embed chunk types:

- `vc_finance_rule`
- `financial_claim_taxonomy`
- `market_sizing_rule`
- `roi_validation_rule`
- `unit_economics_rule`
- `fundraising_rule`
- `valuation_red_flag`
- `accepted_finance_edit`

### Phase 3: Feedback loop

When a user accepts a finance-related change, store:

- original claim
- issue detected
- accepted safer wording
- audience
- deck stage
- confidence
- whether evidence was added

### Phase 4: Evaluation loop

Add regression cases for:

- overstated market size
- unsupported ROI
- GMV vs revenue confusion
- raise/use-of-funds mismatch
- valuation without basis
- stage-inappropriate financial claims

### Phase 5: Fine-tuning later

Fine-tuning or LoRA is only useful after enough reviewed before/after examples exist.

## Required output fields

Audience Diligence must include:

- `financialInsights.overallFinancialCredibility`
- `financialInsights.financialClaims`
- `financialInsights.financialConsistencyIssues`
- `financialInsights.overstatedClaims`
- `financialInsights.missingFinancialEvidence`
- `financialInsights.saferWording`
- `financialInsights.slideImplementationInstructions`
