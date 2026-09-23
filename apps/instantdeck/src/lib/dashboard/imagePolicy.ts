const allowedImageProtocols = new Set(['https:', 'data:']);

export function safeDashboardImageUrl(value: string | null | undefined) {
  if (!value) return null;

  if (value.startsWith('/')) {
    return value;
  }

  try {
    const url = new URL(value);
    return allowedImageProtocols.has(url.protocol) ? url.toString() : null;
  } catch {
    return null;
  }
}

export function dashboardImageCspSources() {
  return ["'self'", 'https:', 'data:'];
}
