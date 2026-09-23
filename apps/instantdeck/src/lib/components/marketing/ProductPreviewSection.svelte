<script lang="ts">
  import { previewPanes } from '$lib/data/marketing/home';
</script>

<section class="panel section">
  <div class="section-head">
    <div>
      <div class="eyebrow">Product preview</div>
      <h2>Preview the operating surface before sign-in.</h2>
    </div>
    <p class="muted">
      The public site previews the shape of the workflow, while the app keeps the real deck, findings, and
      edits inside the signed-in shell.
    </p>
  </div>

  <div class="preview-grid">
    {#each previewPanes as pane}
      <article>
        <strong>{pane.title}</strong>
        <p class="muted">{pane.body}</p>
      </article>
    {/each}
  </div>
</section>

<style>
  .section {
    padding: clamp(2rem, 3vw, 3.5rem) clamp(1.8rem, 3vw, 3.5rem);
    display: grid;
    gap: 1.65rem;
  }

  .section-head {
    display: grid;
    grid-template-columns: minmax(0, 0.9fr) minmax(0, 1.1fr);
    gap: 1.35rem;
    align-items: end;
  }

  .section-head h2 {
    margin: 0.35rem 0 0;
    font-size: clamp(1.7rem, 2.6vw, 2.45rem);
    line-height: 1.02;
    letter-spacing: -0.04em;
  }

  .preview-grid {
    display: grid;
    gap: 1.25rem;
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .preview-grid article {
    border: 1px solid var(--line);
    border-radius: 18px;
    padding: 1.45rem 1.35rem;
    background: var(--surface-soft);
    display: grid;
    gap: 0.6rem;
    transition: transform 180ms ease, box-shadow 180ms ease;
  }

  .preview-grid article:hover {
    transform: translateY(-2px);
    box-shadow: 0 12px 28px rgba(0, 0, 0, 0.18);
  }

  @media (max-width: 960px) {
    .section-head,
    .preview-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
