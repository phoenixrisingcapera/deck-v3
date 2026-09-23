<script lang="ts">
  import type { SmartDeckAssistantRunResponse } from '$lib/api/smartDeckWorkspace';

  type ChatMessage = { role: 'user' | 'assistant' | 'system'; content: string };

  interface Props {
    messages: ChatMessage[];
    conversationState: 'idle' | 'sending' | 'error';
    conversationMessage?: string;
    onSendConversation: (instruction: string) => void;
    latestAssistantRun?: SmartDeckAssistantRunResponse | null;
    saveInsightState?: 'idle' | 'saving' | 'saved' | 'error';
    saveInsightMessage?: string;
    onSaveInsight?: () => void;
    title?: string;
    eyebrow?: string;
    description?: string;
    emptyText?: string;
    placeholder?: string;
    sendLabel?: string;
    sendingLabel?: string;
    retryAvailable?: boolean;
    onRetry?: () => void;
    infoHref?: string;
    workspaceRegion?: boolean;
    belowToolbar?: boolean;
  }

  let {
    messages,
    conversationState,
    conversationMessage = '',
    onSendConversation,
    latestAssistantRun = null,
    saveInsightState = 'idle',
    saveInsightMessage = '',
    onSaveInsight,
    title = 'Deck assistant',
    eyebrow = 'Conversation',
    description = 'Ask about the selected slide or the whole deck.',
    emptyText = 'Start a conversation about evidence, narrative, risks, or audience fit. Messages are saved to the workspace.',
    placeholder = 'Ask about this deck...',
    sendLabel = 'Ask',
    sendingLabel = 'Thinking...',
    retryAvailable = false,
    onRetry,
    infoHref,
    workspaceRegion = false,
    belowToolbar = false
  }: Props = $props();

  let conversationDraft = $state('');

  function submitConversation() {
    const instruction = conversationDraft.trim();
    if (!instruction || conversationState === 'sending') return;
    onSendConversation(instruction);
    conversationDraft = '';
  }
</script>

