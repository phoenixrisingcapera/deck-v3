<script lang="ts">
  import { page } from '$app/state';
  import { goto } from '$app/navigation';
  import PublicAuthShell from '$components/PublicAuthShell.svelte';
  import AuthSuccessLoader from '$lib/components/AuthSuccessLoader.svelte';
  import { signIn } from '$lib/api/auth';
  import { toApiErrorBannerModel } from '$lib/api/apiError';

  type SignInFormState = {
    email: string;
    password: string;
  };

  let form = $state<SignInFormState>({ email: '', password: '' });
  let submitting = $state(false);
  let errorMessage = $state('');
  let redirecting = $state(false);
  let formNode = $state<HTMLFormElement | null>(null);
  function validateNextUrl(next: string | null): string | null {
    if (!next) return null;
    try {
      const parsed = new URL(next, page.url.origin);
      if (parsed.origin !== page.url.origin || !next.startsWith('/') || next.startsWith('//')) return null;
      if (/^[\\\u0000-\u001f]/.test(next) || next.toLowerCase().includes('javascript:')) return null;
      return `${parsed.pathname}${parsed.search}${parsed.hash}`;
    } catch { return null; }
  }

  async function submitSignIn() {
    if (typeof window !== 'undefined') {
      (window as typeof window & { __deckSignInSubmitCount?: number }).__deckSignInSubmitCount =
        ((window as typeof window & { __deckSignInSubmitCount?: number }).__deckSignInSubmitCount ?? 0) + 1;
    }

    if (!formNode?.reportValidity()) {
      return;
    }

    submitting = true; errorMessage = ''; redirecting = false;
    try {
      const email = form.email.trim().toLowerCase();
      const password = form.password;
      if (!email || !password) { errorMessage = 'Email and password are required.'; submitting = false; return; }
      if (password.length < 8) { errorMessage = 'Password must be at least 8 characters.'; submitting = false; return; }
      const response = await signIn({ email, password });
      const rawNext = page.url.searchParams.get('next');
      const nextUrl = validateNextUrl(rawNext) || response.nextUrl || '/dashboard';
      redirecting = true;
      await goto(nextUrl);
    } catch (error) {
      redirecting = false;
      errorMessage = toApiErrorBannerModel(error, 'Could not sign in.').message;
    } finally { submitting = false; }
  }

  async function handleSubmit(event: SubmitEvent) {
    event.preventDefault();
    await submitSignIn();
  }

</script>

<PublicAuthShell
  title="Sign in"
  subtitle=""
  alternateHref={`/auth/sign-up${page.url.search ? `?${page.url.searchParams.toString()}` : ''}`}
  alternateLabel="Don't have an account?"
  alternateCta="Sign up"
>
  <form bind:this={formNode} class="auth-form" onsubmit={handleSubmit}>
    <label>
      <span>Email</span>
      <!-- UPDATED: Use a personal email hint rather than implying that a company address is required. -->
      <input type="email" bind:value={form.email} autocomplete="email" placeholder="Your email" required />
    </label>
    <label>
      <span>Password</span>
      <input type="password" bind:value={form.password} autocomplete="current-password" required minlength="8" />
    </label>
    <div class="forgot-row">
      <a href="/auth/reset-password" class="forgot-link">Forgot password?</a>
    </div>
    {#if errorMessage}
      <p class="error-copy">{errorMessage}</p>
    {/if}
    <button class="button" type="submit" disabled={submitting} style="width:100%;min-height:44px;">
      {submitting ? 'Signing in...' : 'Sign in'}
    </button>
  </form>
</PublicAuthShell>

{#if redirecting}
  <AuthSuccessLoader open={true} overlay={true} title="Signed in" subtitle="Redirecting..." statusLabel="Ready" notice="" steps={[]} />
{/if}

<style>
  .auth-form {
    display: grid;
    gap: 1rem;
  }

  label {
    display: grid;
    gap: 6px;
  }

  label > span {
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--text-secondary);
    letter-spacing: 0.02em;
  }

  input[type='email'],
  input[type='password'] {
    width: 100%;
    padding: 11px 14px;
    border-radius: var(--radius-md);
    border: 1px solid var(--border);
    background: var(--surface-input, var(--bg-subtle));
    color: var(--text);
    font-size: 0.875rem;
    font-family: var(--font-body);
    transition: border-color 0.15s ease, box-shadow 0.15s ease;
  }

  input[type='email']:focus,
  input[type='password']:focus {
    outline: none;
    border-color: var(--accent);
    box-shadow: 0 0 0 3px var(--accent-soft);
  }

  input::placeholder {
    color: var(--text-muted);
  }

  .forgot-row {
    display: flex;
    justify-content: flex-end;
    margin-top: -0.25rem;
  }

  .forgot-link {
    font-size: 0.75rem;
    color: var(--text-secondary);
    text-decoration: none;
    transition: color 0.15s ease;
  }

  .forgot-link:hover {
    color: var(--accent);
    text-decoration: underline;
  }

  :global(.auth-form .button) {
    margin-top: 0.25rem;
  }

  :global(.auth-form .error-copy) {
    margin: 0;
    padding: 10px 14px;
    border-radius: var(--radius-md);
    border: 1px solid var(--danger);
    background: var(--danger-soft);
    color: var(--danger);
    font-size: 0.8125rem;
    line-height: 1.5;
  }
</style>
