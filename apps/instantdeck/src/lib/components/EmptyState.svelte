<script lang="ts">
  interface Props {
    eyebrow?: string;
    title: string;
    message: string;
    primaryHref?: string;
    primaryLabel?: string;
    secondaryHref?: string;
    secondaryLabel?: string;
  }

  let {
    eyebrow = 'Empty state',
    title,
    message,
    primaryHref = '/decks/new',
    primaryLabel = 'Upload first deck',
    secondaryHref = '/templates',
    secondaryLabel = 'Browse templates'
  }: Props = $props();
</script>

<section class="panel empty-state">
  <div class="eyebrow">{eyebrow}</div>
  <h2>{title}</h2>
  <p class="muted">{message}</p>
  <div class="empty-state__actions">
    <a class="button" href={primaryHref}>{primaryLabel}</a>
    <a class="button secondary" href={secondaryHref}>{secondaryLabel}</a>
  </div>
</section>

<style>
  .empty-state {
    padding: 1.4rem;
    display: grid;
    gap: 0.9rem;
  }

  h2 {
    margin: 0;
    font-size: clamp(1.5rem, 2vw, 2rem);
    letter-spacing: -0.04em;
  }

  .empty-state__actions {
    display: flex;
    gap: 0.8rem;
    flex-wrap: wrap;
  }
</style>
