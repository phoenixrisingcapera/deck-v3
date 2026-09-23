<!-- Purpose: chooses between render schema or static slide fallback and renders a reusable preview surface. -->
<script lang="ts">
  import type { RenderSchema } from '$lib/api/smartDeckWorkspace';

  interface Props {
    renderSchema?: RenderSchema | null;
    designTokens?: Record<string, string> | null;
    selectedElementId?: string | null;
    onSelectElement?: (elementId: string) => void;
    onActivateElement?: (elementId: string) => void;
    onChangeElementGeometry?: (elementId: string, geometry: { x: number; y: number; width: number; height: number }) => void;
    lockedElementIds?: string[];
    interactive?: boolean;
    editable?: boolean;
  }

  let { renderSchema = null, designTokens = null, selectedElementId = null, onSelectElement, onActivateElement, onChangeElementGeometry, lockedElementIds = [], interactive = true, editable = false }: Props = $props();

  type DragSession = {
    elementId: string;
    mode: 'move' | 'resize';
    resizeCorner?: 'nw' | 'ne' | 'sw' | 'se';
    startClientX: number;
    startClientY: number;
    startX: number;
    startY: number;
    startWidth: number;
    startHeight: number;
    scaleX: number;
    scaleY: number;
  };

  let dragSession = $state<DragSession | null>(null);
  const lockedIds = $derived(new Set(lockedElementIds));

  function isElementLocked(elementId: string) {
    return lockedIds.has(elementId);
  }

  function elementAriaLabel(kind: string, elementId: string) {
    return `${isElementLocked(elementId) ? 'Select locked' : 'Select'} generated ${kind} ${elementId}`;
  }

  function keyboardDescriptionId(elementId: string) {
    return editable && !isElementLocked(elementId) ? 'generated-slide-keyboard-layout-help' : undefined;
  }

  function clamp(value: number, minimum: number, maximum: number) {
    return Math.min(Math.max(value, minimum), Math.max(minimum, maximum));
  }

  function startGeometryChange(event: PointerEvent, element: RenderSchema['elements'][number], mode: DragSession['mode'], resizeCorner?: DragSession['resizeCorner']) {
    if (!editable || !renderSchema || isElementLocked(element.id)) return;
    event.preventDefault();
    event.stopPropagation();
    const bounds = (event.currentTarget as HTMLElement).closest('.render-stage')?.getBoundingClientRect();
    if (!bounds?.width || !bounds.height) return;
    (event.currentTarget as HTMLElement).setPointerCapture?.(event.pointerId);
    onSelectElement?.(element.id);
    dragSession = {
      elementId: element.id,
      mode,
      resizeCorner,
      startClientX: event.clientX,
      startClientY: event.clientY,
      startX: element.x,
      startY: element.y,
      startWidth: element.width,
      startHeight: element.height,
      scaleX: renderSchema.width / bounds.width,
      scaleY: renderSchema.height / bounds.height
    };
  }

  function updateGeometry(event: PointerEvent) {
    if (!dragSession || !renderSchema) return;
    if (!editable || isElementLocked(dragSession.elementId)) {
      dragSession = null;
      return;
    }
    const deltaX = (event.clientX - dragSession.startClientX) * dragSession.scaleX;
    const deltaY = (event.clientY - dragSession.startClientY) * dragSession.scaleY;
    if (dragSession.mode === 'move') {
      onChangeElementGeometry?.(dragSession.elementId, {
        x: Math.round(clamp(dragSession.startX + deltaX, 0, renderSchema.width - dragSession.startWidth)),
        y: Math.round(clamp(dragSession.startY + deltaY, 0, renderSchema.height - dragSession.startHeight)),
        width: dragSession.startWidth,
        height: dragSession.startHeight
      });
      return;
    }
    const resizeWest = dragSession.resizeCorner?.includes('w') ?? false;
    const resizeNorth = dragSession.resizeCorner?.includes('n') ?? false;
    const minimumWidth = Math.min(24, resizeWest ? dragSession.startX + dragSession.startWidth : renderSchema.width - dragSession.startX);
    const minimumHeight = Math.min(24, resizeNorth ? dragSession.startY + dragSession.startHeight : renderSchema.height - dragSession.startY);
    const nextX = resizeWest ? Math.round(clamp(dragSession.startX + deltaX, 0, dragSession.startX + dragSession.startWidth - minimumWidth)) : dragSession.startX;
    const nextY = resizeNorth ? Math.round(clamp(dragSession.startY + deltaY, 0, dragSession.startY + dragSession.startHeight - minimumHeight)) : dragSession.startY;
    onChangeElementGeometry?.(dragSession.elementId, {
      x: nextX,
      y: nextY,
      width: resizeWest ? dragSession.startWidth + dragSession.startX - nextX : Math.round(clamp(dragSession.startWidth + deltaX, minimumWidth, renderSchema.width - dragSession.startX)),
      height: resizeNorth ? dragSession.startHeight + dragSession.startY - nextY : Math.round(clamp(dragSession.startHeight + deltaY, minimumHeight, renderSchema.height - dragSession.startY))
    });
  }

  function finishGeometryChange(event: PointerEvent) {
    if (dragSession && event.currentTarget instanceof HTMLElement && event.currentTarget.hasPointerCapture?.(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    dragSession = null;
  }

  function handleElementKeydown(event: KeyboardEvent, elementId: string) {
    if (editable && renderSchema && !isElementLocked(elementId) && ['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) {
      const element = renderSchema.elements.find((candidate) => candidate.id === elementId);
      if (!element) return;
      event.preventDefault();
      const step = event.shiftKey ? 10 : 1;
      const xDelta = event.key === 'ArrowLeft' ? -step : event.key === 'ArrowRight' ? step : 0;
      const yDelta = event.key === 'ArrowUp' ? -step : event.key === 'ArrowDown' ? step : 0;
      onChangeElementGeometry?.(elementId, event.altKey
        ? {
            x: element.x,
            y: element.y,
            width: Math.round(clamp(element.width + xDelta, Math.min(24, renderSchema.width - element.x), renderSchema.width - element.x)),
            height: Math.round(clamp(element.height + yDelta, Math.min(24, renderSchema.height - element.y), renderSchema.height - element.y))
          }
        : {
            x: clamp(element.x + xDelta, 0, renderSchema.width - element.width),
            y: clamp(element.y + yDelta, 0, renderSchema.height - element.height),
            width: element.width,
            height: element.height
          });
      return;
    }
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      if (interactive) {
        onSelectElement?.(elementId);
      }
    }
  }

  const tokens = $derived<Record<string, string>>({
    'brand.surface': 'var(--surface-strong)',
    'brand.surfaceAlt': 'var(--surface)',
    'brand.heading': 'var(--ink-strong)',
    'brand.body': 'var(--ink)',
    'brand.accent': 'var(--accent)',
    'brand.muted': 'var(--muted)',
    'brand.headingFont': 'Inter, sans-serif',
    'brand.bodyFont': 'Inter, sans-serif',
    ...(designTokens ?? {})
  });

  // Resolve deck tokens to concrete style values with fallback to raw text.
  function tokenValue(value?: string | null) {
    if (!value) return 'var(--ink)';
    return tokens[value] ?? value;
  }

  // Normalize only trusted URL shapes; drop unknown strings to avoid invalid image paths.
  function assetUrl(value?: string | null) {
    if (!value) return '';
    if (value.startsWith('/api/') || value.startsWith('/uploads/') || value.startsWith('/static/')) return value;
    return '';
  }

  // Build background CSS from supported schema background variants.
  function backgroundStyle(schema: RenderSchema) {
    const background = schema.background;
    if (background.type === 'layered') return tokenValue(background.fill);
    if (background.type === 'token') return tokenValue(background.value);
    if (background.type === 'gradient') {
      return (background.value ?? '')
        .replaceAll('brand.surfaceAlt', tokenValue('brand.surfaceAlt'))
        .replaceAll('brand.surface', tokenValue('brand.surface'))
        .replaceAll('brand.accent', tokenValue('brand.accent'));
    }
    if (background.type === 'image') return `center / cover no-repeat url("${assetUrl(background.value)}")`;
    return background.value ?? 'var(--surface-input-strong)';
  }

  // Build per-layer CSS for layered backgrounds using percentage coordinates from px schema.
  function backgroundLayerStyle(layer: NonNullable<RenderSchema['background']['layers']>[number], schema: RenderSchema) {
    const left = (layer.x / schema.width) * 100;
    const top = (layer.y / schema.height) * 100;
    const width = (layer.width / schema.width) * 100;
    const height = (layer.height / schema.height) * 100;
    const fill = tokenValue(layer.style?.fill);
    const opacity = layer.style?.opacity ?? 1;
    const radius = layer.shape === 'circle' ? 999 : layer.style?.radius ?? 0;
    return [
      `left:${left}%`,
      `top:${top}%`,
      `width:${width}%`,
      `height:${height}%`,
      `z-index:${layer.zIndex ?? 0}`,
      `background:${layer.type === 'shape' ? fill : 'transparent'}`,
      `opacity:${opacity}`,
      `border-radius:${radius}px`
    ].join(';');
  }

  // Build per-element style for rendering text/image/shape placeholders inside the preview stage.
  function elementStyle(element: RenderSchema['elements'][number], schema: RenderSchema) {
    const left = (element.x / schema.width) * 100;
    const top = (element.y / schema.height) * 100;
    const width = (element.width / schema.width) * 100;
    const height = (element.height / schema.height) * 100;
    const fontSize = element.fontSize ? `${(element.fontSize / schema.width) * 100}cqw` : '2.6cqw';
    const color = tokenValue(element.colorToken);
    const fill = tokenValue(element.fillToken);
    const fontFamily = element.fontWeight === 'bold' || Number(element.fontWeight) >= 600 ? tokenValue('brand.headingFont') : tokenValue('brand.bodyFont');
    return [
      `left:${left}%`,
      `top:${top}%`,
      `width:${width}%`,
      `height:${height}%`,
      `z-index:${element.zIndex ?? 20}`,
      `font-size:${fontSize}`,
      `font-family:${fontFamily}`,
      `color:${color}`,
      `background:${element.type === 'shape' ? fill : 'transparent'}`
    ].join(';');
  }
</script>

<svelte:window onpointermove={updateGeometry} onpointerup={finishGeometryChange} onpointercancel={finishGeometryChange} />

{#if renderSchema}
  <div class="render-stage" style={`background:${backgroundStyle(renderSchema)}`}>
    {#if editable}
      <p id="generated-slide-keyboard-layout-help" class="sr-only">Use arrow keys to move the selected element. Hold Alt with arrow keys to resize it. Hold Shift for larger steps.</p>
    {/if}
    {#if renderSchema.background.type === 'layered'}
      {#each renderSchema.background.layers ?? [] as layer}
        {#if layer.type === 'image' && assetUrl(layer.assetUrl)}
          <img class="background-layer" style={backgroundLayerStyle(layer, renderSchema)} src={assetUrl(layer.assetUrl)} alt="" />
        {:else if layer.type === 'shape'}
          <div class="background-layer" style={backgroundLayerStyle(layer, renderSchema)}></div>
        {/if}
      {/each}
    {/if}
    {#each renderSchema.elements as element}
      {#if !interactive}
        <div
          class={`render-element ${element.type === 'chart_placeholder' ? 'chart-placeholder' : element.type}`}
          style={elementStyle(element, renderSchema)}
          aria-hidden="true"
        >
          {#if element.type === 'image' && element.assetUrl}
            <img src={assetUrl(element.assetUrl)} alt="" />
          {:else if element.type === 'chart_placeholder'}
            <span>{element.text ?? 'Chart placeholder'}</span>
          {:else if element.type === 'text'}
            <span style={`font-weight:${element.fontWeight ?? 400}`}>{element.text}</span>
          {/if}
        </div>
      {:else if element.type === 'image' && element.assetUrl}
        <button
           class="render-element image"
           class:selected={selectedElementId === element.id}
           class:locked={isElementLocked(element.id)}
          style={elementStyle(element, renderSchema)}
          type="button"
            aria-label={elementAriaLabel('image element', element.id)}
            aria-describedby={keyboardDescriptionId(element.id)}
            aria-keyshortcuts="ArrowLeft ArrowRight ArrowUp ArrowDown Alt+ArrowLeft Alt+ArrowRight Alt+ArrowUp Alt+ArrowDown"
           onclick={() => onSelectElement?.(element.id)}
           ondblclick={() => onActivateElement?.(element.id)}
           onkeydown={(event) => handleElementKeydown(event, element.id)}
            onpointerdown={(event) => startGeometryChange(event, element, 'move')}
        >
          <span class="element-content"><img src={assetUrl(element.assetUrl)} alt="" /></span>
          {#if editable && !isElementLocked(element.id) && selectedElementId === element.id}
            <span class="move-grip" aria-hidden="true" onpointerdown={(event) => startGeometryChange(event, element, 'move')} ondblclick={(event) => event.stopPropagation()}></span>
            {#each ['nw', 'ne', 'sw', 'se'] as corner}<span class={`resize-handle resize-handle--${corner}`} aria-hidden="true" onpointerdown={(event) => startGeometryChange(event, element, 'resize', corner as DragSession['resizeCorner'])} ondblclick={(event) => event.stopPropagation()}></span>{/each}
          {/if}
        </button>
      {:else if element.type === 'shape'}
        <button
           class="render-element shape"
           class:selected={selectedElementId === element.id}
           class:locked={isElementLocked(element.id)}
          style={elementStyle(element, renderSchema)}
          type="button"
            aria-label={elementAriaLabel('shape element', element.id)}
            aria-describedby={keyboardDescriptionId(element.id)}
            aria-keyshortcuts="ArrowLeft ArrowRight ArrowUp ArrowDown Alt+ArrowLeft Alt+ArrowRight Alt+ArrowUp Alt+ArrowDown"
           onclick={() => onSelectElement?.(element.id)}
           ondblclick={() => onActivateElement?.(element.id)}
           onkeydown={(event) => handleElementKeydown(event, element.id)}
            onpointerdown={(event) => startGeometryChange(event, element, 'move')}
        >{#if editable && !isElementLocked(element.id) && selectedElementId === element.id}<span class="move-grip" aria-hidden="true" onpointerdown={(event) => startGeometryChange(event, element, 'move')} ondblclick={(event) => event.stopPropagation()}></span>{#each ['nw', 'ne', 'sw', 'se'] as corner}<span class={`resize-handle resize-handle--${corner}`} aria-hidden="true" onpointerdown={(event) => startGeometryChange(event, element, 'resize', corner as DragSession['resizeCorner'])} ondblclick={(event) => event.stopPropagation()}></span>{/each}{/if}</button>
      {:else if element.type === 'chart_placeholder'}
        <button
           class="render-element chart-placeholder"
           class:selected={selectedElementId === element.id}
           class:locked={isElementLocked(element.id)}
          style={elementStyle(element, renderSchema)}
          type="button"
            aria-label={elementAriaLabel('chart placeholder', element.id)}
            aria-describedby={keyboardDescriptionId(element.id)}
            aria-keyshortcuts="ArrowLeft ArrowRight ArrowUp ArrowDown Alt+ArrowLeft Alt+ArrowRight Alt+ArrowUp Alt+ArrowDown"
           onclick={() => onSelectElement?.(element.id)}
           ondblclick={() => onActivateElement?.(element.id)}
           onkeydown={(event) => handleElementKeydown(event, element.id)}
            onpointerdown={(event) => startGeometryChange(event, element, 'move')}
        >
          <span class="element-content"><span>{element.text ?? 'Chart placeholder'}</span></span>
          {#if editable && !isElementLocked(element.id) && selectedElementId === element.id}<span class="move-grip" aria-hidden="true" onpointerdown={(event) => startGeometryChange(event, element, 'move')} ondblclick={(event) => event.stopPropagation()}></span>{#each ['nw', 'ne', 'sw', 'se'] as corner}<span class={`resize-handle resize-handle--${corner}`} aria-hidden="true" onpointerdown={(event) => startGeometryChange(event, element, 'resize', corner as DragSession['resizeCorner'])} ondblclick={(event) => event.stopPropagation()}></span>{/each}{/if}
        </button>
      {:else}
        <button
           class="render-element text"
           class:selected={selectedElementId === element.id}
           class:locked={isElementLocked(element.id)}
          style={elementStyle(element, renderSchema)}
          type="button"
            aria-label={elementAriaLabel('text element', element.id)}
            aria-describedby={keyboardDescriptionId(element.id)}
            aria-keyshortcuts="ArrowLeft ArrowRight ArrowUp ArrowDown Alt+ArrowLeft Alt+ArrowRight Alt+ArrowUp Alt+ArrowDown"
           onclick={() => onSelectElement?.(element.id)}
           ondblclick={() => onActivateElement?.(element.id)}
           onkeydown={(event) => handleElementKeydown(event, element.id)}
            onpointerdown={(event) => startGeometryChange(event, element, 'move')}
        >
          <span class="element-content"><span style={`font-weight:${element.fontWeight ?? 400}`}>{element.text}</span></span>
          {#if editable && !isElementLocked(element.id) && selectedElementId === element.id}<span class="move-grip" aria-hidden="true" onpointerdown={(event) => startGeometryChange(event, element, 'move')} ondblclick={(event) => event.stopPropagation()}></span>{#each ['nw', 'ne', 'sw', 'se'] as corner}<span class={`resize-handle resize-handle--${corner}`} aria-hidden="true" onpointerdown={(event) => startGeometryChange(event, element, 'resize', corner as DragSession['resizeCorner'])} ondblclick={(event) => event.stopPropagation()}></span>{/each}{/if}
        </button>
      {/if}
    {/each}
  </div>
{:else}
  <div class="render-empty">No render schema saved</div>
{/if}

<style>
  .render-stage,
  .render-empty {
    width: min(100%, 72rem);
    aspect-ratio: 16 / 9;
    border-radius: 8px;
    border: 1px solid color-mix(in srgb, var(--line-strong) 72%, transparent);
    position: relative;
    overflow: visible;
    box-shadow: var(--shadow);
  }

  .render-stage {
    container-type: inline-size;
  }

  .sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
  }

  .render-empty {
    display: grid;
    place-items: center;
    color: var(--muted);
  }

  .render-element {
    position: absolute;
    overflow: hidden;
    border: 1px solid transparent;
    padding: 0;
    text-align: left;
    font: inherit;
    cursor: pointer;
    appearance: none;
    z-index: 20;
  }

  .render-element[aria-hidden='true'] {
    cursor: default;
    pointer-events: none;
  }

  .render-element:focus-visible {
    outline: 3px solid color-mix(in srgb, var(--accent) 82%, white);
    outline-offset: 2px;
  }

  .background-layer {
    position: absolute;
    display: block;
    pointer-events: none;
  }

  .render-element.text,
  .render-element.chart-placeholder {
    line-height: 1.08;
    overflow-wrap: anywhere;
  }

  .element-content { position: absolute; inset: 0; display: flex; align-items: flex-start; overflow: hidden; border-radius: inherit; pointer-events: none; }
  .render-element.chart-placeholder .element-content { align-items: center; justify-content: center; }

  .render-element.chart-placeholder {
    align-items: center;
    justify-content: center;
    border-color: color-mix(in srgb, var(--accent) 34%, transparent);
    border-style: dashed;
    color: var(--muted);
    background: color-mix(in srgb, var(--surface) 82%, transparent);
  }

  .render-element.shape {
    border-radius: 999px;
  }

  .render-element.image {
    display: block;
  }

  .render-element.image .element-content,
  .render-element.image img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }

  .render-element:hover,
  .render-element.selected {
    border-color: var(--accent);
    box-shadow: 0 0 0 2px var(--accent-soft);
  }

  .render-element.locked {
    cursor: not-allowed;
  }

  .resize-handle {
    position: absolute;
    width: 18px;
    height: 18px;
    background: var(--accent);
    filter: drop-shadow(0 0 1px white) drop-shadow(0 1px 2px rgba(0, 0, 0, 0.55));
    touch-action: none;
    z-index: 4;
    pointer-events: auto;
  }
  .resize-handle--nw { left: 1px; top: 1px; clip-path: polygon(0 0, 100% 0, 0 100%); cursor: nwse-resize; }
  .resize-handle--ne { right: 1px; top: 1px; clip-path: polygon(0 0, 100% 0, 100% 100%); cursor: nesw-resize; }
  .resize-handle--sw { left: 1px; bottom: 1px; clip-path: polygon(0 0, 0 100%, 100% 100%); cursor: nesw-resize; }
  .resize-handle--se { right: 1px; bottom: 1px; clip-path: polygon(100% 0, 0 100%, 100% 100%); cursor: nwse-resize; }
  .move-grip { position: absolute; left: 50%; top: 5px; width: 30px; height: 12px; transform: translateX(-50%); border: 1px solid color-mix(in srgb, white 84%, var(--accent)); border-radius: 999px; background-color: color-mix(in srgb, var(--accent) 88%, black); background-image: radial-gradient(circle, white 1.25px, transparent 1.5px); background-size: 6px 6px; cursor: move; touch-action: none; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.45); z-index: 5; pointer-events: auto; }
</style>
