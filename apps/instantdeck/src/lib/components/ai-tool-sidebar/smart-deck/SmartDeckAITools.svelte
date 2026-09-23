<script lang="ts">
  import type { DeckGraph } from '$types/domain';
  import type { RenderSchema } from '$lib/api/smartDeckWorkspace';
  import type { SmartDeckDeckType, SmartDeckSubject } from '$lib/types/smart-deck-subjects';
  import type {
    SmartDeckAIGenerationState,
    SmartDeckInspectorTab,
    SmartDeckUserSlideViewModel,
    SmartDeckUserVersionViewModel
  } from '$lib/features/smart-deck/user/smartDeckUserTypes';
  import AIToolSidebar from '$lib/components/ai-tool-sidebar/AIToolSidebar.svelte';
  import SmartDeckAiToolsPanel from '$lib/features/smart-deck/user/SmartDeckAiToolsPanel.svelte';
  import SmartDeckDesignTab from '$lib/features/smart-deck/user/SmartDeckDesignTab.svelte';
  import SmartDeckMapTab from '$lib/features/smart-deck/user/SmartDeckMapTab.svelte';

  interface Props {
    surface?: 'smart-deck' | 'instant-deck';
    activeTab: SmartDeckInspectorTab;
    selectedSlide: SmartDeckUserSlideViewModel | null;
    selectedElementId: string | null;
    renderSchema: RenderSchema | null;
    audience: string | null;
    deckType: SmartDeckDeckType;
    goal: SmartDeckSubject;
    prompt: string;
    generationState: SmartDeckAIGenerationState;
    generationMessage: string;
    generatedVersions: SmartDeckUserVersionViewModel[];
    selectedVersionId: string | null;
    selectedVersion: SmartDeckUserVersionViewModel | null;
    canApplySelectedVersion: boolean;
    validationStatus: string | null;
    designTokens: Record<string, string> | null;
    typographySaving: boolean;
    typographyMessage: string;
    designState: SmartDeckAIGenerationState;
    designMessage: string;
    designBusyOptionKey: string | null;
    designOptions: Array<{ key: string; label: string; summary: string }>;
    generatedDesignOptions: Array<{ key: string; label: string; versionId: string }>;
    audienceOptions: string[];
    deckTypeOptions: Array<{ value: SmartDeckDeckType; label: string }>;
    goalOptions: Array<{ value: SmartDeckSubject; label: string }>;
    quickActions: Array<{ label: string; prompt: string; goal: SmartDeckSubject }>;
    graph: DeckGraph;
    taskLabel?: string;
    focusedGeneration?: boolean;
    onClose: () => void;
    onTabChange: (tab: SmartDeckInspectorTab) => void;
    onAudienceChange: (value: string | null) => void;
    onDeckTypeChange: (value: SmartDeckDeckType) => void;
    onGoalChange: (value: SmartDeckSubject) => void;
    onPromptChange: (value: string) => void;
    onQuickAction: (prompt: string, goal: SmartDeckSubject) => void;
    onGenerate: () => void;
    onApply: () => void;
    onKeep: () => void;
    onDiscard: () => void;
    onSelectVersion: (versionId: string) => void;
    onOpenSmartEdit: () => void;
    onSelectElement: (renderElementId: string) => void;
    onSaveTypography: (input: { headingFont: string; bodyFont: string }) => void | Promise<void>;
    onGenerateBackgroundOption: (optionKey: string) => void;
    onSelectBackground: () => void;
    onSelectSlideContent: () => void;
    onSelectWholeDeck: () => void;
  }

  let {
    surface = 'smart-deck',
    activeTab,
    selectedSlide,
    selectedElementId,
    renderSchema,
    audience,
    deckType,
    goal,
    prompt,
    generationState,
    generationMessage,
    generatedVersions,
    selectedVersionId,
    selectedVersion,
    canApplySelectedVersion,
    validationStatus,
    designTokens,
    typographySaving,
    typographyMessage,
    designState,
    designMessage,
    designBusyOptionKey,
    designOptions,
    generatedDesignOptions,
    audienceOptions,
    deckTypeOptions,
    goalOptions,
    quickActions,
    graph,
    taskLabel = 'Whole deck',
    focusedGeneration = false,
    onClose,
    onTabChange,
    onAudienceChange,
    onDeckTypeChange,
    onGoalChange,
    onPromptChange,
    onQuickAction,
    onGenerate,
    onApply,
    onKeep,
    onDiscard,
    onSelectVersion,
    onOpenSmartEdit,
    onSelectElement,
    onSaveTypography,
    onGenerateBackgroundOption,
    onSelectBackground,
    onSelectSlideContent,
    onSelectWholeDeck
  }: Props = $props();

  const tabs = $derived<Array<{ key: SmartDeckInspectorTab; label: string }>>([
    { key: 'ask_ai', label: 'Generate' },
    ...(surface === 'instant-deck' ? [{ key: 'design' as const, label: 'Design' }] : []),
    { key: 'map', label: 'Map' }
  ]);

  function moveTabFocus(event: KeyboardEvent, index: number) {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    const buttons = Array.from(
      (event.currentTarget as HTMLButtonElement).parentElement?.querySelectorAll<HTMLButtonElement>('[role="tab"]') ?? []
    );
    if (!buttons.length) return;
    const nextIndex = event.key === 'Home'
      ? 0
      : event.key === 'End'
        ? buttons.length - 1
        : (index + (event.key === 'ArrowRight' ? 1 : -1) + buttons.length) % buttons.length;
    buttons[nextIndex]?.focus();
    onTabChange(tabs[nextIndex].key);
  }
