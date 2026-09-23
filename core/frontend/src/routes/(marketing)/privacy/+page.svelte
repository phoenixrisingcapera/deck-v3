<script lang="ts">
  import MarketingCardGrid from '$lib/components/marketing/MarketingCardGrid.svelte';
  import MarketingPageHero from '$lib/components/marketing/MarketingPageHero.svelte';

  const sections = [
    {
      title: 'Public-site information',
      body: 'The public site may collect lead-intake data such as email, company name, role, use case, and message when someone submits the Show Interest form.'
    },
    {
      title: 'API keys',
      body: 'If you add an OpenAI, OpenRouter, or Claude API key, Deck AIStack sends a small live connection check before saving it, encrypts the key before storage, and uses it only to run AI features for your signed-in workspace. We do not display the full key back to you after save; product and admin views only show safe credential state such as provider, model, last four characters, timestamps, and whether the key is active or revoked. You can replace or revoke a saved workspace key.'
    },
    {
      title: 'Operational product data',
      body: 'Uploaded decks, review notes, suggestions, iterations, and export history are treated as protected workspace data.'
    }
  ];
</script>

<section class="marketing-container">
  <div class="marketing-page">
    <MarketingPageHero
      eyebrow="Privacy"
      title="Privacy policy"
      body="This page explains the current operating privacy position for the marketing funnel and the signed-in Deck AIStack workflow."
      secondaryBody="It is still an implementation-stage policy page, but it now reflects the real handling rules used in the product build."
      highlights={[
        { label: 'Lead intake', value: 'Structured and explicit' },
        { label: 'AI access', value: 'Encrypted before storage' },
        { label: 'Raw secret return', value: 'Never returned' },
        { label: 'Product data', value: 'Deck workflow history' }
      ]}
    />

    <MarketingCardGrid
      eyebrow="Current handling"
      title="What the platform currently stores and protects"
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
