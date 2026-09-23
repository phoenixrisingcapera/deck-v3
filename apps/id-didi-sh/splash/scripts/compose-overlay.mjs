#!/usr/bin/env node
/**
 * compose-overlay.mjs — canonical Lossless SVG-text-on-OG-image compositor.
 *
 * Two modes:
 *
 *   1. Single image
 *      node compose-overlay.mjs \
 *        --base public/ogimage__Project--BannerImage.jpg \
 *        --out  public/ogimage__Project--BannerImage--overlaid.jpg \
 *        --eyebrow "PROJECT · CATEGORY" \
 *        --h1 "Short Title" \
 *        --note "a hand-scrawled phrase" \
 *        --gradient "#5eead4,#fbbf24,#e879f9" \
 *        --gradient-angle 90 \
 *        --quality 90
 *
 *   2. Batch (manifest of formats sharing the same text + gradient)
 *      node compose-overlay.mjs --manifest overlay.manifest.json
 *
 *      manifest shape:
 *        {
 *          "formats": [
 *            { "base": "public/ogimage__P--BannerImage.jpg",
 *              "out":  "public/ogimage__P--BannerImage.jpg" },
 *            { "base": "public/ogimage__P--BannerImageTall.jpg",
 *              "out":  "public/ogimage__P--BannerImageTall.jpg" }
 *          ],
 *          "text": {
 *            "eyebrow": "PROJECT · CATEGORY",
 *            "h1": "Short Title",
 *            "note": "a hand-scrawled phrase"
 *          },
 *          "gradient": { "angle": 90, "stops": ["#5eead4","#fbbf24","#e879f9"] },
 *          "quality": 90,
 *          "archive": true
 *        }
 *
 * Requires: sharp (Node, librsvg under the hood).
 *   pnpm add -D sharp
 *
 * Conventions:
 *  - Output is JPEG (open-graph-share-seo-geo skill: JPEG-over-WebP).
 *  - When --out matches an existing file, the existing one is archived to
 *    .ogimage-archive/<basename>--<YYYY-MM-DD>.jpg before the new bytes
 *    are written. The unfurler URL stays stable; byte history is preserved.
 *  - Font sizing scales with min(width, height) so the same SVG layout
 *    re-aspects across the four canonical formats without overflow on
 *    narrow-tall variants.
 *  - Positions are percentages of canvas height so the overlay sits inside
 *    the top-1/3 empty-region zone produced by generate-consistent-og-images.
 */

import sharp from 'sharp';
import { readFile, writeFile, mkdir, stat, copyFile } from 'node:fs/promises';
import { dirname, basename, join } from 'node:path';
import { parseArgs } from 'node:util';

// ─── Layout — percentages of canvas height / width ──────────────────
// All positions live in the top 1/3 of the frame (the empty-region zone
// generate-consistent-og-images leaves clean). Edit cautiously.
const LAYOUT = {
  padding_x_pct:    0.05,   // 5% horizontal padding from left edge
  eyebrow_y_pct:    0.12,   // baseline at 12% of height
  h1_y_pct:         0.22,   // baseline at 22% of height
  note_y_pct:       0.30,   // baseline at 30% of height
  // Font sizes as fraction of min(width, height):
  eyebrow_size_pct: 0.030,
  h1_size_pct:      0.087,
  note_size_pct:    0.036,
  // Eyebrow tracking — 0.20em is the brand-canonical wide tracking.
  eyebrow_tracking_em: 0.20,
};

// ─── Type stack — brand-wide defaults ──────────────────────────────
const FONTS = {
  eyebrow: 'Inter, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
  h1:      '"Hack Nerd Font Mono", Hack, ui-monospace, SFMono-Regular, Menlo, monospace',
  note:    '"Poor Story", Caveat, "Patrick Hand", "Indie Flower", cursive',
};

// ─── SVG construction ──────────────────────────────────────────────
function gradientStopsToSvg(stops) {
  // Accept either ["#aaa", "#bbb"] (evenly spaced) or
  // [{offset: "0%", color: "#aaa"}, ...] (explicit).
  const n = stops.length;
  return stops.map((s, i) => {
    if (typeof s === 'string') {
      const offset = n === 1 ? '0%' : `${Math.round((i / (n - 1)) * 100)}%`;
      return `<stop offset="${offset}" stop-color="${s}"/>`;
    }
    return `<stop offset="${s.offset}" stop-color="${s.color}"/>`;
  }).join('\n      ');
}

function angleToGradientCoords(angleDeg) {
  // CSS gradient angles: 0deg points up, 90deg points right.
  // SVG linearGradient uses x1/y1 → x2/y2 in objectBoundingBox space.
  const rad = ((angleDeg - 90) * Math.PI) / 180; // shift so 90deg → right
  const x = Math.cos(rad);
  const y = Math.sin(rad);
  // Map [-1,1] cos/sin to [0,1] bbox space.
  return {
    x1: ((1 - x) / 2).toFixed(4),
    y1: ((1 - y) / 2).toFixed(4),
    x2: ((1 + x) / 2).toFixed(4),
    y2: ((1 + y) / 2).toFixed(4),
  };
}

function escapeXml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

