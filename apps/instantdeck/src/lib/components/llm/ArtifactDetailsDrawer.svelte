<script lang="ts">
  interface Props {
    open: boolean;
    title: string;
    subtitle?: string | null;
    payload: Record<string, unknown> | null;
    onClose?: () => void;
  }

  let { open, title, subtitle = null, payload, onClose }: Props = $props();

  const formatted = $derived(payload ? JSON.stringify(payload, null, 2) : 'No payload available.');
</script>

{#if open}
  <button class="artifact-drawer-backdrop" type="button" aria-label="Close details" onclick={() => onClose?.()}></button>
  <div class="artifact-drawer" role="dialog" aria-modal="true" aria-label={title}>
    <div class="artifact-drawer__head">
      <div>
        <h3>{title}</h3>
        {#if subtitle}<p>{subtitle}</p>{/if}
      </div>
      <button type="button" onclick={() => onClose?.()}>Close</button>
    </div>
    <pre>{formatted}</pre>
  </div>
{/if}

<style>
  .artifact-drawer-backdrop {
    position: fixed;
    inset: 0;
    border: 0;
    background: rgba(2, 6, 23, 0.55);
    cursor: pointer;
    z-index: 39;
  }

  .artifact-drawer {
    position: fixed;
    top: 0;
    right: 0;
    width: min(100vw, 520px);
    height: 100vh;
    z-index: 40;
    background: #0f172a;
    color: #e2e8f0;
    box-shadow: -24px 0 60px rgba(2, 6, 23, 0.5);
    display: grid;
    grid-template-rows: auto 1fr;
  }

  .artifact-drawer__head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1rem;
    padding: 1rem;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  }

  .artifact-drawer__head h3,
  .artifact-drawer__head p {
    margin: 0;
  }

  .artifact-drawer__head p {
    color: #94a3b8;
    font-size: 0.85rem;
    margin-top: 0.35rem;
  }

  .artifact-drawer__head button {
    border-radius: 8px;
    border: 1px solid rgba(255, 255, 255, 0.08);
    background: rgba(255, 255, 255, 0.03);
    color: #e2e8f0;
    cursor: pointer;
    padding: 0.4rem 0.8rem;
  }

  .artifact-drawer pre {
    margin: 0;
    padding: 1rem;
    overflow: auto;
    font-size: 0.78rem;
    line-height: 1.5;
    background: #020617;
    color: #cbd5e1;
  }
</style>
