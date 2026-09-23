<script lang="ts">
  import type { AdaptationSuggestion } from '$types/domain';

  interface Props {
    suggestion: AdaptationSuggestion;
  }

  let { suggestion }: Props = $props();
</script>

<article class="suggestion">
  <div class="topline">
    <strong>{suggestion.title}</strong>
    <span class="pill">{suggestion.status}</span>
  </div>
  <p class="muted">{suggestion.reason}</p>
  <blockquote>{suggestion.suggestedText}</blockquote>
</article>

<style>
  .suggestion {
    border: 1px solid var(--line);
    border-radius: var(--radius-md);
    padding: 1rem;
    background: rgba(255, 255, 255, 0.72);
  }

  .topline {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
  }

  blockquote {
    margin: 0.8rem 0 0;
    padding-left: 1rem;
    border-left: 3px solid var(--accent);
  }
</style>
