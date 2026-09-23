<script lang="ts">
  import CTASection from '$lib/components/marketing/CTASection.svelte';
</script>

<div class="marketing-page billing-page">
  <section class="panel page-copy">
    <div class="eyebrow">Billing</div>
    <h1>Commercial packaging for investor-grade review workflows.</h1>
    <p class="muted">
      Public billing explains plan packaging before a visitor becomes a full user. Workspace subscriptions
      and invoices remain part of the signed-in app shell.
    </p>
  </section>

  <section class="plan-grid">
    <article class="panel plan-card">
      <div class="eyebrow">Starter</div>
      <h2>$0<span>/month</span></h2>
      <p class="muted">For early evaluation, public interest capture, and product exploration.</p>
    </article>
    <article class="panel plan-card featured">
      <div class="eyebrow">Pro</div>
      <h2>$149<span>/month</span></h2>
      <p class="muted">For solo investors and operators using Smart Deck, Smart Edit, and exports.</p>
    </article>
    <article class="panel plan-card">
      <div class="eyebrow">Team</div>
      <h2>Custom</h2>
      <p class="muted">For partner teams, IC prep flows, and shared diligence review operations.</p>
    </article>
  </section>

  <CTASection />
</div>

<style>
  .billing-page {
    display: grid;
    gap: 1rem;
  }

  .page-copy {
    padding: 1.35rem;
  }

  .plan-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 1rem;
  }

  .plan-card {
    padding: 1.35rem;
    display: grid;
    gap: 0.8rem;
  }

  .plan-card h2 {
    margin: 0;
    font-size: clamp(2rem, 3vw, 3rem);
    letter-spacing: -0.05em;
  }

  .plan-card span {
    margin-left: 0.25rem;
    font-size: 1rem;
    color: var(--muted);
  }

  .featured {
    box-shadow: var(--shadow), var(--shadow-glow-blue);
  }

  @media (max-width: 960px) {
    .plan-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
