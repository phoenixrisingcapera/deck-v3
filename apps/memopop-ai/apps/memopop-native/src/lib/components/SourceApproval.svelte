<script lang="ts">
  import { onDestroy } from 'svelte';
  import { openUrl } from '@tauri-apps/plugin-opener';
  import { WebviewWindow } from '@tauri-apps/api/webviewWindow';
  import { flow } from '$lib/stores/flow.svelte';
  import { sources, DENY_REASONS } from '$lib/stores/sources.svelte';

  /** One reused window — clicking through 79 candidates must not open 79. */
  const QUICK_LOOK = 'quick-look';

  interface Props {
    firm: string;
    deal: string;
    /**
     * What "continue" means depends on where this was opened from. In the
     * create-deal flow it advances to ready_to_run; from an existing deal's
     * workspace it just closes the panel. Defaults to the flow behavior.
     */
    onDone?: () => void;
    /** The create-deal flow offers "run unconstrained"; a saved deal doesn't. */
    showSkip?: boolean;
    /** Shown above the heading for context. */
    onBack?: () => void;
  }

  let {
    firm,
    deal,
    onDone = () => flow.sourcesSettled(),
    showSkip = true,
    onBack = () => flow.editDeal(),
  }: Props = $props();

  let pasteUrl = $state('');
  let denyingUrl = $state<string | null>(null);
  let loadedFor = $state<string | null>(null);

  // Load once per (firm, deal). $effect rather than onMount because the
  // stage can be re-entered with a different deal without remounting.
  $effect(() => {
    const key = `${firm}/${deal}`;
    if (!firm || !deal || loadedFor === key) return;
    loadedFor = key;
    sources.reset();
    sources.load(firm, deal);
  });

  async function back() {
    await sources.flush();   // never lose a partial session to navigation
    onBack();
  }

  function savedAgo(iso: string | null): string {
    if (!iso) return '';
    const secs = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
    if (secs < 5) return 'just now';
    if (secs < 60) return `${secs}s ago`;
    return `${Math.round(secs / 60)}m ago`;
  }

  // Re-render the "saved Ns ago" label without touching the store.
  let tick = $state(0);
  $effect(() => {
    const id = setInterval(() => (tick += 1), 5000);
    return () => clearInterval(id);
  });

  /**
   * Open a source in a reusable in-app window.
   *
   * Deliberately NOT an iframe. 14 of the first 24 real ImmuneCo sources send
   * X-Frame-Options — nejm.org, thelancet.com, science.org, pmc.ncbi.nlm.nih.gov,
   * who.int, epa.gov, forbes.com among them — so a majority would render as a
   * blank box, and cross-origin that failure is silent (no usable onerror, no
   * readable contentDocument), meaning the UI could not even admit it failed.
   *
   * A second webview is a *top-level navigation*, so frame policy never
   * applies: 100% of sources render. WebKit is already resident, so there is
   * no browser cold start either — which is the point, since handing off to a
   * browser carrying a day of tabs is what made this slow.
   *
   * Close-and-recreate rather than re-navigate: Tauri 2 has no clean
   * "point this webview somewhere else" call, and recreating avoids carrying
   * history or scroll state between unrelated sources.
   */
  async function quickLook(url: string) {
    try {
      const existing = await WebviewWindow.getByLabel(QUICK_LOOK);
      if (existing) await existing.close();

      const w = new WebviewWindow(QUICK_LOOK, {
        url,
        title: `Quick look — ${hostOf(url)}`,
        width: 1100,
        height: 900,
        center: true,
      });
      // Creation is async on the Rust side; a failure arrives as an event
      // rather than a rejected promise, so the fallback lives here.
      w.once('tauri://error', () => void openExternal(url));
    } catch {
      // Not in Tauri (browser dev mode), or window creation is unavailable.
      await openExternal(url);
    }
  }

  /** The escape hatch: the analyst's real browser, with their logins. */
  async function openExternal(url: string) {
    try {
      await openUrl(url);
    } catch {
      // Opener unavailable (browser dev mode) — fall back to a new tab.
      window.open(url, '_blank', 'noopener');
    }
  }

  function addPasted(e: Event) {
    e.preventDefault();
    const url = pasteUrl.trim();
    if (!url) return;
    if (!/^https?:\/\//i.test(url)) {
      sources.error = 'Paste a full http(s) URL.';
      return;
    }
    if (!sources.add(url)) {
      sources.error = 'That URL is already in the list.';
      return;
    }
    sources.error = null;
    pasteUrl = '';
  }

  function deny(url: string, reason: string) {
    sources.setVerdict(url, 'rejected', reason);
    denyingUrl = null;
  }

  async function approveAndContinue() {
    const ok = await sources.approveAndCommit();
    if (ok) onDone();
  }

  function skip() {
    // Explicitly running unconstrained. The deal stays non-codified, so the
    // membership gate does not apply — same behavior as before this surface
    // existed. Offered because a first run with no curated sources is a
    // legitimate thing to want.
    onDone();
  }

  function jumpToFirstUnreviewed() {
    const row = sources.rows[sources.firstUnreviewedIndex];
    if (!row) return;
    document
      .querySelector(`[data-url="${CSS.escape(row.url)}"]`)
      ?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }

  function hostOf(url: string): string {
    try {
      return new URL(url).hostname.replace(/^www\./, '');
    } catch {
      return url;
    }
  }

  // A quick-look window outliving the surface that opened it is confusing —
  // and on a second visit it would sit there showing a source from the
  // previous deal.
  onDestroy(() => {
    void sources.flush();
    void WebviewWindow.getByLabel(QUICK_LOOK)
      .then((w) => w?.close())
      .catch(() => {});
  });
