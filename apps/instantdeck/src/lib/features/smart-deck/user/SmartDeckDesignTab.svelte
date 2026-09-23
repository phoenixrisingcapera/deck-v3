<script lang="ts">
  import SmartDeckTextPanel from './SmartDeckTextPanel.svelte';
  import type { SmartDeckAIGenerationState, SmartDeckDesignTaskType, SmartDeckUserSlideViewModel, SmartDeckUserVersionViewModel } from './smartDeckUserTypes';

  interface Props {
    selectedSlide: SmartDeckUserSlideViewModel | null;
    selectedVersion: SmartDeckUserVersionViewModel | null;
    selectedElementId: string | null;
    validationStatus: string | null;
    designTokens: Record<string, string> | null;
    typographySaving: boolean;
    typographyMessage: string;
    designState: SmartDeckAIGenerationState;
    designMessage: string;
    designBusyOptionKey: string | null;
    designOptions: Array<{ key: string; label: string; summary: string }>;
    generatedDesignOptions: Array<{ key: string; label: string; versionId: string }>;
    onSaveTypography: (input: { headingFont: string; bodyFont: string }) => void | Promise<void>;
    onSelectVersion: (versionId: string) => void;
    onGenerateBackgroundOption: (optionKey: string) => void;
  }
  let {
    selectedSlide,
    selectedVersion,
    selectedElementId,
    validationStatus,
    designTokens,
    typographySaving,
    typographyMessage,
    designState,
    designMessage,
    designBusyOptionKey,
    designOptions,
    generatedDesignOptions,
    onSaveTypography,
    onSelectVersion,
    onGenerateBackgroundOption
  }: Props = $props();
  let task = $state<SmartDeckDesignTaskType>('background');
  const tasks: Array<{key:SmartDeckDesignTaskType;label:string}> = [{key:'background',label:'Background'},{key:'style',label:'Style'},{key:'graph',label:'Graphs'},{key:'layout',label:'Layout'},{key:'typography',label:'Typography'},{key:'image',label:'Images'}];
</script>

<section class="design-tab">
  <header><h3>Design</h3><p>Compose visual changes without rewriting slide content.</p></header>
  <div class="summary"><span>Slide <strong>{selectedSlide?.number ?? '—'}</strong></span><span>Target <strong>{selectedElementId ? 'Element' : 'Slide'}</strong></span><span>Version <strong>{selectedVersion?.name ?? 'None'}</strong></span><span>Validation <strong>{validationStatus ?? 'Unavailable'}</strong></span></div>
  <div class="task-tabs" aria-label="Design tasks">{#each tasks as item}<button class:active={task===item.key} aria-pressed={task===item.key} onclick={() => task=item.key}>{item.label}</button>{/each}</div>
  {#if task === 'typography'}
    <SmartDeckTextPanel hasGeneratedSlide={Boolean(selectedSlide?.generatedSlideId)} {designTokens} saving={typographySaving} message={typographyMessage} onSave={onSaveTypography}/>
  {:else if task === 'background'}
    <div class="capability capability--background">
      <strong>Background</strong>
      <p>Generate reviewable background candidates from the current slide evidence and brand context. These modes are starting points, not locked templates.</p>
      <div class="background-options" aria-label="Background options">
        {#each designOptions as option}
          <article>
            <div>
              <strong>{option.label}</strong>
              <p>{option.summary}</p>
            </div>
            <button type="button" disabled={!selectedSlide || designState === 'generating'} onclick={() => onGenerateBackgroundOption(option.key)}>
              {designBusyOptionKey === option.key && designState === 'generating' ? 'Generating...' : 'Generate option'}
            </button>
          </article>
        {/each}
      </div>
      {#if generatedDesignOptions.length}
        <div class="generated-options" aria-label="Generated design options">
          {#each generatedDesignOptions as option}
            <button type="button" class:active={selectedVersion?.id === option.versionId} onclick={() => onSelectVersion(option.versionId)}>{option.label}</button>
          {/each}
        </div>
      {/if}
      {#if designMessage}
        <p class:error={designState === 'error'}>{designMessage}</p>
      {/if}
    </div>
  {:else}
    <div class="capability"><strong>{tasks.find((item)=>item.key===task)?.label}</strong><p>This visual task is defined and validated, but editing is disabled until its durable reviewable backend command exists. No fake values or silent content changes are sent.</p><button disabled>Create reviewable task</button></div>
  {/if}
</section>

<style>
  .design-tab,header,.capability{display:grid;gap:.75rem}h3,p{margin:0}header p,.capability p{color:#94a3b8;line-height:1.5}.summary{display:grid;grid-template-columns:1fr 1fr;gap:.4rem}.summary span{padding:.55rem;border-radius:8px;background:rgba(255,255,255,.04);color:#94a3b8;font-size:.72rem}.summary strong{display:block;color:#e2e8f0;margin-top:.2rem}.task-tabs{display:grid;grid-template-columns:repeat(3,1fr);gap:.35rem}.task-tabs button,.capability button,.generated-options button{border:1px solid rgba(255,255,255,.1);border-radius:9px;background:rgba(15,23,42,.8);color:#cbd5e1;padding:.55rem;cursor:pointer}.task-tabs button.active,.generated-options button.active{border-color:#8b5cf6;color:#fff;background:rgba(124,58,237,.16)}.capability{padding:.9rem;border:1px solid rgba(255,255,255,.08);border-radius:12px;background:rgba(15,23,42,.55)}.capability button:disabled{opacity:.55;cursor:not-allowed}.background-options{display:grid;gap:.6rem}.background-options article{display:grid;gap:.6rem;padding:.8rem;border:1px solid rgba(255,255,255,.08);border-radius:12px;background:rgba(8,13,27,.58)}.background-options article strong{color:#f8fafc}.generated-options{display:flex;flex-wrap:wrap;gap:.45rem}.error{color:#fca5a5}
</style>
