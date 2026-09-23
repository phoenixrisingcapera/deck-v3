<script lang="ts">
  import RiskBadge from '$components/RiskBadge.svelte';
  import type { AnalysisFinding } from '$types/domain';

  interface Props {
    finding: AnalysisFinding;
  }

  let { finding }: Props = $props();
</script>

<article class="finding-card">
  <div class="topline">
    <RiskBadge level={finding.severity} />
    <span class="pill">{finding.category}</span>
  </div>
  <h4>{finding.title}</h4>
  <p>{finding.detail}</p>
</article>

<style>
  .finding-card {
    border: 1px solid var(--line);
    border-radius: var(--radius-md);
    padding: 1rem;
    background: rgba(255, 255, 255, 0.03);
  }

  .topline {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  h4 {
    margin: 0.7rem 0 0.35rem;
  }

  p {
    margin: 0;
    color: var(--muted);
  }
</style>
