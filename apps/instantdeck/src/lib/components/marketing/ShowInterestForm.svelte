<script lang="ts">
  import { deckServiceClient } from '$lib/api/deckServiceClient';

  interface Props {
    sourcePage?: string;
  }

  let { sourcePage = 'home' }: Props = $props();

  let email = $state('');
  let submitting = $state(false);
  let successMessage = $state('');
  let errorMessage = $state('');

  async function handleSubmit(event: SubmitEvent) {
    event.preventDefault();
    submitting = true; successMessage = ''; errorMessage = '';
    try {
      const response = await deckServiceClient.submitPublicInterest({
        email, source_page: sourcePage
      });
      successMessage = response.message;
      email = '';
    } catch (error) {
      errorMessage = error instanceof Error ? error.message : 'Something went wrong.';
    } finally { submitting = false; }
  }
</script>

<section class="panel interest-form">
  <div>
    <div class="eyebrow">Early access</div>
    <h2>Get notified when Deck launches</h2>
    <p class="muted">Enter your email. We'll reach out when access opens.</p>
  </div>
  <form onsubmit={handleSubmit}>
    <div class="interest-form__row">
      <input type="email" bind:value={email} placeholder="you@company.com" required />
      <button class="button" type="submit" disabled={submitting}>
        {submitting ? 'Submitting...' : 'Notify me'}
      </button>
    </div>
    {#if successMessage}
      <p class="success">{successMessage}</p>
    {/if}
    {#if errorMessage}
      <p class="error">{errorMessage}</p>
    {/if}
  </form>
</section>

<style>
  .interest-form {
    padding: clamp(2.5rem, 4vw, 4rem) clamp(1.8rem, 3vw, 3.5rem);
    display: grid;
    gap: 1.25rem;
    border: 1px solid rgba(148, 163, 184, 0.15);
    border-radius: var(--radius-xl);
    background:
      radial-gradient(circle at 80% 20%, rgba(240, 84, 197, 0.06), transparent 35%),
      radial-gradient(circle at 20% 80%, rgba(78, 122, 255, 0.06), transparent 35%),
      var(--gradient-surface);
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.2);
  }

  .interest-form h2 {
    margin: 0;
    font-size: clamp(1.4rem, 2.5vw, 1.8rem);
    line-height: 1.15;
    letter-spacing: -0.03em;
  }

  .interest-form p {
    margin: 0.25rem 0 0;
    font-size: 0.9rem;
    line-height: 1.55;
    color: var(--text-secondary);
  }

  .interest-form__row {
    display: flex;
    gap: 10px;
    padding-top: 0.5rem;
  }

  input {
    flex: 1;
    padding: 11px 14px;
    border-radius: var(--radius-md);
    border: 1px solid var(--border);
    background: var(--surface-input, var(--bg-subtle));
    color: var(--text);
    font-size: 0.875rem;
    font-family: var(--font-body);
    transition: border-color 0.15s ease, box-shadow 0.15s ease;
  }

  input:focus {
    outline: none;
    border-color: var(--accent);
    box-shadow: 0 0 0 3px var(--accent-soft);
  }

  input::placeholder {
    color: var(--text-muted);
  }

  .success {
    margin: 0;
    font-size: 0.8125rem;
    color: var(--success);
    padding: 8px 12px;
    border-radius: var(--radius-md);
    background: var(--success-soft);
    border: 1px solid var(--success);
  }

  .error {
    margin: 0;
    font-size: 0.8125rem;
    color: var(--danger);
    padding: 8px 12px;
    border-radius: var(--radius-md);
    background: var(--danger-soft);
    border: 1px solid var(--danger);
  }

  @media (max-width: 500px) {
    .interest-form__row {
      flex-direction: column;
    }
  }
</style>
