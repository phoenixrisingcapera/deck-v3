<script lang="ts">
  import { onMount } from 'svelte';
  import AppLogo from '$components/AppLogo.svelte';
  import ThemeToggle from '$components/ThemeToggle.svelte';
  import { theme } from '$lib/stores/theme';
  import { sessionState } from '$lib/stores/session';

  let { children }: { children: import('svelte').Snippet } = $props();

  onMount(() => {
    theme.init('light');
    sessionState.load();
  });
</script>

<div class="marketing-shell">
  <div class="marketing-utility">
    <div class="marketing-utility__inner">
      <div class="marketing-trust">
        <span class="marketing-trust__dot"></span>
        Enterprise-grade security. Your data stays private and reviewable.
      </div>
      <div class="marketing-utility__links">
        <a href="/privacy">Privacy</a>
        <a href="/terms">Terms</a>
        <a href="/contact">Contact</a>
        <a href="/auth/sign-in">Sign in</a>
        <ThemeToggle />
      </div>
    </div>
  </div>

  <header class="marketing-nav">
    <a href="/" class="marketing-brand">
      <AppLogo alt="Deck logo" />
      <span>
        <strong>deck.aistack.codes</strong>
      </span>
    </a>
    <nav class="marketing-nav__links">
      <a href="/dashboard">Product</a>
      <a href="/vcs">Use cases</a>
      <a href="/pricing">Pricing</a>
      <a href="/about">About</a>
      <a href="/contact">Contact</a>
    </nav>
    <div class="marketing-nav__actions">
      <a class="button secondary" href="/auth/sign-in">Sign in</a>
      <a class="button" href="/auth/sign-up">Get started</a>
    </div>
  </header>

  <main class="marketing-main">
    {@render children()}
  </main>

  <footer class="marketing-footer">
    <span>deck.aistack.codes</span>
    <div class="marketing-nav__links">
      <a href="/about">About</a>
      <a href="/pricing">Pricing</a>
      <a href="/contact">Contact</a>
      <a href="/privacy">Privacy</a>
      <a href="/terms">Terms</a>
    </div>
  </footer>
</div>
