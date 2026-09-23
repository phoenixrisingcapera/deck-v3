<script lang="ts">
  import PublicAuthShell from '$components/PublicAuthShell.svelte';
</script>

<PublicAuthShell
  title="Page not found"
  subtitle="This route does not exist in the current Deck AIStack build."
>
  <section class="panel content">
    <div class="eyebrow">404</div>
    <h2>Page not found</h2>
    <p class="muted">Return to the dashboard or continue through deck intake.</p>
    <div class="actions">
      <a class="button" href="/dashboard">Open dashboard</a>
      <a class="button secondary" href="/decks/new">Go to intake</a>
    </div>
  </section>
</PublicAuthShell>

<style>
  .content {
    padding: 1.25rem;
    display: grid;
    gap: 0.9rem;
  }

  h2 {
    margin: 0;
  }

  .actions {
    display: flex;
    gap: 0.75rem;
    flex-wrap: wrap;
  }
</style>
