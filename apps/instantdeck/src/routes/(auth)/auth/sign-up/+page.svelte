<script lang="ts">
  import { page } from '$app/state';
  import { goto } from '$app/navigation';
  import PublicAuthShell from '$components/PublicAuthShell.svelte';
  import AuthSuccessLoader from '$lib/components/AuthSuccessLoader.svelte';
  import { signUp } from '$lib/api/auth';
  import { toApiErrorBannerModel } from '$lib/api/apiError';

  type SignUpFormState = {
    name: string;
    email: string;
    password: string;
    confirmPassword: string;
    companyName: string;
    acceptedTerms: boolean;
  };

  let form = $state<SignUpFormState>({ name: '', email: '', password: '', confirmPassword: '', companyName: '', acceptedTerms: false });
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

  async function submitSignUp() {
    if (!formNode?.reportValidity()) {
      return;
    }

    submitting = true; errorMessage = ''; redirecting = false;
    try {
      const name = form.name.trim();
      const email = form.email.trim().toLowerCase();
      const password = form.password;
      if (!name || !email || !password) { errorMessage = 'Name, email, and password are required.'; submitting = false; return; }
      if (password !== form.confirmPassword) { errorMessage = 'Passwords do not match.'; submitting = false; return; }
      if (!form.acceptedTerms) { errorMessage = 'Accept the terms to continue.'; submitting = false; return; }
      const response = await signUp({ name, email, password, companyName: form.companyName.trim() || undefined, acceptedTerms: form.acceptedTerms });
      const rawNext = page.url.searchParams.get('next');
      const nextUrl = validateNextUrl(rawNext) || response.nextUrl || '/dashboard';
      redirecting = true;
      await goto(nextUrl);
    } catch (error) {
      redirecting = false;
      errorMessage = toApiErrorBannerModel(error, 'Could not create account.').message;
    } finally { submitting = false; }
  }

  async function handleSubmit(event: SubmitEvent) {
    event.preventDefault();
    if (typeof window !== 'undefined') {
      (window as typeof window & { __deckSignUpSubmitCount?: number }).__deckSignUpSubmitCount =
        ((window as typeof window & { __deckSignUpSubmitCount?: number }).__deckSignUpSubmitCount ?? 0) + 1;
    }
    await submitSignUp();
  }
</script>

<PublicAuthShell
  title="Create account"
  subtitle=""
  alternateHref={`/auth/sign-in${page.url.search ? `?${page.url.searchParams.toString()}` : ''}`}
  alternateLabel="Already have an account?"
  alternateCta="Sign in"
>
  <form bind:this={formNode} class="auth-form" onsubmit={handleSubmit}>
    <label>
      <span>Name</span>
      <input bind:value={form.name} placeholder="Your name" autocomplete="name" required minlength="2" />
    </label>
    <label>
      <span>Email</span>
      <input type="email" bind:value={form.email} placeholder="you@company.com" autocomplete="email" required />
    </label>
    <label>
      <span>Password</span>
      <input type="password" bind:value={form.password} placeholder="At least 8 characters" autocomplete="new-password" required minlength="8" />
    </label>
    <label>
      <span>Confirm password</span>
      <input type="password" bind:value={form.confirmPassword} placeholder="Confirm password" autocomplete="new-password" required minlength="8" />
    </label>
    <label>
      <span>Company <span class="optional">(optional)</span></span>
      <input bind:value={form.companyName} placeholder="Fund or company" autocomplete="organization" />
    </label>
    <label class="terms">
      <input type="checkbox" bind:checked={form.acceptedTerms} required />
      <span>I agree to the terms and privacy policy.</span>
    </label>
    {#if errorMessage}
      <p class="error-copy">{errorMessage}</p>
    {/if}
    <button class="button" type="submit" disabled={submitting} style="width:100%;min-height:44px;">
      {submitting ? 'Creating...' : 'Create account'}
    </button>
  </form>
</PublicAuthShell>

{#if redirecting}
  <AuthSuccessLoader open={true} overlay={true} title="Account created" subtitle="Redirecting..." statusLabel="Ready" notice="" steps={[]} />
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

  .optional {
    font-weight: 400;
    color: var(--text-muted);
  }

  input[type='text'],
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

  input[type='text']:focus,
  input[type='email']:focus,
  input[type='password']:focus {
    outline: none;
    border-color: var(--accent);
    box-shadow: 0 0 0 3px var(--accent-soft);
  }

  input::placeholder {
    color: var(--text-muted);
  }

  input[type='checkbox'] {
    width: 16px;
    height: 16px;
    accent-color: var(--accent);
  }

  .terms {
    grid-template-columns: 16px 1fr;
    align-items: start;
    gap: 8px;
    color: var(--text-muted);
    font-size: 0.75rem;
    line-height: 1.5;
  }

  .terms a {
    color: var(--accent);
    text-decoration: none;
  }

  .terms a:hover {
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
