export const heroHighlights = [
  'Preserves founder narrative',
  'Built for partner and IC review',
  'Reviewable AI, not black-box rewrite'
];

export const howItWorksSteps = [
  {
    number: '①',
    title: 'Source Intelligence',
    short: 'Your deck becomes structured knowledge, not a file.',
    kicker: 'Source intelligence',
    headline: 'Every slide, heading, chart, image, and claim becomes editable context.',
    body: 'Deck AIStack extracts the founder deck into a structured knowledge graph so the original presentation can be analysed, versioned, and improved without losing provenance.',
    problem:
      'Teams waste time re-reading the same deck because the source material is trapped inside a file instead of becoming reusable deal intelligence.',
    solution:
      'Deck AIStack converts the incoming deck into structured, reviewable data so every claim, image, and heading can be traced back to the original source.',
    signals: ['Slides parsed', 'Claims indexed', 'Provenance retained'],
    routeLabel: 'Structured deck ingestion',
    tone: 'blue',
    visualTitle: 'Source layer captured',
    visualSubtitle: 'The original deck is transformed into structured knowledge without losing the source trail.',
    visualPoints: ['Slide content extracted', 'Claims linked to sources', 'Editable knowledge graph ready']
  },
  {
    number: '②',
    title: 'Investment Analysis',
    short: 'Your deck is evaluated like an investor would.',
    kicker: 'Investment analysis',
    headline: 'Score narrative quality, evidence strength, and investor readiness before rewrite.',
    body: 'Deck AIStack assesses the deck the way an investor would, surfacing weak claims, missing proof, and structural issues before any rewrite begins.',
    problem:
      'Without a formal analysis pass, teams jump straight to rewriting and miss the evidence gaps that actually matter in diligence.',
    solution:
      'Deck AIStack scores narrative quality, evidence strength, market credibility, competitive positioning, and investor readiness before recommendations are generated.',
    signals: ['Narrative scored', 'Evidence gaps flagged', 'Readiness measured'],
    routeLabel: 'Investor scoring',
    tone: 'teal',
    visualTitle: 'Assessment layer active',
    visualSubtitle: 'The deck is scored against investor criteria before any generation begins.',
    visualPoints: ['Weak claims flagged', 'Proof gaps surfaced', 'IC readiness tracked']
  },
  {
    number: '③',
    title: 'Market Intelligence',
    short: 'Your deck is compared against real market knowledge.',
    kicker: 'Market intelligence',
    headline: 'Ground recommendations in market context, competitor positioning, and audience expectations.',
    body: 'Deck AIStack retrieves industry context, competitor positioning, GTM patterns, and market assumptions so the AI works with external knowledge instead of rewriting slides in isolation.',
    problem:
      'Decks often get rewritten without enough context, which makes the advice generic and weakens the strategic value of the output.',
    solution:
      'Deck AIStack retrieves market knowledge before generating recommendations, so narrative improvements reflect real positioning, not isolated slide edits.',
    signals: ['Competitors compared', 'Market context loaded', 'Audience expectations mapped'],
    routeLabel: 'Market context retrieval',
    tone: 'violet',
    visualTitle: 'Market context attached',
    visualSubtitle: 'The deck is evaluated against external market knowledge before recommendations are generated.',
    visualPoints: ['Category cues loaded', 'Competitors benchmarked', 'GTM patterns referenced']
  },
  {
    number: '④',
    title: 'Controlled AI Generation',
    short: 'Every AI change remains traceable and reviewable.',
    kicker: 'Controlled AI generation',
    headline: 'Generate suggestions from validated facts, not silent rewrites.',
    body: 'Deck AIStack never edits the source deck directly; it generates versioned suggestions from validated facts so every change can be accepted, rejected, or compared before it ships.',
    problem:
      'Blind AI rewrites are hard to trust because nobody can quickly see what changed, why it changed, or which version should be used.',
    solution:
      'Each suggestion is stored as a new version linked to the source facts, so the review loop stays transparent and reversible.',
    signals: ['Suggestions versioned', 'Changes traceable', 'Review required'],
    routeLabel: 'Versioned AI suggestions',
    tone: 'pink',
    visualTitle: 'Review-safe generation',
    visualSubtitle: 'The AI creates alternatives without overwriting the founder source deck.',
    visualPoints: ['Source facts validated', 'Alternative version created', 'Accept reject compare flow']
  },
  {
    number: '⑤',
    title: 'Institutional Memory',
    short: 'Everything stays attached to your deck.',
    kicker: 'Institutional memory',
    headline: 'Keep evidence, decisions, and versions linked throughout the deck lifecycle.',
    body: 'Deck AIStack preserves source evidence, market research, AI reasoning, reviewer decisions, and every version so the deck becomes a continuously improving investment asset.',
    problem:
      'The value of the work is lost when evidence, review notes, and version history disappear once the deck is exported.',
    solution:
      'Deck AIStack keeps every decision and source artifact attached to the deck so the team can revisit, compare, and improve it over time.',
    signals: ['Evidence attached', 'Decisions preserved', 'Versions linked'],
    routeLabel: 'Persistent deck memory',
    tone: 'amber',
    visualTitle: 'Memory layer preserved',
    visualSubtitle: 'Source evidence, reasoning, and review history stay attached to every version.',
    visualPoints: ['Evidence retained', 'Reviewer decisions logged', 'Improvement history maintained']
  }
];

export const genericToolLimitations = [
  'Start from scratch',
  'Generic design output',
  'Lose source structure',
  'No block classification',
  'No investor review trail'
];

export const deckServiceAdvantages = [
  'Start from your deck',
  'Uses brand and company context',
  'Preserves slide and block structure',
  'Classifies content before adaptation',
  'Keeps every AI change reviewable'
];

export const vcUseCases = [
  {
    title: 'Investment committee',
    body: 'Walk into IC with a sharper story, surfaced evidence gaps, and a cleaner decision trail.'
  },
  {
    title: 'Partner review',
    body: 'Reopen the live deck with context intact instead of stitching feedback together from email, PDFs, and chats.'
  },
  {
    title: 'Strategic investor versions',
    body: 'Create audience-specific versions without losing provenance between the founder source deck and the reviewed output.'
  }
];

export const previewPanes = [
  {
    title: 'Smart Deck workspace',
    body: 'Slides, blocks, findings, and audience guidance stay visible in one reviewable shell.'
  },
  {
    title: 'Design iterations',
    body: 'Create whole-deck or selected-slide iterations linked to the original deck storyline.'
  },
  {
    title: 'Smart Edit',
    body: 'Select one block, issue one instruction, and review the result before it is applied.'
  }
];
