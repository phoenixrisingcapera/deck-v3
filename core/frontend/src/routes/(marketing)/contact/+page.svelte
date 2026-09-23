<script lang="ts">
  import CTASection from '$lib/components/marketing/CTASection.svelte';
  import MarketingCardGrid from '$lib/components/marketing/MarketingCardGrid.svelte';
  import MarketingPageHero from '$lib/components/marketing/MarketingPageHero.svelte';

  const contactOptions = [
    {
      title: 'Pilot inquiries',
      body: 'For funds, advisory firms, or review teams evaluating Deck AIStack in a real operating workflow.'
    },
    {
      title: 'Product walkthroughs',
      body: 'For buyers who want to understand Smart Deck intake, review flow, and workspace setup before rollout.'
    },
    {
      title: 'Deployment questions',
      body: 'For teams assessing security, rollout options, and how Deck AIStack fits their operating workflow.'
    }
  ];

  const nextSteps = [
    {
      title: 'Use the Show Interest form',
      body: 'The fastest path is still the structured intake on the home page because it captures role, company, and use case.'
    },
    {
      title: 'Prepare the source deck',
      body: 'The best first conversation starts with a real PDF or PowerPoint workflow rather than a generic product tour.'
    }
  ];
</script>

<div class="marketing-page">
  <MarketingPageHero
    eyebrow="Contact"
    title="Pilot and product inquiries"
    body="Use this page for sales, pilot, and diligence workflow onboarding contact details."
    secondaryBody="If you are evaluating Deck AIStack for a fund, advisory practice, or internal review team, the fastest path is the Show Interest form on the homepage."
    highlights={[
      { label: 'Best first step', value: 'Show Interest intake' },
      { label: 'Audience', value: 'Funds and advisory teams' },
      { label: 'Conversation type', value: 'Pilot and workflow fit' },
      { label: 'Follow-up', value: 'Structured commercial review' }
    ]}
  />

  <MarketingCardGrid
    eyebrow="Contact options"
    title="What this page is for"
    items={contactOptions}
  />

  <MarketingCardGrid
    eyebrow="Next steps"
    title="How to make the conversation more useful"
    items={nextSteps}
    columns={2}
  />

  <CTASection />
</div>

<style>
  .marketing-page {
    display: grid;
    gap: 4rem;
  }
</style>
