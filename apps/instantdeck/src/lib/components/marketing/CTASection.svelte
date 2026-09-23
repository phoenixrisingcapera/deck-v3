<script lang="ts">
  import AppLogo from '$components/AppLogo.svelte';
</script>

<section class="cta-section">
  <div class="cta-section__atmosphere" aria-hidden="true">
    <span class="cta-section__orb cta-section__orb--blue"></span>
    <span class="cta-section__orb cta-section__orb--pink"></span>
    <span class="cta-section__grid"></span>
  </div>

  <div class="cta-section__content">
    <div class="cta-section__logo-row">
      <AppLogo size="sm" alt="Deck" />
    </div>
    <h2>Ready to analyze your first deck?</h2>
    <p>Upload a PDF or PowerPoint. AI analysis starts in seconds.</p>
    <div class="cta-section__actions">
      <a class="button" href="/auth/sign-up">Get started free</a>
      <a class="button secondary" href="/auth/sign-in">Sign in</a>
    </div>
    <div class="cta-section__pills">
      <span class="cta-section__pill">No credit card required</span>
      <span class="cta-section__pill">Free tier available</span>
    </div>
  </div>
</section>

<style>
  .cta-section {
    position: relative;
    padding: clamp(3rem, 6vw, 5rem) clamp(1.5rem, 4vw, 3rem);
    border-radius: var(--radius-xl);
    overflow: hidden;
    isolation: isolate;
    background:
      radial-gradient(circle at 30% 40%, rgba(48, 154, 255, 0.14), transparent 40%),
      radial-gradient(circle at 75% 25%, rgba(255, 82, 168, 0.10), transparent 35%),
      linear-gradient(180deg, rgba(6, 13, 30, 0.98), rgba(2, 6, 23, 1));
    border: 1px solid rgba(148, 163, 184, 0.15);
    box-shadow:
      0 30px 80px rgba(0, 0, 0, 0.3),
      inset 0 1px 0 rgba(255, 255, 255, 0.04);
  }

  .cta-section__atmosphere {
    position: absolute;
    inset: 0;
    pointer-events: none;
    z-index: 0;
  }

  .cta-section__orb {
    position: absolute;
    border-radius: 999px;
    filter: blur(20px);
    opacity: 0.45;
  }

  .cta-section__orb--blue {
    width: 14rem;
    height: 14rem;
    left: -3rem;
    bottom: -4rem;
    background: rgba(48, 154, 255, 0.16);
  }

  .cta-section__orb--pink {
    width: 11rem;
    height: 11rem;
    right: -2rem;
    top: -3rem;
    background: rgba(255, 82, 168, 0.12);
  }

  .cta-section__grid {
    position: absolute;
    inset: 0;
    background-image:
      linear-gradient(rgba(255, 255, 255, 0.025) 1px, transparent 1px),
      linear-gradient(90deg, rgba(255, 255, 255, 0.025) 1px, transparent 1px);
    background-size: 32px 32px;
    mask-image: linear-gradient(180deg, rgba(0, 0, 0, 0.25), transparent 60%);
    opacity: 0.2;
  }

  .cta-section__content {
    position: relative;
    z-index: 1;
    display: grid;
    gap: 1rem;
    max-width: 36rem;
  }

  .cta-section__logo-row {
    margin-bottom: 0.5rem;
  }

  .cta-section__content h2 {
    font-size: clamp(1.5rem, 3.5vw, 2.2rem);
    color: #f8fbff;
    letter-spacing: -0.04em;
    line-height: 1.15;
    margin: 0;
  }

  .cta-section__content p {
    color: rgba(223, 232, 248, 0.78);
    font-size: 1rem;
    line-height: 1.6;
    margin: 0;
  }

  .cta-section__actions {
    display: flex;
    gap: 0.75rem;
    flex-wrap: wrap;
    padding-top: 0.5rem;
  }

  .cta-section__actions :global(.button) {
    padding: 0.7rem 1.5rem;
    border-radius: var(--radius-md);
    font-weight: 600;
    font-size: 0.875rem;
    text-decoration: none;
    transition: transform 0.15s ease, box-shadow 0.15s ease;
  }

  .cta-section__actions :global(.button:hover) {
    transform: translateY(-1px);
  }

  .cta-section__actions :global(.button:not(.secondary)) {
    background: var(--gradient-brand);
    color: #fff;
    box-shadow: 0 4px 20px rgba(0, 183, 255, 0.25);
  }

  .cta-section__actions :global(.button:not(.secondary):hover) {
    box-shadow: 0 6px 28px rgba(0, 183, 255, 0.35);
  }

  .cta-section__actions :global(.button.secondary) {
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(148, 163, 184, 0.2);
    color: rgba(239, 244, 255, 0.85);
  }

  .cta-section__actions :global(.button.secondary:hover) {
    background: rgba(255, 255, 255, 0.1);
    border-color: rgba(148, 163, 184, 0.3);
  }

  .cta-section__pills {
    display: flex;
    gap: 0.6rem;
    flex-wrap: wrap;
    padding-top: 0.25rem;
  }

  .cta-section__pill {
    padding: 0.3rem 0.7rem;
    border-radius: 999px;
    border: 1px solid rgba(148, 163, 184, 0.15);
    background: rgba(255, 255, 255, 0.04);
    color: rgba(223, 232, 248, 0.7);
    font-size: 0.75rem;
  }

  @media (max-width: 600px) {
    .cta-section {
      padding: 2.5rem 1.25rem;
    }

    .cta-section__content {
      max-width: 100%;
    }
  }
</style>
