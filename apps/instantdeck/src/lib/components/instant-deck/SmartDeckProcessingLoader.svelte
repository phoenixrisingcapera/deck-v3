<script lang="ts">
  import type { ProcessingStep } from './processingTypes';

  interface Props {
    progress?: number;
    steps?: ProcessingStep[];
    deckTitle?: string;
    subtitle?: string;
  }

  let {
    progress = 0,
    steps = [
      { id: 'file_received', label: '1. File received', detail: 'Upload successful', status: 'done' },
      { id: 'reading_slides', label: '2. Reading slides', detail: 'Content recognized', status: 'done' },
      { id: 'creating_previews', label: '3. Creating previews', detail: 'Generating thumbnails', status: 'active' },
      { id: 'extracting_brand', label: '4. Extracting brand context', detail: 'Analyzing brand elements', status: 'pending' },
      { id: 'building_context', label: '5. Building SmartDeckContext', detail: 'Structuring intelligence', status: 'pending' },
      { id: 'preparing_workspace', label: '6. Preparing workspace', detail: 'Finalizing your space', status: 'pending' }
    ],
    deckTitle = 'your uploaded deck',
    subtitle = "We're turning your uploaded deck into a Smart Deck with previews, brand context, and editable slide intelligence."
  }: Props = $props();

  const slideCards = [
    { title: 'Q1 Business Review', subtitle: 'Executive Summary', kind: 'mountain' },
    { title: 'Growth Strategy', subtitle: 'Market Analysis', kind: 'bars' },
    { title: 'Market Overview', subtitle: 'Key Insights', kind: 'donut' },
    { title: 'Financials Deck', subtitle: 'Performance', kind: 'line' }
  ];

  const safeProgress = $derived(Math.max(0, Math.min(100, Math.round(progress))));
  const activeStep = $derived(steps.find((step) => step.status === 'active'));
</script>

