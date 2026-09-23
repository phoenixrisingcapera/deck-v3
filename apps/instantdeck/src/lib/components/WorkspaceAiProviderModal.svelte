<script lang="ts">
  import { createEventDispatcher, onMount } from 'svelte';
  import { deckServiceClient } from '$lib/api/deckServiceClient';
  import {
    loadWorkspaceAiProviderSummary,
    setWorkspaceAiProviderSummary
  } from '$lib/stores/workspaceAiProvider';
  import type { WorkspaceAiProvider, WorkspaceAiProviderRouteResponse } from '@deck-aistack-codes/shared';

  const dispatch = createEventDispatcher<{
    configured: WorkspaceAiProviderRouteResponse['summary'];
    skipped: WorkspaceAiProviderRouteResponse['summary'];
  }>();

  interface Props {
    workspaceId?: string | null;
    forceOpen?: boolean;
    allowSkip?: boolean;
    onClose?: () => void;
    onConfigured?: (summary: WorkspaceAiProviderRouteResponse['summary']) => void;
  }

  let { workspaceId = null, forceOpen = true, allowSkip = true, onClose, onConfigured }: Props = $props();

  let open = $state(false);
  let loadingState = $state<'booting' | 'idle' | 'saving'>('booting');
  let provider = $state<WorkspaceAiProvider>('openai');
  let preferredModel = $state('gpt-5');
  let reasoningModel = $state('gpt-5');
  let embeddingModel = $state('text-embedding-3-small');
  let apiKey = $state('');
  let errorMsg = $state('');
  let isConfigured = $state(false);

  // OpenAI is the active production provider. The other entries remain in the
  // compatibility map so historical persisted summaries can still render.
  const providerCopy: Record<WorkspaceAiProvider, { name: string; placeholder: string; defaultModel: string }> = {
    openai: { name: 'OpenAI', placeholder: 'sk-...', defaultModel: 'gpt-5' },
    openrouter: { name: 'OpenRouter', placeholder: 'disabled', defaultModel: '' },
    claude: { name: 'Claude', placeholder: 'disabled', defaultModel: '' },
    qwen: { name: 'Qwen — Alibaba Cloud', placeholder: 'sk-...', defaultModel: 'qwen-plus-2025-07-28' }
  };

  let availableModels = $state<WorkspaceAiProviderRouteResponse['summary']['availableModels']>([]);
  let defaults = $state<WorkspaceAiProviderRouteResponse['summary']['defaults']>({});

  const chatModels = $derived(availableModels.filter((model) => model.supportsChat));
  const reasoningModels = $derived(availableModels.filter((model) => model.supportsReasoning));
  const embeddingModels = $derived(availableModels.filter((model) => model.supportsEmbeddings));

  function applySummary(summary: WorkspaceAiProviderRouteResponse['summary'] | null) {
    if (!summary) return;
    if (summary.provider) provider = summary.provider;
    availableModels = summary.availableModels ?? [];
    defaults = summary.defaults ?? {};
    isConfigured = summary.isConfigured;
    preferredModel = summary.preferredModel ?? summary.defaults?.chat ?? preferredModel;
    reasoningModel = summary.reasoningModel ?? summary.defaults?.reasoning ?? preferredModel;
    embeddingModel = summary.embeddingModel ?? summary.defaults?.embedding ?? embeddingModel;
  }

  onMount(async () => {
    open = forceOpen;

    try {
      const summary = await loadWorkspaceAiProviderSummary(workspaceId);
      applySummary(summary);

      if (summary?.isConfigured && !forceOpen) {
        open = false;
      }
    } catch {
      errorMsg = 'Could not load workspace AI configuration.';
    } finally {
      loadingState = 'idle';
    }
  });

  $effect(() => {
    if (forceOpen) {
      open = true;
    }
  });

  async function dismissForNow() {
    if (isConfigured) {
      closeWithoutChangingConfiguration();
      return;
    }
    open = false;
    await persist(true);
  }

  function closeWithoutChangingConfiguration() {
    open = false;
    onClose?.();
  }

  async function persist(skipForNow = false) {
    errorMsg = '';
    loadingState = 'saving';

    try {
      const response = await deckServiceClient.saveWorkspaceAiProvider({
        provider,
        workspaceId,
        apiKey,
        preferredModel,
        reasoningModel,
        embeddingModel,
        skipForNow
      });

      setWorkspaceAiProviderSummary(response.summary, workspaceId);
      applySummary(response.summary);
      apiKey = '';
      open = false;
      dispatch(skipForNow ? 'skipped' : 'configured', response.summary);
      if (!skipForNow) onConfigured?.(response.summary);
    } catch (error) {
      errorMsg = error instanceof Error ? error.message : 'Could not save workspace AI configuration.';
    } finally {
      loadingState = 'idle';
    }
  }

  async function revokeProvider() {
    if (!window.confirm('Revoke this workspace AI key? Smart Deck will return to the configured platform provider.')) return;
    errorMsg = '';
    loadingState = 'saving';
    try {
      const response = await deckServiceClient.revokeWorkspaceAiProvider(workspaceId);
      setWorkspaceAiProviderSummary(response.summary, workspaceId);
      open = false;
      onConfigured?.(response.summary);
    } catch (error) {
      errorMsg = error instanceof Error ? error.message : 'Could not revoke workspace AI configuration.';
    } finally {
      loadingState = 'idle';
    }
  }
