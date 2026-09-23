import { env } from '$env/dynamic/private';
import { resolveInstantHtmlRendererOrigin } from '$lib/config/instantHtmlRendererOrigin.js';

export const INSTANT_HTML_RENDERER_ORIGIN = resolveInstantHtmlRendererOrigin(env);
