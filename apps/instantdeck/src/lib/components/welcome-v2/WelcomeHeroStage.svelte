<script lang="ts">
  interface PreviewRow {
    label: string;
    copy: string;
  }

  interface RecentDeck {
    title: string;
    status: string;
  }

  interface Props {
    workspaceName: string;
    workspaceNotice: string | null;
    previewRows: readonly PreviewRow[];
    recentDecks: readonly RecentDeck[];
    deckCount: number;
    readyDeckCount: number;
    exportCount: number;
  }

  let {
    workspaceName,
    workspaceNotice,
    previewRows,
    recentDecks,
    deckCount,
    readyDeckCount,
    exportCount
  }: Props = $props();
</script>

<aside class="hero-stage panel" aria-label="Workspace summary">
  <div class="hero-stage__top">
    <div>
      <div class="hero-stage__eyebrow">Smart Deck workspace</div>
      <h2 class="hero-stage__title">Review your uploaded deck</h2>
    </div>
    <span class="hero-stage__chip">{workspaceName}</span>
  </div>

  {#if workspaceNotice}
    <div class="hero-stage__notice" role="status">
      <strong>Previous decks unavailable</strong>
      <p>{workspaceNotice}</p>
    </div>
  {/if}

  <div class="hero-stage__art" aria-hidden="true">
    <span class="hero-stage__ring hero-stage__ring--one"></span>
    <span class="hero-stage__ring hero-stage__ring--two"></span>
    <span class="hero-stage__ring hero-stage__ring--three"></span>
    <span class="hero-stage__star hero-stage__star--one"></span>
    <span class="hero-stage__star hero-stage__star--two"></span>
    <span class="hero-stage__star hero-stage__star--three"></span>
    <span class="hero-stage__glow hero-stage__glow--one"></span>
    <span class="hero-stage__glow hero-stage__glow--two"></span>
    <div class="hero-stage__frame hero-stage__frame--back"></div>
    <div class="hero-stage__frame hero-stage__frame--mid"></div>
    <div class="hero-stage__frame hero-stage__frame--front">
      <div class="hero-stage__panel">
        <div class="hero-stage__panel-head">
          <span>Investor update</span>
          <span>Smart Deck</span>
        </div>
        <div class="hero-stage__panel-title">Investor<br />Update</div>
        <div class="hero-stage__bars">
          <i></i>
          <i></i>
          <i></i>
          <i></i>
          <i></i>
        </div>
        <div class="hero-stage__dial"></div>
        <div class="hero-stage__spark"></div>
      </div>
    </div>
    <div class="hero-stage__badge hero-stage__badge--left">
      <span>Deck</span>
      <strong>{deckCount}</strong>
    </div>
    <div class="hero-stage__badge hero-stage__badge--right">
      <span>Ready</span>
      <strong>{readyDeckCount}</strong>
    </div>
  </div>

  <div class="hero-stage__tracks">
    {#each previewRows as row}
      <div class="hero-stage__track">
        <span>{row.label}</span>
        <p>{row.copy}</p>
      </div>
    {/each}
  </div>

  <div class="hero-stage__signals">
    <span class="pill">Decks: {deckCount}</span>
    <span class="pill">Ready: {readyDeckCount}</span>
    <span class="pill">Exports: {exportCount}</span>
  </div>

  {#if recentDecks.length > 0}
    <div class="hero-stage__history">
      <div class="hero-stage__history-label">Recent decks</div>
      <ul>
        {#each recentDecks.slice(0, 3) as deck}
          <li>
            <span>{deck.title}</span>
            <small>{deck.status}</small>
          </li>
        {/each}
      </ul>
    </div>
  {/if}
</aside>

<style>
  .hero-stage {
    display: grid;
    gap: 0.95rem;
    align-content: start;
    padding: 1.15rem;
    border-color: color-mix(in srgb, var(--line-strong) 42%, var(--line));
    background:
      radial-gradient(circle at top right, color-mix(in srgb, var(--accent) 15%, transparent), transparent 40%),
      linear-gradient(180deg, color-mix(in srgb, var(--surface-strong) 84%, transparent), color-mix(in srgb, var(--surface) 96%, transparent));
    min-width: 0;
  }

  .hero-stage__top {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 0.75rem;
    min-width: 0;
  }

  .hero-stage__eyebrow {
    text-transform: uppercase;
    letter-spacing: 0.14em;
    font-size: 0.76rem;
    color: var(--accent);
  }

  .hero-stage__title {
    margin: 0.35rem 0 0;
    min-width: 0;
    overflow-wrap: anywhere;
    font-size: clamp(1.45rem, 2.7vw, 2rem);
    line-height: 1.05;
    letter-spacing: -0.04em;
  }

  .hero-stage__chip {
    display: inline-flex;
    align-items: center;
    min-height: 2rem;
    padding: 0 0.8rem;
    border-radius: 999px;
    border: 1px solid color-mix(in srgb, var(--line-strong) 36%, var(--line));
    background: var(--surface-chip);
    color: var(--ink-soft);
    font-size: 0.74rem;
    white-space: nowrap;
  }

  .hero-stage__notice {
    display: grid;
    gap: 0.25rem;
    padding: 0.85rem 0.95rem;
    border-radius: 16px;
    border: 1px solid color-mix(in srgb, var(--accent) 22%, var(--line));
    background:
      linear-gradient(180deg, color-mix(in srgb, var(--accent-soft) 36%, transparent), transparent),
      color-mix(in srgb, var(--surface-soft) 88%, transparent);
  }

  .hero-stage__notice strong {
    color: var(--ink-strong);
    font-size: 0.94rem;
  }

  .hero-stage__notice p {
    margin: 0;
    color: var(--muted);
    line-height: 1.55;
    font-size: 0.92rem;
  }

  .hero-stage__art {
    position: relative;
    height: clamp(16rem, 25vw, 21rem);
    border-radius: 24px;
    border: 1px solid color-mix(in srgb, var(--line-strong) 42%, var(--line));
    background:
      radial-gradient(circle at 18% 20%, color-mix(in srgb, var(--accent-soft) 58%, transparent), transparent 24%),
      radial-gradient(circle at 78% 28%, color-mix(in srgb, var(--accent-2) 26%, transparent), transparent 24%),
      linear-gradient(180deg, rgba(14, 20, 38, 0.94), rgba(11, 15, 31, 0.98));
    overflow: hidden;
  }

  .hero-stage__glow {
    position: absolute;
    border-radius: 999px;
    filter: blur(12px);
    pointer-events: none;
  }

  .hero-stage__ring,
  .hero-stage__star {
    position: absolute;
    pointer-events: none;
  }

  .hero-stage__ring {
    border-radius: 999px;
    border: 1px solid rgba(98, 124, 255, 0.14);
  }

  .hero-stage__ring--one {
    width: 15rem;
    height: 15rem;
    right: 1rem;
    top: 2rem;
  }

  .hero-stage__ring--two {
    width: 11rem;
    height: 11rem;
    right: 3rem;
    top: 4rem;
  }

  .hero-stage__ring--three {
    width: 7rem;
    height: 7rem;
    right: 5rem;
    top: 6rem;
  }

  .hero-stage__star {
    width: 0.22rem;
    height: 0.22rem;
    border-radius: 999px;
    background: rgba(210, 223, 255, 0.85);
    box-shadow: 0 0 12px rgba(124, 152, 255, 0.55);
  }

  .hero-stage__star--one {
    top: 2.2rem;
    left: 18%;
  }

  .hero-stage__star--two {
    top: 5rem;
    right: 14%;
  }

  .hero-stage__star--three {
    bottom: 3rem;
    right: 22%;
  }

  .hero-stage__glow--one {
    left: -1.5rem;
    top: 1.8rem;
    width: 9rem;
    height: 9rem;
    background: rgba(74, 118, 255, 0.22);
  }

  .hero-stage__glow--two {
    right: -1rem;
    bottom: 1rem;
    width: 10rem;
    height: 10rem;
    background: rgba(255, 66, 160, 0.16);
  }

  .hero-stage__frame {
    position: absolute;
    inset: auto;
    border-radius: 20px;
    border: 1px solid rgba(150, 169, 255, 0.18);
    background: rgba(20, 28, 52, 0.72);
    box-shadow: 0 24px 52px rgba(3, 8, 28, 0.32);
  }

  .hero-stage__frame--back {
    top: 2rem;
    right: 3.2rem;
    width: 60%;
    height: 62%;
    transform: rotate(-6deg);
    opacity: 0.7;
  }

  .hero-stage__frame--mid {
    top: 3.7rem;
    right: 1.2rem;
    width: 54%;
    height: 58%;
    transform: rotate(1deg);
    opacity: 0.9;
  }

  .hero-stage__frame--front {
    left: 1.25rem;
    bottom: 1.2rem;
    width: 62%;
    height: 64%;
    padding: 1rem;
    background:
      radial-gradient(circle at top left, rgba(108, 148, 255, 0.2), transparent 34%),
      linear-gradient(180deg, rgba(22, 31, 62, 0.96), rgba(12, 18, 39, 0.98));
  }

  .hero-stage__panel {
    position: relative;
    display: grid;
    gap: 0.8rem;
    width: 100%;
    height: 100%;
  }

  .hero-stage__panel-title {
    color: rgba(236, 242, 255, 0.94);
    font-size: 2rem;
    line-height: 1.02;
    letter-spacing: -0.05em;
    max-width: 5ch;
  }

  .hero-stage__panel-head {
    display: flex;
    justify-content: space-between;
    gap: 0.75rem;
    color: rgba(230, 237, 255, 0.85);
    text-transform: uppercase;
    letter-spacing: 0.12em;
    font-size: 0.7rem;
  }

  .hero-stage__bars {
    display: flex;
    align-items: end;
    gap: 0.45rem;
    height: 4.5rem;
    padding-top: 0.25rem;
  }

  .hero-stage__bars i {
    flex: 1 1 0;
    border-radius: 999px 999px 6px 6px;
    background: linear-gradient(180deg, rgba(92, 110, 255, 0.98), rgba(188, 85, 216, 0.96));
    box-shadow: 0 0 18px rgba(114, 107, 255, 0.2);
  }

  .hero-stage__bars i:nth-child(1) {
    height: 42%;
  }

  .hero-stage__bars i:nth-child(2) {
    height: 62%;
  }

  .hero-stage__bars i:nth-child(3) {
    height: 78%;
  }

  .hero-stage__bars i:nth-child(4) {
    height: 54%;
  }

  .hero-stage__bars i:nth-child(5) {
    height: 86%;
  }

  .hero-stage__dial {
    position: absolute;
    right: 0.2rem;
    bottom: 0.4rem;
    width: 5.2rem;
    height: 5.2rem;
    border-radius: 50%;
    background:
      radial-gradient(circle at 50% 50%, rgba(65, 75, 255, 0.3), rgba(65, 75, 255, 0) 58%),
      conic-gradient(from 0deg, rgba(111, 139, 255, 0.92), rgba(199, 88, 255, 0.86), rgba(96, 197, 255, 0.9), rgba(111, 139, 255, 0.92));
    box-shadow: inset 0 0 0 10px rgba(16, 22, 42, 0.96);
  }

  .hero-stage__dial::after {
    content: '';
    position: absolute;
    inset: 1rem;
    border-radius: 50%;
    background:
      radial-gradient(circle at 30% 30%, rgba(255, 255, 255, 0.22), transparent 38%),
      rgba(12, 18, 39, 0.94);
  }

  .hero-stage__spark {
    position: absolute;
    left: 1rem;
    bottom: 1rem;
    width: 40%;
    height: 0.8rem;
    border-radius: 999px;
    background: linear-gradient(90deg, rgba(108, 131, 255, 0.95), rgba(213, 82, 203, 0.92));
    box-shadow: 0 0 18px rgba(116, 104, 255, 0.2);
  }

  .hero-stage__badge {
    position: absolute;
    display: grid;
    gap: 0.12rem;
    padding: 0.7rem 0.8rem;
    border-radius: 18px;
    border: 1px solid rgba(155, 171, 255, 0.2);
    background: rgba(13, 19, 37, 0.8);
    backdrop-filter: blur(12px);
    min-width: 5rem;
  }

  .hero-stage__badge span {
    color: rgba(214, 225, 255, 0.7);
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.14em;
  }

  .hero-stage__badge strong {
    font-size: 1.5rem;
    line-height: 1;
    letter-spacing: -0.04em;
  }

  .hero-stage__badge--left {
    left: 1rem;
    top: 5.2rem;
  }

  .hero-stage__badge--right {
    right: 1rem;
    bottom: 2.4rem;
  }

  .hero-stage__tracks {
    display: grid;
    gap: 0.7rem;
  }

  .hero-stage__track {
    display: grid;
    gap: 0.25rem;
    padding: 0.85rem 0.95rem;
    border-radius: 18px;
    border: 1px solid color-mix(in srgb, var(--line) 92%, transparent);
    background: color-mix(in srgb, var(--surface-soft) 85%, transparent);
  }

  .hero-stage__track span,
  .hero-stage__history-label {
    color: var(--ink-soft);
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.12em;
  }

  .hero-stage__track p {
    margin: 0;
    color: var(--muted);
    line-height: 1.5;
    min-width: 0;
    overflow-wrap: anywhere;
  }

  .hero-stage__signals {
    display: flex;
    flex-wrap: wrap;
    gap: 0.55rem;
  }

  .hero-stage__history {
    display: grid;
    gap: 0.55rem;
    padding-top: 0.1rem;
  }

  .hero-stage__history ul {
    display: grid;
    gap: 0.5rem;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .hero-stage__history li {
    display: flex;
    justify-content: space-between;
    gap: 0.75rem;
    padding: 0.8rem 0.9rem;
    border-radius: 14px;
    border: 1px solid var(--line);
    background: color-mix(in srgb, var(--surface-muted) 90%, transparent);
  }

  .hero-stage__history span {
    min-width: 0;
    overflow-wrap: anywhere;
    color: var(--ink);
  }

  .hero-stage__history small {
    color: var(--ink-soft);
    text-transform: capitalize;
    white-space: nowrap;
  }

  @media (max-width: 760px) {
    .hero-stage {
      padding: 1rem;
    }

    .hero-stage__art {
      height: 18rem;
    }

    .hero-stage__frame--back {
      right: 2.4rem;
    }

    .hero-stage__frame--mid {
      right: 1rem;
    }

    .hero-stage__frame--front {
      width: 70%;
    }

    .hero-stage__badge--left {
      top: 4.8rem;
    }
  }
</style>
