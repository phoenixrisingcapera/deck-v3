<script lang="ts">
  interface Props {
    value?: string;
  }

  const stages = [
    { value: 'initial_review', label: 'Initial review' },
    { value: 'partner_review', label: 'Partner review' },
    { value: 'ic_review', label: 'IC review' },
    { value: 'deep_diligence', label: 'Deep diligence' },
    { value: 'final_approval', label: 'Final approval' }
  ];

  let { value = 'initial_review' }: Props = $props();
</script>

<label class="selector">
  <span>Diligence stage</span>
  <select name="diligenceStage" bind:value>
    {#each stages as stage}
      <option value={stage.value}>{stage.label}</option>
    {/each}
  </select>
</label>

<style>
  .selector {
    display: grid;
    gap: 0.45rem;
  }

  select {
    border-radius: var(--radius-sm);
    border: 1px solid var(--line-strong);
    background: rgba(255, 255, 255, 0.82);
    padding: 0.8rem 0.9rem;
  }
</style>
