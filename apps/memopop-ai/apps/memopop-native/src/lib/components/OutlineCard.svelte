<script lang="ts">
  import type { Outline } from '$lib/types';

  interface Props {
    outline: Outline;
    onpreview: (outline: Outline) => void;
    ontry: (outline: Outline) => void;
  }

  let { outline, onpreview, ontry }: Props = $props();

  let typeClass = $derived(outline.outline_type === 'fund_commitment' ? 'fund' : 'direct');
  let firmLabel = $derived(outline.firm ? outline.firm : null);
</script>

<article class="card">
  <button type="button" class="card-body" onclick={() => onpreview(outline)}>
    <div class="card-head">
      <span class="badge {typeClass}">{outline.type_label}</span>
      {#if firmLabel}
        <span class="firm">{firmLabel}</span>
      {/if}
    </div>

    <h3 class="title">{outline.title}</h3>

    {#if outline.description}
      <p class="description">{outline.description}</p>
    {/if}

    <div class="meta">
      <span class="meta-item">
        <strong>{outline.section_count}</strong> sections
      </span>
      {#if outline.compatible_modes.length > 0}
        <span class="meta-item">
          {outline.compatible_modes.map(m => m === 'consider' ? 'Evaluate' : 'Justify').join(' · ')}
        </span>
      {/if}
      {#if outline.version}
        <span class="meta-item version">v{outline.version}</span>
      {/if}
    </div>
  </button>

  <div class="card-footer">
    <button type="button" class="link" onclick={() => onpreview(outline)}>
      Preview details
    </button>
    <button type="button" class="cta" onclick={() => ontry(outline)}>
      Try this on a company →
    </button>
  </div>
</article>

<style>
  .card {
    background: white;
    border: 1px solid #e5e5e5;
    border-radius: 12px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    transition: border-color 0.15s ease, transform 0.15s ease, box-shadow 0.15s ease;
  }

  .card:hover {
    border-color: #c4b5fd;
    box-shadow: 0 4px 12px rgba(91, 33, 182, 0.08);
  }

  .card-body {
    background: transparent;
    border: none;
    padding: 1.25rem 1.25rem 0.75rem;
    text-align: left;
    cursor: pointer;
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
    color: inherit;
    font: inherit;
  }

  .card-head {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .badge {
    display: inline-block;
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    padding: 0.2rem 0.55rem;
    border-radius: 999px;
  }

  .badge.direct {
    background: #ecfdf5;
    color: #065f46;
  }

  .badge.fund {
    background: #eff6ff;
    color: #1e40af;
  }

  .firm {
    font-size: 0.75rem;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .title {
    font-size: 1.1rem;
    margin: 0;
    line-height: 1.3;
    color: #0f0f0f;
  }

  .description {
    font-size: 0.92rem;
    color: #4b5563;
    margin: 0;
    line-height: 1.5;
    /* Clamp to 3 lines */
    display: -webkit-box;
    -webkit-line-clamp: 3;
    line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .meta {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-top: auto;
    padding-top: 0.5rem;
    flex-wrap: wrap;
  }

  .meta-item {
    font-size: 0.85rem;
    color: #6b7280;
  }

  .meta-item strong {
    color: #0f0f0f;
    font-weight: 600;
  }

  .meta-item.version {
    font-family: ui-monospace, SFMono-Regular, monospace;
    font-size: 0.75rem;
    background: #f3f4f6;
    padding: 0.1rem 0.4rem;
    border-radius: 4px;
  }

  .card-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.75rem 1.25rem 1.1rem;
    gap: 0.5rem;
  }

  button.link {
    background: transparent;
    border: none;
    padding: 0;
    color: #6b7280;
    font: inherit;
    font-size: 0.85rem;
    cursor: pointer;
    text-decoration: underline;
    text-underline-offset: 2px;
  }

  button.link:hover {
    color: #5b21b6;
  }

  button.cta {
    background: #5b21b6;
    color: white;
    border: none;
    padding: 0.5rem 0.85rem;
    border-radius: 8px;
    font: inherit;
    font-weight: 500;
    font-size: 0.85rem;
    cursor: pointer;
  }

  button.cta:hover {
    background: #4c1d95;
  }

  @media (prefers-color-scheme: dark) {
    .card {
      background: #2a2a2c;
      border-color: #3a3a3c;
    }

    .card:hover {
      border-color: #5b21b6;
    }

    .title {
      color: #f6f6f6;
    }

    .description {
      color: #d1d5db;
    }

    .badge.direct {
      background: #064e3b;
      color: #a7f3d0;
    }

    .badge.fund {
      background: #1e3a8a;
      color: #bfdbfe;
    }

    .firm {
      color: #9ca3af;
    }

    .meta-item {
      color: #9ca3af;
    }

    .meta-item strong {
      color: #f6f6f6;
    }

    .meta-item.version {
      background: #1c1c1e;
    }

    button.link {
      color: #9ca3af;
    }

    button.link:hover {
      color: #c4b5fd;
    }
  }
</style>
