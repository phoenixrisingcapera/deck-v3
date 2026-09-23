<script lang="ts">
  interface Props {
    expanded?: boolean;
    onToggle?: () => void;
  }

  let { expanded = true, onToggle }: Props = $props();
</script>

<button type="button" class="floating-ai-button" class:is-expanded={expanded} aria-label="Toggle AI Assistant" onclick={() => onToggle?.()}>
  AI
</button>

<style>
  .floating-ai-button {
    position: fixed;
    right: 24px;
    bottom: 24px;
    z-index: 30;
    width: 56px;
    height: 56px;
    border-radius: 999px;
    border: none;
    background: linear-gradient(135deg, #7c3aed, #0ea5e9);
    color: white;
    font-weight: 800;
    letter-spacing: 0.04em;
    box-shadow: 0 18px 36px rgba(76, 29, 149, 0.45);
    cursor: pointer;
    transition: transform 140ms ease, box-shadow 140ms ease;
  }

  .floating-ai-button:hover {
    transform: scale(1.05);
    box-shadow: 0 22px 42px rgba(14, 165, 233, 0.35);
  }

  .floating-ai-button.is-expanded {
    box-shadow: 0 0 0 4px rgba(124, 58, 237, 0.18), 0 18px 36px rgba(76, 29, 149, 0.45);
  }
</style>
