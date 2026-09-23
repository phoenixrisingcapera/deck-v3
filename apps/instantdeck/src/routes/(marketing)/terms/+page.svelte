<script lang="ts">
  import MarketingCardGrid from '$lib/components/marketing/MarketingCardGrid.svelte';
  import MarketingPageHero from '$lib/components/marketing/MarketingPageHero.svelte';

  const sections = [
    {
      title: 'Product position',
      body: 'Deck AIStack is an AI diligence deck adaptation platform for investor and advisory workflows, not a generic public document editor.'
    },
    {
      title: 'User responsibility',
      body: 'Users are responsible for the decks, brand materials, and company data they upload or connect into the system.'
    },
    {
      title: 'Reviewability rule',
      body: 'The product is designed around reviewable suggestions, but the user remains responsible for deciding whether to accept, reject, or export any output.'
    }
  ];
</script>

<section class="marketing-container">
  <div class="marketing-page">
    <MarketingPageHero
      eyebrow="Terms"
      title="Terms of service"
      body="This page describes the current operating terms for the preview-stage marketing funnel and the product workflow."
      secondaryBody="It is implementation-stage legal copy, but it now reflects how the current product experience is intended to work."
      highlights={[
        { label: 'Product category', value: 'Workflow platform' },
        { label: 'Primary material', value: 'User deck data' },
        { label: 'AI output rule', value: 'Review before apply' },
        { label: 'Scope', value: 'Marketing and app use' }
      ]}
    />

    <MarketingCardGrid
      eyebrow="Current terms themes"
      title="The main usage expectations reflected by the current build"
      items={sections}
    />
  </div>
</section>

<style>
  .marketing-page {
    display: grid;
    gap: 1.1rem;
  }

  .marketing-container :global(.panel) {
    width: 100%;
  }

  .marketing-container {
    display: grid;
    gap: 1rem;
  }
</style>
