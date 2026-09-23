<!-- A second trigger-pack, registered as a LEAF directive (`::badge{...}`) so
     the demo exercises both directive shapes, not just containers. -->
<script lang="ts">
  let { label, tone = 'neutral' }: { label?: string; tone?: string } = $props();
</script>

<span class="badge" data-tone={tone}>{label}</span>

<style>
  .badge {
    --t: var(--color-tone-neutral);
    display: inline-block;
    padding: 1px var(--space-2);
    border: 1px solid var(--t);
    border-radius: var(--radius-pill);
    font-family: var(--font__mono);
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--t);
  }
  .badge[data-tone='info'] { --t: var(--color-tone-info); }
  .badge[data-tone='warning'] { --t: var(--color-tone-warning); }
  .badge[data-tone='danger'] { --t: var(--color-tone-danger); }
</style>
