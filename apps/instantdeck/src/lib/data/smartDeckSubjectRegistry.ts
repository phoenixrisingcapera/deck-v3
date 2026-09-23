import type { SmartDeckDeckType, SmartDeckSubject, SmartDeckSubjectDefinition } from '$lib/types/smart-deck-subjects';

export const smartDeckSubjectRegistry: SmartDeckSubjectDefinition[] = [
  {
    id: 'problem',
    defaultSlug: 'problem',
    slugVariants: ['the-problem', 'pain-point', 'the-pain'],
    label: 'Problem',
    description: 'The pain the startup exists to relieve.',
    deckTypes: ['startup_pitch'],
    oftenBeforeSlides: [],
    oftenAfterSlides: ['why_now', 'solution', 'market_size'],
    requiredChecks: ['Clear target customer', 'Specific pain', 'Broken current workflow', 'Urgency', 'Scale relevance'],
    investorLogic: 'Show who hurts, why current alternatives fail, and why the pain is urgent enough to fund a company.'
  },
  {
    id: 'solution',
    defaultSlug: 'solution',
    slugVariants: ['the-solution', 'our-solution', 'approach'],
    label: 'Solution',
    description: 'The thesis-level answer to the problem.',
    deckTypes: ['startup_pitch'],
    oftenBeforeSlides: ['problem'],
    oftenAfterSlides: ['product_walkthrough', 'market_size', 'business_model'],
    requiredChecks: ['Clear product description', 'Problem connection', 'Differentiated approach', 'Simple value proposition'],
    investorLogic: 'Explain what the product does and why this approach is meaningfully better than the alternatives.'
  },
  {
    id: 'market_size',
    defaultSlug: 'market-size',
    slugVariants: ['tam', 'tam-sam-som', 'market-opportunity', 'market', 'opportunity-size'],
    label: 'Market Size',
    description: 'How large the addressable opportunity is.',
    deckTypes: ['startup_pitch'],
    oftenBeforeSlides: ['problem', 'solution'],
    oftenAfterSlides: ['business_model', 'competition', 'positioning'],
    requiredChecks: ['TAM/SAM/SOM distinction', 'Sourced assumptions', 'Bottom-up logic', 'Venture-scale outcome'],
    investorLogic: 'Show that the market can support a venture-scale outcome and that the assumptions are credible.'
  },
  {
    id: 'traction',
    defaultSlug: 'traction',
    slugVariants: ['progress', 'metrics', 'momentum', 'milestones', 'kpis', 'traction-and-metrics'],
    label: 'Traction',
    description: 'Evidence the thing is working.',
    deckTypes: ['startup_pitch', 'vc_fund_pitch'],
    oftenBeforeSlides: ['product_walkthrough', 'business_model', 'positioning'],
    oftenAfterSlides: ['core_team', 'roadmap'],
    requiredChecks: ['Best metric is dominant', 'Growth over time', 'Stage-appropriate proof', 'Named logo or pipeline signal'],
    investorLogic: 'Make the proof easy to scan and stage-appropriate for the audience.'
  },
  {
    id: 'business_model',
    defaultSlug: 'business-model',
    slugVariants: ['go-to-market', 'gtm', 'revenue-model', 'monetization', 'how-we-make-money', 'unit-economics'],
    label: 'Business Model',
    description: 'How the company captures value.',
    deckTypes: ['startup_pitch'],
    oftenBeforeSlides: ['solution', 'product_walkthrough'],
    oftenAfterSlides: ['traction', 'competition', 'positioning'],
    requiredChecks: ['Buyer identified', 'Pricing logic', 'Sales motion', 'Revenue model', 'Scalability'],
    investorLogic: 'Clarify who pays, how they pay, and how the model can scale into a large business.'
  },
  {
    id: 'competition',
    defaultSlug: 'competition',
    slugVariants: ['competitive-landscape', 'market-landscape', 'landscape', 'competitors', 'alternatives'],
    label: 'Competition',
    description: 'Who else is in the space and how the company differs.',
    deckTypes: ['startup_pitch'],
    oftenBeforeSlides: ['business_model', 'market_size'],
    oftenAfterSlides: ['positioning', 'traction'],
    requiredChecks: ['Real alternatives included', 'Comparison dimensions', 'Defensible difference', 'No empty 2x2'],
    investorLogic: 'Show why the company wins against real alternatives, not against a strawman.'
  },
  {
    id: 'positioning',
    defaultSlug: 'positioning',
    slugVariants: ['differentiation', 'moat', 'why-us', 'unique-value', 'competitive-advantage', 'our-edge'],
    label: 'Positioning',
    description: 'The defensible difference.',
    deckTypes: ['startup_pitch', 'vc_fund_pitch'],
    oftenBeforeSlides: ['competition', 'market_size', 'fund_thesis'],
    oftenAfterSlides: ['traction', 'core_team', 'track_record'],
    requiredChecks: ['Clear wedge', 'Defensible difference', 'Investor can see why this wins'],
    investorLogic: 'Translate feature differences into a durable market advantage.'
  },
  {
    id: 'why_now',
    defaultSlug: 'why-now',
    slugVariants: ['timing', 'market-timing', 'the-moment', 'the-wave', 'macro', 'macro-tailwinds', 'inflection', 'inflection-point', 'why-this-moment'],
    label: 'Why Now',
    description: 'The inflection that makes this the right window.',
    deckTypes: ['startup_pitch', 'vc_fund_pitch'],
    oftenBeforeSlides: ['problem', 'fund_thesis', 'market_size'],
    oftenAfterSlides: ['regulatory_tailwinds', 'solution', 'market_size', 'positioning', 'track_record'],
    requiredChecks: ['Timing shift', 'Market change', 'Why this is urgent now'],
    investorLogic: 'Make the audience believe the timing changed in a way that creates a real opening.'
  },
  {
    id: 'roadmap',
    defaultSlug: 'roadmap',
    slugVariants: ['plan', 'milestones-roadmap', 'next-12-months', 'what-we-will-do', 'vision', '18-month-plan'],
    label: 'Roadmap',
    description: 'What the company will do with the runway.',
    deckTypes: ['startup_pitch'],
    oftenBeforeSlides: ['traction', 'core_team', 'extended_team'],
    oftenAfterSlides: ['ask', 'use_of_proceeds'],
    requiredChecks: ['Milestones', 'Hiring plan', 'Product bets', 'Timeline'],
    investorLogic: 'Show what the round funds and why those milestones matter.'
  },
  {
    id: 'ask',
    defaultSlug: 'ask',
    slugVariants: ['the-ask', 'raise', 'round', 'raising', 'funding-ask', 'we-are-raising'],
    label: 'Ask',
    description: 'How much the company is raising and what milestones the round funds.',
    deckTypes: ['startup_pitch'],
    oftenBeforeSlides: ['roadmap', 'core_team', 'extended_team'],
    oftenAfterSlides: ['use_of_proceeds'],
    requiredChecks: ['Raise amount', 'Round structure', 'Runway or milestone logic', 'Connection to use of proceeds'],
    investorLogic: 'State the amount and make the amount feel sized to the plan.'
  },
  {
    id: 'use_of_proceeds',
    defaultSlug: 'use-of-proceeds',
    slugVariants: ['uop', 'where-the-money-goes', 'deployment', 'spend-plan', 'fund-allocation', 'capital-allocation'],
    label: 'Use of Proceeds',
    description: 'How the raised capital is deployed.',
    deckTypes: ['startup_pitch'],
    oftenBeforeSlides: ['ask', 'roadmap'],
    oftenAfterSlides: [],
    requiredChecks: ['Headcount', 'Engineering', 'GTM', 'Runway', 'Milestone linkage'],
    investorLogic: 'Show the round is sized to the plan, not the other way around.'
  },
  {
    id: 'core_team',
    defaultSlug: 'core-team',
    slugVariants: ['team', 'founders', 'leadership', 'founding-team', 'the-team', 'executive-team'],
    label: 'Core Team',
    description: 'The operating people behind the company or fund.',
    deckTypes: ['startup_pitch', 'vc_fund_pitch'],
    oftenBeforeSlides: ['traction', 'positioning', 'portfolio_construction'],
    oftenAfterSlides: ['extended_team', 'roadmap', 'ask'],
    requiredChecks: ['Role clarity', 'Credibility', 'Why this team'],
    investorLogic: 'Make the people behind the bet feel credible and relevant to the problem.'
  },
  {
    id: 'extended_team',
    defaultSlug: 'extended-team',
    slugVariants: ['advisors', 'board', 'team-extended', 'advisory-board', 'investors-and-advisors', 'backers-and-advisors'],
    label: 'Extended Team',
    description: 'The credibility ring around the core.',
    deckTypes: ['startup_pitch', 'vc_fund_pitch'],
    oftenBeforeSlides: ['core_team'],
    oftenAfterSlides: ['roadmap', 'ask', 'lp_terms'],
    requiredChecks: ['Advisors', 'Board', 'Backers', 'Credibility ring'],
    investorLogic: 'Show the supporting cast that de-risks the core team.'
  },
  {
    id: 'product_walkthrough',
    defaultSlug: 'product-walkthrough',
    slugVariants: ['product', 'sample', 'how-it-works', 'what-we-built', 'the-product'],
    label: 'Product Sample',
    description: 'Screenshots, flow, or video that make the solution concrete.',
    deckTypes: ['startup_pitch'],
    oftenBeforeSlides: ['solution'],
    oftenAfterSlides: ['business_model', 'traction'],
    requiredChecks: ['Visible product', 'Concrete flow', 'Product-specific language'],
    investorLogic: 'Turn claims into artifacts the investor can see.'
  },
  {
    id: 'lighthouse_customers',
    defaultSlug: 'lighthouse-customers',
    slugVariants: ['marquee-customers', 'design-partners', 'anchor-customers', 'named-customers', 'logo-slide', 'customer-logos', 'flagship-customers', 'early-customers'],
    label: 'Lighthouse Customers',
    description: 'Named marquee customers or design partners.',
    deckTypes: ['startup_pitch', 'vc_fund_pitch'],
    oftenBeforeSlides: ['traction', 'product_walkthrough', 'business_model'],
    oftenAfterSlides: ['traction', 'business_model', 'references', 'media_mentions', 'core_team'],
    requiredChecks: ['Named proof', 'Category signal', 'De-risking value'],
    investorLogic: 'Use the names that make the category feel real and the GTM thesis feel less risky.'
  },
  {
    id: 'regulatory_tailwinds',
    defaultSlug: 'regulatory-tailwinds',
    slugVariants: ['regulation', 'regulatory-environment', 'policy-tailwinds', 'regulatory-backdrop', 'policy', 'compliance-tailwinds', 'policy-environment'],
    label: 'Regulatory Tailwinds',
    description: 'The policy or regulatory shift that creates the opening.',
    deckTypes: ['startup_pitch', 'vc_fund_pitch'],
    oftenBeforeSlides: ['why_now', 'problem', 'fund_thesis', 'market_size'],
    oftenAfterSlides: ['solution', 'market_size', 'business_model', 'positioning'],
    requiredChecks: ['Policy shift', 'Demand pull', 'Timing relevance'],
    investorLogic: 'Show that regulation is moving demand or cost structure in your favor.'
  },
  {
    id: 'media_mentions',
    defaultSlug: 'media-mentions',
    slugVariants: ['press', 'as-seen-in', 'media', 'press-coverage', 'in-the-news', 'press-logos', 'media-coverage'],
    label: 'Media Mentions',
    description: 'Third-party validation via press or awards.',
    deckTypes: ['startup_pitch', 'vc_fund_pitch'],
    oftenBeforeSlides: ['traction', 'track_record', 'recent_exits'],
    oftenAfterSlides: ['extended_team', 'core_team', 'references'],
    requiredChecks: ['Third-party validation', 'Readable logos', 'Relevance'],
    investorLogic: 'Use external proof as credibility, not as decoration.'
  },
  {
    id: 'references',
    defaultSlug: 'references',
    slugVariants: ['customer-references', 'lp-references', 'vouchers', 'references-available', 'willing-references', 'backchannel-references', 'happy-to-connect'],
    label: 'References',
    description: 'Named people willing to take a diligence call.',
    deckTypes: ['startup_pitch', 'vc_fund_pitch'],
    oftenBeforeSlides: ['traction', 'extended_team', 'media_mentions', 'recent_exits'],
    oftenAfterSlides: ['ask', 'use_of_proceeds', 'lp_terms'],
    requiredChecks: ['Named reference', 'Diligence value', 'Contact route'],
    investorLogic: 'Make the backchannel easier and more credible.'
  },
  {
    id: 'thought_leadership',
    defaultSlug: 'thought-leadership',
    slugVariants: ['content', 'writing', 'publications', 'talks', 'podcast', 'substack', 'original-research', 'papers', 'speaking'],
    label: 'Thought Leadership',
    description: 'Original content that samplenstrates category authority.',
    deckTypes: ['startup_pitch', 'vc_fund_pitch'],
    oftenBeforeSlides: ['positioning', 'core_team', 'fund_thesis', 'track_record'],
    oftenAfterSlides: ['media_mentions', 'references', 'extended_team', 'traction'],
    requiredChecks: ['Original point of view', 'Category authority', 'Credibility'],
    investorLogic: 'Show that the team has a point of view the market recognizes.'
  },
  {
    id: 'who_is_in',
    defaultSlug: 'who-is-in',
    slugVariants: ['existing-investors', 'current-investors', 'round-participants', 'committed-capital', 'anchor-investors', 'soft-commits', 'lead-and-followers', 'already-committed'],
    label: 'Who Is In',
    description: 'Who has already committed to the round or fund.',
    deckTypes: ['startup_pitch', 'vc_fund_pitch'],
    oftenBeforeSlides: ['ask', 'lp_terms', 'extended_team'],
    oftenAfterSlides: ['use_of_proceeds', 'pipeline'],
    requiredChecks: ['Committed names', 'Check sizes', 'Lead status'],
    investorLogic: 'Use social proof to show momentum around the round.'
  },
  {
    id: 'blue_ocean_strategy',
    defaultSlug: 'blue-ocean-strategy',
    slugVariants: ['strategy-canvas', 'value-curve', 'eric-grid', 'eric-framework', 'four-actions', 'eliminate-reduce-raise-create', 'value-innovation', 'blue-ocean'],
    label: 'Blue Ocean Strategy',
    description: 'Strategy Canvas positioning against incumbents.',
    deckTypes: ['startup_pitch', 'vc_fund_pitch'],
    oftenBeforeSlides: ['competition', 'positioning', 'market_size'],
    oftenAfterSlides: ['positioning', 'traction', 'business_model', 'fund_thesis'],
    requiredChecks: ['Value curve', 'ERIC delta', 'Incumbent comparison'],
    investorLogic: 'Visually show the delta against incumbents and the strategy for creating a new space.'
  },
  {
    id: 'fund_thesis',
    defaultSlug: 'fund-thesis',
    slugVariants: ['thesis', 'investment-thesis', 'our-thesis', 'why-this-fund', 'fund-strategy'],
    label: 'Fund Thesis',
    description: 'The world-view the fund invests behind.',
    deckTypes: ['vc_fund_pitch'],
    oftenBeforeSlides: [],
    oftenAfterSlides: ['why_now', 'positioning', 'track_record', 'portfolio_construction'],
    requiredChecks: ['Investment worldview', 'Sector/stage/geography', 'Why now', 'LP-relevant return logic'],
    investorLogic: 'Make the fund’s worldview legible and compelling as a repeatable investment engine.'
  },
  {
    id: 'portfolio_construction',
    defaultSlug: 'portfolio-construction',
    slugVariants: ['portfolio', 'portfolio-strategy', 'allocation-model', 'check-sizes', 'construction', 'portfolio-model'],
    label: 'Portfolio Construction',
    description: 'How the fund deploys capital.',
    deckTypes: ['vc_fund_pitch'],
    oftenBeforeSlides: ['fund_thesis', 'track_record'],
    oftenAfterSlides: ['pipeline', 'core_team'],
    requiredChecks: ['Number of investments', 'Check size', 'Reserve strategy', 'Ownership target'],
    investorLogic: 'Show how the fund is built to produce the intended return profile.'
  },
  {
    id: 'track_record',
    defaultSlug: 'track-record',
    slugVariants: ['past-performance', 'returns', 'history', 'prior-funds', 'track', 'performance'],
    label: 'Track Record',
    description: "The fund's prior performance.",
    deckTypes: ['vc_fund_pitch'],
    oftenBeforeSlides: ['fund_thesis', 'positioning'],
    oftenAfterSlides: ['recent_exits', 'portfolio_construction'],
    requiredChecks: ['DPI/TVPI/IRR', 'Vintage context', 'Named wins', 'Attribution'],
    investorLogic: 'Make the performance legible and attributable.'
  },
  {
    id: 'pipeline',
    defaultSlug: 'pipeline',
    slugVariants: ['deal-flow', 'active-pipeline', 'live-deals', 'near-term-investments', 'current-pipeline'],
    label: 'Pipeline',
    description: 'Live deals the fund is actively diligencing.',
    deckTypes: ['vc_fund_pitch'],
    oftenBeforeSlides: ['portfolio_construction', 'recent_exits'],
    oftenAfterSlides: ['core_team', 'lp_terms'],
    requiredChecks: ['Live deal-flow', 'Diligence stage', 'Thesis fit', 'Access signal'],
    investorLogic: 'Prove the thesis is translating into a real pipeline right now.'
  },
  {
    id: 'lp_terms',
    defaultSlug: 'lp-terms',
    slugVariants: ['terms', 'fund-terms', 'lp-economics', 'fees-and-carry', 'fund-structure', 'economics'],
    label: 'LP Terms',
    description: 'The economic and structural terms of the LP commitment.',
    deckTypes: ['vc_fund_pitch'],
    oftenBeforeSlides: ['pipeline', 'extended_team', 'core_team'],
    oftenAfterSlides: [],
    requiredChecks: ['Management fee', 'Carry', 'GP commit', 'Fund life', 'Close timeline'],
    investorLogic: 'Clarify the commercial terms and any out-of-band structures that need explanation.'
  },
  {
    id: 'recent_exits',
    defaultSlug: 'recent-exits',
    slugVariants: ['exits', 'wins', 'notable-exits', 'realizations', 'liquidity-events'],
    label: 'Recent Exits',
    description: 'Specific named exits with multiples and attribution.',
    deckTypes: ['vc_fund_pitch'],
    oftenBeforeSlides: ['track_record'],
    oftenAfterSlides: ['portfolio_construction', 'pipeline'],
    requiredChecks: ['Named exits', 'Multiple or outcome', 'Attribution'],
    investorLogic: 'Use recent exits to make the fund’s return pattern concrete.'
  }
];

export function getSmartDeckDeckType(audience?: string | null, purpose?: string | null): SmartDeckDeckType {
  const text = `${audience ?? ''} ${purpose ?? ''}`.toLowerCase();
  if (text.includes('lp') || text.includes('limited partner') || text.includes('fund') || text.includes('vc partner')) {
    return 'vc_fund_pitch';
  }
  if (text.includes('startup') || text.includes('pitch') || text.includes('investor') || text.includes('founder')) {
    return 'startup_pitch';
  }
  return 'unknown';
}
