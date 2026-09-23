<script lang="ts">
  import EmptyState from '$components/EmptyState.svelte';

  interface Props {
    title: string;
    message: string;
  }

  let { title, message }: Props = $props();
</script>

<EmptyState
  eyebrow="Locked until first deck"
  {title}
  {message}
  primaryHref="/welcome"
  primaryLabel="Upload first deck"
  secondaryHref="/decks/new?mode=guided"
  secondaryLabel="Guided intake"
/>
