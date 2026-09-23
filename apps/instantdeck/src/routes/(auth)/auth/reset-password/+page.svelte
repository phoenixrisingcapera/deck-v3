<script lang="ts">
  import { page } from '$app/state';
  import { goto } from '$app/navigation';
  import PublicAuthShell from '$components/PublicAuthShell.svelte';
  import AuthSuccessLoader from '$lib/components/AuthSuccessLoader.svelte';
  import { changePassword } from '$lib/api/auth';
  import { toApiErrorBannerModel } from '$lib/api/apiError';

  type ChangePasswordFormState = {
    currentPassword: string;
    newPassword: string;
    confirmPassword: string;
  };

  let form = $state<ChangePasswordFormState>({ currentPassword: '', newPassword: '', confirmPassword: '' });
  let submitting = $state(false);
  let errorMessage = $state('');
  let successMessage = $state('');
  let redirecting = $state(false);
  let formNode = $state<HTMLFormElement | null>(null);

  async function submitChangePassword() {
    if (!formNode?.reportValidity()) {
      return;
    }

    submitting = true; errorMessage = ''; successMessage = ''; redirecting = false;
    try {
      const currentPassword = form.currentPassword;
      const newPassword = form.newPassword;
      const confirmPassword = form.confirmPassword;

      if (!currentPassword) { errorMessage = 'Current password is required.'; submitting = false; return; }
      if (!newPassword) { errorMessage = 'New password is required.'; submitting = false; return; }
      if (newPassword.length < 8) { errorMessage = 'Password must be at least 8 characters.'; submitting = false; return; }
      if (newPassword !== confirmPassword) { errorMessage = 'Passwords do not match.'; submitting = false; return; }
      if (currentPassword === newPassword) { errorMessage = 'New password must be different from current password.'; submitting = false; return; }

      await changePassword({ currentPassword, newPassword, confirmPassword });
      successMessage = 'Password changed successfully. Signing you out...';
      form = { currentPassword: '', newPassword: '', confirmPassword: '' };

      // Redirect to sign-in after 2 seconds
      setTimeout(() => {
        redirecting = true;
        goto('/auth/sign-in');
      }, 2000);
    } catch (error) {
      redirecting = false;
      errorMessage = toApiErrorBannerModel(error, 'Could not change password.').message;
    } finally { submitting = false; }
  }

  async function handleSubmit(event: SubmitEvent) {
    event.preventDefault();
    await submitChangePassword();
  }

</script>

<PublicAuthShell
  title="Change password"
  subtitle="Enter your current and new password"
  alternateHref={`/auth/sign-in${page.url.search ? `?${page.url.searchParams.toString()}` : ''}`}
  alternateLabel="Done changing?"
  alternateCta="Sign in"
>
  <form bind:this={formNode} class="auth-form" onsubmit={handleSubmit}>
    <label>
      <span>Current password</span>
      <input type="password" bind:value={form.currentPassword} autocomplete="current-password" placeholder="Current password" required minlength="8" />
    </label>
    <label>
      <span>New password</span>
      <input type="password" bind:value={form.newPassword} autocomplete="new-password" placeholder="New password" required minlength="8" />
    </label>
    <label>
      <span>Confirm new password</span>
      <input type="password" bind:value={form.confirmPassword} autocomplete="new-password" placeholder="Confirm new password" required minlength="8" />
    </label>
    {#if errorMessage}
      <p class="error-copy">{errorMessage}</p>
    {/if}
    {#if successMessage}
      <p class="success-copy">{successMessage}</p>
    {/if}
    <button class="button" type="submit" disabled={submitting} style="width:100%;min-height:44px;">
      {submitting ? 'Changing password...' : 'Change password'}
    </button>
  </form>
</PublicAuthShell>

{#if redirecting}
  <AuthSuccessLoader open={true} overlay={true} title="Password changed" subtitle="Redirecting to sign in..." statusLabel="Ready" notice="" steps={[]} />
{/if}

<style>
  .auth-form { display: grid; gap: 14px; }
  label { display: grid; gap: 5px; }
  label span { font-size: 12px; font-weight: 500; color: var(--text-secondary); }
  input {
    width: 100%; padding: 10px 12px; border-radius: var(--radius);
    border: 1px solid var(--border); background: var(--bg-subtle);
    color: var(--text); font-size: 14px;
  }
  input:focus { outline: none; border-color: var(--accent); }
  .error-copy { color: var(--danger); font-size: 13px; margin: 0; }
  .success-copy { color: var(--success); font-size: 13px; margin: 0; }
</style>
