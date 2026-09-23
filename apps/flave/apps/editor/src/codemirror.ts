import { EditorView, keymap, lineNumbers, highlightActiveLine } from '@codemirror/view';
import { EditorState, Compartment } from '@codemirror/state';
import { history, defaultKeymap, historyKeymap } from '@codemirror/commands';
import { markdown } from '@codemirror/lang-markdown';
import { css } from '@codemirror/lang-css';
import { json } from '@codemirror/lang-json';
import { yaml } from '@codemirror/lang-yaml';

export type Lang = 'markdown' | 'css' | 'json' | 'yaml' | 'text';

function extensionFor(lang: Lang) {
  switch (lang) {
    case 'css': return css();
    case 'json': return json();
    case 'yaml': return yaml();
    case 'markdown': return markdown();
    default: return [];
  }
}

/**
 * Svelte action mounting CodeMirror 6, with the language in a Compartment so
 * opening a .css after a .md reconfigures in place instead of tearing the
 * editor down and losing scroll and undo history.
 *
 * CodeMirror owns the buffer; Svelte owns the render. They are joined by
 * `onChange` and nothing else — the rendered pane never writes back here.
 */
export function codemirror(
  node: HTMLElement,
  opts: { doc: string; lang: Lang; onChange: (value: string) => void },
) {
  const language = new Compartment();
  let current = opts;

  const view = new EditorView({
    parent: node,
    state: EditorState.create({
      doc: opts.doc,
      extensions: [
        lineNumbers(),
        highlightActiveLine(),
        history(),
        keymap.of([...defaultKeymap, ...historyKeymap]),
        language.of(extensionFor(opts.lang)),
        EditorView.lineWrapping,
        EditorView.updateListener.of((u) => {
          if (u.docChanged) current.onChange(u.state.doc.toString());
        }),
      ],
    }),
  });

  return {
    update(next: { doc: string; lang: Lang; onChange: (value: string) => void }) {
      const langChanged = next.lang !== current.lang;
      const docChanged = next.doc !== view.state.doc.toString();
      current = next;
      if (langChanged) {
        view.dispatch({ effects: language.reconfigure(extensionFor(next.lang)) });
      }
      // Only replace the document when the change came from outside (a new file
      // was opened) — never echo the user's own keystrokes back at them.
      if (docChanged) {
        view.dispatch({
          changes: { from: 0, to: view.state.doc.length, insert: next.doc },
        });
      }
    },
    destroy: () => view.destroy(),
  };
}
