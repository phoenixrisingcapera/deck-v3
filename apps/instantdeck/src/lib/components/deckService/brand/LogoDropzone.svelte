<!-- Purpose: handles logo drag/drop/file selection for brand extraction inputs. -->
<script lang="ts">
  let {
    file,
    previewUrl = '',
    dragActive = false,
    accept,
    formatFileSize,
    onDragEnter,
    onDragLeave,
    onDrop,
    onFileChange
  }: {
    file: File | null;
    previewUrl?: string;
    dragActive?: boolean;
    accept: string;
    formatFileSize: (size: number) => string;
    onDragEnter: (event: DragEvent) => void;
    onDragLeave: (event: DragEvent) => void;
    onDrop: (event: DragEvent) => void;
    onFileChange: (file: File | null) => void;
  } = $props();
</script>

<label
  class:drag-active={dragActive}
  class="logo-dropzone"
  ondragenter={onDragEnter}
  ondragover={onDragEnter}
  ondragleave={onDragLeave}
  ondrop={onDrop}
>
  <input
    type="file"
    {accept}
    onchange={(event) => {
      const target = event.currentTarget as HTMLInputElement;
      onFileChange(target.files?.[0] ?? null);
    }}
  />
  <div class="logo-dropzone__content">
    {#if file && previewUrl}
      <span class="logo-dropzone__preview">
        <img src={previewUrl} alt="Selected logo preview" />
      </span>
    {/if}
    <span>
      <strong>{file ? file.name : 'Upload your brand logo'}</strong>
      <span class="muted">
        {file ? `Loaded for brand extraction • ${formatFileSize(file.size)}` : 'PNG, JPG, SVG, or WEBP'}
      </span>
    </span>
  </div>
</label>

<style>
  .logo-dropzone {
    position: relative;
    overflow: hidden;
    border: 1px dashed rgba(120, 145, 255, 0.26);
    border-radius: 12px;
    padding: 1.2rem 1rem;
    text-align: center;
    background: rgba(255, 255, 255, 0.02);
  }

  .logo-dropzone__content {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.8rem;
    max-width: 100%;
  }

  .logo-dropzone__preview {
    width: 3rem;
    height: 3rem;
    display: grid;
    place-items: center;
    border: 1px solid rgba(120, 145, 255, 0.24);
    border-radius: 10px;
    background: rgba(255, 255, 255, 0.06);
    overflow: hidden;
  }

  .logo-dropzone__preview img {
    width: 100%;
    height: 100%;
    object-fit: contain;
    padding: 0.35rem;
  }

  .logo-dropzone.drag-active {
    border-color: rgba(96, 130, 255, 0.7);
    background:
      radial-gradient(circle at top, rgba(72, 112, 255, 0.2), transparent 38%),
      rgba(77, 124, 255, 0.08);
  }

  .logo-dropzone input {
    position: absolute;
    inset: 0;
    opacity: 0;
    cursor: pointer;
  }

  .logo-dropzone strong {
    display: block;
    margin-bottom: 0.25rem;
  }

  .muted {
    display: block;
    color: var(--muted);
    font-size: 0.84rem;
  }
</style>
