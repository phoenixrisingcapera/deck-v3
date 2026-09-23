<script lang="ts">
  interface Props {
    label: string;
    value: number;
    trend: string;
    tone: 'violet' | 'blue' | 'amber' | 'green';
    icon: string;
  }

  let { label, value, trend, tone, icon }: Props = $props();
</script>

<article class={`dashboard-stat dashboard-stat--${tone}`}>
  <div class="dashboard-stat__icon" aria-hidden="true">{icon}</div>
  <div class="dashboard-stat__copy">
    <span>{label}</span>
    <strong>{value}</strong>
    <small>{trend}</small>
  </div>
</article>
