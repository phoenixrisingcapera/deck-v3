<script lang="ts">
  import StatusBadge from '$components/StatusBadge.svelte';

  interface Props {
    title: string;
    sourceType?: string;
    originalText?: string;
    suggestedText: string;
    finalText?: string | null;
    reason?: string;
    riskLevel?: string;
    status: string;
    saving?: boolean;
    editHref?: string | null;
    onAccept?: () => void;
    onReject?: () => void;
  }

  let {
    title,
    sourceType = 'reviewable change',
    originalText = '',
    suggestedText,
    finalText = null,
    reason = '',
    riskLevel = 'medium',
    status,
    saving = false,
    editHref = null,
    onAccept,
    onReject
  }: Props = $props();
</script>

<article class="review-card">
  <div class="topline">
    <div>
      <strong>{title}</strong>
      <p class="meta">{sourceType} · risk {riskLevel}</p>
    </div>
    <StatusBadge {status} />
  </div>
  {#if originalText}
    <div class="comparison">
      <div>
        <span class="label">Original</span>
        <p class="text">{originalText}</p>
      </div>
      <div>
        <span class="label">Suggested</span>
        <p class="text">{suggestedText}</p>
      </div>
    </div>
  {:else}
    <p class="text">{suggestedText}</p>
  {/if}
  {#if finalText}
    <div class="final-state">
      <span class="label">Final text</span>
      <p class="text">{finalText}</p>
    </div>
  {/if}
  {#if reason}
    <p class="reason">{reason}</p>
  {/if}
  <div class="actions">
    <button class="button" type="button" onclick={onAccept} disabled={saving || status === 'accepted' || status === 'applied'}>
      {saving ? 'Saving...' : status === 'accepted' || status === 'applied' ? 'Accepted' : 'Accept'}
    </button>
    <button class="button secondary" type="button" onclick={onReject} disabled={saving || status === 'rejected'}>
      {saving ? 'Saving...' : status === 'rejected' ? 'Rejected' : 'Reject'}
    </button>
    {#if editHref}
      <a class="button tertiary" href={editHref} aria-disabled={saving}>Edit first</a>
    {:else}
      <button class="button tertiary" type="button" disabled={saving}>Edit first</button>
    {/if}
  </div>
</article>

<style>
  .review-card {
    border-radius: 18px;
    border: 1px solid var(--line);
    background: rgba(255,255,255,0.03);
    padding: 1rem;
    display: grid;
    gap: 0.75rem;
  }

  .topline,
  .actions {
    display: flex;
    justify-content: space-between;
    gap: 0.75rem;
    flex-wrap: wrap;
  }

  .reason {
    margin: 0;
    color: var(--muted);
  }

  .meta,
  .label {
    margin: 0.2rem 0 0;
    color: var(--muted);
    font-size: 0.82rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }

  .comparison {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.85rem;
  }

  .comparison > div,
  .final-state {
    border: 1px solid var(--line);
    border-radius: 14px;
    background: rgba(255,255,255,0.03);
    padding: 0.85rem;
  }

  .text {
    margin: 0;
    line-height: 1.6;
  }

  .tertiary {
    background: rgba(255,255,255,0.04);
    color: var(--ink-soft);
  }

  @media (max-width: 720px) {
    .comparison {
      grid-template-columns: 1fr;
    }
  }
</style>