</script>

<AIToolSidebar {surface} title={surface === 'instant-deck' ? 'Instant Deck' : 'Smart Deck'} open={true} {onClose}>
  <div class="tool-tabs" role="tablist" aria-label={`${surface === 'instant-deck' ? 'Instant Deck' : 'Smart Deck'} tools`}>
    {#each tabs as tab, index}
      <button
        type="button"
        role="tab"
        aria-selected={activeTab === tab.key}
        tabindex={activeTab === tab.key ? 0 : -1}
        class:active={activeTab === tab.key}
        onclick={() => onTabChange(tab.key)}
        onkeydown={(event) => moveTabFocus(event, index)}
      >{tab.label}</button>
    {/each}
  </div>

  <div class="tool-body" role="tabpanel">
    {#if activeTab === 'design'}
      <SmartDeckDesignTab
        {selectedSlide}
        {selectedVersion}
        {selectedElementId}
        {validationStatus}
        {designTokens}
        {typographySaving}
        {typographyMessage}
        {designState}
        {designMessage}
        {designBusyOptionKey}
        {designOptions}
        {generatedDesignOptions}
        {onSaveTypography}
        onSelectVersion={onSelectVersion}
        {onGenerateBackgroundOption}
      />
    {:else if activeTab === 'map'}
      <SmartDeckMapTab {selectedSlide} {selectedElementId} {renderSchema} {graph} {onSelectElement} {onOpenSmartEdit} />
    {:else}
      <section class="generation-tools" aria-label="Deck generation tools">
        {#if !focusedGeneration}
          <SmartDeckAiToolsPanel
            hasSelectedSlide={Boolean(selectedSlide)}
            {onSelectBackground}
            {onSelectSlideContent}
            {onSelectWholeDeck}
          />
        {/if}

        <details class="generation-context">
          <summary>Generation context</summary>
          <div class="generation-context__fields">
            <label>
              <span>Audience</span>
              <select value={audience ?? ''} onchange={(event) => onAudienceChange((event.currentTarget as HTMLSelectElement).value || null)}>
                {#each audienceOptions as option}<option value={option}>{option}</option>{/each}
              </select>
            </label>
            <label>
              <span>Deck type</span>
              <select value={deckType} onchange={(event) => onDeckTypeChange((event.currentTarget as HTMLSelectElement).value as SmartDeckDeckType)}>
                {#each deckTypeOptions as option}<option value={option.value}>{option.label}</option>{/each}
              </select>
            </label>
            <label>
              <span>Goal</span>
              <select value={goal} onchange={(event) => onGoalChange((event.currentTarget as HTMLSelectElement).value as SmartDeckSubject)}>
                {#each goalOptions as option}<option value={option.value}>{option.label}</option>{/each}
              </select>
            </label>
          </div>
        </details>

        <label>
          <span>Prompt</span>
          <textarea
            id="smart-deck-ai-prompt"
            rows="7"
            value={prompt}
            placeholder={focusedGeneration ? 'Describe the complete deck you want to generate.' : 'Describe the slide or whole-deck improvement you want.'}
            oninput={(event) => onPromptChange((event.currentTarget as HTMLTextAreaElement).value)}
          ></textarea>
        </label>
        <p class="task-scope">AI task: <strong>{taskLabel}</strong></p>

        {#if !focusedGeneration}
          <div class="quick-actions">
            {#each quickActions as action}
              <button type="button" onclick={() => onQuickAction(action.prompt, action.goal)}>{action.label}</button>
            {/each}
          </div>
        {/if}

        <button type="button" class="generate" disabled={generationState === 'generating' || !selectedSlide || !prompt.trim()} onclick={onGenerate}>
          {generationState === 'generating' ? 'Generating...' : 'Regenerate new deck'}
        </button>
        {#if generationMessage}<p class="status" class:is-error={generationState === 'error'} role="status">{generationMessage}</p>{/if}

        <section class="versions">
          <h3>Generated versions</h3>
          <div class="versions__list">
            {#if generatedVersions.length}
              {#each generatedVersions as version}
                <button type="button" class:active={version.id === selectedVersionId} onclick={() => onSelectVersion(version.id)}>
                  <span><strong>{version.label}</strong><small>{version.name}</small></span>
                  <small>{version.slideCount} slides</small>
                </button>
              {/each}
            {:else}
              <div class="versions__empty"><strong>No generated versions yet</strong><span>Add a prompt to create the first reviewable version.</span></div>
            {/if}
          </div>
          <div class="versions__actions">
            <button type="button" class="primary" disabled={!canApplySelectedVersion} onclick={onApply}>Apply</button>
            <button type="button" disabled={!selectedVersionId} onclick={onKeep}>Keep</button>
            <button type="button" class="danger" disabled={!selectedVersionId} onclick={onDiscard}>Discard</button>
          </div>
        </section>
      </section>
    {/if}
  </div>
</AIToolSidebar>

<style>
  .tool-tabs { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0.3rem; margin-bottom: 0.8rem; }
  .tool-tabs button { min-height: 38px; border: 1px solid rgba(255,255,255,.08); border-radius: 8px; background: rgba(15,23,42,.72); color: #94a3b8; font: inherit; cursor: pointer; }
  .tool-tabs button.active { border-color: rgba(129,140,248,.65); background: rgba(79,70,229,.16); color: #fff; }
  .tool-body, .generation-tools, .generation-context__fields, label, .versions, .versions__list { display: grid; gap: 0.75rem; }
  .generation-context { border: 1px solid rgba(255,255,255,.08); border-radius: 10px; background: rgba(15,23,42,.48); }
  .generation-context summary { padding: 0.7rem; color: #cbd5e1; font-size: 0.8rem; cursor: pointer; }
  .generation-context__fields { padding: 0 0.7rem 0.7rem; }
  label span, .task-scope { color: #cbd5e1; font-size: 0.78rem; }
  select, textarea { width: 100%; border: 1px solid rgba(255,255,255,.1); border-radius: 9px; background: rgba(15,23,42,.85); color: #f8fafc; padding: 0.7rem; font: inherit; }
  textarea { min-height: 7rem; resize: vertical; }
  .task-scope, .status { margin: 0; color: #94a3b8; font-size: 0.8rem; }
  .quick-actions { display: flex; flex-wrap: wrap; gap: 0.4rem; }
  .quick-actions button, .versions button { border: 1px solid rgba(255,255,255,.08); border-radius: 9px; background: rgba(15,23,42,.82); color: #dbeafe; padding: 0.55rem 0.65rem; font: inherit; cursor: pointer; }
  .generate { min-height: 42px; border: 0; border-radius: 9px; background: #4f46e5; color: #fff; font: inherit; font-weight: 700; cursor: pointer; }
  button:disabled { cursor: not-allowed; opacity: 0.5; }
  .status.is-error { color: #fca5a5; }
  .versions { padding-top: 0.75rem; border-top: 1px solid rgba(255,255,255,.08); }
  .versions h3 { margin: 0; font-size: 0.95rem; }
  .versions__list button { display: flex; justify-content: space-between; gap: 0.5rem; text-align: left; }
  .versions__list button span { display: grid; gap: 0.2rem; }
  .versions__list button.active { border-color: #818cf8; background: rgba(79,70,229,.16); }
  .versions__list small, .versions__empty span { color: #94a3b8; }
  .versions__empty { display: grid; gap: 0.3rem; padding: 0.75rem; border: 1px dashed rgba(255,255,255,.14); border-radius: 9px; }
  .versions__actions { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: 0.4rem; }
  .versions__actions button.primary { background: #4f46e5; color: #fff; }
  .versions__actions button.danger { color: #fda4af; }
</style>
