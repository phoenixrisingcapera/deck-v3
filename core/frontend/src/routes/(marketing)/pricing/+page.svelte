<script lang="ts">
  import MarketingCardGrid from '$lib/components/marketing/MarketingCardGrid.svelte';
  import MarketingPageHero from '$lib/components/marketing/MarketingPageHero.svelte';

  const workflowUses = [
    {
      title: 'Prepare a company for investor conversations',
      body: 'Sharpen the deck before outreach so the company story, evidence, and structure hold up under review.'
    },
    {
      title: 'Improve a fundraising deck before outreach',
      body: 'Turn messy or inconsistent materials into a clearer investor narrative without losing source substance.'
    },
    {
      title: 'Adapt the deck for a specific audience',
      body: 'Create iterations for investors, advisors, LPs, or strategic reviewers while keeping change control visible.'
    }
  ];

  const included = [
    {
      title: 'Smart Deck setup',
      body: 'We create a Smart Deck workspace from your existing PDF or PowerPoint deck and company website.'
    },
    {
      title: 'Brand-aware deck preparation',
      body: 'The deck stays visually aligned with your company materials, including colours, logo, tone, and style direction.'
    },
    {
      title: 'Investor narrative review',
      body: 'We review clarity, sequencing, missing sections, weak areas, and overall investor-readiness structure.'
    },
    {
      title: 'Slide-by-slide improvement workflow',
      body: 'You can review suggested updates, compare versions, and decide what should be kept, changed, or rejected.'
    },
    {
      title: 'Design iterations',
      body: 'Prepare improved design directions for selected slides or the full deck depending on the scope.'
    },
    {
      title: 'Change review and export-ready outputs',
      body: 'Suggested updates are reviewed before application, and the final workspace supports export and review materials.'
    }
  ];

  const audiences = [
    {
      title: 'Founders preparing for fundraising',
      body: 'For teams that need a clearer investor story before active outreach and serious conversations.'
    },
    {
      title: 'Startups approaching angels, seed funds, or VCs',
      body: 'For companies moving from early draft decks to investor-facing materials that need stronger structure.'
    },
    {
      title: 'Consultants and advisors',
      body: 'For people helping companies sharpen decks and investor communication with a more controlled workflow.'
    },
    {
      title: 'Venture teams and portfolio support',
      body: 'For investment teams reviewing or improving founder materials without flattening them into generic slide edits.'
    }
  ];

  const vcValue = [
    {
      title: 'Clarity of the company story',
      body: 'Make the deck easier to understand, discuss, and review quickly.'
    },
    {
      title: 'Consistency across slides',
      body: 'Reduce duplicated, contradictory, or weakly connected slide narratives.'
    },
    {
      title: 'Readiness for investor review',
      body: 'Expose missing information and strengthen the structure before serious review moments.'
    },
    {
      title: 'Speed of iteration with control',
      body: 'Improve design direction, change visibility, and follow-up quality without silent deck rewrites.'
    }
  ];

  const consultationReasons = [
    {
      title: 'Fundraising stage',
      body: 'We need to understand the company’s current financing context and target investor type.'
    },
    {
      title: 'Current deck quality',
      body: 'Some decks need light refinement, while others need deeper restructuring and narrative review.'
    },
    {
      title: 'Timeline and support level',
      body: 'Scope depends on urgency, number of iterations, and how much hands-on guidance is needed.'
    },
    {
      title: 'Fit confirmation',
      body: 'A short consultation confirms whether Deck AIStack is the right fit before any final scope is locked.'
    }
  ];

  const faqs = [
    {
      title: 'Can I pay directly online?',
      body: 'Not for the premium transformation package. This service starts with a consultation so the team can understand the deck, the company, and the required level of support.'
    },
    {
      title: 'Is this only for founders?',
      body: 'No. Deck AIStack also fits advisors, consultants, and venture teams working with portfolio-company decks.'
    },
    {
      title: 'Do I need an existing deck?',
      body: 'Yes. Deck AIStack works best when you already have a PDF or PowerPoint deck that can be transformed into a Smart Deck workspace.'
    },
    {
      title: 'Can you work with my company website and brand?',
      body: 'Yes. The workflow is designed to use your website and brand materials so the deck feels connected to the company, not generic.'
    },
    {
      title: 'Does the system change my deck automatically?',
      body: 'No. Suggested changes should be reviewed before they are accepted. The user stays in control of what is kept, changed, or rejected.'
    },
    {
      title: 'Is this a generic AI presentation tool?',
      body: 'No. Deck AIStack is focused on investor decks, fundraising communication, diligence preparation, and controlled deck improvement.'
    }
  ];
