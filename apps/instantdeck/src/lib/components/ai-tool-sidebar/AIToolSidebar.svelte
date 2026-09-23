<script lang="ts">
  interface Props {
    surface: 'smart-deck' | 'instant-deck' | 'smart-edit' | 'due-diligence';
    title: string;
    open: boolean;
    children: import('svelte').Snippet;
    onClose?: () => void;
  }

  let { surface, title, open, children, onClose }: Props = $props();
</script>

{#if open}
  <aside
    id={`${surface}-ai-tools`}
    class="ai-tool-sidebar"
    data-ai-tool-sidebar={surface}
    aria-label={`${title} AI tools`}
  >
    <header>
      <div>
        <span>AI tools</span>
        <strong>{title}</strong>
      </div>
      {#if onClose}
        <button type="button" onclick={onClose} aria-label={`Close ${title} AI tools`}>Close</button>
      {/if}
    </header>
    <div class="ai-tool-sidebar__body">
      {@render children()}
    </div>
  </aside>
{/if}

<style>
  .ai-tool-sidebar {
    grid-column: 2;
    grid-row: 1 / -1;
    z-index: 35;
    min-width: 0;
    min-height: 0;
    display: grid;
    grid-template-rows: auto minmax(0, 1fr);
    border-right: 1px solid rgba(255, 255, 255, 0.1);
    background: rgba(9, 15, 30, 0.98);
    box-shadow: 18px 0 36px rgba(2, 6, 23, 0.32);
    color: #f8fafc;
    overflow: hidden;
  }

  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    min-height: 58px;
    padding: 0.75rem;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  }

  header div {
    min-width: 0;
    display: grid;
    gap: 0.1rem;
  }

  header span {
    color: #818cf8;
    font-size: 0.66rem;
    font-weight: 800;
    letter-spacing: 0.1em;
    text-transform: uppercase;
  }

  header strong {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  header button {
    border: 1px solid rgba(148, 163, 184, 0.22);
    border-radius: 8px;
    background: rgba(15, 23, 42, 0.72);
    color: #cbd5e1;
    padding: 0.42rem 0.58rem;
    font: inherit;
    font-size: 0.72rem;
    cursor: pointer;
  }

  .ai-tool-sidebar__body {
    min-height: 0;
    overflow-y: auto;
    padding: 0.75rem;
  }

  @media (max-width: 960px) {
    .ai-tool-sidebar {
      grid-column: 2;
      grid-row: 1 / -1;
      width: min(22rem, 100%);
    }
  }

  @media (max-width: 720px) {
    .ai-tool-sidebar {
      grid-column: 1;
      grid-row: 3;
      width: 100%;
      max-height: min(34rem, 65vh);
    }
  }
</style>
