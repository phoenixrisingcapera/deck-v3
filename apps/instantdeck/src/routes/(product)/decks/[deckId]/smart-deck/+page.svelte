<script lang="ts">
  import UserSmartDeckWorkspace from '$lib/features/smart-deck/user/UserSmartDeckWorkspace.svelte';
  import ProductDeveloperVisibilityCard from '$components/visibility/DeveloperVisibilityCard.svelte';
  import { createDeveloperVisibilityItems as createProductDeveloperVisibilityItems, type ProductDeveloperToolsPayload } from '$lib/developer-tools/payload';
  import type { PageData } from './$types';
  let { data }: { data: PageData } = $props();
  const mountedDeveloperToolsPayload = $derived(data.developerToolsPayload as ProductDeveloperToolsPayload);
  const instantDeckRuntime = $derived(
    (data.smartDeckWorkspace?.runtimeCapabilities?.instantDeck ?? null) as {
      generationMode?: string;
      knowledgePack?: { name?: string; version?: string; source?: string; moduleCount?: number } | null;
      promptPackage?: { name?: string; version?: string; sections?: string[] } | null;
      agentOrchestration?: {
        agentKey?: string;
        commandRoute?: string;
        workflowJobType?: string | null;
        jobChain?: string[];
        workerServices?: string[];
        requiredInputFields?: string[];
      } | null;
    } | null
  );
  const mountedDeveloperDiagnostics = $derived(
    createProductDeveloperVisibilityItems(mountedDeveloperToolsPayload, [
      { label: 'Workflow next action', value: mountedDeveloperToolsPayload.workflow.nextAction ?? null },
      { label: 'Primary request id', value: mountedDeveloperToolsPayload.correlation.requestId ?? null },
      { label: 'Primary failure ticket', value: mountedDeveloperToolsPayload.correlation.ticketId ?? null },
      { label: 'Instant Deck mode', value: instantDeckRuntime?.generationMode ?? null },
      { label: 'Instant Deck knowledge pack', value: instantDeckRuntime?.knowledgePack?.name ?? null },
      { label: 'Instant Deck knowledge version', value: instantDeckRuntime?.knowledgePack?.version ?? null },
      { label: 'Instant Deck knowledge source', value: instantDeckRuntime?.knowledgePack?.source ?? null },
      {
        label: 'Instant Deck knowledge modules',
        value: typeof instantDeckRuntime?.knowledgePack?.moduleCount === 'number' ? String(instantDeckRuntime.knowledgePack.moduleCount) : null
      },
      { label: 'Instant Deck prompt package', value: instantDeckRuntime?.promptPackage?.name ?? null },
      { label: 'Instant Deck prompt version', value: instantDeckRuntime?.promptPackage?.version ?? null },
      { label: 'Instant Deck prompt sections', value: instantDeckRuntime?.promptPackage?.sections?.join(' → ') ?? null },
      { label: 'Instant Deck agent key', value: instantDeckRuntime?.agentOrchestration?.agentKey ?? null },
      { label: 'Instant Deck command route', value: instantDeckRuntime?.agentOrchestration?.commandRoute ?? null },
      { label: 'Instant Deck workflow job type', value: instantDeckRuntime?.agentOrchestration?.workflowJobType ?? null },
      { label: 'Instant Deck worker chain', value: instantDeckRuntime?.agentOrchestration?.workerServices?.join(' → ') ?? null },
      { label: 'Instant Deck job chain', value: instantDeckRuntime?.agentOrchestration?.jobChain?.join(' → ') ?? null },
      { label: 'Instant Deck required inputs', value: instantDeckRuntime?.agentOrchestration?.requiredInputFields?.join(', ') ?? null }
    ])
  );
</script>

{#key data.graph.deck.id}
  <UserSmartDeckWorkspace
    workspaceLabel={data.workspaceLabel}
    currentDeckLabel={data.currentDeckLabel}
    graph={data.graph}
    initialWorkspace={data.smartDeckWorkspace}
    initialProperties={data.properties}
    initialWorkspacePreferences={data.workspacePreferences}
    initialSelectedSlideId={data.selectedSlideId}
    instantMode={data.instantDeckMode === true}
    fallbackMessage={data.smartDeckWorkspaceStatus?.message ?? null}
    fallbackActionHref={data.smartDeckWorkspaceStatus?.actionHref ?? null}
    fallbackActionLabel={data.smartDeckWorkspaceStatus?.actionLabel ?? null}
  />
{/key}

<ProductDeveloperVisibilityCard
  title="Smart Deck developer tools"
  summary="Deck-scoped readiness, degraded dependency, and request correlation for the mounted Smart Deck route."
  items={mountedDeveloperDiagnostics}
/>