</script>

{#if open}
  <div class="modal-backdrop" role="presentation">
    <div class="provider-modal-shell" role="dialog" aria-modal="true" aria-labelledby="workspace-ai-modal-title">
      <section class="panel provider-modal">
        <header class="modal-top">
          <div class="modal-copy">
            <div class="eyebrow">Workspace access</div>
            <h2 id="workspace-ai-modal-title">Connect your own AI key</h2>
            <p class="muted">OpenAI is the default. Add a key only if this workspace should use its own OpenAI project quota.</p>
          </div>

          <button class="dismiss-button" type="button" onclick={allowSkip ? dismissForNow : closeWithoutChangingConfiguration} disabled={loadingState === 'saving'}>
            {allowSkip ? 'Maybe later' : 'Close'}
          </button>
        </header>

        <div class="provider-tabs">
          <button class:active={provider === 'openai'} type="button" onclick={() => { provider = 'openai'; preferredModel = defaults.chat ?? providerCopy.openai.defaultModel; reasoningModel = defaults.reasoning ?? defaults.chat ?? providerCopy.openai.defaultModel; embeddingModel = defaults.embedding ?? 'text-embedding-3-small'; }}>
            OpenAI
          </button>
          <!-- DISABLED: Qwen was the previous production tab. Restore only if
               the product owner explicitly re-enables multi-provider selection. -->
          <!--
          <button class:active={provider === 'qwen'} type="button" onclick={() => { provider = 'qwen'; preferredModel = providerCopy.qwen.defaultModel; }}>
            Qwen
          </button>
          <button class:active={provider === 'claude'} type="button" onclick={() => { provider = 'claude'; preferredModel = providerCopy.claude.defaultModel; }}>
            Claude
          </button>
          <button class:active={provider === 'openrouter'} type="button" onclick={() => { provider = 'openrouter'; preferredModel = providerCopy.openrouter.defaultModel; }}>
            OpenRouter
          </button>
          -->
        </div>

        <form class="provider-form" onsubmit={(event) => { event.preventDefault(); persist(false); }}>
          <label>
            <span>API key</span>
            <input
              id="workspace-ai-provider-api-key"
              name="apiKey"
              type="password"
              autocomplete="new-password"
              bind:value={apiKey}
              placeholder={isConfigured ? 'Leave blank to keep the current key' : providerCopy[provider].placeholder}
            />
          </label>

          <label>
            <span>Optional model preference</span>
            <select bind:value={preferredModel}>
              {#each chatModels as model}
                <option value={model.id}>{model.label}</option>
              {/each}
            </select>
          </label>

          <label>
            <span>Reasoning model</span>
            <select bind:value={reasoningModel}>
              {#each reasoningModels as model}
                <option value={model.id}>{model.label}</option>
              {/each}
            </select>
          </label>

          <label>
            <span>Embedding model</span>
            <select bind:value={embeddingModel}>
              {#each embeddingModels as model}
                <option value={model.id}>{model.label}</option>
              {/each}
            </select>
          </label>

          {#if !chatModels.length || !embeddingModels.length}
            <p class="trust-note">Automatic model discovery is not available yet for this provider, so only compatible catalog models are shown.</p>
          {/if}

          <p class="trust-note">
            {isConfigured
              ? 'Leave the key blank to save model changes. Enter a new key only to rotate the workspace credential.'
              : 'We verify the key, encrypt it, and use it only for this workspace.'}
          </p>

          {#if errorMsg}
            <p class="error-copy">{errorMsg}</p>
          {/if}

          <div class="modal-actions">
            {#if isConfigured}
              <button class="button secondary-cta" type="button" disabled={loadingState !== 'idle'} onclick={revokeProvider}>
                Revoke workspace key
              </button>
            {/if}
            <button class="button primary-cta" type="submit" disabled={loadingState !== 'idle' || (!isConfigured && !apiKey.trim())}>
              {loadingState === 'saving' ? 'Saving...' : isConfigured && !apiKey.trim() ? 'Save models' : 'Save and connect'}
            </button>
          </div>
        </form>
      </section>
    </div>
  </div>
{/if}

<style>
  .modal-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(5, 11, 31, 0.72);
    backdrop-filter: blur(14px);
    display: grid;
    place-items: center;
    padding: 1.5rem;
    z-index: 50;
  }

  .provider-modal-shell {
    width: min(560px, 100%);
    position: relative;
  }

  .provider-modal {
    width: min(560px, 100%);
    padding: 1.5rem;
    display: grid;
    gap: 1.1rem;
    box-shadow: var(--shadow);
  }

  .modal-top {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    align-items: start;
  }

  .modal-copy {
    display: grid;
    gap: 0.45rem;
  }

  h2 {
    margin: 0;
    font-size: clamp(1.7rem, 3vw, 2.1rem);
    letter-spacing: -0.04em;
  }

  .dismiss-button {
    border: 1px solid var(--line);
    border-radius: 999px;
    background: var(--surface-soft);
    color: var(--ink-soft);
    min-height: 42px;
    padding: 0.7rem 1rem;
    white-space: nowrap;
  }

  .provider-tabs {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 0.65rem;
  }

  .provider-tabs button {
    min-height: 52px;
    padding: 0.85rem 1rem;
    border-radius: 16px;
    border: 1px solid var(--line);
    background: var(--surface-soft);
    color: var(--ink);
    font-weight: 600;
  }

  .provider-tabs button.active {
    background: var(--surface-active);
    color: var(--ink-strong);
    border-color: var(--line-strong);
  }

  .provider-form {
    display: grid;
    gap: 1rem;
  }

  .provider-form label {
    display: grid;
    gap: 0.45rem;
    color: var(--ink-soft);
    font-size: 0.95rem;
  }

  .provider-form input,
  .provider-form select {
    border-radius: 16px;
    border: 1px solid var(--line);
    background: var(--surface-input);
    color: var(--ink);
    padding: 0.9rem 1rem;
  }

  .trust-note {
    margin: 0;
    color: var(--muted);
    font-size: 0.9rem;
    line-height: 1.55;
  }

  .modal-actions {
    display: flex;
    gap: 0.75rem;
    justify-content: flex-end;
  }

  .error-copy {
    margin: 0;
    color: var(--danger);
  }

  @media (max-width: 720px) {
    .modal-backdrop {
      padding: 1rem 0.85rem;
    }

    .modal-top {
      flex-direction: column;
      align-items: stretch;
    }

    .modal-actions .button {
      width: 100%;
    }
  }
</style>
