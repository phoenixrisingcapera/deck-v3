<!-- Purpose: renders empty-state panel for the uploaded decks list. -->
<script lang="ts">
  type Props = {
    title?: string;
    message?: string;
  };

  let {
    title = 'No decks uploaded yet.',
    message = 'Upload a PDF or PowerPoint file to get started.'
  }: Props = $props();
</script>

<div class="empty-decks-state">
  <strong>{title}</strong>
  <p>{message}</p>
</div>

<style>
  .empty-decks-state {
    border: 1px dashed rgba(91, 115, 170, 0.34);
    border-radius: 18px;
    padding: 1rem 1.05rem;
    background: rgba(12, 22, 44, 0.76);
    display: grid;
    gap: 0.3rem;
  }

  .empty-decks-state strong {
    color: rgba(243, 246, 255, 0.97);
  }

  .empty-decks-state p {
    margin: 0;
    color: rgba(188, 201, 231, 0.74);
    font-size: 0.88rem;
    line-height: 1.45;
  }
</style>
