<script lang="ts">
  import type { RenderSchema } from '$lib/api/smartDeckWorkspace';
  import type { SmartDeckUserSlideViewModel } from './smartDeckUserTypes';
  import DeckMapPanel from './DeckMapPanel.svelte';
  import type { DeckGraph } from '$types/domain';

  interface Props {
    selectedSlide: SmartDeckUserSlideViewModel | null;
    selectedElementId: string | null;
    renderSchema: RenderSchema | null;
    graph: DeckGraph;
    onSelectElement: (renderElementId: string) => void;
    onOpenSmartEdit: () => void;
  }

  let { selectedSlide, selectedElementId, renderSchema, graph, onSelectElement, onOpenSmartEdit }: Props = $props();
  let view = $state<'elements' | 'analysis'>('elements');
  const renderElements = $derived(renderSchema?.elements ?? []);
  const persistedByKey = $derived(new Map((selectedSlide?.persistedElements ?? []).map((element) => [element.elementKey, element])));
  const selectedRender = $derived(renderElements.find((element) => element.id === selectedElementId) ?? null);
  const selectedPersisted = $derived(selectedRender ? persistedByKey.get(selectedRender.id) ?? null : null);

  function labelFor(type: string, text?: string | null) {
    if (type === 'chart_placeholder') return 'Chart';
    if (type === 'image') return 'Image';
    if (type === 'shape') return 'Shape';
    if (text && /[$€£%]|\d/.test(text)) return 'Metric or proof';
    return text && text.length < 80 ? 'Heading or label' : 'Body text';
  }
</script>

<section class="map-tab">
  <header><h3>Map</h3><p>Inspect this slide and choose the exact persisted element to target.</p></header>
  <div class="view-tabs" aria-label="Map views">
    <button class:active={view === 'elements'} aria-pressed={view === 'elements'} onclick={() => view = 'elements'}>Slide elements</button>
    <button class:active={view === 'analysis'} aria-pressed={view === 'analysis'} onclick={() => view = 'analysis'}>Deck Analysis</button>
  </div>
  {#if view === 'analysis'}
    <DeckMapPanel {graph} />
  {:else if !selectedSlide}
    <div class="state">Select a slide to inspect its elements.</div>
  {:else if !selectedSlide.hasGeneratedVersion}
    <div class="state"><strong>No generated version</strong><p>Source content remains read-only until this slide has a generated version.</p></div>
  {:else if !renderElements.length}
    <div class="state"><strong>Visual mapping unavailable</strong><p>No active render schema elements are available. Generate or repair this slide version.</p></div>
  {:else}
    <div class="element-list" aria-label="Persisted slide elements">
      {#each renderElements as element, index (element.id)}
        {@const persisted = persistedByKey.get(element.id)}
        <button class:selected={element.id === selectedElementId} class:readonly={!persisted} disabled={!persisted} onclick={() => onSelectElement(element.id)}>
          <span class="order">{index + 1}</span><span><strong>{labelFor(element.type, element.text)}</strong><small>{element.text?.slice(0, 90) || element.type.replaceAll('_', ' ')}</small></span><em>{persisted ? 'Editable' : 'Read-only'}</em>
        </button>
      {/each}
    </div>
    {#if selectedRender}
      <article class="detail">
        <h4>Selected target</h4>
        <dl>
          <div><dt>Element</dt><dd>{labelFor(selectedRender.type, selectedRender.text)} · {selectedRender.type}</dd></div>
          <div><dt>Content</dt><dd>{selectedRender.text ?? 'Visual element'}</dd></div>
          <div><dt>Persisted ID</dt><dd>{selectedPersisted?.id ?? 'Not linked'}</dd></div>
          <div><dt>Render key</dt><dd>{selectedRender.id}</dd></div>
          <div><dt>Bounds</dt><dd>{selectedRender.x}, {selectedRender.y} · {selectedRender.width} × {selectedRender.height}</dd></div>
        </dl>
        <button class="smart-edit" onclick={onOpenSmartEdit}>Open Smart Edit</button>
      </article>
    {/if}
  {/if}
</section>

<style>
  .map-tab, header, .detail, dl { display:grid; gap:.75rem; } h3,h4,p,dl,dt,dd{margin:0} header p,.state p{color:#94a3b8;line-height:1.5}.view-tabs{display:grid;grid-template-columns:1fr 1fr;gap:.35rem}.view-tabs button,.element-list button,.smart-edit{border:1px solid rgba(255,255,255,.1);border-radius:10px;background:rgba(15,23,42,.8);color:#cbd5e1;padding:.65rem;cursor:pointer}.view-tabs button.active,.element-list button.selected{border-color:#8b5cf6;background:rgba(124,58,237,.16);color:#fff}.element-list{display:grid;gap:.45rem}.element-list button{display:grid;grid-template-columns:24px 1fr auto;gap:.55rem;text-align:left;align-items:start}.element-list button.readonly{opacity:.65}.element-list span{display:grid;gap:.2rem}.element-list small,.element-list em{color:#94a3b8;font-size:.72rem;font-style:normal}.order{color:#a78bfa}.state,.detail{padding:.85rem;border:1px solid rgba(255,255,255,.08);border-radius:12px;background:rgba(15,23,42,.55)}dl div{display:grid;gap:.25rem;padding-bottom:.45rem;border-bottom:1px solid rgba(255,255,255,.06)}dt{font-size:.7rem;color:#94a3b8;text-transform:uppercase}dd{color:#e2e8f0;overflow-wrap:anywhere}.smart-edit{background:linear-gradient(135deg,#7c3aed,#0ea5e9);color:#fff;font-weight:800}
</style>