<section class="processing-shell" aria-live="polite">
  <div class="orbital-grid"></div>

  <div class="loader-card">
    <div class="eyebrow">
      <span class="spark">✦</span>
      <span>Smart Deck processing</span>
    </div>

    <h1>Preparing your AI workspace</h1>
    <p class="subtitle">{subtitle}</p>
    <p class="deck-copy">Source: {deckTitle}</p>

    <div class="animation-stage">
      <div class="slide-stream" aria-hidden="true">
        {#each slideCards as card, index}
          <article class="flying-slide" style={`--i: ${index}; --delay: ${index * 0.34}s;`}>
            <div class="mini-title">{card.title}</div>
            <div class="mini-subtitle">{card.subtitle}</div>

            {#if card.kind === 'mountain'}
              <div class="mountain-visual"><span></span><span></span></div>
            {:else if card.kind === 'bars'}
              <div class="bars-visual"><i></i><i></i><i></i><i></i></div>
            {:else if card.kind === 'donut'}
              <div class="donut-visual"></div>
            {:else}
              <div class="line-visual">
                <svg viewBox="0 0 120 48" role="presentation"><path d="M4 38 C22 30 25 18 42 23 C58 29 66 8 82 15 C96 22 100 10 116 7" /></svg>
              </div>
            {/if}
          </article>
        {/each}

        <div class="energy-beam"></div>
      </div>

      <div class="laptop-wrap" aria-hidden="true">
        <div class="laptop-screen">
          <div class="screen-sidebar"><span></span><span></span><span></span></div>

          <div class="screen-main">
            <div class="screen-header"><span>✦</span><strong>Your Smart Deck is ready</strong></div>

            <div class="screen-grid">
              <div class="preview-tile"></div>
              <div class="chart-tile"><i></i><i></i><i></i></div>
              <div class="text-tile"><span></span><span></span><span></span></div>
              <div class="donut-tile"></div>
            </div>
          </div>

          <aside class="screen-panel">
            <div class="panel-block">
              <strong>Brand context</strong>
              <span></span><span></span><span></span>
              <div class="color-row"><i></i><i></i><i></i><i></i></div>
            </div>

            <div class="panel-block">
              <strong>Slide intelligence</strong>
              <span></span><span></span><span></span>
            </div>
          </aside>
        </div>

        <div class="laptop-base"></div>
      </div>
    </div>

    <div class="progress-copy">
      {safeProgress}% complete
      {#if activeStep}<span> · {activeStep.detail}</span>{/if}
    </div>

    <div class="progress-track"><div class="progress-fill" style={`width: ${safeProgress}%`}></div></div>

    <div class="steps-grid">
      {#each steps as step}
        <article class={`step-card ${step.status}`}>
          <div class="status-icon">
            {#if step.status === 'done'}✓{:else if step.status === 'failed'}!{:else}<span></span>{/if}
          </div>

          <div>
            <strong>{step.label}</strong>
            <p>{step.detail}</p>
          </div>
        </article>
      {/each}
    </div>

    <p class="footer-note"><span>◆</span>This usually takes less than a minute.</p>
  </div>
</section>

<style>
  .processing-shell { min-height: 100vh; display: grid; place-items: center; padding: 32px; color: #f8fafc; background: radial-gradient(circle at 20% 50%, rgba(124, 58, 237, 0.22), transparent 28%), radial-gradient(circle at 80% 40%, rgba(59, 130, 246, 0.16), transparent 30%), linear-gradient(180deg, #030712 0%, #07101f 100%); overflow: hidden; position: relative; }
  .orbital-grid { position: absolute; inset: -20%; background: repeating-radial-gradient(circle at 20% 55%, rgba(139, 92, 246, 0.26) 0 1px, transparent 1px 22px); opacity: 0.25; transform: rotate(-12deg); pointer-events: none; }
  .loader-card { width: min(1180px, 100%); min-height: 720px; position: relative; z-index: 1; border: 1px solid rgba(148, 163, 184, 0.22); border-radius: 28px; background: linear-gradient(180deg, rgba(15, 23, 42, 0.74), rgba(2, 6, 23, 0.92)), radial-gradient(circle at 50% 30%, rgba(124, 58, 237, 0.18), transparent 38%); box-shadow: 0 30px 100px rgba(0, 0, 0, 0.55), inset 0 1px 0 rgba(255, 255, 255, 0.08); padding: 28px 32px 32px; overflow: hidden; }
  .eyebrow { width: fit-content; margin: 0 auto 18px; display: flex; align-items: center; gap: 8px; padding: 8px 16px; border: 1px solid rgba(139, 92, 246, 0.35); border-radius: 999px; color: #c4b5fd; background: rgba(88, 28, 135, 0.34); font-weight: 700; font-size: 14px; }
  .spark { color: #a78bfa; }
  h1 { margin: 0; text-align: center; font-size: clamp(36px, 5vw, 58px); line-height: 0.95; letter-spacing: -0.055em; }
  .subtitle { max-width: 660px; margin: 18px auto 0; text-align: center; color: #a8b3c7; font-size: 17px; line-height: 1.55; }
  .deck-copy { text-align: center; color: #8ea3c9; margin: 10px 0 0; font-size: 0.9rem; }
  .animation-stage { position: relative; height: 320px; margin: 16px auto 0; display: grid; grid-template-columns: 1fr 480px; align-items: center; gap: 18px; }
  .slide-stream { position: relative; height: 240px; }
  .flying-slide { position: absolute; left: calc(10px + var(--i) * 145px); top: calc(88px - var(--i) * 18px); width: 132px; height: 98px; padding: 12px; border-radius: 10px; border: 1px solid rgba(167, 139, 250, 0.55); background: linear-gradient(180deg, rgba(30, 41, 59, 0.96), rgba(15, 23, 42, 0.92)), radial-gradient(circle at 30% 80%, rgba(124, 58, 237, 0.42), transparent 54%); box-shadow: 0 0 28px rgba(139, 92, 246, 0.42), inset 0 1px 0 rgba(255, 255, 255, 0.09); transform: perspective(900px) rotateY(18deg) rotateZ(4deg); animation: slideIntoLaptop 3.2s cubic-bezier(0.65, 0, 0.35, 1) infinite; animation-delay: var(--delay); }
  .mini-title { font-size: 8px; font-weight: 800; }
  .mini-subtitle { margin-top: 4px; font-size: 6px; color: #cbd5e1; }
  .mountain-visual { position: absolute; left: 12px; right: 12px; bottom: 12px; height: 38px; overflow: hidden; border-radius: 8px; background: linear-gradient(135deg, rgba(49, 46, 129, 0.9), rgba(88, 28, 135, 0.7)); }
  .mountain-visual span { position: absolute; inset: auto 0 0; height: 24px; background: linear-gradient(135deg, #5b21b6, #a855f7); clip-path: polygon(0 80%, 22% 35%, 44% 62%, 62% 20%, 100% 72%, 100% 100%, 0 100%); }
  .mountain-visual span:last-child { opacity: 0.45; transform: translateY(8px); }
  .bars-visual { position: absolute; left: 20px; right: 20px; bottom: 16px; height: 46px; display: flex; align-items: end; gap: 10px; }
  .bars-visual i, .chart-tile i { display: block; width: 12px; border-radius: 3px 3px 0 0; background: linear-gradient(180deg, #c084fc, #7c3aed); }
  .bars-visual i:nth-child(1) { height: 18px; } .bars-visual i:nth-child(2) { height: 28px; } .bars-visual i:nth-child(3) { height: 38px; } .bars-visual i:nth-child(4) { height: 48px; }
  .donut-visual, .donut-tile { position: absolute; width: 42px; height: 42px; border-radius: 50%; background: conic-gradient(#a855f7 0 72%, #334155 72% 100%); }
  .donut-visual { right: 22px; bottom: 18px; }
  .donut-visual::after, .donut-tile::after { content: ''; position: absolute; inset: 12px; border-radius: 50%; background: #0f172a; }
  .line-visual { position: absolute; left: 12px; right: 12px; bottom: 18px; }
  .line-visual path { fill: none; stroke: #a855f7; stroke-width: 5; stroke-linecap: round; }
  .energy-beam { position: absolute; left: 54%; top: 137px; width: 260px; height: 34px; transform: translateX(-16%); background: linear-gradient(90deg, transparent, rgba(124, 58, 237, 0.2), #a855f7, #ffffff); filter: blur(2px); clip-path: polygon(0 35%, 100% 50%, 0 65%); animation: beamPulse 1.4s ease-in-out infinite; }
  .laptop-wrap { position: relative; width: 480px; margin-right: 36px; }
  .laptop-screen { height: 235px; border: 2px solid rgba(148, 163, 184, 0.72); border-radius: 16px 16px 6px 6px; background: linear-gradient(180deg, rgba(15, 23, 42, 0.98), rgba(2, 6, 23, 1)); box-shadow: 0 0 55px rgba(124, 58, 237, 0.32), inset 0 1px 0 rgba(255, 255, 255, 0.16); padding: 18px; display: grid; grid-template-columns: 56px 1fr 118px; gap: 14px; }
  .screen-sidebar { border-right: 1px solid rgba(148, 163, 184, 0.16); display: grid; align-content: start; gap: 14px; padding-top: 16px; }
  .screen-sidebar span { width: 22px; height: 22px; border-radius: 50%; border: 1px solid rgba(148, 163, 184, 0.26); }
  .screen-header { display: flex; align-items: center; gap: 8px; color: #ede9fe; font-size: 13px; margin-bottom: 14px; }
  .screen-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  .preview-tile, .chart-tile, .text-tile, .donut-tile, .panel-block { border: 1px solid rgba(148, 163, 184, 0.14); border-radius: 10px; background: rgba(15, 23, 42, 0.82); }
  .preview-tile { height: 72px; background: linear-gradient(135deg, rgba(49, 46, 129, 0.95), rgba(124, 58, 237, 0.65)), radial-gradient(circle at 65% 65%, #7c3aed, transparent 38%); }
  .chart-tile { height: 72px; display: flex; align-items: end; justify-content: center; gap: 10px; padding-bottom: 16px; }
  .chart-tile i:nth-child(1) { height: 18px; } .chart-tile i:nth-child(2) { height: 26px; } .chart-tile i:nth-child(3) { height: 40px; }
  .text-tile { height: 74px; padding: 14px; }
  .text-tile span, .panel-block span { display: block; height: 6px; margin-bottom: 9px; border-radius: 99px; background: rgba(148, 163, 184, 0.24); }
  .text-tile span:nth-child(1) { width: 78%; } .text-tile span:nth-child(2) { width: 62%; } .text-tile span:nth-child(3) { width: 86%; }
  .donut-tile { position: relative; margin: auto; }
  .screen-panel { display: grid; gap: 10px; }
  .panel-block { padding: 12px; min-height: 86px; }
  .panel-block strong { display: block; margin-bottom: 12px; font-size: 10px; color: #e2e8f0; }
  .color-row { display: flex; gap: 6px; } .color-row i { width: 10px; height: 10px; border-radius: 50%; }
  .color-row i:nth-child(1) { background: #a78bfa; } .color-row i:nth-child(2) { background: #38bdf8; } .color-row i:nth-child(3) { background: #fb7185; } .color-row i:nth-child(4) { background: #fbbf24; }
  .laptop-base { height: 18px; width: 570px; margin-left: -45px; border-radius: 0 0 999px 999px; background: linear-gradient(90deg, #1e293b, #94a3b8, #1e293b), linear-gradient(180deg, #64748b, #0f172a); box-shadow: 0 18px 45px rgba(0, 0, 0, 0.55), 0 0 18px rgba(124, 58, 237, 0.8); }
  .progress-copy { text-align: center; color: #e2e8f0; font-weight: 700; margin: 8px 0 10px; }
  .progress-copy span { color: #a78bfa; }
  .progress-track { height: 10px; width: min(790px, 80%); margin: 0 auto 22px; border-radius: 999px; overflow: hidden; background: rgba(51, 65, 85, 0.78); }
  .progress-fill { height: 100%; border-radius: inherit; background: linear-gradient(90deg, #7c3aed, #a855f7, #60a5fa); box-shadow: 0 0 24px rgba(168, 85, 247, 0.7); transition: width 420ms ease; }
  .steps-grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 12px; }
  .step-card { min-height: 78px; display: flex; gap: 12px; padding: 16px; border-radius: 12px; border: 1px solid rgba(148, 163, 184, 0.16); background: rgba(15, 23, 42, 0.72); }
  .step-card.active { border-color: rgba(168, 85, 247, 0.8); box-shadow: inset 0 0 0 1px rgba(168, 85, 247, 0.22); }
  .step-card.failed { border-color: rgba(248, 113, 113, 0.74); }
  .status-icon { width: 26px; height: 26px; flex: 0 0 26px; display: grid; place-items: center; border-radius: 50%; color: #fff; font-weight: 800; background: rgba(71, 85, 105, 0.8); }
  .done .status-icon { background: linear-gradient(135deg, #34d399, #10b981); }
  .active .status-icon { background: transparent; border: 3px solid rgba(168, 85, 247, 0.35); border-top-color: #a855f7; animation: spin 1s linear infinite; }
  .active .status-icon span { display: none; }
  .failed .status-icon { background: #ef4444; }
  .step-card strong { display: block; color: #f8fafc; font-size: 13px; line-height: 1.35; }
  .step-card p { margin: 7px 0 0; color: #a8b3c7; font-size: 11px; line-height: 1.35; }
  .active p { color: #c4b5fd; }
  .footer-note { display: flex; justify-content: center; align-items: center; gap: 12px; margin: 24px 0 0; color: #f8fafc; font-weight: 800; }
  .footer-note span { width: 34px; height: 34px; display: grid; place-items: center; border-radius: 50%; color: #c4b5fd; background: rgba(124, 58, 237, 0.32); }
  @keyframes slideIntoLaptop { 0% { opacity: 0; transform: translateX(-60px) translateY(28px) scale(0.8) perspective(900px) rotateY(22deg) rotateZ(5deg);} 14% {opacity:1;} 54% {opacity:1; transform: translateX(170px) translateY(2px) scale(1) perspective(900px) rotateY(18deg) rotateZ(3deg);} 82% {opacity:.8; transform: translateX(520px) translateY(22px) scale(.44) perspective(900px) rotateY(0deg) rotateZ(0deg);} 100% {opacity:0; transform: translateX(560px) translateY(28px) scale(.28);} }
  @keyframes beamPulse { 0%,100% { opacity:.45; transform: translateX(-16%) scaleX(.82);} 50% { opacity:1; transform: translateX(-12%) scaleX(1.08);} }
  @keyframes spin { to { transform: rotate(360deg);} }
  @media (max-width: 980px) { .animation-stage { grid-template-columns: 1fr; height: auto; } .slide-stream { height: 210px; transform: scale(.8); transform-origin: left center; } .laptop-wrap { width: min(480px, 100%); margin: 0 auto; transform: scale(.86); transform-origin: top center; } .steps-grid { grid-template-columns: repeat(2, 1fr); } }
  @media (max-width: 640px) { .processing-shell { padding: 14px; } .loader-card { padding: 22px 16px; } .slide-stream { display: none; } .steps-grid { grid-template-columns: 1fr; } .progress-track { width: 100%; } }
</style>
