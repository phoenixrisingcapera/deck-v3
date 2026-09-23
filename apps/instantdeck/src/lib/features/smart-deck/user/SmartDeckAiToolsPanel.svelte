<script lang="ts">
  interface Props {
    hasSelectedSlide: boolean;
    onSelectBackground?: () => void;
    onSelectSlideContent?: () => void;
    onSelectWholeDeck?: () => void;
  }
  let { hasSelectedSlide, onSelectBackground, onSelectSlideContent, onSelectWholeDeck }: Props = $props();
</script>

<section class="tool-panel">
  <header><span>AI Tools</span><h2>Choose a prompt starter</h2><p>Set the scope here, then review and submit it in the route-owned AI workspace.</p></header>
  <button class="primary" type="button" disabled={!hasSelectedSlide} onclick={() => onSelectBackground?.()}>Redesign background with vision</button>
  <button type="button" disabled={!hasSelectedSlide} onclick={() => onSelectSlideContent?.()}>Redesign slide content with LLM</button>
  <button type="button" onclick={() => onSelectWholeDeck?.()}>Regenerate new deck</button>
  <small>Nothing is submitted until you confirm it in the prompt workspace.</small>
</section>

<style>
  .tool-panel { display: grid; gap: .7rem; }
  header { display: grid; gap: .35rem; margin-bottom: .2rem; }
  header > span { color: #38bdf8; font-size: .72rem; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
  h2, p { margin: 0; }
  p { color: #94a3b8; line-height: 1.45; }
  button { min-height: 42px; border: 1px solid rgba(255,255,255,.1); border-radius: 10px; background: rgba(15,23,42,.9); color: #e2e8f0; text-align: left; padding: .7rem; cursor: pointer; }
  button.primary { border: 0; background: linear-gradient(135deg,#7c3aed,#0ea5e9); color: white; font-weight: 800; }
  button:disabled { opacity: .45; cursor: not-allowed; }
</style>
