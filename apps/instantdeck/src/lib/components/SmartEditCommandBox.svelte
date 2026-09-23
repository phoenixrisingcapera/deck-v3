<script lang="ts">
  interface Props {
    deckId: string;
    slideId: string;
    blockId?: string;
    selectedText?: string;
  }

  let { deckId, slideId, blockId = '', selectedText = '' }: Props = $props();
  const audienceType = 'investment_committee';
  const examplePrompts = [
    'Make this more suitable for Investment Committee.',
    'Make this more precise and less founder-hype.',
    'Rewrite this for a strategic investor.',
    'Flag unsupported claims.',
    'Strengthen the diligence logic.',
    'Shorten this slide.',
    'Rewrite in a JPMorgan-style advisory tone.'
  ];
</script>

<form class="panel command-box" method="POST" action={`/api/decks/${deckId}/slides/${slideId}/smart-edit/patch`}>
  <input type="hidden" name="blockId" value={blockId} />
  <input type="hidden" name="audienceType" value={audienceType} />
  <!-- DISABLED: the legacy /api/decks/{deckId}/smart-edit generation route is
       being retired in favor of the canonical slide-scoped patch workflow. -->
  <!-- <input type="hidden" name="slideId" value={slideId} /> -->
  <div class="eyebrow">Smart Edit</div>
  <p class="muted">Every suggestion is reviewable before apply. The deck is never silently overwritten.</p>
  <textarea
    name="instruction"
    rows="4"
    placeholder="Make this more suitable for Investment Committee."
    required
    disabled={!blockId}
  ></textarea>
  <div class="selected-block">
    <strong>Selected block</strong>
    <p>{selectedText || 'Choose a slide block to enable Smart Edit.'}</p>
  </div>
  <div class="examples">
    {#each examplePrompts as prompt}
      <span class="pill">{prompt}</span>
    {/each}
  </div>
  <button class="button" type="submit" disabled={!blockId}>Generate suggestion</button>
</form>

<style>
  .command-box {
    display: grid;
    gap: 0.9rem;
    padding: 1rem;
    background:
      radial-gradient(circle at top right, rgba(104, 161, 255, 0.12), transparent 30%),
      rgba(255,255,255,0.03);
  }

  textarea {
    resize: vertical;
    border-radius: var(--radius-sm);
    border: 1px solid var(--line-strong);
    padding: 0.9rem;
    background: rgba(255, 255, 255, 0.04);
    color: var(--ink);
  }

  .examples {
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
  }

  .selected-block {
    border-radius: var(--radius-sm);
    padding: 0.85rem;
    background: rgba(255, 255, 255, 0.04);
  }

  .selected-block p {
    margin: 0.4rem 0 0;
  }
</style>
