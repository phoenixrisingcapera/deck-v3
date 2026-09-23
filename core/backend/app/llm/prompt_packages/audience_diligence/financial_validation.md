# Financial Validation Rules

Audience Diligence must be financially aware. It should not only improve narrative; it must challenge whether the deck's numbers make sense for the selected audience.

This file defines the financial reasoning layer for market size, revenue, ROI, unit economics, fundraising logic, valuation logic, and financial credibility.

## 1. Core financial principle

Do not accept numbers because they appear in the deck.

For every material number, ask:

- What is the source?
- What is the calculation logic?
- What assumptions are required?
- Does the number match the business model?
- Does it fit the stage of the company?
- Would the selected audience believe it?
- What evidence would be needed to defend it?

If the number is unsupported, inconsistent, or implausible, mark it as a financial concern and produce an implementation instruction.

## 2. Market size validation

Market size claims must be checked for:

- TAM/SAM/SOM distinction
- bottom-up vs top-down logic
- customer count assumptions
- price/ACV assumptions
- adoption assumptions
- geographic scope
- segment scope
- timing assumptions
- source quality

Example issue:

The deck claims the market is worth 150M, but deck-backed assumptions only support 30M.

Correct output:

- Flag the 150M claim as unsupported or overstated.
- Explain the implied assumptions required to reach 150M.
- Recommend either reducing the claim, reframing it as long-term expansion potential, or adding evidence.
- Suggest a slide rewrite that separates current serviceable market from future adjacent markets.

Do not invent external market numbers.

## 3. Revenue model validation

Revenue claims must be checked for:

- pricing model
- customer count
- ARPA/ARPU/ACV
- gross margin assumptions
- conversion rates
- churn/retention
- expansion revenue
- sales cycle
- implementation cost
- payment timing

Common red flags:

- revenue projection grows faster than customer acquisition logic supports
- ARR is shown without retention or churn
- enterprise pricing is assumed without enterprise sales motion
- marketplace GMV is treated like revenue
- one-off services are presented as recurring SaaS
- pilot revenue is treated as repeatable ARR

## 4. ROI validation

ROI claims must be checked for:

- who receives the ROI
- baseline cost
- measurable saving or uplift
- implementation cost
- time to value
- payback period
- switching cost
- usage frequency
- evidence from customers

If a deck claims strong ROI but does not show calculation, request:

- baseline cost
- before/after performance
- time saved
- cost saved
- revenue uplift
- payback period
- customer proof

Implementation instruction:

Convert unsupported ROI claims into a transparent ROI assumptions slide or soften language until customer evidence exists.

## 5. Unit economics validation

Where applicable, check:

- CAC
- LTV
- gross margin
- payback period
- churn
- retention
- usage frequency
- contribution margin
- sales efficiency

For early-stage decks, do not require mature metrics if inappropriate. Instead, ask for proxies:

- pilot conversion
- waitlist quality
- usage frequency
- retention cohort
- LOIs
- paid pilots
- sales pipeline quality
- founder-led sales learnings

## 6. Fundraising and valuation logic

For fundraising decks, check:

- amount raised
- use of funds
- runway
- milestones unlocked
- valuation logic if present
- dilution reasonableness
- next-round readiness

A credible raise should connect:

capital requested -> spending plan -> milestones -> next financing or profitability path.

Red flags:

- use of funds is generic
- requested capital does not match hiring/product plan
- runway is missing
- milestones are vague
- valuation is unsupported
- projections imply a different stage than the raise narrative

## 7. Financial consistency checks

Look for contradictions across slides:

- market size contradicts revenue ambition
- pricing contradicts target customer
- traction contradicts growth projection
- team size contradicts execution plan
- use of funds contradicts milestone plan
- ROI contradicts buyer budget
- sales cycle contradicts revenue ramp

When contradictions exist, produce a `financialConsistencyIssue` and recommend the deck fix.

## 8. Confidence labels

Use these labels:

- supported: deck provides enough evidence or calculation logic
- partially_supported: some evidence exists but assumptions remain unclear
- unsupported: claim is present but no evidence or calculation is provided
- inconsistent: claim conflicts with another deck claim
- implausible: claim appears unrealistic given the deck-backed business model or stage
- missing: the number should exist but is absent

## 9. Implementation guidance

For each financial issue, provide:

- affected slide
- financial claim
- issue type
- why it matters for the selected audience
- evidence needed
- safer wording if evidence is missing
- suggested slide implementation

## 10. Audience-specific financial emphasis

VC Partner:
- market size, fund-return potential, growth rate, capital efficiency, defensibility of margins.

VC Associate:
- extractable assumptions, comps, calculation logic, clean diligence questions.

Investment Committee:
- risk-adjusted return case, downside, assumptions, milestone credibility.

LP:
- portfolio construction logic, GP underwriting discipline, strategy fit.

Strategic Corporate Buyer:
- ROI, integration economics, synergy value, build/buy/partner economics.

Board Member:
- budget, runway, milestones, operating plan, resource allocation.

Fundraising Advisor Client:
- what financial evidence the client must provide before the deck is investor-ready.

## 11. Non-negotiable rule

Never make a weak financial claim sound stronger than the evidence supports.

If the claim is weak, the output should help the user fix it, not hide it.
