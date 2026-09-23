"""Secret-free Playwright child process for deterministic render proofs.

The parent sends a bounded sanitized HTML document over stdin. This module must
not import application settings, database, storage, crypto, or observability.
"""

from __future__ import annotations

import base64
import ctypes
import json
import os
import platform
import resource
import sys
import time
from typing import Any

MAX_REQUEST_BYTES = 1_100_000
MAX_RENDER_DOCUMENT_BYTES = 1_000_000
MAX_RESPONSE_BYTES = 20_000_000
TEST_MODE_ENV = "PLAYWRIGHT_CHILD_TEST_MODE"


def serialize_request_payload(payload: dict[str, Any]) -> bytes:
    """Serialize the exact parent-to-child request without ASCII expansion."""

    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def apply_process_hardening() -> dict[str, bool]:
    """Best-effort non-root Linux hardening; never broadens privileges."""

    result = {"noNewPrivileges": False, "resourceLimits": False}
    try:
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        soft_nofile, hard_nofile = resource.getrlimit(resource.RLIMIT_NOFILE)
        nofile = min(1024, hard_nofile) if hard_nofile != resource.RLIM_INFINITY else 1024
        resource.setrlimit(resource.RLIMIT_NOFILE, (nofile, hard_nofile))
        # Do not set RLIMIT_FSIZE here. Chromium cannot create a page under a
        # finite file-size limit in Railway's container runtime, even when the
        # limit is substantially larger than the rendered output. Bounded IPC,
        # browser timeouts, and process-group cleanup constrain app-visible
        # output without breaking Chromium's internal profile files.
        result["resourceLimits"] = True
    except (OSError, ValueError):
        pass
    if platform.system() == "Linux":
        try:
            libc = ctypes.CDLL(None, use_errno=True)
            if libc.prctl(38, 1, 0, 0, 0) == 0:  # PR_SET_NO_NEW_PRIVS
                result["noNewPrivileges"] = True
        except (AttributeError, OSError):
            pass
    return result

