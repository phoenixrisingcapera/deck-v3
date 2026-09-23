<script lang="ts">
  import HeroSection from '$lib/components/marketing/HeroSection.svelte';
  import HowItWorksSection from '$lib/components/marketing/HowItWorksSection.svelte';
  import ComparisonSection from '$lib/components/marketing/ComparisonSection.svelte';
  import ShowInterestForm from '$lib/components/marketing/ShowInterestForm.svelte';
</script>

<div class="marketing-page">
  <section class="panel about-hero">
    <div class="about-hero__copy">
      <div class="eyebrow">About Deck AIStack</div>
      <h1 class="display">Built for diligence adaptation, not generic slide generation.</h1>
      <p class="about-hero__body">
        Deck AIStack is designed for venture, advisory, and strategic review workflows where the uploaded deck remains the source of truth and every AI suggestion must be reviewable before it changes content.
      </p>
      <p class="about-hero__body">
        That means structured slides, editable blocks, classification, analysis, audience adaptation, Smart Edit, change review, and export all operate as one controlled workflow.
      </p>
      <div class="about-hero__actions">
        <a class="button" href="/#show-interest">Talk to Deck AIStack</a>
        <a class="button secondary" href="/auth/sign-in">Sign in</a>
      </div>
    </div>

    <div class="about-hero__stats">
      <article>
        <span>Source of truth</span>
        <strong>Uploaded deck</strong>
      </article>
      <article>
        <span>AI behaviour</span>
        <strong>Reviewable suggestions</strong>
      </article>
      <article>
        <span>Primary users</span>
        <strong>VC, advisory, investment</strong>
      </article>
      <article>
        <span>Output style</span>
        <strong>Investor-grade adaptation</strong>
      </article>
    </div>
  </section>

  <section class="panel principles-section">
    <div class="section-intro">
      <div class="eyebrow">Core principles</div>
      <h2>What the product is actually designed to do</h2>
      <p class="muted">
        Deck AIStack is opinionated about reviewability, provenance, and investor workflow control.
      </p>
    </div>

    <div class="principles-grid">
      <article>
        <strong>Deck-first system</strong>
        <p>The uploaded deck remains the source of truth. Deck AIStack adapts from that material instead of starting from a blank prompt.</p>
      </article>
      <article>
        <strong>Block-level intelligence</strong>
        <p>Slides become structured editable blocks that can be classified, reviewed, and traced through the workflow.</p>
      </article>
      <article>
        <strong>Review before apply</strong>
        <p>Smart Edit, adaptation, and analysis outputs are presented as reviewable suggestions rather than silent overwrites.</p>
      </article>
    </div>
  </section>

  <HowItWorksSection />

  <section class="panel workflow-section">
    <div class="section-intro">
      <div class="eyebrow">Workflow</div>
      <h2>One controlled system from upload to export</h2>
      <p class="muted">
        The product is shaped as a connected operational flow, not as isolated AI features.
      </p>
    </div>

    <div class="workflow-grid">
      <article>
        <strong>Parse and structure</strong>
        <p>Upload PDF or PowerPoint material and turn the deck into reviewable slides, sections, and source-linked context.</p>
      </article>
      <article>
        <strong>Classify and analyse</strong>
        <p>Classify each block, identify diligence gaps, and generate findings tied to the real deck structure.</p>
      </article>
      <article>
        <strong>Adapt and export</strong>
        <p>Create audience-specific versions, review edits, and export investor-ready outputs once changes are approved.</p>
      </article>
    </div>
  </section>

  <ComparisonSection />
  <ShowInterestForm />
</div>

<style>
  .marketing-page {
    display: grid;
    gap: 4rem;
  }

  .about-hero {
    padding: clamp(2rem, 3vw, 3.5rem) clamp(1.8rem, 3vw, 3.5rem);
    display: grid;
    grid-template-columns: minmax(0, 1.1fr) minmax(280px, 0.9fr);
    gap: 2rem;
    align-items: center;
  }

  .about-hero__copy {
    display: grid;
    gap: 1.15rem;
    align-content: start;
  }

  .about-hero__copy h1 {
    font-size: clamp(2rem, 3.5vw, 3rem);
    max-width: 18ch;
  }

  .about-hero__body {
    margin: 0;
    color: var(--text-secondary);
    line-height: 1.65;
    max-width: 48ch;
  }

  .about-hero__actions {
    display: flex;
    gap: 0.85rem;
    flex-wrap: wrap;
  }

  .about-hero__stats {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 1.1rem;
  }

  .about-hero__stats article {
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    background: var(--surface);
    padding: 1.15rem;
    display: grid;
    gap: 0.55rem;
    transition: transform 180ms ease, box-shadow 180ms ease;
  }

  .about-hero__stats article:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 20px rgba(0, 0, 0, 0.12);
  }

  .about-hero__stats span {
    color: var(--text-secondary);
    font-size: 0.82rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }

  .about-hero__stats strong {
    font-size: 1.1rem;
    color: var(--text);
  }

  .principles-section,
  .workflow-section {
    padding: clamp(2rem, 3vw, 3.5rem) clamp(1.8rem, 3vw, 3.5rem);
  }

  .section-intro {
    display: grid;
    gap: 0.85rem;
    max-width: 48rem;
    margin-bottom: 1.75rem;
  }

  .section-intro h2 {
    margin: 0;
  }

  .principles-grid,
  .workflow-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 1.15rem;
  }

  .principles-grid article,
  .workflow-grid article {
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    background: var(--surface);
    padding: 1.4rem;
    display: grid;
    gap: 0.85rem;
    transition: transform 180ms ease, box-shadow 180ms ease;
  }

  .principles-grid article:hover,
  .workflow-grid article:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 20px rgba(0, 0, 0, 0.12);
  }

  .principles-grid p,
  .workflow-grid p {
    margin: 0;
    color: var(--text-secondary);
    line-height: 1.6;
  }

  @media (max-width: 960px) {
    .about-hero,
    .principles-grid,
    .workflow-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
