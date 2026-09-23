<script lang="ts">
  import { onMount } from 'svelte';
  import { fade, fly } from 'svelte/transition';

  import { howItWorksSteps } from '$lib/data/marketing/home';

  const stepIndices = howItWorksSteps.map((_, index) => index);

  let activeStep = $state(0);
  let hoverStep: number | null = $state(null);

  const activeStepData = $derived(howItWorksSteps[activeStep]);
  const expandedStep = $derived(hoverStep ?? activeStep);

  onMount(() => {
    const timer = window.setInterval(() => {
      activeStep = (activeStep + 1) % howItWorksSteps.length;
    }, 4600);

    return () => window.clearInterval(timer);
  });

  function setActiveStep(index: number) {
    activeStep = index;
  }

  function setHoverStep(index: number | null) {
    hoverStep = index;
  }
</script>

<section class="panel how-it-works">
  <div class="how-it-works__intro">
    <div>
      <div class="eyebrow">Five-stage workflow</div>
      <h2 id="how-it-works-title">From source intelligence to institutional memory, every step keeps the deck reviewable.</h2>
    </div>

    <p class="muted">
      The platform is designed for investment teams that need more than a prettier presentation. Each stage
      adds structure, market context, and review control without breaking provenance.
    </p>
  </div>

  <div class="how-it-works__selector" role="tablist" aria-label="How Deck AIStack works">
    {#each howItWorksSteps as step, index}
      <button
        type="button"
        role="tab"
        aria-selected={activeStep === index}
        class={`how-it-works__step how-it-works__step--${step.tone}`}
        class:is-active={activeStep === index}
        class:is-hovered={hoverStep === index}
        onclick={() => setActiveStep(index)}
        onfocus={() => setActiveStep(index)}
        onmouseenter={() => setHoverStep(index)}
        onmouseleave={() => setHoverStep(null)}
        onblur={() => setHoverStep(null)}
      >
        <span class="how-it-works__step-index">{step.number}</span>
        <strong>{step.title}</strong>
        <small>{step.short}</small>
        <div class="how-it-works__step-detail">
          <p>{step.headline}</p>
          <span>{step.body}</span>
        </div>
        <span class="how-it-works__step-glow" aria-hidden="true"></span>
      </button>
    {/each}
  </div>

  {#key activeStep}
    <article
      class={`how-it-works__stage how-it-works__stage--${activeStepData.tone}`}
      in:fly={{ y: 12, duration: 260 }}
      out:fade={{ duration: 180 }}
    >
      <div class="how-it-works__copy">
        <div class="how-it-works__copy-top">
          <span class="eyebrow">{activeStepData.kicker}</span>
          <span class="how-it-works__route">{activeStepData.routeLabel}</span>
        </div>

        <h3>{activeStepData.headline}</h3>
        <p class="how-it-works__body">{activeStepData.body}</p>

        <div class="how-it-works__notes">
          <article class="how-it-works__note">
            <span>VC bottleneck</span>
            <p>{activeStepData.problem}</p>
          </article>

          <article class="how-it-works__note">
            <span>Deck AIStack response</span>
            <p>{activeStepData.solution}</p>
          </article>
        </div>

        <div class="how-it-works__signals">
          {#each activeStepData.signals as signal}
            <span>{signal}</span>
          {/each}
        </div>

        <p class="how-it-works__expanded-summary">
          {howItWorksSteps[expandedStep].title} · {howItWorksSteps[expandedStep].headline}
        </p>
      </div>

      <div class="how-it-works__visual" aria-hidden="true">
        <div class="how-it-works__visual-orb"></div>
        <div class="how-it-works__visual-orb how-it-works__visual-orb--secondary"></div>

        <div class="how-it-works__visual-grid">
          <article class="how-it-works__visual-card how-it-works__visual-card--wide">
            <span class="how-it-works__visual-kicker">{activeStepData.visualTitle}</span>
            <strong>{activeStepData.visualSubtitle}</strong>

            <div class="how-it-works__visual-lines">
              <span class="how-it-works__line how-it-works__line--1"></span>
              <span class="how-it-works__line how-it-works__line--2"></span>
              <span class="how-it-works__line how-it-works__line--3"></span>
              <span class="how-it-works__line how-it-works__line--4"></span>
            </div>
          </article>

          <article class="how-it-works__visual-card how-it-works__visual-card--stack">
            {#each activeStepData.visualPoints as point}
              <div class="how-it-works__visual-point">
                <span class="how-it-works__visual-dot"></span>
                <p>{point}</p>
              </div>
            {/each}
          </article>

          <article class="how-it-works__visual-card how-it-works__visual-card--progress">
            <span class="how-it-works__visual-kicker">Workflow progress</span>

            <div class="how-it-works__progress">
              {#each stepIndices as stepIndex}
                <span class="how-it-works__progress-dot" class:how-it-works__progress-dot--active={stepIndex <= activeStep}>
                  {howItWorksSteps[stepIndex].number}
                </span>
              {/each}
            </div>

            <small>Provenance, context, and review history stay attached to the deck from intake to export.</small>
          </article>
        </div>

        <span class="how-it-works__beam"></span>
      </div>
    </article>
  {/key}
</section>

<style>
  .how-it-works {
    padding: 1.8rem;
    display: grid;
    gap: 1.35rem;
    background:
      radial-gradient(circle at top left, rgba(86, 132, 255, 0.14), transparent 18rem),
      radial-gradient(circle at top right, rgba(240, 74, 176, 0.12), transparent 16rem),
      linear-gradient(180deg, rgba(7, 14, 34, 0.98), rgba(4, 9, 23, 0.99));
  }

  .how-it-works__intro {
    display: grid;
    grid-template-columns: minmax(0, 1.08fr) minmax(320px, 0.92fr);
    gap: 1.4rem;
    align-items: end;
  }

  .how-it-works__intro h2 {
    margin: 0;
    max-width: 14ch;
    font-size: clamp(1.8rem, 3vw, 3rem);
    line-height: 0.98;
    letter-spacing: -0.05em;
  }

  .how-it-works__intro p {
    margin: 0;
    line-height: 1.65;
  }

  .how-it-works__selector {
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    gap: 0.85rem;
  }

  .how-it-works__step {
    position: relative;
    overflow: hidden;
    appearance: none;
    border: 1px solid rgba(117, 138, 194, 0.18);
    border-radius: 24px;
    padding: 1.05rem 1.05rem 1.1rem;
    background: linear-gradient(180deg, rgba(18, 29, 66, 0.94), rgba(9, 16, 35, 0.98));
    color: rgba(234, 241, 255, 0.76);
    display: grid;
    gap: 0.52rem;
    text-align: left;
    cursor: pointer;
    box-shadow:
      0 18px 34px rgba(2, 7, 19, 0.16),
      inset 0 1px 0 rgba(255, 255, 255, 0.04);
    transition:
      transform 180ms ease,
      border-color 180ms ease,
      box-shadow 180ms ease,
      background 180ms ease,
      color 180ms ease;
  }

  @media (max-width: 1180px) {
    .how-it-works__intro {
      grid-template-columns: 1fr;
      align-items: start;
    }

    .how-it-works__intro h2 {
      max-width: 18ch;
    }

    .how-it-works__selector {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }

  .how-it-works__step:hover,
  .how-it-works__step.is-active,
  .how-it-works__step.is-hovered,
  .how-it-works__step:focus-visible {
    transform: translateY(-3px);
    border-color: rgba(136, 176, 255, 0.3);
    color: #f8fbff;
    box-shadow:
      0 18px 34px rgba(2, 7, 19, 0.26),
      0 0 0 1px rgba(126, 173, 255, 0.06),
      inset 0 1px 0 rgba(255, 255, 255, 0.05);
  }

  .how-it-works__step:focus-visible {
    outline: none;
  }

  .how-it-works__step strong,
  .how-it-works__step small {
    position: relative;
    z-index: 1;
  }

  .how-it-works__step strong {
    font-size: 0.96rem;
    line-height: 1.18;
    color: #f8fbff;
  }

  .how-it-works__step small {
    font-size: 0.8rem;
    line-height: 1.45;
    color: rgba(222, 231, 247, 0.65);
  }

  .how-it-works__step-detail {
    display: grid;
    gap: 0.35rem;
    margin-top: 0.15rem;
    opacity: 0;
    max-height: 0;
    overflow: hidden;
    transform: translateY(-0.25rem);
    transition:
      opacity 180ms ease,
      max-height 220ms ease,
      transform 180ms ease;
  }

  .how-it-works__step:hover .how-it-works__step-detail,
  .how-it-works__step.is-hovered .how-it-works__step-detail,
  .how-it-works__step.is-active .how-it-works__step-detail,
  .how-it-works__step:focus-visible .how-it-works__step-detail {
    opacity: 1;
    max-height: 10rem;
    transform: translateY(0);
  }

  .how-it-works__step-detail p {
    margin: 0;
    color: #f8fbff;
    font-size: 0.92rem;
    line-height: 1.38;
  }

  .how-it-works__step-detail span {
    color: rgba(222, 231, 247, 0.7);
    font-size: 0.82rem;
    line-height: 1.5;
  }

  .how-it-works__step-index {
    position: relative;
    z-index: 1;
    width: 2rem;
    height: 2rem;
    border-radius: 999px;
    display: grid;
    place-items: center;
    border: 1px solid rgba(154, 185, 255, 0.22);
    background: rgba(255, 255, 255, 0.04);
    color: #f3f7ff;
    font-size: 0.85rem;
  }

  .how-it-works__step-glow {
    position: absolute;
    inset: auto -1.5rem -2rem auto;
    width: 6rem;
    height: 6rem;
    border-radius: 999px;
    filter: blur(18px);
    opacity: 0.38;
    transition: opacity 180ms ease, transform 180ms ease;
  }

  .how-it-works__step:hover .how-it-works__step-glow,
  .how-it-works__step.is-active .how-it-works__step-glow,
  .how-it-works__step:focus-visible .how-it-works__step-glow {
    opacity: 0.6;
    transform: scale(1.08);
  }

  .how-it-works__step--blue .how-it-works__step-glow {
    background: rgba(75, 143, 255, 0.32);
  }

  .how-it-works__step--teal .how-it-works__step-glow {
    background: rgba(69, 215, 165, 0.28);
  }

  .how-it-works__step--violet .how-it-works__step-glow {
    background: rgba(159, 107, 255, 0.3);
  }

  .how-it-works__step--pink .how-it-works__step-glow {
    background: rgba(240, 106, 200, 0.28);
  }

  .how-it-works__step--amber .how-it-works__step-glow {
    background: rgba(255, 193, 92, 0.26);
  }

  .how-it-works__stage {
    position: relative;
    overflow: hidden;
    display: grid;
    grid-template-columns: minmax(0, 1.02fr) minmax(340px, 0.98fr);
    gap: 1rem;
    border: 1px solid rgba(117, 138, 194, 0.2);
    border-radius: 28px;
    padding: 1.1rem;
    background:
      radial-gradient(circle at top right, rgba(86, 124, 255, 0.14), transparent 20rem),
      linear-gradient(180deg, rgba(18, 29, 66, 0.97), rgba(8, 15, 33, 0.99));
    box-shadow:
      0 28px 52px rgba(2, 7, 19, 0.32),
      inset 0 1px 0 rgba(255, 255, 255, 0.04);
  }

  .how-it-works__stage--blue {
    background:
      radial-gradient(circle at top right, rgba(83, 167, 255, 0.18), transparent 18rem),
      linear-gradient(180deg, rgba(18, 29, 66, 0.97), rgba(8, 15, 33, 0.99));
  }

  .how-it-works__stage--teal {
    background:
      radial-gradient(circle at top right, rgba(69, 215, 165, 0.18), transparent 18rem),
      linear-gradient(180deg, rgba(17, 30, 58, 0.97), rgba(7, 15, 31, 0.99));
  }

  .how-it-works__stage--violet {
    background:
      radial-gradient(circle at top right, rgba(161, 109, 255, 0.18), transparent 18rem),
      linear-gradient(180deg, rgba(19, 29, 68, 0.97), rgba(9, 15, 34, 0.99));
  }

  .how-it-works__stage--pink {
    background:
      radial-gradient(circle at top right, rgba(240, 106, 200, 0.18), transparent 18rem),
      linear-gradient(180deg, rgba(20, 28, 62, 0.97), rgba(9, 14, 32, 0.99));
  }

  .how-it-works__stage--amber {
    background:
      radial-gradient(circle at top right, rgba(255, 193, 92, 0.18), transparent 18rem),
      linear-gradient(180deg, rgba(20, 28, 58, 0.97), rgba(9, 15, 31, 0.99));
  }

  .how-it-works__copy {
    position: relative;
    z-index: 1;
    display: grid;
    align-content: start;
    gap: 0.9rem;
  }

  .how-it-works__copy-top {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    gap: 0.7rem;
    align-items: center;
  }

  .how-it-works__route {
    padding: 0.35rem 0.7rem;
    border-radius: 999px;
    border: 1px solid rgba(133, 154, 206, 0.2);
    background: rgba(255, 255, 255, 0.04);
    color: rgba(236, 242, 255, 0.78);
    font-size: 0.78rem;
  }

  .how-it-works__copy h3 {
    margin: 0;
    max-width: 16ch;
    font-size: clamp(1.45rem, 2vw, 2.2rem);
    line-height: 1.02;
    letter-spacing: -0.05em;
  }

  .how-it-works__body {
    margin: 0;
    max-width: 36rem;
    color: rgba(236, 242, 255, 0.8);
    line-height: 1.65;
  }

  .how-it-works__notes {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.8rem;
  }

  .how-it-works__note {
    padding: 0.9rem;
    border-radius: 20px;
    border: 1px solid rgba(117, 138, 194, 0.16);
    background: rgba(255, 255, 255, 0.03);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.03);
  }

  .how-it-works__note span,
  .how-it-works__visual-kicker {
    color: #8fb7ff;
    font-size: 0.72rem;
    letter-spacing: 0.14em;
    text-transform: uppercase;
  }

  .how-it-works__note p {
    margin: 0.55rem 0 0;
    color: rgba(236, 242, 255, 0.76);
    line-height: 1.58;
  }

  .how-it-works__signals {
    display: flex;
    flex-wrap: wrap;
    gap: 0.6rem;
  }

  .how-it-works__signals span {
    padding: 0.42rem 0.72rem;
    border-radius: 999px;
    border: 1px solid rgba(133, 154, 206, 0.18);
    background: rgba(255, 255, 255, 0.04);
    color: #f8fbff;
    font-size: 0.82rem;
  }

  .how-it-works__expanded-summary {
    margin: 0.1rem 0 0;
    color: rgba(236, 242, 255, 0.7);
    font-size: 0.86rem;
    line-height: 1.5;
  }

  .how-it-works__visual {
    position: relative;
    min-height: 24rem;
    border-radius: 24px;
    border: 1px solid rgba(117, 138, 194, 0.18);
    background:
      linear-gradient(180deg, rgba(11, 20, 47, 0.96), rgba(7, 13, 29, 0.98)),
      linear-gradient(135deg, rgba(255, 255, 255, 0.04), transparent 42%);
    overflow: hidden;
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.05);
  }

  .how-it-works__visual-orb {
    position: absolute;
    width: 11rem;
    height: 11rem;
    top: -2rem;
    right: -2rem;
    border-radius: 999px;
    filter: blur(18px);
    opacity: 0.4;
    animation: float-orb 8s ease-in-out infinite;
  }

  .how-it-works__visual-orb--secondary {
    width: 8rem;
    height: 8rem;
    right: auto;
    left: -1.5rem;
    bottom: -2rem;
    top: auto;
    animation-duration: 10s;
  }

  .how-it-works__stage--blue .how-it-works__visual-orb {
    background: rgba(83, 167, 255, 0.28);
  }

  .how-it-works__stage--blue .how-it-works__visual-orb--secondary {
    background: rgba(104, 116, 255, 0.2);
  }

  .how-it-works__stage--teal .how-it-works__visual-orb {
    background: rgba(69, 215, 165, 0.28);
  }

  .how-it-works__stage--teal .how-it-works__visual-orb--secondary {
    background: rgba(83, 167, 255, 0.16);
  }

  .how-it-works__stage--violet .how-it-works__visual-orb {
    background: rgba(161, 109, 255, 0.28);
  }

  .how-it-works__stage--violet .how-it-works__visual-orb--secondary {
    background: rgba(92, 120, 255, 0.16);
  }

  .how-it-works__stage--pink .how-it-works__visual-orb {
    background: rgba(240, 106, 200, 0.28);
  }

  .how-it-works__stage--pink .how-it-works__visual-orb--secondary {
    background: rgba(136, 108, 255, 0.18);
  }

  .how-it-works__stage--amber .how-it-works__visual-orb {
    background: rgba(255, 193, 92, 0.26);
  }

  .how-it-works__stage--amber .how-it-works__visual-orb--secondary {
    background: rgba(83, 167, 255, 0.15);
  }

  .how-it-works__visual-grid {
    position: relative;
    z-index: 1;
    display: grid;
    grid-template-columns: minmax(0, 1.15fr) minmax(180px, 0.85fr);
    gap: 0.85rem;
    padding: 1rem;
    height: 100%;
  }

  .how-it-works__visual-card {
    position: relative;
    overflow: hidden;
    border-radius: 22px;
    border: 1px solid rgba(117, 138, 194, 0.16);
    background:
      linear-gradient(180deg, rgba(22, 34, 76, 0.88), rgba(11, 18, 38, 0.96)),
      linear-gradient(135deg, rgba(255, 255, 255, 0.03), transparent 48%);
    padding: 0.95rem;
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
  }

  .how-it-works__visual-card--wide {
    min-height: 13.2rem;
    display: grid;
    align-content: start;
    gap: 0.8rem;
  }

  .how-it-works__visual-card--wide strong {
    max-width: 18ch;
    line-height: 1.28;
    color: #f8fbff;
  }

  .how-it-works__visual-lines {
    display: grid;
    gap: 0.75rem;
    margin-top: 0.2rem;
  }

  .how-it-works__line {
    display: block;
    height: 0.72rem;
    border-radius: 999px;
    background: linear-gradient(90deg, rgba(150, 193, 255, 0.9), rgba(108, 111, 255, 0.6));
  }

  .how-it-works__line--1 {
    width: 42%;
  }

  .how-it-works__line--2 {
    width: 88%;
  }

  .how-it-works__line--3 {
    width: 72%;
  }

  .how-it-works__line--4 {
    width: 56%;
  }

  .how-it-works__visual-card--stack {
    display: grid;
    align-content: start;
    gap: 0.7rem;
  }

  .how-it-works__visual-point {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    gap: 0.55rem;
    align-items: start;
    padding: 0.7rem 0.75rem;
    border-radius: 18px;
    background: rgba(255, 255, 255, 0.04);
  }

  .how-it-works__visual-point p {
    margin: 0;
    color: rgba(236, 242, 255, 0.78);
    line-height: 1.45;
  }

  .how-it-works__visual-dot {
    width: 0.58rem;
    height: 0.58rem;
    border-radius: 999px;
    margin-top: 0.34rem;
    background: linear-gradient(180deg, #53a7ff, #45d7a5);
    box-shadow: 0 0 14px rgba(83, 167, 255, 0.4);
  }

  .how-it-works__visual-card--progress {
    grid-column: 1 / -1;
    display: grid;
    gap: 0.8rem;
    align-content: start;
  }

  .how-it-works__progress {
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    gap: 0.55rem;
  }

  .how-it-works__progress-dot {
    min-height: 2.2rem;
    border-radius: 999px;
    display: grid;
    place-items: center;
    border: 1px solid rgba(133, 154, 206, 0.16);
    background: rgba(255, 255, 255, 0.04);
    color: rgba(236, 242, 255, 0.68);
    font-size: 0.82rem;
    transition: background 180ms ease, color 180ms ease, border-color 180ms ease;
  }

  .how-it-works__progress-dot--active {
    border-color: rgba(143, 183, 255, 0.24);
    background: linear-gradient(135deg, rgba(72, 157, 255, 0.22), rgba(161, 109, 255, 0.22));
    color: #f8fbff;
  }

  .how-it-works__visual-card--progress small {
    color: rgba(236, 242, 255, 0.68);
    line-height: 1.55;
  }

  .how-it-works__beam {
    position: absolute;
    left: -18%;
    bottom: 5.6rem;
    width: 60%;
    height: 2px;
    border-radius: 999px;
    background: linear-gradient(90deg, rgba(83, 167, 255, 0), rgba(83, 167, 255, 0.88), rgba(240, 106, 200, 0));
    box-shadow:
      0 0 16px rgba(83, 167, 255, 0.35),
      0 0 28px rgba(240, 106, 200, 0.22);
    animation: beam-sweep 5.6s ease-in-out infinite;
  }

  @keyframes beam-sweep {
    0%,
    100% {
      transform: translateX(0) rotate(-6deg);
      opacity: 0.45;
    }

    50% {
      transform: translateX(40%) rotate(-3deg);
      opacity: 0.88;
    }
  }

  @keyframes float-orb {
    0%,
    100% {
      transform: translate3d(0, 0, 0);
    }

    50% {
      transform: translate3d(0, 14px, 0);
    }
  }

  @media (max-width: 1120px) {
    .how-it-works__selector {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .how-it-works__stage {
      grid-template-columns: 1fr;
    }
  }

  @media (max-width: 860px) {
    .how-it-works__intro {
      grid-template-columns: 1fr;
    }

    .how-it-works__visual-grid,
    .how-it-works__notes {
      grid-template-columns: 1fr;
    }
  }

  @media (max-width: 640px) {
    .how-it-works {
      padding: 1rem;
      border-radius: 26px;
    }

    .how-it-works__selector,
    .how-it-works__progress {
      grid-template-columns: 1fr;
    }

    .how-it-works__step,
    .how-it-works__stage {
      border-radius: 22px;
    }

    .how-it-works__step-detail {
      opacity: 1;
      max-height: none;
      transform: none;
    }

    .how-it-works__visual {
      min-height: auto;
    }

    .how-it-works__beam {
      display: none;
    }
  }
</style>
