<script lang="ts">
  interface Props {
    audience: string | null;
    deckType: string;
    goal: string;
    onConfigureProvider?: () => void;
  }
  let { audience, deckType, goal, onConfigureProvider }: Props = $props();
</script>

<section class="tool-panel">
  <header><span>Settings</span><h2>Deck configuration</h2><p>Generation preferences are saved automatically from Ask AI.</p></header>
  <dl><div><dt>Audience</dt><dd>{audience ?? 'Not set'}</dd></div><div><dt>Deck type</dt><dd>{deckType.replaceAll('_', ' ')}</dd></div><div><dt>Goal</dt><dd>{goal.replaceAll('_', ' ')}</dd></div></dl>
  <button type="button" onclick={() => onConfigureProvider?.()}>Manage OpenAI key and model</button>
  <a href="/settings">Open account settings</a>
  <small>API keys are verified and encrypted. Only masked configuration status is returned to the browser.</small>
</section>

<style>
  .tool-panel { display: grid; gap: .8rem; }
  header { display: grid; gap: .35rem; }
  header > span { color: #38bdf8; font-size: .72rem; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
  h2, p, dl { margin: 0; }
  p, small { color: #94a3b8; line-height: 1.45; }
  dl { display: grid; gap: .55rem; }
  dl div { border: 1px solid rgba(255,255,255,.08); border-radius: 10px; padding: .65rem; background: rgba(15,23,42,.75); }
  dt { color: #94a3b8; font-size: .72rem; }
  dd { margin: .2rem 0 0; color: #f8fafc; text-transform: capitalize; }
  button, a { min-height: 42px; display: flex; align-items: center; border-radius: 10px; padding: .7rem; text-decoration: none; font: inherit; }
  button { border: 0; background: linear-gradient(135deg,#7c3aed,#0ea5e9); color: white; font-weight: 800; cursor: pointer; }
  a { border: 1px solid rgba(255,255,255,.1); color: #c4b5fd; }
</style>
