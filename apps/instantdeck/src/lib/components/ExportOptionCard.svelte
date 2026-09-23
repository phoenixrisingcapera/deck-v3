<script lang="ts">
  interface Props {
    title: string;
    detail: string;
    state?: 'idle' | 'selected' | 'ready';
  }

  let { title, detail, state = 'idle' }: Props = $props();
</script>

<article class={`export-card ${state}`}>
  <div class="eyebrow">Output</div>
  <h3>{title}</h3>
  <p>{detail}</p>
  <span class={`export-card__status ${state === 'selected' ? 'export-card__status--selected' : ''}`}>
    {state === 'ready' ? 'Generated' : state === 'selected' ? 'Selected' : 'Select'}
  </span>
</article>

<style>
  .export-card {
    border-radius: 20px;
    border: 1px solid var(--line);
    background: rgba(255,255,255,0.03);
    padding: 1rem;
    display: grid;
    gap: 0.65rem;
  }

  .export-card.selected {
    border-color: rgba(104, 161, 255, 0.3);
    background: rgba(104, 161, 255, 0.08);
  }

  .export-card.ready {
    border-color: rgba(84, 179, 126, 0.25);
  }

  h3,
  p {
    margin: 0;
  }

  p {
    color: var(--muted);
  }

  .export-card__status {
    display: inline-flex;
    justify-self: start;
    align-items: center;
    border-radius: 999px;
    border: 1px solid var(--line);
    padding: 0.45rem 0.75rem;
    color: var(--muted);
    font-size: 0.78rem;
    font-weight: 700;
  }

  .export-card__status--selected {
    color: var(--text);
    border-color: var(--line-strong);
  }
</style>
