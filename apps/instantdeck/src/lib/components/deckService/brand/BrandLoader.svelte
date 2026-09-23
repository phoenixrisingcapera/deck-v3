<!-- Purpose: orchestrates brand extraction modal with URL/logo/guidelines inputs and status strip. -->
<script lang="ts">
  import BrandExtractionStatus from './BrandExtractionStatus.svelte';
  import BrandPreviewCard from './BrandPreviewCard.svelte';
  import BrandSelectorEditor from './BrandSelectorEditor.svelte';
  import LogoDropzone from './LogoDropzone.svelte';
  import SmartBrandStepPanel from './SmartBrandStepPanel.svelte';
  import UploadedDocumentRow from '$lib/components/deckService/upload/UploadedDocumentRow.svelte';
  import type { UploadedDocumentViewModel } from '$lib/components/deckService/upload/upload-deck.types';
  import type { BrandGuidelinesStatus, BrandProfile, BrandStatus } from '$lib/types/deckService-brand';
  import { hasBrandSignals } from '$lib/types/deckService-brand';
  import type { DeckExtractionStatus } from '$lib/api/deckService/workflow.client';

  let {
    openAsModal = false,
    modalTitle = 'Review your brand',
    modalSubtitle = 'Upload your brand alongside the deck so the workspace can keep preparing in the background.',
    companyUrl,
    logoFile,
    logoPreviewUrl = '',
    brandGuidelinesFile,
    logoDragActive = false,
    guidelinesDragActive = false,
    acceptedLogoTypes,
    acceptedGuidelineTypes,
    brandStatus,
    deckExtractionStatus = 'idle',
    brandGuidelinesStatus = 'idle',
    brandError = '',
    brandProfile = null,
    brandApproved = false,
    editingBrand = false,
    savingBrand = false,
    brandSaveError = '',
    canExtractBrand,
    canContinue = false,
    formatFileSize,
    onCompanyUrlChange,
    onLogoDragEnter,
    onLogoDragLeave,
    onLogoDrop,
    onLogoFileChange,
    onGuidelinesDragEnter,
    onGuidelinesDragLeave,
    onGuidelinesDrop,
    onGuidelinesFileChange,
    onExtract,
    onEdit,
    onApprove,
    onContinue,
    onClose,
    onSaveBrand,
    onSkipToSmartDeck
  }: {
    openAsModal?: boolean;
    modalTitle?: string;
    modalSubtitle?: string;
    companyUrl: string;
    logoFile: File | null;
    logoPreviewUrl?: string;
    brandGuidelinesFile: File | null;
    logoDragActive?: boolean;
    guidelinesDragActive?: boolean;
    acceptedLogoTypes: string;
    acceptedGuidelineTypes: string;
    brandStatus: BrandStatus;
    deckExtractionStatus?: DeckExtractionStatus;
    brandGuidelinesStatus?: BrandGuidelinesStatus;
    brandError?: string;
    brandProfile?: BrandProfile | null;
    brandApproved?: boolean;
    editingBrand?: boolean;
    savingBrand?: boolean;
    brandSaveError?: string;
    canExtractBrand: boolean;
    canContinue?: boolean;
    canSkipToSmartDeck?: boolean;
    formatFileSize: (size: number) => string;
    onCompanyUrlChange: (value: string) => void;
    onLogoDragEnter: (event: DragEvent) => void;
    onLogoDragLeave: (event: DragEvent) => void;
    onLogoDrop: (event: DragEvent) => void;
    onLogoFileChange: (file: File | null) => void;
    onGuidelinesDragEnter: (event: DragEvent) => void;
    onGuidelinesDragLeave: (event: DragEvent) => void;
    onGuidelinesDrop: (event: DragEvent) => void;
    onGuidelinesFileChange: (file: File | null) => void;
    onExtract: () => void;
    onEdit: () => void;
    onApprove: () => void;
    onContinue: () => void;
    onClose?: () => void;
    onSaveBrand: (payload: {
      primaryColor: string;
      secondaryColor: string;
      accentColor: string;
      backgroundColor: string;
      textColor: string;
      visualStyle: string;
      fontCandidates: string[];
    }) => void;
    onSkipToSmartDeck?: () => void;
  } = $props();

</script>

