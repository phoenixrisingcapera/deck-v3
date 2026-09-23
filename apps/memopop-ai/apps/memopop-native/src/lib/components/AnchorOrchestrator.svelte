<script lang="ts">
  import { open } from '@tauri-apps/plugin-dialog';
  import { openUrl } from '@tauri-apps/plugin-opener';
  import { settings } from '$lib/stores/settings.svelte';

  const ORCHESTRATOR_REPO_URL = 'https://github.com/lossless-group/investment-memo-orchestrator';

  let pickError = $state<string | null>(null);

  async function openOrchestratorRepo() {
    await openUrl(ORCHESTRATOR_REPO_URL);
  }

  async function browse() {
    pickError = null;
    const selected = await open({
      directory: true,
      multiple: false,
      title: 'Select the memopop-orchestrator repo root',
    });
    if (typeof selected === 'string') {
      await settings.setRepoPath(selected);
    }
  }
</script>

<section class="anchor">
  <div class="hero">
    <div class="logo-wrap">
      <span class="logo-letter">M</span>
    </div>
    <h1>Welcome to MemoPop</h1>
    <p class="lede">
      AI-driven investment memos. To get started, point this app at the
      orchestrator repo on your machine.
    </p>
  </div>

  <div class="card">
    <h2>You'll need the orchestrator installed locally</h2>
    <p>
      MemoPop is the desktop frontend; the orchestrator is the Python engine
      that does the heavy lifting. You'll only do this once.
    </p>

    <ol class="steps">
      <li>
        <strong>Clone the repo</strong> from GitHub:
        <button type="button" class="link" onclick={openOrchestratorRepo}>
          github.com/lossless-group/investment-memo-orchestrator&nbsp;↗
        </button>
      </li>
      <li>
        <strong>Follow the README</strong> to install dependencies — or hand it
        to your AI assistant. Should be straightforward with a little patience.
      </li>
      <li>
        <strong>Click Browse</strong> below and point this app at the directory
        where you cloned the orchestrator.
      </li>
    </ol>

    <div class="action-row">
      <button type="button" class="primary" onclick={browse}>
        Browse for orchestrator…
      </button>
    </div>

    {#if pickError}
      <p class="error">{pickError}</p>
    {/if}
  </div>
</section>

<style>
  .anchor {
    max-width: 720px;
    margin: 4rem auto;
    padding: 0 1.5rem;
  }

  .hero {
    text-align: center;
    margin-bottom: 2.5rem;
  }

  .logo-wrap {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 56px;
    height: 56px;
    border-radius: 14px;
    background: linear-gradient(135deg, #5b21b6, #a855f7);
    margin-bottom: 1rem;
  }

  .logo-letter {
    color: white;
    font-weight: 700;
    font-size: 1.5rem;
  }

  h1 {
    font-size: 2rem;
    margin: 0 0 0.5rem;
  }

  .lede {
    font-size: 1.05rem;
    color: #6b7280;
    margin: 0;
  }

  .card {
    background: white;
    border: 1px solid #e5e5e5;
    border-radius: 12px;
    padding: 2rem;
  }

  h2 {
    font-size: 1.15rem;
    margin: 0 0 0.5rem;
  }

  .card > p {
    color: #6b7280;
    margin: 0 0 1.5rem;
  }

  .steps {
    margin: 0 0 1.5rem;
    padding-left: 1.25rem;
  }

  .steps li {
    margin-bottom: 0.6rem;
    line-height: 1.5;
  }

  .action-row {
    display: flex;
    justify-content: flex-start;
  }

  button.primary {
    padding: 0.6rem 1.2rem;
    border-radius: 8px;
    border: 1px solid transparent;
    background: #5b21b6;
    color: white;
    font: inherit;
    font-weight: 500;
    cursor: pointer;
  }

  button.primary:hover {
    background: #4c1d95;
  }

  button.link {
    background: transparent;
    border: none;
    padding: 0;
    color: #5b21b6;
    text-decoration: underline;
    text-underline-offset: 2px;
    font: inherit;
    cursor: pointer;
  }

  button.link:hover {
    color: #4c1d95;
  }

  .error {
    margin-top: 1rem;
    color: #c0392b;
    font-size: 0.9rem;
  }

  @media (prefers-color-scheme: dark) {
    .lede {
      color: #9ca3af;
    }

    .card {
      background: #2a2a2c;
      border-color: #3a3a3c;
    }

    .card > p {
      color: #9ca3af;
    }

    button.link {
      color: #c4b5fd;
    }

    button.link:hover {
      color: #ddd6fe;
    }
  }
</style>
