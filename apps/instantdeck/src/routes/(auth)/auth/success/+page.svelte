<script lang="ts">
  import { goto } from '$app/navigation';
  import AuthSuccessLoader from '$lib/components/AuthSuccessLoader.svelte';
  import { validateSession } from '$lib/api/auth';
  import { deckServiceClient } from '$lib/api/deckServiceClient';

  let errorMessage = $state('');

  const steps = [
    'Validate session',
    'Resolve workspace summary',
    'Route into welcome or dashboard'
  ];

  async function resolveNextRoute() {
    try {
      const session = await validateSession();

      if (!session.valid) {
        await goto('/auth/sign-in');
        return;
      }

      const workspace = await deckServiceClient.getWorkspaceSummary();
      const nextUrl = workspace.workspace.deckCount === 0 ? '/welcome' : '/dashboard';
      await goto(nextUrl);
    } catch (error) {
      errorMessage = error instanceof Error ? error.message : 'Could not prepare your workspace.';
    }
  }

  $effect(() => {
    resolveNextRoute();
  });
</script>

<section class="success-page">
  <AuthSuccessLoader
    title="You are signed in."
    subtitle="Preparing your Deck AIStack workspace..."
    {steps}
    {errorMessage}
  />

  {#if errorMessage}
    <div class="success-actions">
      <a class="button" href="/dashboard">Continue to dashboard</a>
      <a class="button secondary" href="/auth/sign-in">Return to sign in</a>
    </div>
  {/if}
</section>

<style>
  .success-page {
    width: min(100%, 720px);
    margin: 0 auto;
    display: grid;
    gap: 1rem;
  }

  .success-actions {
    display: flex;
    gap: 0.8rem;
    flex-wrap: wrap;
  }
</style>
