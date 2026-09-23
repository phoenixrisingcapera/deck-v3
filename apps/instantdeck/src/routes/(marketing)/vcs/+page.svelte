<script lang="ts">
  import HeroSection from '$lib/components/marketing/HeroSection.svelte';
  import HowItWorksSection from '$lib/components/marketing/HowItWorksSection.svelte';
  import ForVCsSection from '$lib/components/marketing/ForVCsSection.svelte';
  import UseCaseStrip from '$lib/components/marketing/UseCaseStrip.svelte';
  import ShowInterestForm from '$lib/components/marketing/ShowInterestForm.svelte';
</script>

<div class="marketing-page">
  <section class="panel vcs-hero">
    <div class="vcs-hero__copy">
      <div class="eyebrow">For VCs</div>
      <h1 class="display">Deck AIStack is for venture teams that need a better deck workflow, not just better slide cosmetics.</h1>
      <p>
        The product helps funds turn founder decks into structured, reviewable diligence workspaces, then create
        controlled investor-facing iterations for partner review, IC discussion, and strategic follow-up.
      </p>
      <div class="vcs-hero__actions">
        <a class="button" href="/#show-interest">Talk to Deck AIStack</a>
        <a class="button secondary" href="/auth/sign-in">Sign in</a>
      </div>
    </div>

    <div class="vcs-hero__panel">
      <article>
        <span class="eyebrow">What changes</span>
        <strong>The deck stops being a file and becomes an operating surface.</strong>
        <ul>
          <li>slide context is structured</li>
          <li>evidence gaps are surfaced</li>
          <li>AI versions stay reviewable</li>
          <li>the original founder source remains intact</li>
        </ul>
      </article>
    </div>
  </section>

  <ForVCsSection />
  <UseCaseStrip />
  <HowItWorksSection />

  <section class="panel value-section">
    <div class="section-intro">
      <div class="eyebrow">Why it matters</div>
      <h2>Why this is more useful to a fund than generic AI presentation software.</h2>
    </div>
    <div class="value-grid">
      <article>
        <strong>The deck becomes workflow state</strong>
        <p>Instead of bouncing between PDF comments, memos, and chat threads, the review work stays attached to the actual deck.</p>
      </article>
      <article>
        <strong>AI output stays reviewable</strong>
        <p>Generated changes are versioned, compareable, and reversible before anyone applies them.</p>
      </article>
      <article>
        <strong>Investor logic is explicit</strong>
        <p>The product is designed around how venture teams read a deck, not around generic presentation generation.</p>
      </article>
    </div>
  </section>

  <section class="panel operating-panel">
    <div class="section-intro">
      <div class="eyebrow">Operating model</div>
      <h2>The product is built around review control, not blind generation.</h2>
    </div>
    <div class="operating-list">
      <div class="operating-list__item">
        <span>01</span>
        <strong>existing founder deck as the source asset</strong>
      </div>
      <div class="operating-list__item">
        <span>02</span>
        <strong>structured Smart Deck workspace for review</strong>
      </div>
      <div class="operating-list__item">
        <span>03</span>
        <strong>VC task-guided redesign controls</strong>
      </div>
      <div class="operating-list__item">
        <span>04</span>
        <strong>iteration history for selected-slide versions</strong>
      </div>
      <div class="operating-list__item">
        <span>05</span>
        <strong>apply/discard/export only after review</strong>
      </div>
    </div>
  </section>

  <ShowInterestForm />
</div>

<style>
  .marketing-page {
    display: grid;
    gap: 4rem;
  }

  .vcs-hero {
    padding: clamp(2rem, 3vw, 3.5rem) clamp(1.8rem, 3vw, 3.5rem);
    display: grid;
    grid-template-columns: minmax(0, 1.1fr) minmax(300px, 0.9fr);
    gap: 2rem;
    align-items: center;
  }

  .vcs-hero__copy {
    display: grid;
    gap: 1.15rem;
  }

  .vcs-hero__copy h1 {
    font-size: clamp(2rem, 3.5vw, 3rem);
    max-width: 18ch;
  }

  .vcs-hero__copy p {
    margin: 0;
    color: var(--text-secondary);
    line-height: 1.65;
  }

  .vcs-hero__actions {
    display: flex;
    gap: 0.85rem;
    flex-wrap: wrap;
  }

  .vcs-hero__panel article {
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    background: var(--surface);
    padding: 1.6rem;
    display: grid;
    gap: 1.1rem;
    transition: transform 180ms ease, box-shadow 180ms ease;
  }

  .vcs-hero__panel article:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 20px rgba(0, 0, 0, 0.12);
  }

  .vcs-hero__panel strong {
    color: var(--text);
    font-size: 1.1rem;
  }

  .vcs-hero__panel ul {
    margin: 0;
    padding-left: 1.25rem;
    color: var(--text-secondary);
    display: grid;
    gap: 0.55rem;
  }

  .value-section,
  .operating-panel {
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

  .value-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 1.15rem;
  }

  .value-grid article {
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    background: var(--surface);
    padding: 1.4rem;
    display: grid;
    gap: 0.85rem;
    transition: transform 180ms ease, box-shadow 180ms ease;
  }

  .value-grid article:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 20px rgba(0, 0, 0, 0.12);
  }

  .value-grid p {
    margin: 0;
    color: var(--text-secondary);
    line-height: 1.6;
  }

  .operating-list {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 1.15rem;
  }

  .operating-list__item {
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    background: var(--surface);
    padding: 1.4rem;
    display: grid;
    gap: 0.85rem;
    transition: transform 180ms ease, box-shadow 180ms ease;
  }

  .operating-list__item:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 20px rgba(0, 0, 0, 0.12);
  }

  .operating-list__item span {
    color: var(--accent);
    font-weight: 700;
    font-size: 1.5rem;
  }

  .operating-list__item strong {
    color: var(--text);
    font-size: 0.95rem;
    line-height: 1.4;
  }

  @media (max-width: 960px) {
    .vcs-hero,
    .value-grid,
    .operating-list {
      grid-template-columns: 1fr;
    }
  }
</style>
