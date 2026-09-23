import { parseMarkdown } from '@lossless-group/lfm';

const samples = {
  'directive-container': ':::metric-card{value="42" label="ARR"}\ninner prose\n:::',
  'directive-leaf':      '::badge{kind="new"}',
  'directive-text':      'inline :abbr[LFM]{title="Lossless Flavored Markdown"} here',
  'callout-with-table':  '> [!warning] Heads up\n>\n> | a | b |\n> |---|---|\n> | 1 | 2 |',
  'callout-with-fence':  '> [!note] Code\n>\n> ```js\n> const a = 1;\n> ```',
  'blockquote':          '> just a quote',
  'link-image':          '[text](https://a.b) and ![alt](/img.png)',
};

function summarize(n, depth = 0, out = []) {
  const pad = '  '.repeat(depth);
  const hp = n.data?.hProperties ? ` hProps=${JSON.stringify(n.data.hProperties)}` : '';
  const attrs = n.attributes ? ` attrs=${JSON.stringify(n.attributes)}` : '';
  const name = n.name ? ` name=${n.name}` : '';
  const lang = n.lang ? ` lang=${n.lang}` : '';
  const val = n.value != null ? ` value=${JSON.stringify(String(n.value).slice(0, 30))}` : '';
  const pos = n.position ? ` pos=${n.position.start.offset}-${n.position.end.offset}` : ' pos=NONE';
  out.push(`${pad}${n.type}${name}${lang}${attrs}${hp}${val}${pos}`);
  (n.children || []).forEach((c) => summarize(c, depth + 1, out));
  return out;
}

for (const [k, src] of Object.entries(samples)) {
  const tree = await parseMarkdown(src);
  console.log(`\n########## ${k} ##########`);
  console.log(summarize(tree).join('\n'));
}
