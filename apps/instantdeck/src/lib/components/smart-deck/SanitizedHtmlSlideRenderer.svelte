<script lang="ts">
  import { getCachedInstantHtmlCapability, mintInstantHtmlFullDeckCapability, type HtmlCompiledSlideRenderIdentity } from '$lib/api/smartDeckWorkspace';

  interface Props {
    slide: HtmlCompiledSlideRenderIdentity;
    mode?: 'visualizer' | 'miniature' | 'full-document';
    loading?: 'eager' | 'lazy';
    label?: string;
  }
  let { slide, mode = 'visualizer', loading = 'eager', label = 'Generated HTML slide' }: Props = $props();
  let container = $state<HTMLDivElement | null>(null);
  let renderUrl = $state<string | null>(null);
  let canvasScale = $state(1);

  $effect(() => {
    if (!container || mode === 'full-document') return;
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      if (width > 0 && height > 0) canvasScale = Math.min(width / 1920, height / 1080);
    });
    observer.observe(container);
    return () => observer.disconnect();
  });
  let loadState = $state<'loading' | 'ready' | 'failed'>('loading');
  let message = $state('Preparing slide…');
  let remintNonce = $state(0);
  const fullDocumentInstructionsId = $derived(`full-deck-instructions-${slide.generatedSlideId}`);

  function remintFullDocument() {
    renderUrl = null;
    loadState = 'loading';
    message = 'Reminting secure access to this exact compiled deck…';
    remintNonce += 1;
  }

  $effect(() => {
    const identity = `${slide.designVersionId}:${slide.htmlArtifactId}:${slide.artifactSha256}:${slide.generatedSlideId}:${slide.sectionId}:${slide.sectionSha256 ?? ''}:${slide.compilationHash ?? ''}:${mode}:${remintNonce}`;
    let current = true;
    let observer: IntersectionObserver | null = null;
    renderUrl = null;
    if (slide.renderProofStatus === 'failed') {
      loadState = 'failed';
      message = 'This generated slide failed browser render proof.';
      return;
    }
    if (slide.renderProofStatus !== 'ready') {
      loadState = 'loading';
      message = 'Preparing slide…';
      return;
    }
    loadState = 'loading';
    message = loading === 'lazy' ? 'Preparing slide…' : 'Preparing slide…';

    const load = () => {
      message = 'Preparing slide…';
      const capabilityRequest = mode === 'full-document'
        ? mintInstantHtmlFullDeckCapability(slide)
        : getCachedInstantHtmlCapability(slide);
      void capabilityRequest
        .then((capability) => {
          if (!current || identity !== `${slide.designVersionId}:${slide.htmlArtifactId}:${slide.artifactSha256}:${slide.generatedSlideId}:${slide.sectionId}:${slide.sectionSha256 ?? ''}:${slide.compilationHash ?? ''}:${mode}:${remintNonce}`) return;
          renderUrl = capability.renderUrl;
        })
        .catch((error) => {
          if (!current) return;
          loadState = 'failed';
          message = error instanceof Error ? error.message : mode === 'full-document' ? 'The complete generated deck could not be loaded securely.' : 'Generated slide could not be loaded securely.';
        });
    };

    if (loading === 'lazy' && container && typeof IntersectionObserver !== 'undefined') {
      observer = new IntersectionObserver((entries) => {
        if (!entries.some((entry) => entry.isIntersecting)) return;
        observer?.disconnect();
        load();
      }, { rootMargin: '160px' });
      observer.observe(container);
    } else {
      load();
    }

    return () => {
      current = false;
      observer?.disconnect();
    };
  });
</script>

<div bind:this={container} class:miniature={mode === 'miniature'} class:full-document={mode === 'full-document'} class="html-slide" data-render-mode="html_compiled.v1" data-display-scope={mode === 'full-document' ? 'full_deck' : 'section'} data-scroll-owner={mode === 'full-document' ? 'iframe' : undefined} data-design-version-id={slide.designVersionId} data-html-artifact-id={slide.htmlArtifactId} data-artifact-sha256={slide.artifactSha256} data-generated-slide-id={slide.generatedSlideId} data-section-id={slide.sectionId} aria-hidden={mode === 'miniature' ? 'true' : undefined}>
  {#if mode === 'full-document'}
    <p id={fullDocumentInstructionsId} class="sr-only">Complete generated deck. Focus this document and use arrow keys, Page Up, or Page Down to scroll vertically.</p>
  {/if}
  {#if renderUrl}
    <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
    <iframe
      title={label}
      style={mode === 'full-document' ? undefined : `width:1920px;height:1080px;min-height:0;transform:scale(${canvasScale});transform-origin:top left`}
      src={renderUrl}
      sandbox=""
      referrerpolicy="no-referrer"
      tabindex={mode === 'full-document' ? 0 : -1}
      aria-describedby={mode === 'full-document' ? fullDocumentInstructionsId : undefined}
      scrolling={mode === 'full-document' ? 'yes' : undefined}
      onload={() => { loadState = 'ready'; }}
      onerror={() => {
        loadState = 'failed';
        message = mode === 'full-document'
          ? 'Secure deck access expired or could not be loaded. Remint it to retry the same compiled version.'
          : 'Generated slide could not be loaded securely.';
      }}
    ></iframe>
  {/if}
  {#if mode === 'full-document'}
    <button type="button" class="remint" onclick={remintFullDocument}>{loadState === 'failed' ? 'Retry exact compiled deck' : 'Reload secure deck'}</button>
  {/if}
  {#if loadState !== 'ready'}
    <div class:failed={loadState === 'failed'} class="status" role={mode === 'miniature' ? undefined : loadState === 'failed' ? 'alert' : 'status'} aria-live={mode === 'miniature' ? 'off' : 'polite'}>{message}</div>
  {/if}
</div>

<style>
  .html-slide { position: relative; width: 100%; height: 100%; min-height: 320px; background: #fff; overflow: hidden; }
  iframe { display: block; width: 100%; height: 100%; min-height: 320px; border: 0; background: #fff; }
  .status { position: absolute; inset: 0; display: grid; place-items: center; padding: 1rem; color: #334155; background: #f8fafc; text-align: center; }
  .status.failed { color: #991b1b; background: #fef2f2; }
  .html-slide.miniature { min-height: 0; }
  .miniature iframe { pointer-events: none; }
  .miniature .status { padding: 0.4rem; font-size: 0.68rem; }
  .html-slide.full-document { height: 100%; min-height: 0; overflow: hidden; }
  .full-document iframe { height: 100%; min-height: 0; overflow: auto; overscroll-behavior: contain; }
  .remint { position: absolute; right: .75rem; bottom: .75rem; z-index: 2; padding: .45rem .7rem; border: 1px solid #94a3b8; border-radius: 9px; background: rgba(255,255,255,.94); color: #0f172a; font: inherit; font-size: .78rem; font-weight: 700; cursor: pointer; }
  .sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; border: 0; }
  @media (max-width: 720px) {
    .remint { right: .5rem; bottom: .5rem; max-width: calc(100% - 1rem); }
  }
</style>
