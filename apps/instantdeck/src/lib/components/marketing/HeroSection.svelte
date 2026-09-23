<script lang="ts">
  import AppLogo from '$components/AppLogo.svelte';
  import { heroHighlights } from '$lib/data/marketing/home';

  const reviewSignals = ['Narrative model', 'Swatches attached', 'Tone calibration', 'Risk notes', 'Financials'];
  const previewFooterPills = ['Readiness view', 'Evidence-led review', 'IC-ready output'];
</script>

<section class="hero panel">
  <div class="hero__atmosphere" aria-hidden="true">
    <span class="hero__orb hero__orb--blue"></span>
    <span class="hero__orb hero__orb--pink"></span>
    <span class="hero__grid"></span>
  </div>

  <div class="hero-copy">
    <div class="eyebrow">Built for investment teams</div>
    <h1 class="display">Turn an inbound founder deck into a live diligence workspace.</h1>
    <p class="hero-copy__body">
      Deck takes the raw PDF, company site, and scattered context a fund receives and rebuilds them into
      one reviewable Smart Deck with brand memory, evidence signals, and committee-ready output.
    </p>
    <div class="hero-actions">
      <a class="button" href="/auth/sign-up">Get started</a>
      <a class="button secondary" href="/auth/sign-in">Sign in</a>
    </div>
    <div class="hero-highlights">
      {#each heroHighlights as item}
        <div class="pill hero-highlight">{item}</div>
      {/each}
    </div>
  </div>

  <div class="hero-preview" aria-hidden="true">
    <div class="hero-preview__frame">
      <span class="hero-preview__frame-glow hero-preview__frame-glow--blue"></span>
      <span class="hero-preview__frame-glow hero-preview__frame-glow--pink"></span>
      <span class="hero-preview__pulse hero-preview__pulse--1"></span>
      <span class="hero-preview__pulse hero-preview__pulse--2"></span>

      <div class="hero-preview__topbar">
        <div class="hero-preview__brand">
          <AppLogo class="hero-preview__logo" size="sm" alt="Deck logo" />
          <div>
            <strong>deck.aistack.codes</strong>
            <small>AI-powered diligence workspace</small>
          </div>
        </div>
        <div class="pill hero-preview__status">Review-ready</div>
      </div>

      <div class="hero-preview__stage">
        <article class="hero-preview__deck-card">
          <div class="hero-preview__deck-head">
            <span class="hero-preview__deck-kicker">Active Smart Deck</span>
            <span class="hero-preview__deck-badge">VC review flow</span>
          </div>

          <div class="hero-preview__deck-summary">
            <AppLogo class="hero-preview__logo hero-preview__logo--large" size="lg" alt="Deck logo" />
            <div>
              <strong>Active investor deck</strong>
              <small>18 slides · Updated 2m ago</small>
            </div>
          </div>

          <div class="hero-preview__deck-canvas">
            <div class="hero-preview__canvas-line hero-preview__canvas-line--1"></div>
            <div class="hero-preview__canvas-line hero-preview__canvas-line--2"></div>
            <div class="hero-preview__canvas-line hero-preview__canvas-line--3"></div>
            <div class="hero-preview__canvas-line hero-preview__canvas-line--4"></div>
          </div>

          <div class="hero-preview__deck-foot">
            <span class="pill hero-preview__foot-pill">Brand-aware</span>
            <span class="pill hero-preview__foot-pill">Evidence-led</span>
          </div>
        </article>

        <div class="hero-preview__analysis-stack">
          <article class="hero-preview__metric hero-preview__metric--score">
            <span>Readiness score</span>
            <div class="hero-preview__gauge">
              <div class="hero-preview__gauge-ring">
                <strong>92%</strong>
              </div>
            </div>
            <small>Board + IC ready</small>
          </article>

          <article class="hero-preview__metric hero-preview__metric--signals">
            <span>Review signals</span>
            <ul class="hero-preview__signal-list">
              {#each reviewSignals as signal}
                <li>{signal}</li>
              {/each}
            </ul>
          </article>
        </div>
      </div>

      <div class="hero-preview__footer">
        {#each previewFooterPills as pill}
          <span class="hero-preview__footer-pill">{pill}</span>
        {/each}
      </div>
    </div>
  </div>
</section>

<style>
  .hero {
    position: relative;
    padding: clamp(1.8rem, 3vw, 2.8rem);
    display: grid;
    grid-template-columns: minmax(0, 1.05fr) minmax(420px, 0.95fr);
    gap: 2rem;
    overflow: hidden;
    isolation: isolate;
    background:
      radial-gradient(circle at 28% 35%, var(--glow-blue), transparent 32%),
      radial-gradient(circle at 78% 26%, var(--glow-pink), transparent 26%),
      var(--gradient-surface);
  }

  .hero__atmosphere {
    position: absolute;
    inset: 0;
    pointer-events: none;
    z-index: 0;
  }

  .hero__orb {
    position: absolute;
    border-radius: 999px;
    filter: blur(18px);
    opacity: 0.55;
  }

  .hero__orb--blue {
    width: 20rem;
    height: 20rem;
    left: -5rem;
    bottom: -6rem;
    background: rgba(48, 154, 255, 0.18);
  }

  .hero__orb--pink {
    width: 16rem;
    height: 16rem;
    right: 8%;
    top: -4rem;
    background: rgba(255, 82, 168, 0.14);
  }

  .hero__grid {
    position: absolute;
    inset: 0;
    background-image:
      linear-gradient(rgba(255, 255, 255, 0.04) 1px, transparent 1px),
      linear-gradient(90deg, rgba(255, 255, 255, 0.04) 1px, transparent 1px);
    background-size: 36px 36px;
    mask-image: linear-gradient(180deg, rgba(0, 0, 0, 0.35), transparent 82%);
    opacity: 0.2;
  }

  .hero-copy {
    position: relative;
    z-index: 1;
    display: grid;
    align-content: start;
    gap: 1.35rem;
    padding: clamp(0.6rem, 1vw, 1.2rem) 0;
  }

  .hero-copy .eyebrow,
  .hero-copy .display,
  .hero-preview__brand,
  .hero-preview__metric strong {
    color: #f8fbff;
  }

  .hero-copy__body {
    max-width: 39rem;
    margin: 0;
    color: rgba(236, 242, 255, 0.82);
    font-size: 1.1rem;
    line-height: 1.7;
  }

  .hero-actions {
    display: flex;
    gap: 0.9rem;
    flex-wrap: wrap;
    padding-top: 0.25rem;
  }

  .hero-highlights {
    display: flex;
    gap: 0.7rem;
    flex-wrap: wrap;
    padding-top: 0.7rem;
  }

  .hero-highlight {
    color: #f8fbff;
    background: rgba(255, 255, 255, 0.08);
    border-color: rgba(255, 255, 255, 0.1);
  }

  .hero-preview {
    position: relative;
    z-index: 1;
    display: grid;
    align-content: start;
    min-height: 33rem;
  }

  .hero-preview__frame {
    position: relative;
    border: 1px solid rgba(115, 136, 194, 0.22);
    border-radius: 32px;
    background:
      radial-gradient(circle at 88% 10%, rgba(240, 84, 197, 0.12), transparent 17rem),
      radial-gradient(circle at 12% 22%, rgba(78, 122, 255, 0.14), transparent 18rem),
      linear-gradient(180deg, rgba(10, 18, 42, 0.97), rgba(5, 11, 27, 0.99));
    box-shadow:
      0 30px 72px rgba(1, 7, 20, 0.42),
      inset 0 1px 0 rgba(255, 255, 255, 0.05);
    overflow: hidden;
    min-height: 27rem;
  }

  @media (max-width: 1180px) {
    .hero {
      grid-template-columns: 1fr;
    }

    .hero-copy {
      max-width: 100%;
    }

    .hero-preview {
      min-height: 28rem;
    }
  }

  .hero-preview__frame-glow {
    position: absolute;
    border-radius: 999px;
    filter: blur(18px);
    opacity: 0.5;
    pointer-events: none;
  }

  .hero-preview__frame-glow--blue {
    width: 14rem;
    height: 14rem;
    left: -4rem;
    bottom: -5rem;
    background: rgba(64, 145, 255, 0.18);
  }

  .hero-preview__frame-glow--pink {
    width: 12rem;
    height: 12rem;
    right: -2rem;
    top: -3rem;
    background: rgba(244, 74, 174, 0.18);
  }

  .hero-preview__pulse {
    position: absolute;
    height: 2px;
    border-radius: 999px;
    background: linear-gradient(90deg, rgba(92, 100, 255, 0), rgba(92, 100, 255, 0.9), rgba(242, 74, 176, 0));
    box-shadow:
      0 0 18px rgba(118, 104, 255, 0.45),
      0 0 34px rgba(239, 81, 177, 0.24);
    opacity: 0.78;
    pointer-events: none;
  }

  .hero-preview__pulse::after {
    content: '';
    position: absolute;
    right: 1.4rem;
    top: 50%;
    width: 0.5rem;
    height: 0.5rem;
    border-radius: 999px;
    transform: translateY(-50%);
    background: #f06ac8;
    box-shadow: 0 0 14px rgba(240, 106, 200, 0.66);
  }

  .hero-preview__pulse--1 {
    top: 4.85rem;
    left: 14rem;
    width: 8rem;
    transform: rotate(-3deg);
  }

  .hero-preview__pulse--2 {
    top: 6.15rem;
    right: 4.2rem;
    width: 6.2rem;
    transform: rotate(4deg);
  }

  .hero-preview__topbar {
    position: relative;
    z-index: 1;
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    align-items: center;
    padding: 1rem 1rem 0.9rem;
    border-bottom: 1px solid rgba(115, 136, 194, 0.16);
    background: rgba(255, 255, 255, 0.02);
  }

  .hero-preview__brand {
    display: inline-flex;
    align-items: center;
    gap: 0.7rem;
  }

  .hero-preview__brand strong {
    display: block;
    color: #f8fbff;
    font-size: 1rem;
  }

  .hero-preview__brand small {
    display: block;
    margin-top: 0.18rem;
    color: rgba(223, 232, 248, 0.6);
    font-size: 0.78rem;
  }

  .hero-preview__status {
    background: rgba(255, 255, 255, 0.05);
    border-color: rgba(116, 137, 194, 0.2);
    color: #f8fbff;
  }

  :global(.hero-preview__logo) {
    width: 1.7rem;
    height: 1.7rem;
    border-radius: 0.7rem;
  }

  :global(.hero-preview__logo--large) {
    width: 2.6rem;
    height: 2.6rem;
    border-radius: 1rem;
  }

  .hero-preview__stage {
    position: relative;
    z-index: 1;
    display: grid;
    grid-template-columns: minmax(0, 1.14fr) minmax(210px, 0.82fr);
    gap: 0.95rem;
    padding: 1rem;
  }

  .hero-preview__deck-card {
    display: grid;
    align-content: start;
    gap: 0.9rem;
    border: 1px solid rgba(115, 136, 194, 0.18);
    border-radius: 24px;
    background:
      linear-gradient(180deg, rgba(16, 27, 63, 0.94), rgba(10, 18, 40, 0.98));
    padding: 1rem;
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.05);
  }

  .hero-preview__deck-head,
  .hero-preview__deck-summary,
  .hero-preview__deck-foot {
    display: flex;
    justify-content: space-between;
    gap: 0.85rem;
    align-items: center;
  }

  .hero-preview__deck-summary {
    justify-content: start;
  }

  .hero-preview__deck-summary strong {
    display: block;
    margin-bottom: 0.2rem;
    color: #f8fbff;
  }

  .hero-preview__deck-summary small {
    color: rgba(223, 232, 248, 0.66);
  }

  .hero-preview__deck-kicker {
    color: #8fb7ff;
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.14em;
  }

  .hero-preview__deck-badge {
    padding: 0.28rem 0.62rem;
    border-radius: 999px;
    border: 1px solid rgba(119, 140, 200, 0.2);
    background: rgba(255, 255, 255, 0.03);
    color: rgba(239, 244, 255, 0.74);
    font-size: 0.74rem;
  }

  .hero-preview__deck-canvas {
    display: grid;
    gap: 0.75rem;
    padding: 1rem;
    border-radius: 22px;
    border: 1px solid rgba(115, 136, 194, 0.16);
    background:
      radial-gradient(circle at 15% 15%, rgba(89, 118, 255, 0.12), transparent 12rem),
      linear-gradient(180deg, rgba(11, 20, 48, 0.92), rgba(7, 14, 32, 0.98));
  }

  .hero-preview__canvas-line {
    height: 0.72rem;
    border-radius: 999px;
    background: linear-gradient(90deg, rgba(141, 188, 255, 0.88), rgba(90, 95, 208, 0.68));
  }

  .hero-preview__canvas-line--1 {
    width: 38%;
  }

  .hero-preview__canvas-line--2 {
    width: 84%;
  }

  .hero-preview__canvas-line--3 {
    width: 94%;
  }

  .hero-preview__canvas-line--4 {
    width: 72%;
  }

  .hero-preview__foot-pill,
  .hero-preview__footer-pill {
    background: rgba(255, 255, 255, 0.04);
    border-color: rgba(115, 136, 194, 0.18);
    color: rgba(239, 244, 255, 0.8);
  }

  .hero-preview__analysis-stack {
    display: grid;
    gap: 0.95rem;
  }

  .hero-preview__metric {
    border: 1px solid rgba(115, 136, 194, 0.18);
    border-radius: 24px;
    background: rgba(255, 255, 255, 0.03);
    padding: 0.95rem;
    display: grid;
    gap: 0.7rem;
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
  }

  .hero-preview__metric span,
  .hero-preview__metric small {
    color: rgba(223, 232, 248, 0.62);
  }

  .hero-preview__metric--score {
    align-content: start;
  }

  .hero-preview__gauge {
    display: grid;
    place-items: center;
  }

  .hero-preview__gauge-ring {
    width: 7.3rem;
    height: 7.3rem;
    border-radius: 999px;
    display: grid;
    place-items: center;
    background:
      radial-gradient(circle at center, rgba(8, 16, 36, 0.98) 54%, transparent 55%),
      conic-gradient(from 180deg, #45d7a5 0deg 110deg, #53a7ff 110deg 238deg, #a56fff 238deg 332deg, rgba(255, 255, 255, 0.08) 332deg 360deg);
    box-shadow:
      0 0 28px rgba(83, 167, 255, 0.16),
      inset 0 0 20px rgba(255, 255, 255, 0.05);
  }

  .hero-preview__gauge-ring strong {
    font-size: 1.45rem;
    letter-spacing: -0.05em;
    color: #f8fbff;
  }

  .hero-preview__signal-list {
    margin: 0;
    padding: 0;
    list-style: none;
    display: grid;
    gap: 0.55rem;
  }

  .hero-preview__signal-list li {
    position: relative;
    padding-left: 1rem;
    color: rgba(239, 244, 255, 0.8);
    font-size: 0.84rem;
  }

  .hero-preview__signal-list li::before {
    content: '';
    position: absolute;
    left: 0;
    top: 0.38rem;
    width: 0.42rem;
    height: 0.42rem;
    border-radius: 999px;
    background: linear-gradient(180deg, #53a7ff, #45d7a5);
    box-shadow: 0 0 10px rgba(83, 167, 255, 0.42);
  }

  .hero-preview__footer {
    position: relative;
    z-index: 1;
    display: flex;
    flex-wrap: wrap;
    gap: 0.65rem;
    padding: 0 1rem 1rem;
  }

  @media (max-width: 960px) {
    .hero {
      grid-template-columns: 1fr;
    }

    .hero-preview {
      min-height: auto;
    }

    .hero-preview__frame {
      min-height: auto;
    }
  }

  @media (max-width: 720px) {
    .hero {
      padding: 1rem;
      border-radius: 28px;
    }

    .hero-preview__stage {
      grid-template-columns: 1fr;
    }

    .hero-preview__pulse {
      display: none;
    }

    .hero-preview__deck-head,
    .hero-preview__deck-foot,
    .hero-preview__topbar {
      flex-wrap: wrap;
    }
  }
</style>
