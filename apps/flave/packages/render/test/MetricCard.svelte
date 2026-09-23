<!-- A trigger-pack component, exactly as an agent would write one for a user.
     Nothing in @flave/render knows this file exists. -->
<script lang="ts">
  let { value, label }: { value?: string; label?: string } = $props();
</script>

<div class="metric-card">
  <span class="metric-card__value">{value}</span>
  <span class="metric-card__label">{label}</span>
</div>