METRICS_SCRIPT = r"""() => {
  const root = document.querySelector('[data-da-slide-root]');
  if (!root) return { visible: false, overflowX: true, overflowY: true, nodeCount: 0 };
  const rect = root.getBoundingClientRect();
  // SVG labels paint their own fill and can overlap independently of the SVG.
  root.querySelectorAll('svg text').forEach((node, index) => {
    if (!node.dataset.daElementKey) node.dataset.daElementKey = `${node.closest('[data-da-element-key]')?.dataset.daElementKey || 'svg'}-text-${index+1}`;
  });
  const elements = [...root.querySelectorAll('[data-da-element-key]')];
  const rgb = value => {
    const match = String(value || '').match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
    return match ? match.slice(1,4).map(Number) : null;
  };
  const alpha = value => {
    const text=String(value || '');
    const match=text.match(/rgba\([^)]*,\s*([\d.]+)\s*\)$/);
    return match ? Number(match[1]) : text.startsWith('rgb(') ? 1 : null;
  };
  const rgba = value => {
    const channels=rgb(value), opacity=alpha(value);
    return channels && opacity !== null ? [...channels,opacity] : null;
  };
  const composite = (front, back) => {
    const outAlpha=front[3] + back[3]*(1-front[3]);
    if (outAlpha <= 0) return null;
    return [0,1,2].map(index => (
      front[index]*front[3] + back[index]*back[3]*(1-front[3])
    )/outAlpha).concat(outAlpha);
  };
  const cssColor = value => `rgba(${Math.round(value[0])}, ${Math.round(value[1])}, ${Math.round(value[2])}, ${value[3]})`;
  const luminance = value => {
    const channels = rgb(value);
    if (!channels) return null;
    const adjusted = channels.map(item => { const n=item/255; return n <= .03928 ? n/12.92 : Math.pow((n+.055)/1.055,2.4); });
    return .2126*adjusted[0] + .7152*adjusted[1] + .0722*adjusted[2];
  };
  const paintedBackgrounds = node => {
    const resolve = current => {
      if (!current) return [];
      const style=getComputedStyle(current);
      const inherited=resolve(current.parentElement);
      // SVG graphics/text expose CSS background styles but do not paint CSS
      // boxes. Grounded labels inherit the compiler's HTML body guard; that
      // computed white background must not replace the real dark SVG field.
      if (current instanceof SVGElement && !(current instanceof SVGSVGElement)) return inherited;
      const background=rgba(style.backgroundColor);
      let candidates=inherited;
      if (background && background[3] > 0) {
        if (background[3] >= .98) candidates=[background];
        else if (inherited.length) candidates=inherited.map(base => composite(background,base)).filter(Boolean);
        else return [];
      }
      if (style.backgroundImage && style.backgroundImage !== 'none') {
        if (/url\s*\(/i.test(style.backgroundImage)) return [];
        const stops=style.backgroundImage.match(/rgba?\([^)]*\)/g) || [];
        if (!stops.length) return [];
        const parsedStops=stops.map(rgba);
        if (parsedStops.some(stop => !stop)) return [];
        if (!candidates.length) {
          if (parsedStops.some(stop => stop[3] < .98)) return [];
          candidates=parsedStops;
          return candidates;
        }
        const bases=candidates;
        const composites=parsedStops.flatMap(overlay => {
          if (overlay[3] <= 0) return [];
          return bases.map(base => composite(overlay,base)).filter(Boolean);
        });
        // An opaque gradient fully paints over its ancestor background. Keeping
        // that hidden ancestor as a candidate creates false contrast failures
        // for light text on dark bands. Transparent stops still retain the
        // underlying surface as a possible visible colour.
        candidates=parsedStops.every(stop => stop[3] >= .98)
          ? parsedStops
          : [...(parsedStops.some(stop => stop[3] <= 0) ? bases : []),...composites].slice(-64);
      }
      return candidates;
    };
    return resolve(node).filter(value => value && value[3] >= .98).map(cssColor);
  };
  const geometry = elements.map(node => {
    const box = node.getBoundingClientRect();
    const style = getComputedStyle(node);
    const textRange=document.createRange();
    textRange.selectNodeContents(node);
    const textRects=[...textRange.getClientRects()].filter(item => item.width > 0 && item.height > 0).map(item => ({
      x:item.x,y:item.y,width:item.width,height:item.height
    }));
    const paintedBox=(alpha(style.backgroundColor) || 0) > 0
      || (style.backgroundImage && style.backgroundImage !== 'none')
      || [style.borderTopWidth,style.borderRightWidth,style.borderBottomWidth,style.borderLeftWidth]
        .some(value => parseFloat(value || '0') > 0);
    return {key: node.dataset.daElementKey, x: box.x, y: box.y, width: box.width, height: box.height,
      display: style.display, visibility: style.visibility, color: style.color, backgroundColor: style.backgroundColor,
      paintRects: paintedBox ? [{x:box.x,y:box.y,width:box.width,height:box.height}] : (textRects.length ? textRects : [{x:box.x,y:box.y,width:box.width,height:box.height}])};
  });
  const clipped = geometry.filter(box => box.x < rect.x || box.y < rect.y || box.x + box.width > rect.right || box.y + box.height > rect.bottom).map(box => box.key);
  const overlaps = [], severeOverlaps = [];
  for (let i=0; i<geometry.length; i++) for (let j=i+1; j<geometry.length; j++) {
    const a=geometry[i], b=geometry[j];
    const nodeA=elements[i], nodeB=elements[j];
    if (nodeA.contains(nodeB) || nodeB.contains(nodeA)) continue;
    const areaA=a.paintRects.reduce((sum,item) => sum+item.width*item.height,0);
    const areaB=b.paintRects.reduce((sum,item) => sum+item.width*item.height,0);
    const intersection=a.paintRects.reduce((sum,first) => sum+b.paintRects.reduce((inner,second) => {
      const width=Math.max(0,Math.min(first.x+first.width,second.x+second.width)-Math.max(first.x,second.x));
      const height=Math.max(0,Math.min(first.y+first.height,second.y+second.height)-Math.max(first.y,second.y));
      return inner+width*height;
    },0),0);
    if (areaA && areaB && intersection > 0) {
      const ratio=intersection/Math.min(areaA,areaB);
      overlaps.push([a.key,b.key,ratio]);
      if (ratio >= .35) severeOverlaps.push([a.key,b.key,ratio]);
    }
  }
  const images = [...root.querySelectorAll('img')];
  const textTags = new Set(['H1','H2','H3','H4','H5','H6','P','LI','TD','TH','FIGCAPTION','BLOCKQUOTE']);
  const wordCount = value => (String(value || '').trim().match(/[\p{L}\p{N}][\p{L}\p{N}'’.-]*/gu) || []).length;
  const textSamples = elements.filter(node => {
    if (!textTags.has(node.tagName)) return false;
    const style=getComputedStyle(node), box=node.getBoundingClientRect();
    return style.display !== 'none' && style.visibility !== 'hidden' && box.width > 0 && box.height > 0 && wordCount(node.innerText) > 0;
  }).map(node => {
    const style=getComputedStyle(node), box=node.getBoundingClientRect();
    return {
      key:node.dataset.daElementKey,
      tagName:node.tagName.toLowerCase(),
      fontSize:Number(parseFloat(style.fontSize || '0').toFixed(2)),
      wordCount:wordCount(node.innerText),
      width:Number(box.width.toFixed(2)),
      height:Number(box.height.toFixed(2))
    };
  });
  const substantialBody = textSamples.filter(item => ['p','li','td','th','figcaption','blockquote'].includes(item.tagName) && item.wordCount >= 4);
  const bodySizes = substantialBody.map(item => item.fontSize).sort((a,b) => a-b);
  const headingSizes = textSamples.filter(item => /^h[1-6]$/.test(item.tagName)).map(item => item.fontSize);
  const allTextSizes = textSamples.map(item => item.fontSize);
  const median = values => values.length ? values[Math.floor((values.length-1)/2)] : null;
  const visualNodes = [...root.querySelectorAll('img,svg')];
  const visualRects = visualNodes.map(node => node.getBoundingClientRect()).filter(box => box.width > 0 && box.height > 0);
  const rootArea = Math.max(1, rect.width*rect.height);
  const largestVisualAreaRatio = visualRects.length
    ? Math.max(...visualRects.map(box => Math.min(1,(box.width*box.height)/rootArea)))
    : 0;
  const visualInkArea = visualNodes.reduce((total,node) => {
    if (node.tagName.toLowerCase() === 'img') {
      const box=node.getBoundingClientRect();
      return total + Math.max(0,box.width)*Math.max(0,box.height);
    }
    const graphics=[...node.querySelectorAll('path,rect,circle,ellipse,line,polyline,polygon,text,image')];
    return total + graphics.reduce((sum,graphic) => {
      const box=graphic.getBoundingClientRect(), style=getComputedStyle(graphic);
      const strokeWidth=Math.max(0,parseFloat(style.strokeWidth || '0') || 0);
      const fillPainted=style.fill !== 'none' && style.fill !== 'transparent' && alpha(style.fill) !== 0 && parseFloat(style.fillOpacity || '1') > 0;
      const strokePainted=style.stroke !== 'none' && style.stroke !== 'transparent' && parseFloat(style.strokeOpacity || '1') > 0 && strokeWidth > 0;
      let area=fillPainted ? Math.max(0,box.width)*Math.max(0,box.height) : 0;
      if (strokePainted) {
        let length=0;
        try { length=typeof graphic.getTotalLength === 'function' ? graphic.getTotalLength() : 0; } catch (_) { length=0; }
        area=Math.max(area,length > 0 ? length*strokeWidth : Math.max(box.width,strokeWidth)*Math.max(box.height,strokeWidth));
      }
      return sum + area;
    },0);
  },0);
  const visualInkAreaRatio=Math.min(1,visualInkArea/rootArea);
  const sampleBackgrounds = [];
  for (const xRatio of [.08,.25,.5,.75,.92]) for (const yRatio of [.1,.5,.9]) {
    const node=document.elementFromPoint(rect.x+rect.width*xRatio,rect.y+rect.height*yRatio);
    const backgrounds=paintedBackgrounds(node);
    if (backgrounds.length) sampleBackgrounds.push(backgrounds[backgrounds.length-1]);
  }
  const sampleLuminances=sampleBackgrounds.map(luminance).filter(value => value !== null);
  const nearWhiteSampleRatio=sampleLuminances.length
    ? sampleLuminances.filter(value => value >= .88).length/sampleLuminances.length
    : null;
  const presentationQuality = {
    policyVersion:'presentation-scale.v2',
    visibleWordCount:wordCount(root.innerText),
    textElementCount:textSamples.length,
    substantialBodyCount:substantialBody.length,
    minimumSubstantialBodyFontSize:bodySizes.length ? bodySizes[0] : null,
    medianSubstantialBodyFontSize:median(bodySizes),
    smallReadableTextKeys:textSamples.filter(item => item.fontSize < 18).map(item => item.key),
    maximumHeadingFontSize:headingSizes.length ? Math.max(...headingSizes) : null,
    maximumTextFontSize:allTextSizes.length ? Math.max(...allTextSizes) : null,
    visualElementCount:visualRects.length,
    largestVisualAreaRatio:Number(largestVisualAreaRatio.toFixed(4)),
    visualInkAreaRatio:Number(visualInkAreaRatio.toFixed(4)),
    backgroundSampleCount:sampleLuminances.length,
    nearWhiteSampleRatio:nearWhiteSampleRatio === null ? null : Number(nearWhiteSampleRatio.toFixed(4))
  };
  // A table/layout container does not paint its descendants' text colour.
  // Each text run belongs to its nearest keyed element (e.g. the actual cell).
  const ownsText = node => {
    const walker = document.createTreeWalker(node, NodeFilter.SHOW_TEXT);
    for (let text = walker.nextNode(); text; text = walker.nextNode()) {
      if (!text.parentElement.closest('title,desc,defs') && text.textContent.trim() && text.parentElement.closest('[data-da-element-key]') === node) return true;
    }
    return false;
  };
  const svgTextBackgrounds = node => {
    const svg=node.ownerSVGElement, matrix=node.getScreenCTM();
    if (!svg || !matrix) return [];
    const shapes=[...svg.querySelectorAll('rect,circle,ellipse,path,polygon,polyline')].filter(shape =>
      !shape.closest('defs') && (shape.compareDocumentPosition(node) & Node.DOCUMENT_POSITION_FOLLOWING));
    const backgrounds=[];
    // Test every glyph against the shape actually painted behind it, not the
    // SVG container's CSS background. Unsupported paints fail closed.
    for (let i=0; i<node.getNumberOfChars(); i++) {
      // SVG character indices address rendered characters, not raw DOM text.
      // Indentation before a tspan is collapsed by layout; indexing textContent
      // with i would skip real glyphs and report readable labels as unknown.
      const box=node.getExtentOfChar(i);
      // A glyph centre can remain on a dark node while its edge spills onto a
      // bright field, especially after rotation. Check its full inset box.
      const inset=Math.min(.25,box.width/4,box.height/4);
      const samples=[[box.x+box.width/2,box.y+box.height/2],
        [box.x+inset,box.y+inset],[box.x+box.width-inset,box.y+inset],
        [box.x+inset,box.y+box.height-inset],[box.x+box.width-inset,box.y+box.height-inset]];
      for (const [x,y] of samples) {
      const point=new DOMPoint(x,y).matrixTransform(matrix);
      let background=paintedBackgrounds(node);
      for (const shape of shapes) {
        const style=getComputedStyle(shape), transform=shape.getScreenCTM();
        if (!transform || style.display==='none' || style.visibility==='hidden' || style.fill==='none') continue;
        if (!shape.isPointInFill(point.matrixTransform(transform.inverse()))) continue;
        const color=rgba(style.fill), opacity=parseFloat(style.fillOpacity || '1')*parseFloat(style.opacity || '1');
        if (color && color[3]*opacity === 0) continue;
        if (!color || !Number.isFinite(opacity)) return [];
        const paint=[...color.slice(0,3),color[3]*opacity];
        if (paint[3]>=.98) background=[cssColor(paint)];
        else {
          if (!background.length) return [];
          background=background.map(base => composite(paint,rgba(base))).filter(Boolean).map(cssColor);
        }
      }
      backgrounds.push(...background);
      }
    }
    return backgrounds;
  };
  const contrastChecks = elements.filter(ownsText).map(node => {
    const isSvgText=node instanceof SVGTextContentElement;
    const foreground=isSvgText ? getComputedStyle(node).fill : getComputedStyle(node).color;
    const backgrounds=isSvgText ? svgTextBackgrounds(node) : paintedBackgrounds(node);
    const a=luminance(foreground);
    const ratios=backgrounds.map(background => {
      const b=luminance(background);
      return (a === null || b === null) ? null : (Math.max(a,b)+.05)/(Math.min(a,b)+.05);
    });
    const ratio=ratios.length && ratios.every(item => item !== null) ? Math.min(...ratios) : null;
    const size=parseFloat(getComputedStyle(node).fontSize || '0');
    const threshold=size >= 24 ? 3 : 4.5;
    return {key: node.dataset.daElementKey, ratio, threshold, passed: ratio !== null && ratio >= threshold};
  });
  const accessibility = {
    missingImageAlt: images.filter(img => !img.hasAttribute('alt')).length,
    missingDocumentTitle: !document.title,
    unlabeledSvg: [...root.querySelectorAll('svg')].filter(svg => !svg.getAttribute('aria-label') && !svg.querySelector('title')).length
  };
  // A centred flex child can consume the root's padding while remaining fully
  // inside the canvas. scrollHeight includes that unpainted trailing padding.
  // Inspect descendant boxes and text ranges before treating it as clipping.
  const outsideY = box => box.height > 0 && (box.top < rect.top - 1 || box.bottom > rect.bottom + 1);
  const descendantOverflowY = [...root.querySelectorAll('*')].some(node => {
    if (!outsideY(node.getBoundingClientRect())) return false;
    const style = getComputedStyle(node);
    if (style.visibility === 'hidden' || Number(style.opacity) === 0) return false;
    // Auto-sized grid wrappers can extend solely through transparent trailing
    // padding. Text is measured independently below; only painted boxes or
    // replaced/visual elements make the wrapper's own bounds significant.
    if (['IMG', 'SVG', 'CANVAS', 'VIDEO'].includes(node.tagName.toUpperCase())) return true;
    if (node instanceof SVGGeometryElement) return style.fill !== 'none' || style.stroke !== 'none';
    const background = rgba(style.backgroundColor);
    if (background && background[3] > 0) return true;
    if (style.backgroundImage !== 'none' || style.boxShadow !== 'none') return true;
    return ['Top', 'Right', 'Bottom', 'Left'].some(side => {
      const color = rgba(style['border' + side + 'Color']);
      return parseFloat(style['border' + side + 'Width']) > 0 && color && color[3] > 0;
    });
  });
  const textWalker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let textOverflowY = false;
  while (textWalker.nextNode()) {
    if (!textWalker.currentNode.textContent.trim()) continue;
    const range = document.createRange();
    range.selectNodeContents(textWalker.currentNode);
    if ([...range.getClientRects()].some(outsideY)) { textOverflowY = true; break; }
  }
  return {
    visible: rect.width > 0 && rect.height > 0 && (root.textContent || '').trim().length > 0,
    overflowX: root.scrollWidth > root.clientWidth || document.documentElement.scrollWidth > 1920,
    overflowY: (root.scrollHeight > root.clientHeight + 1 && (descendantOverflowY || textOverflowY)) || document.documentElement.scrollHeight > 1081,
    nodeCount: document.querySelectorAll('*').length,
    assetLoad: {imageCount: images.length, failedImageCount: images.filter(img => !img.complete || img.naturalWidth === 0).length},
    geometry, clippedElementKeys: clipped, overlapPairs: overlaps, severeOverlapPairs: severeOverlaps,
    contrast: {status: contrastChecks.every(item => item.passed) ? 'passed' : 'failed', checks: contrastChecks},
    accessibility, presentationQuality
  };
}"""


