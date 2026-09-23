<script lang="ts">
  import { formatDueLabel } from '$lib/dashboard/time';
  import type { DashboardTaskItem } from '$lib/types/workspace-dashboard';

  interface Props {
    tasks: DashboardTaskItem[];
  }

  let { tasks }: Props = $props();
</script>

<section class="panel dashboard-card">
  <div class="dashboard-card__head">
    <h2>My Tasks</h2>
  </div>

  <div class="dashboard-tasks">
    {#each tasks as task}
      <a class:dashboard-tasks__row--completed={task.status === 'completed'} class="dashboard-tasks__row" href={task.href}>
        <span class="dashboard-tasks__check" aria-label={task.status === 'completed' ? 'Completed' : 'Open'}>{task.status === 'completed' ? '✓' : ''}</span>
        <div class="dashboard-tasks__copy">
          <strong>{task.title}</strong>
          <small>{task.deckTitle}</small>
        </div>
        <span class={`dashboard-tasks__priority dashboard-tasks__priority--${task.priority}`}>{task.priority}</span>
        <small class="dashboard-tasks__due">{task.status === 'completed' ? 'Completed' : formatDueLabel(task.dueAt)}</small>
      </a>
    {/each}
  </div>
</section>
