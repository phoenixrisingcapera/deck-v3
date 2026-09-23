/**
 * Browser stubs for the node builtins lfm's barrel drags in.
 *
 * `@lossless-group/lfm`'s main entry re-exports `OGCache` from
 * `utils/og-cache.js`, which imports `node:crypto`, `node:fs` and `node:path`
 * at module scope. That makes the barrel unbundleable for a browser target
 * even when the consumer only wants `parseMarkdown` — the same class of defect
 * lfm's own `JSR-Export-Map-Omits-the-Formats-Subpaths` issue records for
 * `plantuml`, but in the main entry point rather than a subpath.
 *
 * The OG cache is only constructed when `ogFetch` is enabled, which the editor
 * never does. So these stubs are unreachable at runtime and throw loudly rather
 * than silently returning something wrong if that ever stops being true.
 *
 * Remove this file when lfm moves `og-cache` behind a subpath export.
 */
const unavailable = (name: string) => (): never => {
  throw new Error(`node builtin "${name}" is not available in the flave browser build`);
};

export const createHash = unavailable('crypto.createHash');
export const dirname = unavailable('path.dirname');
export const promises = new Proxy(
  {},
  { get: (_t, prop) => unavailable(`fs.promises.${String(prop)}`) },
) as unknown as typeof import('node:fs').promises;

export default {};
