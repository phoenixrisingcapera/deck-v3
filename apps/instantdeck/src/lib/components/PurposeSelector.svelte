<script lang="ts">
  interface Props {
    value?: string;
  }

  const purposes = [
    'Series A diligence memo prep',
    'Investment committee update',
    'Strategic partnership review',
    'Board review',
    'M&A buyer screening'
  ];

  // The intake flow binds this field from parent pages, so the prop must stay bindable.
  let { value = $bindable(purposes[0]) }: Props = $props();
</script>

<label class="selector">
  <span>Purpose</span>
  <select name="purpose" bind:value>
    {#each purposes as purpose}
      <option value={purpose}>{purpose}</option>
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