<section class="global-deck-chat-panel" class:global-deck-chat-panel--workspace={workspaceRegion} data-below-toolbar={belowToolbar ? 'true' : undefined} data-deck-region="chat" aria-label="Global deck chat">
  <header>
    <div>
      <span>{eyebrow}</span>
      <h3>{title}</h3>
    </div>
    {#if infoHref}
      <a class="conversation__info" href={infoHref} aria-label="Open LLM report" title="Open LLM report">i</a>
    {/if}
    <p>{description}</p>
  </header>

  <div class="conversation__messages" aria-live="polite">
    {#if messages.length}
      {#each messages as message}
        <article class:assistant={message.role === 'assistant'}>
          <span>{message.role === 'assistant' ? 'Assistant' : 'You'}</span>
          <p>{message.content}</p>
        </article>
      {/each}
    {:else}
      <p class="conversation__empty">{emptyText}</p>
    {/if}
  </div>

  {#if latestAssistantRun?.insight}
    <article class="conversation__insight">
      <strong>{latestAssistantRun.insight.title}</strong>
      <p>{latestAssistantRun.insight.summary}</p>
      {#if latestAssistantRun.insight.missingEvidence.length > 0}
        <div class="conversation__insight-list">
          <span>Missing evidence</span>
          <ul>
            {#each latestAssistantRun.insight.missingEvidence as item}
              <li>{item}</li>
            {/each}
          </ul>
        </div>
      {/if}
      <div class="conversation__insight-actions">
        <button type="button" disabled={saveInsightState === 'saving' || saveInsightState === 'saved'} onclick={onSaveInsight}>
          {saveInsightState === 'saving' ? 'Saving...' : saveInsightState === 'saved' ? 'Saved to export' : 'Save this response'}
        </button>
        {#if saveInsightMessage}<small class:is-error={saveInsightState === 'error'}>{saveInsightMessage}</small>{/if}
      </div>
    </article>
  {/if}

  {#if retryAvailable}
    <button class="conversation__retry" type="button" disabled={conversationState === 'sending'} onclick={onRetry}>Retry last message</button>
  {/if}
  <form onsubmit={(event) => { event.preventDefault(); submitConversation(); }}>
    <textarea bind:value={conversationDraft} rows="3" {placeholder} disabled={conversationState === 'sending'}></textarea>
    <button type="submit" disabled={!conversationDraft.trim() || conversationState === 'sending'}>{conversationState === 'sending' ? sendingLabel : sendLabel}</button>
  </form>
  {#if conversationMessage}<p class="status" class:is-error={conversationState === 'error'}>{conversationMessage}</p>{/if}
</section>

<style>
  .global-deck-chat-panel {
    min-height: 100%;
    display: grid;
    grid-template-rows: auto minmax(8rem, 1fr) auto auto;
    align-content: start;
    gap: 0.75rem;
  }

  .global-deck-chat-panel--workspace {
    grid-column: 4;
    grid-row: 1 / -1;
    min-width: 0;
    min-height: 0;
    overflow-y: auto;
    padding: 1rem;
    border-left: 1px solid rgba(255, 255, 255, 0.08);
    background: rgba(16, 24, 39, 0.96);
  }

  .global-deck-chat-panel--workspace[data-below-toolbar='true'] {
    grid-row: 2 / -1;
  }

  header {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 0.25rem;
    padding-bottom: 0.75rem;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  }

  header div { display: grid; gap: 0.15rem; }
  header p { grid-column: 1 / -1; }
  header span, .conversation__messages span { color: #a5b4fc; font-size: 0.68rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; }
  h3, p { margin: 0; }
  h3 { color: #f8fafc; }
  header p, .status { color: #94a3b8; font-size: 0.82rem; line-height: 1.5; }
  .conversation__info {
    width: 25px;
    height: 25px;
    display: grid;
    place-items: center;
    align-self: start;
    border: 1px solid rgba(165, 180, 252, 0.45);
    border-radius: 999px;
    color: #c7d2fe;
    background: rgba(99, 102, 241, 0.1);
    font: 700 0.78rem/1 system-ui, sans-serif;
    text-decoration: none;
  }
  .conversation__info:hover,
  .conversation__info:focus-visible {
    border-color: #a5b4fc;
    color: #fff;
    background: rgba(99, 102, 241, 0.24);
    outline: none;
  }

  .conversation__messages { display: grid; align-content: start; gap: 0.5rem; min-height: 0; overflow-y: auto; }
  .conversation__messages article { padding: 0.65rem; border: 1px solid rgba(255,255,255,.07); border-radius: 10px; background: rgba(15,23,42,.88); }
  .conversation__messages article.assistant { border-color: rgba(14,165,233,.3); }
  .conversation__messages p, .conversation__empty { margin-top: 0.2rem; color: #e2e8f0; font-size: 0.82rem; line-height: 1.5; white-space: pre-wrap; }
  .conversation__empty { padding: 0.75rem; border: 1px dashed rgba(148,163,184,.18); border-radius: 10px; color: #94a3b8; }

  form { display: grid; grid-template-columns: minmax(0,1fr) auto; gap: 0.45rem; align-items: end; }
  textarea { width: 100%; min-height: 5rem; resize: vertical; border: 1px solid rgba(255,255,255,.1); border-radius: 10px; background: rgba(15,23,42,.85); color: #f8fafc; padding: 0.7rem; font: inherit; }
  form button { height: 40px; padding: 0 0.8rem; border: 0; border-radius: 9px; background: #2563eb; color: white; font: inherit; }
  button:disabled { cursor: not-allowed; opacity: 0.55; }
  .conversation__retry { justify-self: start; min-height: 34px; padding: 0 .75rem; border: 1px solid rgba(245,158,11,.3); border-radius: 9px; background: rgba(245,158,11,.08); color: #fef3c7; }

  .conversation__insight { display: grid; gap: .55rem; padding: .65rem; border: 1px solid rgba(255,255,255,.07); border-radius: 9px; background: rgba(15,23,42,.88); }
  .conversation__insight p { color: #cbd5e1; font-size: 0.82rem; line-height: 1.5; }
  .conversation__insight-list { display: grid; gap: .3rem; }
  .conversation__insight-list span, .conversation__insight-actions small { color: #94a3b8; font-size: .75rem; }
  .conversation__insight-list ul { margin: 0; padding-left: 1rem; color: #e2e8f0; font-size: .78rem; }
  .conversation__insight-actions { display: grid; gap: .4rem; }
  .conversation__insight-actions button { justify-self: start; height: 34px; padding: 0 .75rem; border: 1px solid rgba(124,58,237,.3); border-radius: 9px; background: rgba(124,58,237,.14); color: #f5f3ff; }
  .is-error { color: #fca5a5; }

  @media (max-width: 960px) {
    .global-deck-chat-panel--workspace { grid-column: 3; }
  }

  @media (max-width: 720px) {
    .global-deck-chat-panel--workspace { grid-column: 1; grid-row: 4; min-height: 28rem; max-height: 70vh; }
  }
</style>