function buildOverlaySvg({ width, height, text, gradient }) {
  const min = Math.min(width, height);
  const px = (frac) => Math.round(frac * width);
  const py = (frac) => Math.round(frac * height);
  const pm = (frac) => Math.round(frac * min);

  const xPad = px(LAYOUT.padding_x_pct);
  const eyebrowY  = py(LAYOUT.eyebrow_y_pct);
  const h1Y       = py(LAYOUT.h1_y_pct);
  const noteY     = py(LAYOUT.note_y_pct);
  const eyebrowSize = pm(LAYOUT.eyebrow_size_pct);
  const h1Size      = pm(LAYOUT.h1_size_pct);
  const noteSize    = pm(LAYOUT.note_size_pct);
  const eyebrowTracking = (eyebrowSize * LAYOUT.eyebrow_tracking_em).toFixed(2);

  const angle = gradient.angle ?? 90;
  const { x1, y1, x2, y2 } = angleToGradientCoords(angle);
  const stops = gradientStopsToSvg(gradient.stops);

  return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">
  <defs>
    <linearGradient id="brand" x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}">
      ${stops}
    </linearGradient>
  </defs>
  ${text.eyebrow ? `<text x="${xPad}" y="${eyebrowY}"
        font-family='${FONTS.eyebrow}'
        font-weight="300"
        font-size="${eyebrowSize}"
        letter-spacing="${eyebrowTracking}"
        fill="rgba(255,255,255,0.78)">${escapeXml(text.eyebrow)}</text>` : ''}
  ${text.h1 ? `<text x="${xPad}" y="${h1Y}"
        font-family='${FONTS.h1}'
        font-weight="700"
        font-size="${h1Size}"
        fill="url(#brand)">${escapeXml(text.h1)}</text>` : ''}
  ${text.note ? `<text x="${xPad}" y="${noteY}"
        font-family='${FONTS.note}'
        font-weight="400"
        font-size="${noteSize}"
        fill="#ffffff">${escapeXml(text.note)}</text>` : ''}
</svg>`;
}

// ─── Archive existing canonical before overwrite ────────────────────
async function archiveIfExists(outPath, archiveOn) {
  if (!archiveOn) return;
  try {
    await stat(outPath);
  } catch {
    return; // doesn't exist → nothing to archive
  }
  const dir = dirname(outPath);
  const base = basename(outPath, '.jpg').replace(/\.jpeg$/, '');
  // .ogimage-archive sits as a sibling of public/, not inside it.
  const archiveDir = join(dir, '..', '.ogimage-archive');
  await mkdir(archiveDir, { recursive: true });
  const today = new Date().toISOString().slice(0, 10); // YYYY-MM-DD
  const archivePath = join(archiveDir, `${base}--${today}.jpg`);
  await copyFile(outPath, archivePath);
  process.stdout.write(`  ↳ archived prior bytes to ${archivePath}\n`);
}

// ─── Per-image compositor ──────────────────────────────────────────
async function composeOne({ basePath, outPath, text, gradient, quality, archive }) {
  const baseBuf = await readFile(basePath);
  const { width, height } = await sharp(baseBuf).metadata();
  if (!width || !height) {
    throw new Error(`Could not read dimensions from ${basePath}`);
  }
  const svg = buildOverlaySvg({ width, height, text, gradient });

  await archiveIfExists(outPath, archive);

  await sharp(baseBuf)
    .composite([{ input: Buffer.from(svg), top: 0, left: 0 }])
    .jpeg({ quality, mozjpeg: true })
    .toFile(outPath);

  const outStat = await stat(outPath);
  process.stdout.write(
    `  ✓ ${basename(outPath)}  ${width}×${height}  ${(outStat.size / 1024).toFixed(0)} KB\n`
  );
}

// ─── CLI ────────────────────────────────────────────────────────────
async function main() {
  const { values } = parseArgs({
    options: {
      base:           { type: 'string' },
      out:            { type: 'string' },
      eyebrow:        { type: 'string' },
      h1:             { type: 'string' },
      note:           { type: 'string' },
      gradient:       { type: 'string' },          // "#aaa,#bbb,#ccc"
      'gradient-angle': { type: 'string', default: '90' },
      quality:        { type: 'string', default: '90' },
      manifest:       { type: 'string' },
      'no-archive':   { type: 'boolean', default: false },
    },
  });

  if (values.manifest) {
    const m = JSON.parse(await readFile(values.manifest, 'utf8'));
    const gradient = m.gradient || { angle: 90, stops: ['#ffffff'] };
    const quality = m.quality ?? 90;
    const archive = m.archive !== false;
    process.stdout.write(
      `→ batch overlay  |  ${m.formats.length} format(s)  |  quality ${quality}\n`
    );
    for (const fmt of m.formats) {
      await composeOne({
        basePath: fmt.base,
        outPath:  fmt.out ?? fmt.base,
        text: m.text,
        gradient,
        quality,
        archive,
      });
    }
    return;
  }

  if (!values.base || !values.out) {
    process.stderr.write(
      'Usage: node compose-overlay.mjs --base <jpg> --out <jpg> ' +
      '[--eyebrow <text>] [--h1 <text>] [--note <text>] ' +
      '[--gradient "#aaa,#bbb,#ccc"] [--gradient-angle 90] [--quality 90]\n' +
      '   or: node compose-overlay.mjs --manifest <manifest.json>\n'
    );
    process.exit(2);
  }

  const stops = (values.gradient ?? '#ffffff').split(',').map((s) => s.trim());
  const gradient = { angle: Number(values['gradient-angle']), stops };
  const quality = Number(values.quality);
  const archive = !values['no-archive'];

  await composeOne({
    basePath: values.base,
    outPath:  values.out,
    text: {
      eyebrow: values.eyebrow ?? '',
      h1:      values.h1      ?? '',
      note:    values.note    ?? '',
    },
    gradient,
    quality,
    archive,
  });
}

main().catch((err) => {
  process.stderr.write(`× ${err.message}\n`);
  if (err.message.includes("Cannot find package 'sharp'")) {
    process.stderr.write('  Install sharp at the project root:  pnpm add -D sharp\n');
  }
  process.exit(1);
});
