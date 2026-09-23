<script lang="ts">
  import { settings } from '$lib/stores/settings.svelte';
  import { flow } from '$lib/stores/flow.svelte';

  type StepId = 'outline' | 'firm' | 'deal' | 'curate' | 'generate';
  type StepStatus = 'done' | 'active' | 'pending';

  interface Step {
    id: StepId;
    label: string;
    detail?: string;
    status: StepStatus;
    onClick?: () => void;
  }

  let currentStepId = $derived<StepId>(deriveCurrentStep());

  function deriveCurrentStep(): StepId {
    switch (flow.stage.kind) {
      case 'create_firm':
        return 'firm';
      case 'create_deal':
        return 'deal';
      case 'approving_sources':
        return 'curate';
      case 'ready_to_run':
      case 'running_job':
        return 'generate';
      case 'outline_detail':
      case 'idle':
      default:
        return 'outline';
    }
  }

  let hasFirm = $derived(!!settings.activeFirm);
  let firmLabel = $derived(settings.activeFirm ?? 'Firm');

  let steps = $derived<Step[]>([
    {
      id: 'outline',
      label: 'Outline',
      status: statusFor('outline'),
      onClick: currentStepId !== 'outline' ? () => flow.close() : undefined,
    },
    {
      id: 'firm',
      label: hasFirm ? firmLabel : 'Firm',
      detail: hasFirm && currentStepId !== 'firm' ? 'Active firm' : undefined,
      status: statusFor('firm'),
    },
    {
      id: 'deal',
      label: 'Deal',
      status: statusFor('deal'),
      onClick:
        currentStepId === 'generate' && flow.stage.kind === 'ready_to_run'
          ? () => flow.editDeal()
          : undefined,
      // Note: when running_job, "Deal" is not clickable — we don't want to
      // accidentally cancel a job by going back to the form.
    },
    {
      id: 'curate',
      label: 'Curate',
      // Skippable by design — a first pass on a deal with nothing curated
      // yet is legitimate. Naming it as a step (rather than hiding it behind
      // a button on the Generate panel) is what makes skipping a decision
      // instead of an oversight.
      detail: currentStepId === 'curate' ? 'optional' : undefined,
      status: statusFor('curate'),
      onClick:
        flow.stage.kind === 'ready_to_run'
          ? () => {
              if (flow.stage.kind !== 'ready_to_run') return;
              flow.startApprovingSources(flow.stage.outline, flow.stage.payload);
            }
          : undefined,
    },
    {
      id: 'generate',
      label: 'Generate',
      status: statusFor('generate'),
      onClick:
        flow.stage.kind === 'approving_sources' ? () => flow.sourcesSettled() : undefined,
    },
  ]);

  function statusFor(id: StepId): StepStatus {
    const order: StepId[] = ['outline', 'firm', 'deal', 'curate', 'generate'];
    const currentIdx = order.indexOf(currentStepId);
    const stepIdx = order.indexOf(id);

    if (id === currentStepId) return 'active';

    if (id === 'firm') {
      if (hasFirm) return stepIdx < currentIdx ? 'done' : 'pending';
      return 'pending';
    }

    return stepIdx < currentIdx ? 'done' : 'pending';
  }

  let progressPercent = $derived(progressFromCurrent(currentStepId, hasFirm));

  function progressFromCurrent(id: StepId, hasFirmNow: boolean): number {
    switch (id) {
      case 'outline':
        return hasFirmNow ? 25 : 0;
      case 'firm':
        return 25;
      case 'deal':
        return 50;
      case 'curate':
        return 75;
      case 'generate':
        return 100;
    }
  }
</script>

