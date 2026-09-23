<script lang="ts">
  import HeroSection from '$lib/components/marketing/HeroSection.svelte';
  import HowItWorksSection from '$lib/components/marketing/HowItWorksSection.svelte';
  import ComparisonSection from '$lib/components/marketing/ComparisonSection.svelte';
  import ProductPreviewSection from '$lib/components/marketing/ProductPreviewSection.svelte';
  import ForVCsSection from '$lib/components/marketing/ForVCsSection.svelte';
  import UseCaseStrip from '$lib/components/marketing/UseCaseStrip.svelte';
  import ShowInterestForm from '$lib/components/marketing/ShowInterestForm.svelte';
</script>

<div class="marketing-page">
  <HeroSection />
  <div class="section-divider" aria-hidden="true"></div>
  <HowItWorksSection />
  <div class="section-divider" aria-hidden="true"></div>
  <ComparisonSection />
  <div class="section-divider" aria-hidden="true"></div>
  <ProductPreviewSection />
  <div class="section-divider" aria-hidden="true"></div>
  <ForVCsSection />
  <UseCaseStrip />
  <ShowInterestForm />
</div>

<style>
  .marketing-page {
    display: grid;
    gap: 4.5rem;
  }

  .section-divider {
    width: 100%;
    height: 1px;
    background: linear-gradient(
      90deg,
      transparent,
      rgba(148, 163, 184, 0.18) 20%,
      rgba(148, 163, 184, 0.24) 50%,
      rgba(148, 163, 184, 0.18) 80%,
      transparent
    );
    margin: 0.5rem 0;
  }
</style>
