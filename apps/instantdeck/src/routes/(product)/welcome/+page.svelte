<script lang="ts">
  import AppShell from '$components/AppShell.svelte';
  import WelcomeWorkspaceEntry from '$components/welcome/WelcomeWorkspaceEntry.svelte';
  import FirstDeckWorkflow from '$components/FirstDeckWorkflow.svelte';
  import type { PageData } from './$types';

  let { data }: { data: PageData } = $props();
</script>

<!--
DISABLED 2026-07-14: Minimal route-local welcome layout replaced by shared WelcomeWorkspaceEntry.svelte.
Reason: /welcome is the canonical signed-in route across the product, while the richer welcome-v2 conception
already existed as the better product narrative. Unifying around one shared component avoids route drift.

Previous structure:
- single hero with one Upload deck CTA
- optional recent decks list
- three static steps: Upload / Analyze / Improve
-->

<!-- The route owns the product chrome; WelcomeWorkspaceEntry is content-only. -->
<AppShell
  title="Welcome"
  subtitle="Upload a deck, review it with AI, and keep every suggestion reviewable before you apply it."
  activeNav="welcome"
  showTopBar={false}
  showFooterUtilities={true}
  deckLabel={data.workspace.workspace.name || 'Deck AIStack Workspace'}
>
  <WelcomeWorkspaceEntry
    workspace={data.workspace}
    routeNotice={data.routeNotice ?? null}
    workspaceLoadStatus={data.workspaceLoadStatus ?? null}
    developerToolsPayload={data.developerToolsPayload}
  />

  <FirstDeckWorkflow />
</AppShell>