<nav class="breadcrumbs" aria-label="Onboarding progress">
  <div class="progress-track">
    <div class="progress-fill" style="width: {progressPercent}%"></div>
  </div>

  <ol class="steps">
    {#each steps as step, i (step.id)}
      <li class="step status-{step.status}">
        {#if step.onClick}
          <button type="button" class="step-button" onclick={step.onClick}>
            <span class="badge" aria-hidden="true">
              {#if step.status === 'done'}✓{:else}{i + 1}{/if}
            </span>
            <span class="label-block">
              <span class="label">{step.label}</span>
              {#if step.detail}<span class="detail">{step.detail}</span>{/if}
            </span>
          </button>
        {:else}
          <span class="step-static">
            <span class="badge" aria-hidden="true">
              {#if step.status === 'done'}✓{:else}{i + 1}{/if}
            </span>
            <span class="label-block">
              <span class="label">{step.label}</span>
              {#if step.detail}<span class="detail">{step.detail}</span>{/if}
            </span>
          </span>
        {/if}
      </li>
    {/each}
  </ol>
</nav>

<style>
  .breadcrumbs {
    background: #ffffff;
    border-bottom: 1px solid #e5e5e5;
  }

  .progress-track {
    height: 3px;
    background: #f3f4f6;
    overflow: hidden;
  }

  .progress-fill {
    height: 100%;
    background: linear-gradient(90deg, #5b21b6, #a855f7);
    transition: width 200ms ease-out;
  }

  .steps {
    list-style: none;
    margin: 0;
    padding: 0.6rem 1.5rem;
    display: flex;
    align-items: center;
    gap: 0.4rem;
    overflow-x: auto;
  }

  .step {
    display: flex;
    align-items: center;
    flex-shrink: 0;
  }

  .step:not(:last-child)::after {
    content: '';
    display: inline-block;
    width: 1.5rem;
    height: 1px;
    background: #d1d5db;
    margin: 0 0.6rem;
  }

  .step.status-done:not(:last-child)::after {
    background: #5b21b6;
  }

  .step-button,
  .step-static {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    background: transparent;
    border: none;
    padding: 0.2rem 0.4rem;
    border-radius: 6px;
    font: inherit;
    color: inherit;
    cursor: default;
  }

  .step-button {
    cursor: pointer;
  }

  .step-button:hover {
    background: #f3f4f6;
  }

  .badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 22px;
    height: 22px;
    border-radius: 50%;
    font-size: 0.75rem;
    font-weight: 600;
    flex-shrink: 0;
    border: 1.5px solid;
  }

  .status-pending .badge {
    background: #fafaf9;
    border-color: #d1d5db;
    color: #9ca3af;
  }

  .status-active .badge {
    background: #5b21b6;
    border-color: #5b21b6;
    color: white;
  }

  .status-done .badge {
    background: #ecfdf5;
    border-color: #10b981;
    color: #065f46;
  }

  .label-block {
    display: inline-flex;
    flex-direction: column;
    line-height: 1.1;
  }

  .label {
    font-size: 0.85rem;
    font-weight: 500;
  }

  .status-pending .label {
    color: #9ca3af;
    font-weight: 400;
  }

  .status-active .label {
    color: #5b21b6;
    font-weight: 600;
  }

  .status-done .label {
    color: #0f0f0f;
  }

  .detail {
    font-size: 0.7rem;
    color: #6b7280;
    margin-top: 0.1rem;
  }

  @media (prefers-color-scheme: dark) {
    .breadcrumbs {
      background: #1c1c1e;
      border-bottom-color: #2a2a2c;
    }

    .progress-track {
      background: #2a2a2c;
    }

    .step:not(:last-child)::after {
      background: #3a3a3c;
    }

    .step.status-done:not(:last-child)::after {
      background: #a855f7;
    }

    .step-button:hover {
      background: #2a2a2c;
    }

    .status-pending .badge {
      background: #1c1c1e;
      border-color: #3a3a3c;
      color: #6b7280;
    }

    .status-active .badge {
      background: #a855f7;
      border-color: #a855f7;
    }

    .status-done .badge {
      background: #064e3b;
      border-color: #10b981;
      color: #a7f3d0;
    }

    .status-pending .label {
      color: #6b7280;
    }

    .status-active .label {
      color: #c4b5fd;
    }

    .status-done .label {
      color: #f6f6f6;
    }

    .detail {
      color: #9ca3af;
    }
  }
</style>
