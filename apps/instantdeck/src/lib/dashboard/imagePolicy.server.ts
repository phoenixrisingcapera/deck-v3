export function dashboardImageCspSources() {
  const configured = process.env.DASHBOARD_IMAGE_CSP_SOURCES?.trim();
  if (!configured) return ["'self'", 'https:', 'data:'];
  return Array.from(new Set(["'self'", ...configured.split(/\s+/).filter(Boolean)]));
}
