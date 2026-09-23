<!-- Purpose: renders one uploaded document row with status icon and readable label. -->
<script lang="ts">
  import type { UploadedDocumentViewModel } from './upload-deck.types';

  interface Props {
    document: UploadedDocumentViewModel;
  }

  let { document }: Props = $props();
</script>

<article class="uploaded-document-row">
  <div class="uploaded-document-row__file-icon" aria-hidden="true">
    <div class="uploaded-document-row__file-sheet">
      <div class="uploaded-document-row__file-fold"></div>
      <span>{document.fileKindLabel}</span>
    </div>
  </div>

  <div class="uploaded-document-row__copy">
    <strong>{document.name}</strong>
    <span>{document.sizeLabel}</span>
  </div>

  <div class={`uploaded-document-row__status uploaded-document-row__status--${document.statusTone}`}>
    <span class="uploaded-document-row__status-icon" aria-hidden="true">
      <svg viewBox="0 0 16 16" role="presentation">
        {#if document.statusTone === 'danger'}
          <path d="m5 5 6 6M11 5l-6 6" fill="none" stroke="currentColor" stroke-linecap="round" stroke-width="1.8" />
        {:else if document.statusTone === 'info' || document.statusTone === 'warning'}
          <path d="M8 4.2v4.2l2.6 1.5" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" />
          <path d="M8 14A6 6 0 1 0 8 2a6 6 0 0 0 0 12Z" fill="none" stroke="currentColor" stroke-width="1.4" />
        {:else}
          <path d="m4 8 2.2 2.2L12 4.8" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" />
        {/if}
      </svg>
    </span>
    <span>{document.statusLabel}</span>
  </div>
</article>

<style>
  .uploaded-document-row {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    gap: 0.8rem;
    align-items: center;
    padding: 0.82rem 0.92rem;
    border-radius: 12px;
    border: 1px solid rgba(74, 97, 156, 0.38);
    background: linear-gradient(180deg, rgba(17, 26, 52, 0.94), rgba(14, 22, 43, 0.96));
  }

  .uploaded-document-row__file-icon {
    width: 2rem;
    height: 2rem;
    border-radius: 8px;
    display: grid;
    place-items: center;
    background: linear-gradient(180deg, rgba(245, 248, 255, 0.98), rgba(225, 233, 250, 0.96));
    color: #de774a;
    box-shadow: 0 8px 18px rgba(4, 7, 19, 0.18);
  }

  .uploaded-document-row__file-sheet {
    position: relative;
    width: 1.2rem;
    height: 1.4rem;
    border-radius: 3px;
    background: linear-gradient(180deg, #ffffff, #f6f7fb);
    box-shadow: inset 0 0 0 1px rgba(15, 23, 42, 0.08);
    display: grid;
    place-items: end center;
    padding-bottom: 0.14rem;
  }

  .uploaded-document-row__file-fold {
    position: absolute;
    top: 0;
    right: 0;
    width: 0.42rem;
    height: 0.42rem;
    background: linear-gradient(135deg, rgba(207, 216, 233, 0.95) 0%, rgba(255, 255, 255, 0) 100%);
    clip-path: polygon(0 0, 100% 0, 100% 100%);
  }

  .uploaded-document-row__file-icon span {
    font-size: 0.49rem;
    font-weight: 800;
    letter-spacing: 0.03em;
  }

  .uploaded-document-row__copy,
  .uploaded-document-row__status {
    display: grid;
    gap: 0.2rem;
  }

  .uploaded-document-row__copy {
    min-width: 0;
  }

  .uploaded-document-row__copy strong,
  .uploaded-document-row__copy span,
  .uploaded-document-row__status span {
    margin: 0;
  }

  .uploaded-document-row__copy strong {
    color: rgba(245, 248, 255, 0.98);
    font-size: 0.92rem;
    line-height: 1.2;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .uploaded-document-row__copy span {
    color: rgba(188, 201, 231, 0.78);
    font-size: 0.78rem;
  }

  .uploaded-document-row__status {
    display: inline-flex;
    flex-direction: row;
    align-items: center;
    gap: 0.45rem;
    justify-self: end;
    font-size: 0.82rem;
    white-space: nowrap;
  }

  .uploaded-document-row__status--success {
    color: #62dd8e;
  }

  .uploaded-document-row__status--info {
    color: #8ec9ff;
  }

  .uploaded-document-row__status--danger {
    color: #ff9da2;
  }

  .uploaded-document-row__status-icon {
    width: 1.05rem;
    height: 1.05rem;
    border-radius: 999px;
    display: grid;
    place-items: center;
    border: 1px solid currentColor;
    line-height: 1;
  }

  .uploaded-document-row__status-icon svg {
    width: 0.7rem;
    height: 0.7rem;
  }

  @media (max-width: 560px) {
    .uploaded-document-row {
      grid-template-columns: auto minmax(0, 1fr);
    }

    .uploaded-document-row__status {
      grid-column: 1 / -1;
      justify-self: start;
      padding-left: calc(2rem + 0.8rem);
    }
  }
</style>
