<script lang="ts">
  import { settings } from '$lib/stores/settings.svelte';
  import { flow } from '$lib/stores/flow.svelte';
  import AnchorOrchestrator from '$lib/components/AnchorOrchestrator.svelte';
  import OutlineGallery from '$lib/components/OutlineGallery.svelte';
  import OutlineDetail from '$lib/components/OutlineDetail.svelte';
  import FirmCreationModal from '$lib/components/FirmCreationModal.svelte';
  import DealCreationModal from '$lib/components/DealCreationModal.svelte';
  import JobView from '$lib/components/JobView.svelte';
  import BrandSetupModal from '$lib/components/BrandSetupModal.svelte';
  import SourceApproval from '$lib/components/SourceApproval.svelte';
</script>

{#if !settings.loaded}
  <div class="loading-shell">Loading…</div>
{:else if !settings.repoPath}
  <AnchorOrchestrator />
{:else if flow.stage.kind === 'running_job'}
  <JobView outline={flow.stage.outline} jobId={flow.stage.jobId} />
{:else if flow.stage.kind === 'approving_sources'}
  <!-- Full surface, not a modal: approving 40+ sources is list work, and a
       dialog box that size fights the task. -->
  <SourceApproval
    firm={settings.activeFirm ?? ''}
    deal={flow.stage.payload.companyName || flow.stage.payload.companyUrl}
  />
{:else}
  <OutlineGallery />

  {#if flow.stage.kind === 'outline_detail'}
    <OutlineDetail outline={flow.stage.outline} />
  {:else if flow.stage.kind === 'create_firm'}
    <FirmCreationModal outline={flow.stage.outline} />
  {:else if flow.stage.kind === 'create_deal' || flow.stage.kind === 'ready_to_run'}
    <DealCreationModal outline={flow.stage.outline} />
  {:else if flow.stage.kind === 'brand_setup'}
    <BrandSetupModal firm={flow.stage.firm} />
  {/if}
{/if}

<style>
  .loading-shell {
    padding: 4rem;
    text-align: center;
    color: #6b7280;
  }

  @media (prefers-color-scheme: dark) {
    .loading-shell {
      color: #9ca3af;
    }
  }
</style>
