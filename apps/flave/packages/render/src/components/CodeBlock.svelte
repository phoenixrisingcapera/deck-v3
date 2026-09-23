<script lang="ts">
  import { srcAttrs } from '../position';

  let { node }: { node: any } = $props();
  const lang: string | undefined = $derived(node?.lang ?? undefined);
</script>

<pre {...srcAttrs(node)}><code class={lang ? `language-${lang}` : undefined}>{node.value}</code></pre>
