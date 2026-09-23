<script lang="ts">
  import AppLogo from '$components/AppLogo.svelte';
  import UtilitiesBar from '$components/UtilitiesBar.svelte';

  interface Props {
    compact?: boolean;
  }

  let { compact = false }: Props = $props();
</script>

<section class="app-shell__footer-utilities" class:app-shell__footer-utilities--compact={compact} aria-label="Product utilities">
  <UtilitiesBar placement="footer" />
  {#if compact}
    <nav class="workspace-footer-links" aria-label="Product information">
      <a href="/privacy">Privacy</a>
      <a href="/terms">Terms</a>
    </nav>
  {/if}
</section>

{#if !compact}
<footer class="product-footer" aria-label="Product footer">
  <div class="product-footer__inner">
    <a class="product-footer__brand" href="/dashboard" aria-label="Deck dashboard">
      <AppLogo class="product-footer__logo" size="sm" alt="" />
      <strong>Deck</strong>
    </a>

    <p class="product-footer__descriptor">
      <span class="product-footer__signal" aria-hidden="true"></span>
      AI presentation workspace
    </p>

    <small class="product-footer__legal">
      <span class="product-footer__legal-full">© 2026 AIStack. All rights reserved.</span>
      <span class="product-footer__legal-compact">© 2026 AIStack</span>
    </small>

    <nav class="product-footer__links" aria-label="Product information">
      <a href="/app/billing">Billing</a>
      <a href="/privacy">Privacy</a>
      <a href="/terms">Terms</a>
    </nav>
  </div>
</footer>
{/if}
