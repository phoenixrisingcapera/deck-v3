<script lang="ts">
  import RiskBadge from '$components/RiskBadge.svelte';

  type Panel = 'overview' | 'claims' | 'domains' | 'risks';
  type RecordValue = Record<string, unknown>;

  interface Props {
    workspace?: RecordValue | null;
    activePanel?: Panel;
  }

  let { workspace = null, activePanel = 'overview' }: Props = $props();
  let panel = $state<Panel>('overview');

  const summary = $derived((workspace?.summary ?? null) as RecordValue | null);
  const claims = $derived((Array.isArray(workspace?.claims) ? workspace.claims : []) as RecordValue[]);
  const domains = $derived((Array.isArray(workspace?.domains) ? workspace.domains : []) as RecordValue[]);
  const risks = $derived(
    (Array.isArray(workspace?.riskRegister)
      ? workspace.riskRegister
      : Array.isArray(workspace?.risk_register)
        ? workspace.risk_register
        : Array.isArray(workspace?.risks)
          ? workspace.risks
          : []) as RecordValue[]
  );

  function text(record: RecordValue, ...keys: string[]) {
    for (const key of keys) {
      const value = record[key];
      if (typeof value === 'string' && value.trim()) return value;
    }
    return '';
  }

  function number(record: RecordValue, ...keys: string[]) {
    for (const key of keys) {
      const value = Number(record[key]);
      if (Number.isFinite(value)) return value;
    }
    return 0;
  }

  function strings(record: RecordValue, ...keys: string[]) {
    for (const key of keys) {
      const value = record[key];
      if (Array.isArray(value)) return value.map(String);
    }
    return [];
  }

  $effect(() => {
    panel = activePanel;
  });
</script>

<aside class="analysis-panel" aria-label="Diligence analysis workspace">
  <nav class="analysis-tabs" aria-label="Diligence analysis sections">
    <button class:active={panel === 'overview'} type="button" onclick={() => (panel = 'overview')}>Overview</button>
    <button class:active={panel === 'claims'} type="button" onclick={() => (panel = 'claims')}>Findings</button>
    <button class:active={panel === 'domains'} type="button" onclick={() => (panel = 'domains')}>Domains</button>
    <button class:active={panel === 'risks'} type="button" onclick={() => (panel = 'risks')}>Risks</button>
  </nav>

  <div class="analysis-scroll">
    {#if workspace?.status === 'unavailable'}
      <p class="empty">{text(workspace, 'message') || 'Due diligence analysis is temporarily unavailable.'}</p>
    {:else if panel === 'overview'}
      {#if summary}
        <div class="stat-grid">
          <article><span>Investment readiness</span><strong>{number(summary, 'investment_readiness_score')} / 100</strong></article>
          <article><span>Evidence quality</span><strong>{text(summary, 'evidence_quality') || 'Not available'}</strong></article>
          <article><span>Market claim risk</span><strong>{text(summary, 'market_claim_risk') || 'Not available'}</strong></article>
          <article><span>IC readiness</span><strong>{text(summary, 'ic_readiness') || 'Not available'}</strong></article>
          <article><span>LP suitability</span><strong>{text(summary, 'lp_suitability') || 'Not available'}</strong></article>
        </div>
      {:else}
        <p class="empty">No saved diligence overview is available yet.</p>
      {/if}
    {:else if panel === 'claims'}
      <section class="cards">
        <header><h2>Findings</h2><span>{claims.length}</span></header>
        {#each claims as claim}
          <article class="card">
            <div class="card-head">
              <RiskBadge level={text(claim, 'riskLevel', 'risk_level') || 'low'} />
              <span>{text(claim, 'claimType', 'claim_type') || 'finding'}</span>
              <small>{Math.round(number(claim, 'confidence') * 100)}% confidence</small>
            </div>
            <p>{text(claim, 'claimText', 'claim_text')}</p>
            <small>Evidence: {text(claim, 'evidenceStatus', 'evidence_status') || 'unknown'} · Action: {text(claim, 'recommendedAction', 'recommended_action') || 'review'}</small>
          </article>
        {:else}
          <p class="empty">No saved findings are available.</p>
        {/each}
      </section>
    {:else if panel === 'domains'}
      <section class="cards">
        <header><h2>Domains</h2><span>{domains.length}</span></header>
        {#each domains as domain}
          <article class="card">
            <div class="card-head"><strong>{text(domain, 'label', 'key')}</strong><span>{Math.round(number(domain, 'score'))} / 100</span></div>
            <small>{text(domain, 'status') || 'Not scored'}</small>
            {#if strings(domain, 'findings').length}<ul>{#each strings(domain, 'findings') as finding}<li>{finding}</li>{/each}</ul>{/if}
          </article>
        {:else}
          <p class="empty">No saved domain analysis is available.</p>
        {/each}
      </section>
    {:else}
      <section class="cards">
        <header><h2>Risk register</h2><span>{risks.length}</span></header>
        {#each risks as risk}
          <article class="card">
            <div class="card-head"><strong>{text(risk, 'risk')}</strong><span>{text(risk, 'severity') || 'unknown'}</span></div>
            {#if text(risk, 'category')}<small>{text(risk, 'category')}</small>{/if}
            {#if text(risk, 'evidence')}<p><strong>Evidence:</strong> {text(risk, 'evidence')}</p>{/if}
            {#if text(risk, 'mitigation')}<p><strong>Mitigation:</strong> {text(risk, 'mitigation')}</p>{/if}
          </article>
        {:else}
          <p class="empty">No saved risks are available.</p>
        {/each}
      </section>
    {/if}
  </div>
</aside>

<style>
  .analysis-panel { min-width: 0; max-height: calc(100vh - 11rem); display: grid; grid-template-rows: auto minmax(0, 1fr); overflow: hidden; border: 1px solid var(--border); border-radius: .85rem; background: rgba(7, 11, 22, .92); }
  .analysis-tabs { display: grid; grid-template-columns: repeat(4, 1fr); border-bottom: 1px solid var(--border); }
  .analysis-tabs button { border: 0; border-bottom: 2px solid transparent; padding: .8rem .45rem; background: transparent; color: var(--muted); font: inherit; font-size: .76rem; font-weight: 700; cursor: pointer; }
  .analysis-tabs button.active { color: #f59e0b; border-bottom-color: #f59e0b; }
  .analysis-tabs button:focus-visible { outline: 2px solid #f59e0b; outline-offset: -2px; }
  .analysis-scroll { min-height: 0; overflow-y: auto; padding: .9rem; }
  .stat-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: .65rem; }
  .stat-grid article, .card { display: grid; gap: .4rem; padding: .8rem; border: 1px solid var(--border); border-radius: .7rem; background: rgba(15, 23, 42, .78); }
  .stat-grid span, small, .empty { color: var(--muted); }
  .stat-grid strong { color: #f8fafc; }
  .cards { display: grid; gap: .7rem; }
  .cards > header, .card-head { display: flex; align-items: center; justify-content: space-between; gap: .6rem; }
  .cards h2, .card p, .empty { margin: 0; }
  .card p { line-height: 1.45; }
  .card ul { margin: 0; padding-left: 1rem; }
  @media (max-width: 980px) { .analysis-panel { max-height: none; } }
  @media (max-width: 560px) { .analysis-tabs { grid-template-columns: repeat(2, 1fr); } .stat-grid { grid-template-columns: 1fr; } }
</style>
