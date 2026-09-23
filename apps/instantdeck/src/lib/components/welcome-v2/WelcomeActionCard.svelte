<script lang="ts">
  interface Props {
    step: string;
    icon: string;
    title: string;
    message: string;
    href: string;
    cta: string;
    variant: 'deck' | 'website' | 'brand';
  }

  let { step, icon, title, message, href, cta, variant }: Props = $props();
</script>

<article class="panel action-card" data-variant={variant}>
  <div class="action-card__top">
    <span class="action-card__step">{step}</span>
    <div class="action-card__icon" aria-hidden="true">{icon}</div>
  </div>

  <div class="action-card__copy">
    <h2>{title}</h2>
    <p>{message}</p>
  </div>

  <div class="action-card__art" aria-hidden="true">
    {#if variant === 'deck'}
      <div class="art art--deck">
        <span class="art__sheet art__sheet--back"></span>
        <span class="art__sheet art__sheet--front">
          <i></i>
          <b></b>
          <b></b>
          <b></b>
        </span>
        <span class="art__badge">PDF</span>
      </div>
    {:else if variant === 'website'}
      <div class="art art--website">
        <span class="art__chrome"><i></i><i></i><i></i></span>
        <span class="art__url">https://yourcompany.com</span>
        <span class="art__panel art__panel--one"></span>
        <span class="art__panel art__panel--two"></span>
        <span class="art__panel art__panel--three"></span>
      </div>
    {:else}
      <div class="art art--brand">
        <span class="art__mark">
          <i></i>
          <i></i>
        </span>
        <span class="art__swatches">
          <b></b>
          <b></b>
          <b></b>
          <b></b>
        </span>
      </div>
    {/if}
  </div>

  <a class="button action-card__button" href={href}>{cta}</a>
</article>

<style>
  .action-card {
    min-width: 0;
    display: grid;
    gap: 1rem;
    padding: 1.1rem;
    border-color: color-mix(in srgb, var(--line-strong) 34%, var(--line));
    background:
      linear-gradient(180deg, color-mix(in srgb, var(--surface-strong) 74%, transparent), color-mix(in srgb, var(--surface) 94%, transparent));
    box-shadow: var(--shadow-card);
    overflow: hidden;
  }

  .action-card__top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 0.75rem;
  }

  .action-card__step {
    display: inline-flex;
    align-items: center;
    min-height: 2rem;
    padding: 0 0.7rem;
    border-radius: 999px;
    border: 1px solid var(--line);
    color: var(--accent);
    background: var(--surface-chip);
    font-size: 0.74rem;
    letter-spacing: 0.12em;
    font-weight: 700;
  }

  .action-card__icon {
    width: 2.7rem;
    height: 2.7rem;
    display: grid;
    place-items: center;
    border-radius: 16px;
    color: var(--accent);
    border: 1px solid color-mix(in srgb, var(--accent) 24%, var(--line));
    background:
      radial-gradient(circle at top left, color-mix(in srgb, var(--accent-soft) 60%, transparent), transparent 65%),
      var(--surface-soft);
  }

  .action-card__copy {
    display: grid;
    gap: 0.45rem;
  }

  .action-card__copy h2 {
    margin: 0;
    min-width: 0;
    overflow-wrap: anywhere;
    font-size: clamp(1.2rem, 2vw, 1.45rem);
    line-height: 1.1;
    letter-spacing: -0.03em;
  }

  .action-card__copy p {
    margin: 0;
    min-width: 0;
    overflow-wrap: anywhere;
    color: var(--muted);
    line-height: 1.65;
  }

  .action-card__art {
    min-height: 13rem;
    border-radius: 22px;
    border: 1px solid color-mix(in srgb, var(--line-strong) 38%, var(--line));
    background:
      radial-gradient(circle at top left, color-mix(in srgb, var(--accent-soft) 54%, transparent), transparent 28%),
      radial-gradient(circle at bottom right, color-mix(in srgb, var(--accent-2) 18%, transparent), transparent 38%),
      var(--surface-muted);
    position: relative;
    overflow: hidden;
  }

  .art {
    position: absolute;
    inset: 0;
  }

  .art--deck::before,
  .art--deck::after,
  .art--website::before,
  .art--website::after,
  .art--brand::before,
  .art--brand::after {
    content: '';
    position: absolute;
    inset: auto;
    pointer-events: none;
  }

  .art--deck::before {
    width: 7rem;
    height: 7rem;
    right: 1.1rem;
    bottom: 1.1rem;
    border-radius: 18px;
    background: radial-gradient(circle at 35% 30%, color-mix(in srgb, var(--accent-2) 50%, transparent), transparent 55%);
    filter: blur(4px);
  }

  .art__sheet {
    position: absolute;
    border-radius: 16px;
    border: 1px solid color-mix(in srgb, var(--line-strong) 40%, var(--line));
    background: linear-gradient(180deg, rgba(19, 27, 54, 0.95), rgba(12, 17, 36, 0.95));
    box-shadow: 0 24px 44px rgba(4, 10, 30, 0.35);
  }

  .art__sheet--back {
    inset: 1.75rem 3.2rem 2.1rem 5.8rem;
    transform: rotate(-5deg);
    opacity: 0.7;
  }

  .art__sheet--front {
    inset: 2.35rem 2.2rem 1.3rem 4.3rem;
    transform: rotate(2deg);
    display: grid;
    gap: 0.8rem;
    padding: 1rem;
    background:
      radial-gradient(circle at top left, rgba(100, 130, 255, 0.22), transparent 35%),
      linear-gradient(180deg, rgba(22, 31, 63, 0.96), rgba(13, 18, 40, 0.98));
  }

  .art__sheet--front i {
    width: 42%;
    height: 0.7rem;
    border-radius: 999px;
    background: color-mix(in srgb, var(--ink-soft) 80%, transparent);
    opacity: 0.55;
  }

  .art__sheet--front b {
    display: block;
    height: 1.2rem;
    border-radius: 999px;
    background: linear-gradient(90deg, rgba(82, 99, 244, 0.94), rgba(189, 72, 216, 0.94));
    box-shadow: 0 0 24px rgba(116, 104, 255, 0.2);
  }

  .art__sheet--front b:nth-child(3) {
    width: 72%;
  }

  .art__sheet--front b:nth-child(4) {
    width: 58%;
  }

  .art__badge {
    position: absolute;
    left: 1.2rem;
    bottom: 1.1rem;
    display: inline-flex;
    align-items: center;
    min-height: 2rem;
    padding: 0 0.8rem;
    border-radius: 999px;
    background: rgba(237, 242, 255, 0.96);
    color: #2d3a64;
    font-size: 0.75rem;
    font-weight: 800;
    letter-spacing: 0.08em;
  }

  .art__chrome {
    position: absolute;
    top: 1rem;
    left: 1rem;
    display: flex;
    gap: 0.4rem;
  }

  .art__chrome i {
    width: 0.65rem;
    height: 0.65rem;
    border-radius: 50%;
    background: color-mix(in srgb, var(--accent) 88%, white);
    opacity: 0.9;
  }

  .art__url {
    position: absolute;
    top: 1rem;
    left: 6rem;
    right: 1rem;
    min-height: 1.9rem;
    display: flex;
    align-items: center;
    padding: 0 0.8rem;
    border-radius: 999px;
    border: 1px solid rgba(154, 174, 255, 0.24);
    background: rgba(9, 14, 28, 0.48);
    color: rgba(232, 240, 255, 0.76);
    font-size: 0.78rem;
  }

  .art__panel {
    position: absolute;
    left: 1rem;
    right: 1rem;
    border-radius: 16px;
    border: 1px solid rgba(118, 140, 255, 0.2);
    background: rgba(14, 20, 38, 0.86);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
  }

  .art__panel--one {
    top: 3.4rem;
    height: 3.2rem;
  }

  .art__panel--two {
    top: 6.95rem;
    height: 3.2rem;
    width: 60%;
  }

  .art__panel--three {
    top: 6.95rem;
    left: calc(60% + 1.5rem);
    height: 4.8rem;
  }

  .art--brand {
    display: grid;
    place-items: center;
    gap: 1rem;
  }

  .art__mark {
    width: 7.5rem;
    height: 7.5rem;
    border-radius: 24px;
    border: 1px solid rgba(143, 160, 255, 0.24);
    background:
      radial-gradient(circle at 30% 24%, rgba(108, 196, 255, 0.36), transparent 24%),
      radial-gradient(circle at 78% 72%, rgba(210, 96, 255, 0.3), transparent 30%),
      linear-gradient(160deg, rgba(18, 24, 49, 0.96), rgba(11, 15, 32, 0.98));
    display: grid;
    place-items: center;
    position: absolute;
    top: 1.5rem;
  }

  .art__mark i {
    position: absolute;
    border-radius: 30px;
    background: linear-gradient(180deg, rgba(120, 150, 255, 0.94), rgba(79, 115, 246, 0.8));
    box-shadow: 0 12px 30px rgba(69, 100, 255, 0.24);
  }

  .art__mark i:first-child {
    width: 2.9rem;
    height: 5rem;
    transform: translateX(-0.95rem) rotate(12deg);
  }

  .art__mark i:last-child {
    width: 2.9rem;
    height: 5rem;
    transform: translateX(0.95rem) rotate(-12deg);
    background: linear-gradient(180deg, rgba(212, 104, 255, 0.94), rgba(117, 84, 255, 0.84));
  }

  .art__swatches {
    position: absolute;
    bottom: 1.2rem;
    left: 1.2rem;
    right: 1.2rem;
    display: flex;
    gap: 0.45rem;
  }

  .art__swatches b {
    flex: 1 1 0;
    height: 3rem;
    border-radius: 12px;
    border: 1px solid rgba(145, 168, 255, 0.22);
    background: linear-gradient(160deg, rgba(90, 110, 255, 0.95), rgba(126, 86, 255, 0.92));
  }

  .art__swatches b:nth-child(2) {
    background: linear-gradient(160deg, rgba(126, 86, 255, 0.95), rgba(218, 86, 214, 0.9));
  }

  .art__swatches b:nth-child(3) {
    background: linear-gradient(160deg, rgba(139, 201, 255, 0.9), rgba(88, 151, 255, 0.92));
  }

  .art__swatches b:nth-child(4) {
    background: linear-gradient(160deg, rgba(239, 245, 255, 0.96), rgba(206, 219, 255, 0.9));
  }

  .action-card__button {
    justify-content: center;
    min-width: 11rem;
    width: fit-content;
  }

  @media (max-width: 760px) {
    .action-card__art {
      min-height: 11rem;
    }

    .art__sheet--back {
      inset: 1.3rem 2.5rem 1.7rem 4.4rem;
    }

    .art__sheet--front {
      inset: 1.85rem 1.6rem 1rem 3.2rem;
    }

    .art__panel--three {
      left: 60%;
    }

    .action-card__button {
      width: 100%;
    }
  }
</style>