def _validated_request(payload: Any) -> tuple[str, dict[str, float | int], int]:
    if not isinstance(payload, dict) or payload.get("protocolVersion") != 1:
        raise ValueError("invalid_protocol")
    encoded_document = payload.get("renderDocumentBase64")
    if encoded_document is not None:
        if not isinstance(encoded_document, str):
            raise ValueError("invalid_render_document")
        try:
            document_bytes = base64.b64decode(encoded_document, validate=True)
            document = document_bytes.decode("utf-8")
        except (ValueError, UnicodeDecodeError) as exc:
            raise ValueError("invalid_render_document") from exc
    else:
        # Retain protocol-v1 direct-document compatibility for isolated child
        # callers. The canonical parent always uses the bounded base64 field.
        document = payload.get("renderDocument")
        document_bytes = document.encode("utf-8") if isinstance(document, str) else b""
    viewport = payload.get("viewport")
    if not isinstance(document, str) or len(document_bytes) > MAX_RENDER_DOCUMENT_BYTES:
        raise ValueError("invalid_render_document")
    if not isinstance(viewport, dict):
        raise ValueError("invalid_viewport")
    width = int(viewport.get("width") or 0)
    height = int(viewport.get("height") or 0)
    scale = float(viewport.get("deviceScaleFactor") or 1)
    timeout_seconds = int(payload.get("timeoutSeconds") or 0)
    if not (1 <= width <= 4096 and 1 <= height <= 4096 and 0.5 <= scale <= 4 and 1 <= timeout_seconds <= 1800):
        raise ValueError("invalid_render_options")
    return document, {"width": width, "height": height, "deviceScaleFactor": scale}, timeout_seconds


