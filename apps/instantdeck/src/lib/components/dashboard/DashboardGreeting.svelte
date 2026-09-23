<script lang="ts">
  import type { DashboardGreeting as DashboardGreetingModel } from '$lib/types/workspace-dashboard';

  interface Props {
    greeting: DashboardGreetingModel;
  }

  let { greeting }: Props = $props();
</script>

<section class="dashboard-greeting">
  <div>
    <h1>{greeting.salutation}, {greeting.userName}</h1>
    <p>{greeting.subtitle}</p>
  </div>
</section>
