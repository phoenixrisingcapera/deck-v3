<script lang="ts">
  import { navigating } from '$app/state';

  let visible = $state(false);
  let progress = $state(0);
  let label = $state('Loading workspace');
  let timer: ReturnType<typeof setInterval> | null = null;
  let hideTimer: ReturnType<typeof setTimeout> | null = null;

  function clearTimers() {
    if (timer) {
      clearInterval(timer);
      timer = null;
    }
    if (hideTimer) {
      clearTimeout(hideTimer);
      hideTimer = null;
    }
  }

  function routeLabel(pathname: string) {
    if (pathname === '/dashboard') return 'Opening dashboard';
    if (pathname === '/decks/new') return 'Preparing upload';
    if (pathname === '/decks') return 'Loading deck library';
    if (pathname === '/smart-deck' || pathname.endsWith('/smart-deck')) return 'Opening Smart Deck';
    if (pathname === '/smart-edit' || pathname.endsWith('/smart-edit')) return 'Opening Smart Edit';
    if (pathname.endsWith('/due-diligence')) return 'Loading diligence view';
    if (pathname.endsWith('/export') || pathname === '/exports') return 'Preparing exports';
    if (pathname === '/settings' || pathname.startsWith('/settings/')) return 'Opening settings';
    if (pathname === '/welcome') return 'Loading workspace';
    return 'Loading page';
  }

  $effect(() => {
    const target = navigating.to?.url;
    clearTimers();

    if (!target) {
      if (visible) {
        progress = 100;
        hideTimer = setTimeout(() => {
          visible = false;
          progress = 0;
        }, 180);
      }
      return clearTimers;
    }

    visible = true;
    progress = 9;
    label = routeLabel(target.pathname);
    const startedAt = Date.now();

    timer = setInterval(() => {
      const elapsed = Date.now() - startedAt;
      progress = Math.min(94, Math.round(9 + Math.log1p(elapsed / 130) * 24));
    }, 90);

    return clearTimers;
  });
</script>

{#if visible}
  <div class="route-progress" role="status" aria-live="polite" aria-label={`${label}: ${progress}%`}>
    <div class="route-progress__bar" style={`--route-progress: ${progress}%`}></div>
    <div class="route-progress__card">
      <div class="route-progress__ring" style={`--route-progress-deg: ${progress * 3.6}deg`}>
        <span>{progress}%</span>
      </div>
      <div class="route-progress__copy">
        <strong>{label}</strong>
        <p>Keeping the workspace connected.</p>
      </div>
    </div>
  </div>
{/if}
