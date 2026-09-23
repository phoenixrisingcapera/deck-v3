<script lang="ts">
  interface Props {
    src?: string;
    alt?: string;
    size?: 'sm' | 'md' | 'lg';
    rounded?: boolean;
    class?: string;
  }

  let { src = '/logo.svg', alt = 'Deck AIStack', size = 'md', rounded = true, class: className = '' }: Props = $props();
</script>

<img class={`app-logo app-logo--${size} ${rounded ? 'app-logo--rounded' : ''} ${className}`.trim()} {src} {alt} />

<style>
  .app-logo {
    display: block;
    object-fit: contain;
    object-position: center;
    filter: drop-shadow(0 10px 24px rgba(62, 92, 255, 0.22));
  }

  .app-logo--rounded {
    border-radius: 16px;
  }

  .app-logo--sm {
    width: 40px;
    height: 40px;
  }

  .app-logo--md {
    width: 48px;
    height: 48px;
  }

  .app-logo--lg {
    width: 56px;
    height: 56px;
  }
</style>
