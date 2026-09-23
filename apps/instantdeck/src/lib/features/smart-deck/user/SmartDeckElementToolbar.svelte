<script lang="ts">
  interface Props {
    visible?: boolean;
    disabledLabel?: string;
  }

  let { visible = false, disabledLabel = 'Editing controls are not available in this pass.' }: Props = $props();
</script>

{#if visible}
  <div class="element-toolbar" aria-label="Element editing toolbar">
    <span>{disabledLabel}</span>
  </div>
{/if}

<style>
  .element-toolbar {
    position: absolute;
    top: 1rem;
    left: 50%;
    transform: translateX(-50%);
    z-index: 4;
    display: flex;
    gap: 0.35rem;
    padding: 0.45rem;
    border-radius: 14px;
    background: rgba(255, 255, 255, 0.96);
    box-shadow: 0 18px 38px rgba(15, 23, 42, 0.18);
  }

  .element-toolbar span {
    color: #111827;
    padding: 0.5rem 0.7rem;
    font-size: 0.82rem;
  }
</style>
