<!-- Purpose: renders deck file type icon and optional thumbnail preview. -->
<script lang="ts">
  import type { DeckFileType } from '$lib/contracts/types';

  type Props = {
    fileType: DeckFileType;
    thumbnailUrl?: string | null;
    alt?: string;
  };

  let { fileType, thumbnailUrl = null, alt = '' }: Props = $props();
  const label = $derived(fileType === 'ppt' || fileType === 'pptx' ? 'PPT' : fileType === 'pdf' ? 'PDF' : fileType === 'key' ? 'KEY' : 'FILE');
</script>

<div class="deck-file-icon" aria-hidden={alt ? undefined : 'true'}>
  {#if thumbnailUrl}
    <img src={thumbnailUrl} alt={alt} />
  {:else}
    <div class="deck-file-icon__sheet">
      <div class="deck-file-icon__fold"></div>
      <span>{label}</span>
    </div>
  {/if}
</div>

<style>
  .deck-file-icon {
    width: 44px;
    height: 44px;
    border-radius: 12px;
    background: rgba(255, 255, 255, 0.03);
    display: grid;
    place-items: center;
    overflow: hidden;
    flex: 0 0 auto;
  }

  .deck-file-icon img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .deck-file-icon__sheet {
    width: 34px;
    height: 38px;
    border-radius: 10px;
    background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(226, 233, 252, 0.9));
    color: #f26d35;
    position: relative;
    display: grid;
    place-items: end center;
    padding-bottom: 0.35rem;
    font-size: 0.55rem;
    font-weight: 800;
    letter-spacing: 0.1em;
    box-shadow: 0 12px 28px rgba(1, 7, 20, 0.26);
  }

  .deck-file-icon__fold {
    position: absolute;
    top: 0;
    right: 0;
    width: 12px;
    height: 12px;
    background: linear-gradient(135deg, rgba(225, 229, 243, 0.96), rgba(255, 255, 255, 0.2));
    clip-path: polygon(100% 0, 100% 100%, 0 0);
  }
</style>
