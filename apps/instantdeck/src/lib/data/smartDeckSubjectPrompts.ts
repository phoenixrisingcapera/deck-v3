import type { SmartDeckSubjectPromptAction } from '$lib/types/smart-deck-subjects';

export const smartDeckSubjectPromptActions: SmartDeckSubjectPromptAction[] = [
  {
    id: 'problem_vc_pass',
    subject: 'problem',
    label: 'Problem slide VC pass',
    description: 'Make the pain, user, urgency, and scale clearer.',
    deckTypes: ['startup_pitch'],
    prompt:
      'Improve the selected slide as a VC-grade Problem slide. Clarify who has the problem, why it is painful, why current alternatives fail, and why the problem is urgent now. Avoid generic language. Make the investor understand the pain in under 30 seconds.',
    requiredChecks: ['Clear target customer', 'Specific pain', 'Broken current workflow', 'Urgency', 'Venture-scale relevance']
  },
  {
    id: 'solution_vc_pass',
    subject: 'solution',
    label: 'Solution slide VC pass',
    description: 'Make the product answer the problem clearly.',
    deckTypes: ['startup_pitch'],
    prompt:
      'Improve the selected slide as a VC-grade Solution slide. Explain what the product does, how it solves the stated problem, and why the approach is meaningfully better than existing alternatives. Keep the language concrete and product-specific.',
    requiredChecks: ['Clear product description', 'Connection to problem', 'Differentiated approach', 'Simple value proposition']
  },
  {
    id: 'market_size_vc_pass',
    subject: 'market_size',
    label: 'Market size logic',
    description: 'Clarify TAM/SAM/SOM and assumptions.',
    deckTypes: ['startup_pitch'],
    prompt:
      'Improve the selected slide as a VC-grade Market Size slide. Clarify TAM, SAM, SOM, source labels, calculation assumptions, and why the addressable market can support venture-scale outcomes. Avoid exaggerated unsourced claims.',
    requiredChecks: ['TAM/SAM/SOM distinction', 'Sourced assumptions', 'Bottom-up logic', 'Credible market entry segment']
  },
  {
    id: 'traction_vc_pass',
    subject: 'traction',
    label: 'Traction investor pass',
    description: 'Turn evidence into investor signal.',
    deckTypes: ['startup_pitch'],
    prompt:
      'Improve the selected slide as a VC-grade Traction slide. Highlight the strongest evidence that the product is working: revenue, users, retention, pilots, design partners, pipeline, growth rate, or named logos. Make the signal easy to scan and stage-appropriate.',
    requiredChecks: ['Best metric dominant', 'Growth over time', 'Stage-appropriate proof', 'Named customer or pipeline signal']
  },
  {
    id: 'business_model_vc_pass',
    subject: 'business_model',
    label: 'Business model pass',
    description: 'Clarify pricing, buyer, and revenue logic.',
    deckTypes: ['startup_pitch'],
    prompt:
      'Improve the selected slide as a VC-grade Business Model slide. Clarify who pays, pricing structure, sales motion, revenue model, unit economics, and how this can scale into a large business.',
    requiredChecks: ['Buyer identified', 'Pricing logic', 'Sales motion', 'Revenue model', 'Scalability']
  },
  {
    id: 'competition_vc_pass',
    subject: 'competition',
    label: 'Competition positioning',
    description: 'Make alternatives and differentiation sharper.',
    deckTypes: ['startup_pitch'],
    prompt:
      'Improve the selected slide as a VC-grade Competition slide. Show the real alternatives, explain the competitive dimensions that matter, and make the company’s differentiation obvious without pretending there is no competition.',
    requiredChecks: ['Real alternatives included', 'Comparison dimensions', 'Defensible difference', 'No empty 2x2']
  },
  {
    id: 'positioning_vc_pass',
    subject: 'positioning',
    label: 'Positioning pass',
    description: 'Translate difference into a defendable wedge.',
    deckTypes: ['startup_pitch', 'vc_fund_pitch'],
    prompt:
      'Improve the selected slide as a VC-grade Positioning slide. Make the wedge, differentiation, and market role unmistakable. Translate features into a defendable market position and keep the narrative concise.',
    requiredChecks: ['Clear wedge', 'Differentiated role', 'Investor sees why this wins']
  },
  {
    id: 'why_now_vc_pass',
    subject: 'why_now',
    label: 'Why now pass',
    description: 'Make timing and inflection explicit.',
    deckTypes: ['startup_pitch', 'vc_fund_pitch'],
    prompt:
      'Improve the selected slide as a VC-grade Why Now slide. Explain what changed in the market, technology, regulation, or behavior that makes this the right moment for the bet. Keep the timing logic concrete and source-backed.',
    requiredChecks: ['Timing shift', 'Market change', 'Urgency now']
  },
  {
    id: 'roadmap_vc_pass',
    subject: 'roadmap',
    label: 'Roadmap pass',
    description: 'Connect milestones to the next round.',
    deckTypes: ['startup_pitch'],
    prompt:
      'Improve the selected slide as a VC-grade Roadmap slide. Show the milestones, hires, product bets, and timeline that the round funds. Make the path to the next financing or growth milestone clear.',
    requiredChecks: ['Milestones', 'Hiring plan', 'Timeline', 'Next-round logic']
  },
  {
    id: 'ask_vc_pass',
    subject: 'ask',
    label: 'Ask pass',
    description: 'Clarify round size and use of capital.',
    deckTypes: ['startup_pitch'],
    prompt:
      'Improve the selected slide as a VC-grade Ask slide. Clarify how much is being raised, the instrument or round structure if known, what milestones the capital funds, and why this amount is appropriate for the next stage.',
    requiredChecks: ['Raise amount', 'Round structure', 'Milestone logic', 'Use of proceeds']
  },
  {
    id: 'use_of_proceeds_vc_pass',
    subject: 'use_of_proceeds',
    label: 'Use of proceeds pass',
    description: 'Show the capital plan matches the ask.',
    deckTypes: ['startup_pitch'],
    prompt:
      'Improve the selected slide as a VC-grade Use of Proceeds slide. Show how capital is allocated across hires, engineering, GTM, and runway, and make the relationship to the ask obvious.',
    requiredChecks: ['Capital allocation', 'Milestone linkage', 'Runway logic']
  },
  {
    id: 'fund_thesis_lp_pass',
    subject: 'fund_thesis',
    label: 'Fund thesis pass',
    description: 'Sharpen the investment worldview.',
    deckTypes: ['vc_fund_pitch'],
    prompt:
      'Improve the selected slide as an LP-grade Fund Thesis slide. Clarify the fund’s investment worldview, target sector, stage, geography, timing, and why this thesis creates an attractive opportunity for LPs.',
    requiredChecks: ['Investment thesis', 'Sector/stage/geography', 'Why now', 'LP return logic']
  },
  {
    id: 'portfolio_construction_lp_pass',
    subject: 'portfolio_construction',
    label: 'Portfolio construction pass',
    description: 'Clarify deployment, reserves, and ownership logic.',
    deckTypes: ['vc_fund_pitch'],
    prompt:
      'Improve the selected slide as an LP-grade Portfolio Construction slide. Clarify number of investments, check sizes, reserves, ownership targets, follow-on strategy, and how the construction supports the return target.',
    requiredChecks: ['Number of investments', 'Initial check size', 'Reserve strategy', 'Ownership target']
  },
  {
    id: 'track_record_lp_pass',
    subject: 'track_record',
    label: 'Track record pass',
    description: 'Make performance credible and attributable.',
    deckTypes: ['vc_fund_pitch'],
    prompt:
      'Improve the selected slide as an LP-grade Track Record slide. Present prior performance clearly, including DPI, TVPI, IRR, exits, vintage context, and partner attribution where available. Avoid unsupported performance claims.',
    requiredChecks: ['DPI/TVPI/IRR', 'Vintage context', 'Named wins', 'Partner attribution']
  },
  {
    id: 'pipeline_lp_pass',
    subject: 'pipeline',
    label: 'Pipeline pass',
    description: 'Show live deal-flow credibility.',
    deckTypes: ['vc_fund_pitch'],
    prompt:
      'Improve the selected slide as an LP-grade Pipeline slide. Show live deals, diligence stage, thesis fit, expected check sizes, and why the current pipeline proves access to attractive opportunities.',
    requiredChecks: ['Live deal-flow', 'Diligence stage', 'Thesis fit', 'Access signal']
  },
  {
    id: 'lp_terms_lp_pass',
    subject: 'lp_terms',
    label: 'LP terms pass',
    description: 'Clarify fund economics and structure.',
    deckTypes: ['vc_fund_pitch'],
    prompt:
      'Improve the selected slide as an LP-grade Terms slide. Clearly state management fee, carry, hurdle if any, GP commit, fund life, close timeline, minimum commitment, and any terms that need justification.',
    requiredChecks: ['Management fee', 'Carry', 'GP commit', 'Fund life', 'Close timeline', 'Minimum commitment']
  }
];

export const smartDeckSubjectActionById = smartDeckSubjectPromptActions.reduce<Record<string, SmartDeckSubjectPromptAction>>((lookup, action) => {
  lookup[action.id] = action;
  return lookup;
}, {});
