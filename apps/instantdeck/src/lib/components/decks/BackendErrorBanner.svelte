<script lang="ts">
  import { getBackendHealth, onBackendHealthChange, checkBackendHealth } from '$lib/api/backendHealth';

  let health = $state<boolean | null>(getBackendHealth());
  let dismissed = $state(false);

  $effect(() => {
    const unsub = onBackendHealthChange((h) => {
      health = h;
      // Reset dismiss if status changes
      dismissed = false;
    });
    // Kick off the check if not already done
    checkBackendHealth();
    return unsub;
  });

  const visible = $derived(!dismissed && health === false);
</script>

{#if visible}
  <div class="backend-error-banner" role="alert">
    <div class="backend-error-banner__inner">
      <span class="backend-error-banner__icon" aria-hidden="true">!</span>
      <span class="backend-error-banner__text">
        <strong>Backend service is unreachable.</strong>
        Some features may be unavailable. Please try again in a moment.
      </span>
      <button
        class="backend-error-banner__dismiss"
        onclick={() => (dismissed = true)}
        aria-label="Dismiss"
      >
        &times;
      </button>
    </div>
  </div>
{/if}

<style>
  .backend-error-banner {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    z-index: 9999;
    padding: 0.5rem 1rem;
    background: linear-gradient(135deg, #dc2626, #b91c1c);
    color: #fff;
    font-size: 0.8125rem;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
  }

  .backend-error-banner__inner {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    max-width: 1200px;
    margin: 0 auto;
  }

  .backend-error-banner__icon {
    width: 20px;
    height: 20px;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.2);
    display: inline-grid;
    place-items: center;
    font-weight: 700;
    font-size: 0.75rem;
    flex-shrink: 0;
  }

  .backend-error-banner__text {
    flex: 1;
    line-height: 1.4;
  }

  .backend-error-banner__text strong {
    font-weight: 600;
  }

  .backend-error-banner__dismiss {
    background: none;
    border: none;
    color: #fff;
    font-size: 1.25rem;
    cursor: pointer;
    padding: 0 0.25rem;
    line-height: 1;
    opacity: 0.7;
    transition: opacity 0.15s;
  }

  .backend-error-banner__dismiss:hover {
    opacity: 1;
  }
</style>