</script>

<div class="marketing-page">
  <MarketingPageHero
    eyebrow="Pricing"
    title="Investor-ready decks, prepared with structure, speed, and precision"
    body="Deck AIStack helps founders, venture teams, and advisors turn existing decks into structured, brand-aware, investor-ready Smart Decks."
    secondaryBody="This is not a generic presentation generator. It is a focused deck transformation workflow for fundraising, diligence, and high-stakes investor communication."
    highlights={[
      { label: 'Starting point', value: 'From £8,000' },
      { label: 'Commercial motion', value: 'Consultation-led' },
      { label: 'Primary output', value: 'Smart Deck transformation' },
      { label: 'Product stance', value: 'Not SaaS self-checkout' }
    ]}
  />

  <section class="panel problem-section">
    <div class="section-copy">
      <div class="eyebrow">The problem we solve</div>
      <h2>Most investor decks do not fail because the company lacks substance.</h2>
      <p class="muted">
        They fail because the story is hard to follow, the evidence is scattered, the visuals are
        inconsistent, or the investor cannot quickly understand what matters.
      </p>
      <p class="muted">
        Deck AIStack helps turn existing materials into a structured Smart Deck that is easier to review,
        improve, and present in serious fundraising conversations.
      </p>
    </div>

    <div class="problem-card">
      <strong>Premium deck transformation starts at £8,000.</strong>
      <p class="muted">
        The next step is a conversation, not a checkout flow. Scope is confirmed after consultation.
      </p>
      <div class="problem-actions">
        <a class="button" href="/contact">Contact us</a>
        <a class="button secondary" href="/#show-interest">Book a consultation</a>
      </div>
    </div>
  </section>

  <MarketingCardGrid
    eyebrow="Built for fundraising and diligence workflows"
    title="Use Deck AIStack when the deck actually matters"
    body="This workflow is designed for serious investor communication rather than generic presentation assembly."
    items={workflowUses}
  />

  <MarketingCardGrid
    eyebrow="What is included"
    title="The premium package includes the full Smart Deck transformation workflow"
    items={included}
  />

  <MarketingCardGrid
    eyebrow="Who this is for"
    title="Best suited for founders, advisors, and venture teams with real review pressure"
    items={audiences}
    columns={2}
  />

  <MarketingCardGrid
    eyebrow="Why VCs and venture teams care"
    title="The goal is not artificial polish. The goal is clearer investor understanding."
    items={vcValue}
    columns={2}
  />

  <section class="pricing-grid">
    <section class="panel package-card">
      <div class="eyebrow">Premium package</div>
      <h2>Smart Deck Transformation</h2>
      <div class="package-price">From £8,000</div>
      <p class="muted">
        For serious fundraising, investor review, and venture-ready deck preparation.
      </p>
      <ul>
        <li>Smart Deck workspace setup</li>
        <li>Existing deck review</li>
        <li>Company website and brand capture</li>
        <li>Investor-readiness structure review</li>
        <li>Slide selection and improvement workflow</li>
        <li>Design iteration preparation</li>
        <li>Change review</li>
        <li>Export-ready materials</li>
        <li>Guided setup and support</li>
      </ul>
      <a class="button" href="/contact">Contact us</a>
      <span class="package-note">Scope confirmed after consultation.</span>
    </section>

    <section class="panel package-copy">
      <div class="eyebrow">Why contact us first?</div>
      <h2>Every deck is different.</h2>
      <p class="muted">
        Some teams need a light design and narrative upgrade. Others need a deeper investor-readiness
        review, restructuring, and multiple design directions.
      </p>
      <div class="package-reasons">
        {#each consultationReasons as reason}
          <article>
            <strong>{reason.title}</strong>
            <p class="muted">{reason.body}</p>
          </article>
        {/each}
      </div>
    </section>
  </section>

  <MarketingCardGrid
    eyebrow="Frequently asked questions"
    title="Common questions before the first consultation"
    items={faqs}
    columns={2}
  />

  <section class="panel final-cta">
    <div>
      <div class="eyebrow">Ready to prepare your investor deck?</div>
      <h2>Start with a consultation.</h2>
      <p class="muted">
        We will review your current deck, understand your fundraising context, and confirm whether
        Deck AIStack is the right fit.
      </p>
    </div>
    <div class="final-cta__actions">
      <a class="button" href="/contact">Contact us</a>
      <a class="button secondary" href="/#show-interest">Discuss your deck</a>
    </div>
  </section>
</div>

<style>
  .marketing-page {
    display: grid;
    gap: 4.5rem;
  }

  .problem-section,
  .pricing-grid,
  .final-cta {
    padding: clamp(2rem, 3vw, 3.5rem) clamp(1.8rem, 3vw, 3.5rem);
  }

  .problem-section {
    display: grid;
    grid-template-columns: minmax(0, 1.1fr) minmax(280px, 0.9fr);
    gap: 1.35rem;
    align-items: stretch;
  }

  .section-copy,
  .package-copy {
    display: grid;
    gap: 0.85rem;
    align-content: start;
  }

  .section-copy h2,
  .package-copy h2,
  .package-card h2,
  .final-cta h2 {
    margin: 0;
  }

  .problem-card,
  .package-card {
    border: 1px solid rgba(148, 163, 184, 0.18);
    border-radius: var(--radius-card);
    background:
      radial-gradient(circle at 85% 15%, rgba(240, 84, 197, 0.06), transparent 35%),
      radial-gradient(circle at 15% 85%, rgba(78, 122, 255, 0.06), transparent 35%),
      linear-gradient(135deg, rgba(17, 31, 63, 0.95), rgba(11, 22, 48, 0.98));
    padding: 1.6rem;
    display: grid;
    gap: 1rem;
    align-content: start;
    box-shadow:
      0 20px 50px rgba(0, 0, 0, 0.2),
      inset 0 1px 0 rgba(255, 255, 255, 0.04);
  }

  .problem-card strong,
  .package-price {
    font-size: clamp(1.45rem, 2.2vw, 2rem);
    letter-spacing: -0.04em;
    color: #f8fbff;
  }

  .problem-actions,
  .final-cta__actions {
    display: flex;
    gap: 0.85rem;
    flex-wrap: wrap;
    padding-top: 0.5rem;
  }

  .pricing-grid {
    display: grid;
    grid-template-columns: minmax(320px, 0.85fr) minmax(0, 1.15fr);
    gap: 1.35rem;
    align-items: stretch;
  }

  .package-card ul {
    margin: 0;
    padding-left: 1rem;
    display: grid;
    gap: 0.6rem;
    color: rgba(223, 232, 248, 0.8);
  }

  .package-card li::marker {
    color: var(--accent);
  }

  .package-note {
    color: var(--text-muted);
    font-size: 0.85rem;
  }

  .package-copy {
    border: 1px solid rgba(148, 163, 184, 0.15);
    border-radius: var(--radius-card);
    background:
      radial-gradient(circle at 80% 20%, rgba(78, 122, 255, 0.05), transparent 35%),
      rgba(11, 22, 48, 0.95);
    padding: 1.6rem;
    box-shadow: 0 16px 40px rgba(0, 0, 0, 0.15);
  }

  .package-reasons {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 1rem;
  }

  .package-reasons article {
    border: 1px solid rgba(148, 163, 184, 0.12);
    border-radius: var(--radius-md);
    background: rgba(255, 255, 255, 0.03);
    padding: 1.1rem;
    display: grid;
    gap: 0.5rem;
    transition: border-color 0.15s ease, background 0.15s ease;
  }

  .package-reasons article:hover {
    border-color: rgba(148, 163, 184, 0.22);
    background: rgba(255, 255, 255, 0.05);
  }

  .package-reasons p {
    margin: 0;
    color: rgba(223, 232, 248, 0.75);
    font-size: 0.875rem;
    line-height: 1.55;
  }

  .final-cta {
    display: flex;
    justify-content: space-between;
    gap: 1.35rem;
    align-items: end;
    border-radius: var(--radius-xl);
    background:
      radial-gradient(circle at 20% 50%, rgba(48, 154, 255, 0.12), transparent 35%),
      radial-gradient(circle at 80% 50%, rgba(255, 82, 168, 0.08), transparent 35%),
      linear-gradient(180deg, rgba(6, 13, 30, 0.98), rgba(2, 6, 23, 1));
    border: 1px solid rgba(148, 163, 184, 0.15);
    box-shadow: 0 24px 60px rgba(0, 0, 0, 0.25);
  }

  .final-cta p {
    color: rgba(223, 232, 248, 0.78);
    margin: 0.5rem 0 0;
  }

  @media (max-width: 980px) {
    .problem-section,
    .pricing-grid,
    .package-reasons {
      grid-template-columns: 1fr;
    }

    .final-cta {
      flex-direction: column;
      align-items: start;
    }
  }
</style>