def chromium_launch_options() -> dict[str, Any]:
    """Return the fixed launch contract for the isolated container child."""
    local_executable = str(os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH") or "").strip()
    return {
        "headless": True,
        # Railway's container runtime denies Chromium's credential sandbox.
        # The parent boundary instead requires a non-root worker, passes only a
        # secret-free environment, and this child applies no-new-privileges and
        # bounded resources before Chromium starts.
        "chromium_sandbox": False,
        "executable_path": local_executable or None,
        "args": [
            "--disable-background-networking", "--disable-sync", "--no-first-run", "--disable-dev-shm-usage",
            "--disable-extensions", "--disable-gpu", "--renderer-process-limit=1",
            "--js-flags=--max-old-space-size=128",
        ],
    }


def render_payload(payload: dict[str, Any]) -> dict[str, Any]:
    render_document, viewport, timeout_seconds = _validated_request(payload)
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(**chromium_launch_options())
        try:
            page = browser.new_page(
                viewport={"width": int(viewport["width"]), "height": int(viewport["height"])},
                device_scale_factor=float(viewport["deviceScaleFactor"]),
            )
            page.context.set_offline(True)
            page.route("**/*", lambda route: route.abort())
            console_errors: list[str] = []
            page.on("console", lambda message: console_errors.append(message.type) if message.type == "error" else None)
            page.set_content(render_document, wait_until="load", timeout=timeout_seconds * 1000)
            metrics = page.evaluate(METRICS_SCRIPT)
            screenshot = page.screenshot(type="png", full_page=False)
            return {
                "ok": True,
                "browserVersion": browser.version,
                "metrics": metrics,
                "consoleErrors": console_errors,
                "screenshotBase64": base64.b64encode(screenshot).decode("ascii"),
            }
        finally:
            browser.close()


def main() -> int:
    hardening = apply_process_hardening()
    try:
        raw = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
        if len(raw) > MAX_REQUEST_BYTES:
            raise ValueError("request_too_large")
        payload = json.loads(raw)
        if isinstance(payload, dict) and payload.get("operation") == "diagnostic":
            if os.environ.get(TEST_MODE_ENV) != "1":
                raise ValueError("diagnostic_disabled")
            sleep_ms = max(0, min(10_000, int(payload.get("sleepMilliseconds") or 0)))
            if sleep_ms:
                time.sleep(sleep_ms / 1000)
            padding_bytes = max(0, min(1_000_000, int(payload.get("paddingBytes") or 0)))
            response = {
                "ok": True,
                "operation": "diagnostic",
                "environmentNames": sorted(os.environ),
                "hardening": hardening,
                "padding": "x" * padding_bytes,
            }
        else:
            response = render_payload(payload)
        encoded = json.dumps(response, separators=(",", ":")).encode("utf-8")
        if len(encoded) > MAX_RESPONSE_BYTES:
            raise ValueError("response_too_large")
    except Exception:
        encoded = b'{"ok":false,"error":"render_failed"}'
    sys.stdout.buffer.write(encoded)
    return 0 if b'"ok":true' in encoded[:32] else 1


if __name__ == "__main__":
    raise SystemExit(main())
