<script lang="ts">
  import type { DeckSlide } from '$types/domain';

  interface Props {
    slide: DeckSlide;
  }

  let { slide }: Props = $props();
</script>

<article class="panel viewer">
  <div class="topline">
    <div class="eyebrow">Slide Preview</div>
    <span class="pill">{slide.role}</span>
  </div>
  <h2>{slide.title}</h2>
  <div class="slide-card">
    <p>{slide.rawText}</p>
  </div>
  <div class="notes">
    <strong>Narrative notes</strong>
    <p>{slide.narrativeNotes}</p>
  </div>
</article>

<style>
  .viewer {
    padding: 1.25rem;
  }

  .topline {
    display: flex;
    justify-content: space-between;
    gap: 0.75rem;
    align-items: center;
  }

  .slide-card {
    padding: 1.25rem;
    border-radius: var(--radius-md);
    background:
      radial-gradient(circle at top right, rgba(104, 161, 255, 0.12), transparent 30%),
      linear-gradient(180deg, rgba(255,255,255,0.05), rgba(255,255,255,0.02));
    border: 1px solid var(--line);
    min-height: 260px;
  }

  h2 {
    margin: 0.4rem 0 1rem;
  }

  p {
    line-height: 1.6;
    color: var(--ink-soft);
  }

  .notes {
    margin-top: 1rem;
  }
</style>
