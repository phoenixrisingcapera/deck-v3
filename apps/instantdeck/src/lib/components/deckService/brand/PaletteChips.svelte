<!-- Purpose: displays the first few brand palette swatches for quick visual review. -->
<script lang="ts">
  import type { BrandPaletteSwatch } from '$lib/types/deckService-brand';

  let { palette }: { palette: BrandPaletteSwatch[] } = $props();
</script>

<div class="swatch-bar">
  {#each palette as swatch}
    <div class="swatch">
      <span style={`background:${swatch.value}`}></span>
      <small>{swatch.label}</small>
    </div>
  {/each}
</div>

<style>
  .swatch-bar {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
  }

  .swatch {
    display: grid;
    gap: 0.35rem;
    justify-items: center;
  }

  .swatch span {
    width: 2.1rem;
    min-height: 2.1rem;
    border-radius: 12px;
    border: 1px solid rgba(255, 255, 255, 0.12);
  }

  .swatch small {
    color: var(--muted);
    font-size: 0.72rem;
  }
</style>
