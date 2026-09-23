<!--
  A trigger-pack component. Nothing in @flave/render knows this file exists —
  it becomes syntax purely by being registered in the `packs` map in App.svelte.
  That one-line registration IS the extensibility story at v0.
-->
<script lang="ts">
  let { value, label }: { value?: string; label?: string } = $props();
</script>

<div class="metric-card">
  <span class="metric-card__value">{value}</span>
  <span class="metric-card__label">{label}</span>
</div>

<style>
  .metric-card {
    display: inline-flex;
    flex-direction: column;
    gap: 0.15rem;
    padding: 0.9rem 1.2rem;
    border: 1px solid var(--color-border-strong);
    border-left: 3px solid var(--color-accent);
    background: var(--color-bg-raised);
  }
  .metric-card__value {
    font-size: 1.75rem;
    font-weight: 700;
    line-height: 1;
    color: var(--color-text);
  }
  .metric-card__label {
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--color-text-dim);
  }
</style>