{#snippet loaderInner()}
  <header class="modal-top">
    <div class="modal-copy">
      <div class="eyebrow">Load / review brand</div>
      <h3>{modalTitle}</h3>
      <p class="muted">{modalSubtitle}</p>
    </div>

    {#if onClose}
      <button class="icon-button" type="button" aria-label="Close brand review" onclick={onClose}>×</button>
    {/if}
  </header>

  <div class="status-strip">
    <article>
      <span>Deck extraction</span>
      <strong class={`status-${deckExtractionStatus}`}>{deckExtractionStatus === 'ready' ? 'Deck structure ready' : deckExtractionStatus === 'processing' ? 'Deck extraction in progress' : deckExtractionStatus === 'queued' ? 'Deck extraction queued' : deckExtractionStatus === 'failed' ? 'Deck extraction needs attention' : 'Deck extraction pending'}</strong>
    </article>
    <article>
      <span>Brand status</span>
      <strong class={`status-${brandStatus}`}>{hasBrandSignals(brandProfile) || brandStatus === 'ready' ? 'Brand profile available' : brandStatus === 'extracting' ? 'Extracting brand' : 'Awaiting brand inputs'}</strong>
    </article>
    <article>
      <span>Guidelines</span>
      <strong class={`status-${brandGuidelinesStatus}`}>{brandGuidelinesStatus === 'uploaded' ? 'Guidelines loaded' : brandGuidelinesStatus === 'ready' ? 'Guidelines attached' : 'Optional'}</strong>
    </article>
  </div>

  <div class="loader-grid">
    <div class="loader-column">
      <label class="field">
        <span>Company website URL</span>
        <input
          value={companyUrl}
          type="url"
          placeholder="https://company.com"
          oninput={(event) => onCompanyUrlChange((event.currentTarget as HTMLInputElement).value)}
        />
      </label>

      <div class="brand-divider">
        <span>or use uploaded brand assets</span>
      </div>

      <LogoDropzone
        file={logoFile}
        previewUrl={logoPreviewUrl}
        dragActive={logoDragActive}
        accept={acceptedLogoTypes}
        {formatFileSize}
        onDragEnter={onLogoDragEnter}
        onDragLeave={onLogoDragLeave}
        onDrop={onLogoDrop}
        onFileChange={onLogoFileChange}
      />

      <label
        class:drag-active={guidelinesDragActive}
        class="guideline-dropzone"
        ondragenter={onGuidelinesDragEnter}
        ondragover={onGuidelinesDragEnter}
        ondragleave={onGuidelinesDragLeave}
        ondrop={onGuidelinesDrop}
      >
        <input
          type="file"
          accept={acceptedGuidelineTypes}
          onchange={(event) => {
            const target = event.currentTarget as HTMLInputElement;
            onGuidelinesFileChange(target.files?.[0] ?? null);
          }}
        />
        <strong>{brandGuidelinesFile ? brandGuidelinesFile.name : 'Optional: upload brand guidelines'}</strong>
        <span class="muted">
          {brandGuidelinesFile
            ? `${formatFileSize(brandGuidelinesFile.size)} • saved as a brand reference`
            : 'PDF, PPT, PPTX, DOC, or DOCX'}
        </span>
      </label>

      {#if brandGuidelinesFile}
        <UploadedDocumentRow
          document={{
            name: brandGuidelinesFile.name,
            sizeLabel: formatFileSize(brandGuidelinesFile.size),
            statusLabel:
              brandGuidelinesStatus === 'failed'
                ? 'Failed'
                : brandGuidelinesStatus === 'processing'
                  ? 'Processing'
                  : brandGuidelinesStatus === 'ready'
                    ? 'Attached'
                    : 'Uploaded',
            statusTone:
              brandGuidelinesStatus === 'failed'
                ? 'danger'
                : brandGuidelinesStatus === 'processing'
                  ? 'info'
                  : 'success',
            fileKindLabel: (() => {
              const extension = brandGuidelinesFile.name.split('.').pop()?.toUpperCase();
              if (extension === 'PPT' || extension === 'PPTX') return 'PPT';
              if (extension === 'PDF') return 'PDF';
              if (extension === 'DOC' || extension === 'DOCX') return 'DOC';
              return 'FILE';
            })()
          }}
        />
      {/if}

      <button class="button brand-button" type="button" onclick={onExtract} disabled={!canExtractBrand}>
        {brandStatus === 'extracting' ? 'Extracting brand...' : 'Extract brand'}
      </button>

      <p class="micro-copy">
        Deck AIStack keeps preparing the uploaded deck while you review the brand. No API keys are exposed here.
      </p>

      <BrandExtractionStatus status={brandStatus} error={brandError} />
    </div>

    <div class="loader-column loader-column--preview">
      <SmartBrandStepPanel
        {brandProfile}
        {brandApproved}
        brandStatus={brandStatus}
        {deckExtractionStatus}
        {companyUrl}
        {logoFile}
        {brandGuidelinesFile}
      />

      {#if brandProfile && hasBrandSignals(brandProfile)}
        {#if editingBrand}
          <BrandSelectorEditor
            {brandProfile}
            saving={savingBrand}
            saveError={brandSaveError}
            onSave={onSaveBrand}
            onCancel={onEdit}
          />
        {/if}

        <div class="preview-actions">
          <button class="button secondary" type="button" onclick={onEdit}>
            {editingBrand ? 'Close editor' : 'Edit brand'}
          </button>
          <button
            class="button secondary"
            type="button"
            onclick={() =>
              brandProfile &&
              onSaveBrand({
                primaryColor: brandProfile.primaryColor ?? brandProfile.colors?.find((color) => color.role === 'primary')?.hex ?? '#3B82F6',
                secondaryColor: brandProfile.secondaryColor ?? brandProfile.colors?.find((color) => color.role === 'secondary')?.hex ?? '#0F172A',
                accentColor: brandProfile.accentColor ?? brandProfile.colors?.find((color) => color.role === 'accent')?.hex ?? '#7C3AED',
                backgroundColor: brandProfile.backgroundColor ?? brandProfile.colors?.find((color) => color.role === 'background')?.hex ?? '#081225',
                textColor: brandProfile.textColor ?? brandProfile.colors?.find((color) => color.role === 'text')?.hex ?? '#E5EEF8',
                visualStyle: brandProfile.visualStyle ?? 'Modern, technical, confident',
                fontCandidates: brandProfile.fontCandidates?.length
                  ? brandProfile.fontCandidates
                  : brandProfile.fonts?.map((font) => font.family).filter(Boolean) ?? ['Inter', 'Manrope']
              })
            }
            disabled={savingBrand}
          >
            {savingBrand ? 'Saving brand...' : brandApproved ? 'Brand profile saved' : 'Save brand profile'}
          </button>
          <button class="button secondary" type="button" onclick={onApprove}>
            {brandApproved ? 'Brand approved' : 'Use this brand'}
          </button>
        </div>

        {#if brandSaveError && !editingBrand}
          <p class="error-copy">{brandSaveError}</p>
        {/if}
      {/if}
    </div>
  </div>

  <div class="modal-actions">
    <button class="button secondary" type="button" onclick={onClose ?? (() => {})}>
      Back to intake
    </button>
    {#if onSkipToSmartDeck}
      <button class="button secondary" type="button" onclick={onSkipToSmartDeck}>
        Skip to Smart Deck
      </button>
    {/if}
    {#if canContinue}
      <button class="button" type="button" onclick={onContinue}>Continue</button>
    {/if}
  </div>
{/snippet}

{#if openAsModal}
  <div class="modal-backdrop" role="presentation">
    <div class="modal-shell" role="dialog" aria-modal="true" aria-labelledby="brand-loader-modal-title">
      <section class="panel modal-panel">
        <div class="visually-hidden" id="brand-loader-modal-title">{modalTitle}</div>
        {@render loaderInner()}
      </section>
    </div>
  </div>
{:else}
  <section class="panel">
    {@render loaderInner()}
  </section>
{/if}

<style>
  .panel,
  .modal-panel {
    display: grid;
    gap: 1rem;
    padding: 1.35rem;
  }

  .modal-backdrop {
    position: fixed;
    inset: 0;
    z-index: 40;
    display: grid;
    place-items: center;
    padding: 1.5rem;
    background: rgba(3, 9, 24, 0.76);
    backdrop-filter: blur(12px);
  }

  .modal-shell {
    width: min(1100px, 100%);
  }

  .modal-panel {
    border: 1px solid rgba(112, 139, 255, 0.28);
    background:
      radial-gradient(circle at top left, rgba(81, 113, 255, 0.18), transparent 28%),
      linear-gradient(180deg, rgba(10, 18, 42, 0.98), rgba(8, 15, 36, 0.98));
    box-shadow: 0 26px 80px rgba(0, 0, 0, 0.45);
  }

  .modal-top,
  .status-strip,
  .loader-grid,
  .modal-actions,
  .field,
  .loader-column {
    display: grid;
    gap: 0.9rem;
  }

  .modal-top {
    grid-template-columns: 1fr auto;
    align-items: start;
  }

  .status-strip {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .status-strip article {
    display: grid;
    gap: 0.25rem;
    padding: 0.85rem 0.95rem;
    border-radius: 12px;
    border: 1px solid var(--line);
    background: rgba(255, 255, 255, 0.03);
  }

  .status-strip span,
  .muted,
  .micro-copy,
  .field span,
  .summary {
    color: var(--muted);
    font-size: 0.84rem;
  }

  .error-copy {
    margin: 0;
    color: var(--danger);
  }

  .loader-grid {
    grid-template-columns: minmax(0, 0.95fr) minmax(0, 1.05fr);
    align-items: start;
  }

  .loader-column--preview {
    align-content: start;
  }

  .field input {
    width: 100%;
    border-radius: 12px;
    border: 1px solid var(--line-strong);
    padding: 0.85rem 0.95rem;
    background: var(--surface-input);
    color: var(--ink);
  }

  .brand-divider {
    position: relative;
    text-align: center;
    color: var(--muted);
    font-size: 0.82rem;
  }

  .brand-divider::before {
    content: '';
    position: absolute;
    inset: 50% 0 auto;
    border-top: 1px solid var(--line);
  }

  .brand-divider span {
    position: relative;
    padding: 0 0.65rem;
    background: rgba(9, 15, 35, 0.92);
  }

  .guideline-dropzone {
    position: relative;
    overflow: hidden;
    border: 1px dashed rgba(120, 145, 255, 0.26);
    border-radius: 12px;
    padding: 1.1rem 1rem;
    text-align: center;
    background: rgba(255, 255, 255, 0.02);
  }

  .guideline-dropzone.drag-active {
    border-color: rgba(96, 130, 255, 0.7);
    background: rgba(77, 124, 255, 0.08);
  }

  .guideline-dropzone input {
    position: absolute;
    inset: 0;
    opacity: 0;
    cursor: pointer;
  }

  .brand-button {
    width: 100%;
    justify-content: center;
    background: #2563eb;
    color: #ffffff;
    border: 1px solid #60a5fa;
    font-weight: 700;
  }

  .brand-button:hover { background: #1d4ed8; }

  .brand-preview--pending {
    border: 1px solid var(--line);
    border-radius: 12px;
    padding: 1rem;
    background: rgba(255, 255, 255, 0.02);
  }

  .brand-preview__header,
  .brand-preview__body,
  .brand-signals,
  .preview-actions,
  .modal-actions {
    display: grid;
    gap: 0.9rem;
  }

  .brand-preview__body {
    grid-template-columns: auto 1fr;
    align-items: start;
  }

  .preview-actions {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .modal-actions {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .icon-button {
    width: 2.5rem;
    height: 2.5rem;
    border-radius: 999px;
    border: 1px solid var(--line);
    background: rgba(255, 255, 255, 0.04);
    color: var(--ink);
    font-size: 1.4rem;
  }

  .status-ready {
    color: #7ce39c;
  }

  .status-processing,
  .status-extracting {
    color: #8cc5ff;
  }

  .status-queued,
  .status-uploaded {
    color: #b6c2ff;
  }

  .status-failed {
    color: #ff9292;
  }

  .visually-hidden {
    position: absolute;
    width: 1px;
    height: 1px;
    margin: -1px;
    padding: 0;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    border: 0;
  }

  @media (max-width: 960px) {
    .loader-grid,
    .status-strip,
    .preview-actions,
    .modal-actions {
      grid-template-columns: 1fr;
    }

    .modal-backdrop {
      padding: 0.75rem;
      align-items: end;
    }

    .brand-preview__body,
    .modal-top {
      grid-template-columns: 1fr;
    }
  }
</style>
