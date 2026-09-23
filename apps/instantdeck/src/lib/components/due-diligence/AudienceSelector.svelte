<script lang="ts">
  type AudienceOption = {
    value: string;
    label: string;
  };

  interface Props {
    label?: string;
    value?: string;
    options?: readonly AudienceOption[];
    disabled?: boolean;
    onChange?: (value: string) => void;
  }

  const audiences: AudienceOption[] = [
    { value: 'investment_committee', label: 'Investment Committee' },
    { value: 'seed_vc', label: 'Seed VC' },
    { value: 'series_a_vc', label: 'Series A VC' },
    { value: 'growth_equity', label: 'Growth Equity' },
    { value: 'lp', label: 'LP' },
    { value: 'strategic', label: 'Strategic Investor' }
  ];

  // The intake flow binds this field from parent pages, so the prop must stay bindable.
  let { label = 'Audience', value = $bindable('investment_committee'), options = audiences, disabled = false, onChange }: Props = $props();
</script>

<label class="selector">
  <span>{label}</span>
  <select
    name="audience"
    bind:value
    {disabled}
    onchange={(event) => onChange?.((event.currentTarget as HTMLSelectElement).value)}
  >
    {#each options as option}
      <option value={option.value}>{option.label}</option>
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
    background: var(--surface);
    color: var(--text);
    padding: 0.8rem 0.9rem;
  }

  span {
    color: var(--muted);
    font-size: 0.82rem;
    font-weight: 700;
  }
</style>
