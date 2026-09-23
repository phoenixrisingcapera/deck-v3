<script lang="ts">
  interface Props {
    level: 'low' | 'medium' | 'high' | string;
  }

  let { level }: Props = $props();

  function labelFor(value: string) {
    return `${value.replace(/[_-]+/g, ' ')} risk`;
  }
</script>

<span class={`risk-badge ${level}`}>{labelFor(level)}</span>

<style>
  .risk-badge {
    display: inline-flex;
    align-items: center;
    border-radius: 999px;
    padding: 0.3rem 0.65rem;
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    border: 1px solid var(--line);
  }

  .low {
    color: var(--success);
    background: rgba(84, 179, 126, 0.08);
  }

  .medium {
    color: var(--warn);
    background: rgba(217, 158, 70, 0.08);
  }

  .high {
    color: var(--danger);
    background: rgba(214, 90, 90, 0.08);
  }
</style>
