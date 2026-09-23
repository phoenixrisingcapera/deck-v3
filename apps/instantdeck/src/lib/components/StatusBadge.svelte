<script lang="ts">
  interface Props {
    status: string;
    tone?: 'default' | 'success' | 'warn' | 'danger';
  }

  let { status, tone = 'default' }: Props = $props();

  const derivedTone = $derived(
    tone !== 'default'
      ? tone
      : status.includes('failed')
        ? 'danger'
        : status.includes('ready') || status.includes('reviewed') || status.includes('applied')
          ? 'success'
          : status.includes('adapting') || status.includes('analysing') || status.includes('pending')
            ? 'warn'
            : 'default'
  );
</script>

<span class={`status-badge ${derivedTone}`}>{status.replaceAll('_', ' ')}</span>

<style>
  .status-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.32rem;
    padding: 0.22rem 0.55rem;
    border-radius: 999px;
    border: 1px solid var(--line);
    background: rgba(255,255,255,0.04);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-size: 0.68rem;
    line-height: 1;
    white-space: nowrap;
    color: var(--muted);
  }

  .success {
    color: var(--success);
    border-color: rgba(84, 179, 126, 0.2);
    background: rgba(84, 179, 126, 0.08);
  }

  .warn {
    color: var(--warn);
    border-color: rgba(217, 158, 70, 0.2);
    background: rgba(217, 158, 70, 0.08);
  }

  .danger {
    color: var(--danger);
    border-color: rgba(214, 90, 90, 0.2);
    background: rgba(214, 90, 90, 0.08);
  }
</style>