</script>

<div class="wrap">
  <header class="head">
    <div>
      <span class="eyebrow">{firm} · {deal}</span>
      <h2>Approve the sources this memo may cite</h2>
      <p class="lede">
        Everything you approve becomes the corpus the writer is allowed to
        cite. Anything else gets stripped from the draft, even if the link
        works. Candidates come from a search engine — never from a model.
      </p>
    </div>
    <button class="ghost" onclick={back}>← Back</button>
  </header>

  {#if sources.error}
    <p class="error" role="alert">{sources.error}</p>
  {/if}

  <div class="tally">
    <span class="pill approved">{sources.approvedCount} approved</span>
    <span class="pill rejected">{sources.rejectedCount} denied</span>
    {#if sources.unreviewedCount > 0}
      <span class="pill unreviewed">{sources.unreviewedCount} unreviewed</span>
      <button class="link" onclick={() => sources.approveAllUnreviewed()}>
        approve all unreviewed
      </button>
    {/if}
    {#if sources.origin === 'aggregated'}
      <span class="origin">from the aggregated worksheet</span>
    {/if}

    <span class="spacer"></span>

    <!-- Whether the work is safe should never be a guess on a list this
         long. Reviewing 80 sources takes more than one sitting. -->
    {#key tick}
      <span class="savestate {sources.saveState}">
        {#if sources.saveState === 'saving'}
          Saving…
        {:else if sources.saveState === 'unsaved'}
          Unsaved changes
        {:else if sources.saveState === 'saved'}
          ✓ Saved {savedAgo(sources.lastSavedAt)}
        {:else}
          Autosaves as you go
        {/if}
      </span>
    {/key}
  </div>

  {#if sources.rows.length > 0}
    <div class="progress" role="status">
      <div class="bar">
        <div
          class="fill"
          style="width: {Math.round((sources.reviewedCount / sources.rows.length) * 100)}%"
        ></div>
      </div>
      <span class="count">
        {sources.reviewedCount} of {sources.rows.length} reviewed
      </span>
      {#if sources.firstUnreviewedIndex > 0}
        <button class="link" onclick={jumpToFirstUnreviewed}>resume where you left off →</button>
      {/if}
    </div>
  {/if}

  {#if sources.autosaveError}
    <p class="error" role="alert">
      Autosave failed — your work is still only in this window.
      {sources.autosaveError}
    </p>
  {/if}

  <!-- Add a link: the action reached for most often, so it stays one
       field and one button at the top rather than buried in a panel. -->
  <form class="paste" onsubmit={addPasted}>
    <input
      type="url"
      bind:value={pasteUrl}
      placeholder="Paste a source URL you already trust…"
      aria-label="Add a source by URL"
    />
    <button type="submit" disabled={!pasteUrl.trim()}>Add</button>
  </form>

  <section class="list">
    {#if sources.loading}
      <p class="muted">Loading sources…</p>
    {:else if sources.rows.length === 0}
      <p class="muted">
        No sources yet. Paste a link above, or search below to find some.
      </p>
    {/if}

    {#each sources.rows as row (row.url)}
      <article class="row {row.verdict}" data-url={row.url}>
        <div class="main">
          <div class="title-line">
            <button
              class="titlebtn"
              onclick={() => quickLook(row.url)}
              title="Quick look (same as ⧉ Look)"
            >
              {row.title || hostOf(row.url)}
            </button>
            {#if sources.fetchingMeta.has(row.url)}
              <span class="fetching" title="Looking up the title">…</span>
            {/if}
            {#if row.verdict === 'approved'}<span class="tick">✓</span>{/if}
            {#if row.verdict === 'rejected'}<span class="cross">✕</span>{/if}
          </div>
          <div class="meta">
            <span class="host">{hostOf(row.url)}</span>
            {#if row.publisher}<span>· {row.publisher}</span>{/if}
            {#if row.published_date}<span class="pubdate">· {row.published_date}</span>{/if}
            {#if row.verdict_reason}<span class="reason">· {row.verdict_reason}</span>{/if}
            <!-- The validator's reachability result, shown as context but
                 never counted as approval. That conflation is the bug this
                 whole feature exists to fix. -->
            {#if row.machineVerdict}<span class="machine">· checked: {row.machineVerdict}</span>{/if}
          </div>
        </div>

        <div class="actions">
          <button
            class={row.verdict === 'approved' ? 'act on' : 'act'}
            onclick={() => sources.setVerdict(row.url, 'approved')}
          >Approve</button>

          <button
            class={row.verdict === 'rejected' ? 'act off' : 'act'}
            onclick={() => (denyingUrl = denyingUrl === row.url ? null : row.url)}
          >Deny</button>

          <button
            class="act"
            disabled={sources.busyUrl === row.url}
            onclick={() => sources.recover(row.url)}
            title="Search for the real URL behind this citation"
          >Re-search</button>

          <button
            class="act"
            disabled={sources.busyUrl === row.url}
            onclick={() => sources.preview(row.url)}
          >{sources.previews[row.url] ? 'Hide' : 'Preview'}</button>

          <!-- Both open-modes get a visible control. Title-click is the
               same as Look, but a bare underlined title is indistinguishable
               from "opens in browser" — an affordance you find by accident
               is not an affordance. -->
          <button
            class="act"
            onclick={() => quickLook(row.url)}
            title="Quick look — renders here, instantly, even on sites that block embedding"
          >⧉ Look</button>

          <!-- The real browser, with the analyst's logins and paywall
               subscriptions. Quick look can't have those. -->
          <button
            class="act"
            onclick={() => openExternal(row.url)}
            title="Open in your default browser"
          >↗</button>
        </div>

        {#if denyingUrl === row.url}
          <div class="reasons">
            <span class="muted">Why?</span>
            {#each DENY_REASONS as reason}
              <button class="chip" onclick={() => deny(row.url, reason)}>{reason}</button>
            {/each}
          </div>
        {/if}

        {#if sources.recoveries[row.url]}
          {@const rec = sources.recoveries[row.url]}
          <div class="recovery">
            {#if 'failed' in rec}
              <span class="muted">Re-search: {rec.failed}</span>
              <button class="chip" onclick={() => sources.dismissRecovery(row.url)}>dismiss</button>
            {:else}
              <div>
                <strong>Found:</strong> {rec.matched_title}
                <span class="muted">
                  · {Math.round(rec.jaccard * 100)}% title match · via {rec.via_provider}
                </span>
                <div class="recurl">{rec.recovered_url}</div>
              </div>
              <div class="recact">
                <button class="chip" onclick={() => quickLook(rec.recovered_url)}>open</button>
                <button class="chip go" onclick={() => sources.acceptRecovery(row.url)}>
                  use this URL
                </button>
                <button class="chip" onclick={() => sources.dismissRecovery(row.url)}>dismiss</button>
              </div>
            {/if}
          </div>
        {/if}

        {#if sources.previews[row.url]}
          <pre class="preview">{sources.previews[row.url].slice(0, 4000)}</pre>
        {/if}
      </article>
    {/each}
  </section>

  <section class="search">
    <h3>Find more</h3>
    <div class="searchbar">
      <input
        type="search"
        bind:value={sources.query}
        placeholder="Search the web for sources…"
        onkeydown={(e) => e.key === 'Enter' && sources.search()}
      />
      <button onclick={() => sources.search()} disabled={sources.searching}>
        {sources.searching ? 'Searching…' : 'Search'}
      </button>
      <button class="ghost" onclick={() => sources.seedFromDeal()} disabled={sources.searching}>
        Suggest from deal
      </button>
    </div>

    {#if !sources.searchAvailable}
      <p class="muted">
        {sources.searchReason} — you can still paste links by hand.
      </p>
    {/if}

    {#each sources.candidates as c (c.url)}
      <article class="cand">
        <div class="main">
          <button class="titlebtn" onclick={() => quickLook(c.url)} title="Quick look">
            {c.title || hostOf(c.url)}
          </button>
          <div class="meta">
            <span class="host">{hostOf(c.url)}</span>
            {#if c.found_via}<span>· found via “{c.found_via}”</span>{/if}
            {#if c.known}<span class="known">· already in your list</span>{/if}
          </div>
          {#if c.content}<p class="snippet">{c.content.slice(0, 180)}</p>{/if}
        </div>
        <button
          class="act"
          disabled={sources.hasUrl(c.url)}
          onclick={() =>
            sources.add(c.url, { title: c.title, published_date: c.published_date ?? '' })}
        >{sources.hasUrl(c.url) ? 'Added' : 'Add'}</button>
      </article>
    {/each}
  </section>

  <footer class="foot">
    {#if showSkip}
      <button class="ghost" onclick={skip}>Skip — run unconstrained</button>
    {/if}
    <div class="spacer"></div>
    <button class="ghost" onclick={() => sources.saveDraft()} disabled={sources.saving} title="Take an explicit, backed-up checkpoint (autosave already keeps your work)">
      Checkpoint
    </button>
    <button
      class="primary"
      onclick={approveAndContinue}
      disabled={sources.saving || sources.approvedCount === 0}
    >
      {sources.saving ? 'Saving…' : `Approve ${sources.approvedCount} & continue →`}
    </button>
  </footer>
</div>

<style>
  /* Mode-agnostic by construction: neutral slate at low alpha reads correctly
     over either background, which is the same approach DealWorkspace's
     --ctl-* tokens take. Only genuinely semantic colors (approved green,
     denied red, links) need a dark override, at the bottom. */
  .wrap {
    --s-border: rgba(148, 163, 184, 0.25);
    --s-border-strong: rgba(148, 163, 184, 0.45);
    --s-surface: rgba(148, 163, 184, 0.06);
    --s-surface-hover: rgba(148, 163, 184, 0.14);
    --s-muted: #6b7280;
    --s-link: #1d4ed8;
    --s-radius: 10px;

    display: flex;
    flex-direction: column;
    gap: 1rem;
    padding: 1.5rem 2rem 2rem;
    max-width: 960px;
    margin: 0 auto;
    width: 100%;
    color: inherit;
  }

  .head {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 1rem;
  }
  .eyebrow {
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--s-muted);
  }
  h2 {
    margin: 0.25rem 0 0.35rem;
    font-size: 1.35rem;
  }
  .lede {
    margin: 0;
    color: var(--s-muted);
    font-size: 0.9rem;
    max-width: 62ch;
    line-height: 1.5;
  }

  .error {
    background: rgba(239, 68, 68, 0.12);
    border: 1px solid rgba(239, 68, 68, 0.4);
    color: #dc2626;
    padding: 0.6rem 0.8rem;
    border-radius: 8px;
    margin: 0;
    font-size: 0.85rem;
  }

  .tally {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
    font-size: 0.8rem;
  }
  .pill {
    padding: 0.15rem 0.55rem;
    border-radius: 999px;
    font-weight: 600;
  }
  .pill.approved {
    background: rgba(22, 163, 74, 0.16);
    color: #16a34a;
  }
  .pill.rejected {
    background: rgba(220, 38, 38, 0.16);
    color: #ef4444;
  }
  .pill.unreviewed {
    background: rgba(217, 119, 6, 0.18);
    color: #d97706;
  }
  .origin {
    color: var(--s-muted);
  }
  .tally .spacer { flex: 1; }

  .savestate {
    font-size: 0.78rem;
    color: var(--s-muted);
    white-space: nowrap;
  }
  .savestate.saved { color: #16a34a; }
  .savestate.unsaved { color: #d97706; }
  .savestate.saving { opacity: 0.7; }

  .progress {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    font-size: 0.78rem;
    color: var(--s-muted);
  }
  .progress .bar {
    flex: 1;
    height: 4px;
    border-radius: 999px;
    background: var(--s-surface-hover);
    overflow: hidden;
  }
  .progress .fill {
    height: 100%;
    background: #16a34a;
    transition: width 180ms ease-out;
  }
  .progress .count { white-space: nowrap; }

  /* Inputs must not assume a white page. */
  .paste,
  .searchbar {
    display: flex;
    gap: 0.5rem;
  }
  .paste input,
  .searchbar input {
    flex: 1;
    padding: 0.6rem 0.75rem;
    border: 1px solid var(--s-border);
    border-radius: 8px;
    font: inherit;
    font-size: 0.9rem;
    background: var(--s-surface);
    color: inherit;
  }
  .paste input::placeholder,
  .searchbar input::placeholder {
    color: var(--s-muted);
  }
  .paste input:focus,
  .searchbar input:focus {
    outline: none;
    border-color: var(--s-border-strong);
    background: var(--s-surface-hover);
  }

  .list,
  .search {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  h3 {
    margin: 0.75rem 0 0;
    font-size: 1rem;
  }

  .row,
  .cand {
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 0.5rem 1rem;
    padding: 0.7rem 0.85rem;
    border: 1px solid var(--s-border);
    border-radius: var(--s-radius);
    background: var(--s-surface);
    align-items: start;
  }
  .row.approved {
    border-left: 3px solid #16a34a;
  }
  .row.rejected {
    border-left: 3px solid #dc2626;
    opacity: 0.62;
  }

  .titlebtn {
    background: none;
    border: none;
    padding: 0;
    font: inherit;
    font-weight: 600;
    color: var(--s-link);
    text-align: left;
    cursor: pointer;
    text-decoration: underline;
    text-underline-offset: 2px;
  }
  .title-line {
    display: flex;
    align-items: center;
    gap: 0.4rem;
  }
  .tick {
    color: #16a34a;
    font-weight: 700;
  }
  .cross {
    color: #ef4444;
    font-weight: 700;
  }

  .meta {
    font-size: 0.78rem;
    color: var(--s-muted);
    display: flex;
    gap: 0.3rem;
    flex-wrap: wrap;
    margin-top: 0.15rem;
  }
  .host {
    font-weight: 500;
  }
  .reason {
    color: #ef4444;
  }
  .known {
    color: #d97706;
  }
  .fetching {
    color: var(--s-muted);
    font-size: 0.85rem;
    animation: pulse 1.2s ease-in-out infinite;
  }
  @keyframes pulse {
    0%, 100% { opacity: 0.35; }
    50% { opacity: 1; }
  }
  .pubdate { font-variant-numeric: tabular-nums; }

  .machine {
    color: var(--s-muted);
    font-style: italic;
    opacity: 0.8;
  }
  .snippet {
    margin: 0.35rem 0 0;
    font-size: 0.8rem;
    color: var(--s-muted);
    line-height: 1.4;
  }

  .actions {
    display: flex;
    gap: 0.35rem;
    flex-wrap: wrap;
    justify-content: flex-end;
  }
  .act {
    font-size: 0.78rem;
    padding: 0.3rem 0.6rem;
    border: 1px solid var(--s-border);
    background: transparent;
    color: inherit;
    border-radius: 6px;
    cursor: pointer;
    white-space: nowrap;
  }
  .act:hover:not(:disabled) {
    background: var(--s-surface-hover);
    border-color: var(--s-border-strong);
  }
  .act:disabled {
    opacity: 0.45;
    cursor: default;
  }
  .act.on {
    background: #16a34a;
    border-color: #16a34a;
    color: white;
  }
  .act.off {
    background: #dc2626;
    border-color: #dc2626;
    color: white;
  }

  .reasons,
  .recovery {
    grid-column: 1 / -1;
    display: flex;
    gap: 0.35rem;
    align-items: center;
    flex-wrap: wrap;
    padding-top: 0.5rem;
    border-top: 1px dashed var(--s-border);
    font-size: 0.8rem;
  }
  .recovery {
    justify-content: space-between;
  }
  .recact {
    display: flex;
    gap: 0.35rem;
  }
  .recurl {
    font-family: ui-monospace, monospace;
    font-size: 0.75rem;
    color: var(--s-muted);
    margin-top: 0.2rem;
    word-break: break-all;
  }
  .chip {
    font-size: 0.75rem;
    padding: 0.2rem 0.5rem;
    border: 1px solid var(--s-border);
    border-radius: 999px;
    background: transparent;
    color: inherit;
    cursor: pointer;
  }
  .chip:hover {
    background: var(--s-surface-hover);
  }
  .chip.go {
    background: #1d4ed8;
    border-color: #1d4ed8;
    color: white;
  }

  .preview {
    grid-column: 1 / -1;
    margin: 0.5rem 0 0;
    padding: 0.6rem;
    background: var(--s-surface-hover);
    border-radius: 6px;
    font-size: 0.75rem;
    max-height: 220px;
    overflow: auto;
    white-space: pre-wrap;
    color: inherit;
  }

  /* Sticky footer: a solid backdrop, not a white gradient — the gradient
     was the most obviously wrong thing in dark mode. */
  .foot {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.85rem 0 0.25rem;
    border-top: 1px solid var(--s-border);
    position: sticky;
    bottom: 0;
    background: inherit;
    backdrop-filter: blur(8px);
  }
  .spacer {
    flex: 1;
  }

  button.primary {
    background: linear-gradient(135deg, #7c3aed 0%, #db2777 100%);
    color: white;
    border: 1px solid transparent;
    padding: 0.6rem 1.1rem;
    border-radius: 8px;
    font: inherit;
    font-weight: 600;
    cursor: pointer;
  }
  button.primary:disabled {
    opacity: 0.35;
    cursor: default;
  }
  button.ghost,
  .paste button,
  .searchbar button {
    background: var(--s-surface);
    border: 1px solid var(--s-border);
    color: inherit;
    padding: 0.5rem 0.85rem;
    border-radius: 8px;
    cursor: pointer;
    font: inherit;
    font-size: 0.85rem;
  }
  button.ghost:hover:not(:disabled),
  .paste button:hover:not(:disabled),
  .searchbar button:hover:not(:disabled) {
    background: var(--s-surface-hover);
    border-color: var(--s-border-strong);
  }
  .paste button:disabled,
  .searchbar button:disabled {
    opacity: 0.45;
    cursor: default;
  }
  .link {
    background: none;
    border: none;
    color: var(--s-link);
    cursor: pointer;
    text-decoration: underline;
    font-size: 0.8rem;
    padding: 0;
    font-family: inherit;
  }
  .muted {
    color: var(--s-muted);
    font-size: 0.85rem;
    margin: 0;
  }

  @media (prefers-color-scheme: dark) {
    .wrap {
      /* Links and muted text are the only values that can't be expressed as
         a background-agnostic alpha — they need real contrast against
         #1c1c1e. Everything else above already adapts. */
      --s-link: #93c5fd;
      --s-muted: #9ca3af;
      --s-border: rgba(148, 163, 184, 0.2);
      --s-border-strong: rgba(148, 163, 184, 0.4);
    }
    .error {
      color: #fca5a5;
    }
    .chip.go {
      background: #3b82f6;
      border-color: #3b82f6;
    }
  }
</style>
