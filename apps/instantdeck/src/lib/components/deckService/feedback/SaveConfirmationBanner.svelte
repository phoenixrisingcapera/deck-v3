<!-- Purpose: renders confirmation banner for save-like operations with status tone and optional action link. -->
<script lang="ts">
  import type { SaveConfirmationBannerModel } from '$lib/contracts/types';

  interface Props extends SaveConfirmationBannerModel {
    compact?: boolean;
  }

  let {
    title,
    message = null,
    tone = 'success',
    timestampLabel = null,
    actionLabel = null,
    actionHref = null,
    compact = false
  }: Props = $props();
</script>

<section class={`save-confirmation-banner save-confirmation-banner--${tone}`} class:compact aria-live="polite">
  <div class="save-confirmation-banner__icon" aria-hidden="true">
    {#if tone === 'success'}
      ✓
    {:else if tone === 'danger'}
      !
    {:else if tone === 'warning'}
      !
    {:else}
      i
    {/if}
  </div>

  <div class="save-confirmation-banner__copy">
    <strong>{title}</strong>
    {#if message}
      <p>{message}</p>
    {/if}
    {#if timestampLabel}
      <span class="save-confirmation-banner__meta">{timestampLabel}</span>
    {/if}
  </div>

  {#if actionLabel && actionHref}
    <a class="save-confirmation-banner__action" href={actionHref}>{actionLabel}</a>
  {/if}
</section>

<style>
  .save-confirmation-banner {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    gap: 0.66rem;
    align-items: center;
    padding: 0.8rem 0.92rem;
    border-radius: 12px;
    border: 1px solid rgba(64, 164, 112, 0.36);
    background: linear-gradient(180deg, rgba(16, 42, 38, 0.92), rgba(14, 34, 31, 0.96));
  }

  .save-confirmation-banner.compact {
    padding: 0.74rem 0.86rem;
    gap: 0.62rem;
  }

  .save-confirmation-banner--info {
    border-color: rgba(87, 164, 255, 0.3);
    background: linear-gradient(180deg, rgba(18, 38, 67, 0.92), rgba(15, 28, 47, 0.92));
  }

  .save-confirmation-banner--warning {
    border-color: rgba(255, 191, 94, 0.3);
    background: linear-gradient(180deg, rgba(64, 47, 20, 0.94), rgba(45, 35, 18, 0.92));
  }

  .save-confirmation-banner--danger {
    border-color: rgba(255, 122, 122, 0.3);
    background: linear-gradient(180deg, rgba(66, 26, 32, 0.94), rgba(45, 20, 24, 0.92));
  }

  .save-confirmation-banner__icon {
    width: 1.5rem;
    height: 1.5rem;
    border-radius: 999px;
    display: grid;
    place-items: center;
    background: rgba(68, 190, 116, 0.14);
    color: #79e4aa;
    box-shadow: inset 0 0 0 1px rgba(117, 224, 167, 0.18);
    font-size: 0.76rem;
    font-weight: 700;
  }

  .save-confirmation-banner--info .save-confirmation-banner__icon {
    background: rgba(87, 164, 255, 0.18);
    color: #9fd0ff;
    box-shadow: inset 0 0 0 1px rgba(159, 208, 255, 0.18);
  }

  .save-confirmation-banner--warning .save-confirmation-banner__icon {
    background: rgba(255, 191, 94, 0.18);
    color: #ffd384;
    box-shadow: inset 0 0 0 1px rgba(255, 211, 132, 0.18);
  }

  .save-confirmation-banner--danger .save-confirmation-banner__icon {
    background: rgba(255, 122, 122, 0.18);
    color: #ffb0b0;
    box-shadow: inset 0 0 0 1px rgba(255, 176, 176, 0.16);
  }

  .save-confirmation-banner__copy {
    min-width: 0;
    display: grid;
    gap: 0.12rem;
  }

  .save-confirmation-banner__copy strong,
  .save-confirmation-banner__copy p,
  .save-confirmation-banner__meta {
    margin: 0;
  }

  .save-confirmation-banner__copy strong {
    color: #8ef0bb;
    font-size: 0.9rem;
    line-height: 1.2;
  }

  .save-confirmation-banner__copy p,
  .save-confirmation-banner__meta {
    color: rgba(230, 239, 255, 0.8);
    font-size: 0.8rem;
    line-height: 1.3;
  }

  .save-confirmation-banner__meta {
    color: rgba(230, 239, 255, 0.64);
  }

  .save-confirmation-banner__action {
    color: #8ef0bb;
    font-size: 0.82rem;
    font-weight: 600;
    text-decoration: none;
    white-space: nowrap;
  }

  @media (max-width: 640px) {
    .save-confirmation-banner {
      grid-template-columns: auto minmax(0, 1fr);
    }

    .save-confirmation-banner__action {
      grid-column: 1 / -1;
      padding-left: calc(1.55rem + 0.7rem);
      white-space: normal;
    }
  }
</style>
