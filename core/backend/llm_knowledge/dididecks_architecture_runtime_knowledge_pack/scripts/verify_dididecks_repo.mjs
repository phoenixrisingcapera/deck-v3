#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";

const ROOT = process.cwd();
const EXPECTED_PREFIX = "/api/products/dididecks";
const FORBIDDEN = ["/api/v1"];
const SECRET_PATTERNS = [
  "DATABASE_URL", "POSTGRES", "STRIPE_SECRET", "sk_live", "sk_test",
  "OPENAI_API_KEY", "PRIVATE_KEY", "SECRET_KEY", "JWT_SECRET"
];

const expectedRoutes = [
  "/", "/dashboard", "/decks", "/decks/new", "/decks/[deckId]",
  "/decks/[deckId]/editor", "/decks/[deckId]/map", "/decks/[deckId]/smart-edit",
  "/decks/[deckId]/rebuild", "/decks/[deckId]/review-matrix", "/decks/[deckId]/scroll",
  "/decks/[deckId]/play", "/decks/[deckId]/print", "/decks/[deckId]/versions",
  "/decks/[deckId]/exports", "/decks/[deckId]/access", "/billing", "/auth/sign-in",
  "/legal/privacy", "/legal/terms"
];

const expectedConcepts = [
  "Deck", "DeckSlide", "DeckSlideVariant", "DeckBlock", "PersistentField", "FieldUsage",
  "ChangeRequest", "RebuildJob", "DeckVersion", "AuditLog", "DeckExport", "DeckShareLink",
  "SurfaceReview", "DeckEditorViewModel"
];

const report = {
  blockers: [],
  warnings: [],
  architecture_drift: [],
  security_findings: [],
  info: [],
};

function exists(p) { return fs.existsSync(path.join(ROOT, p)); }
function read(p) { return fs.readFileSync(path.join(ROOT, p), "utf8"); }
function walk(dir, files = []) {
  const full = path.join(ROOT, dir);
  if (!fs.existsSync(full)) return files;
  for (const entry of fs.readdirSync(full, { withFileTypes: true })) {
    if (["node_modules", ".next", "dist", "build", "coverage", ".git"].includes(entry.name)) continue;
    const rel = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(rel, files);
    else files.push(rel);
  }
  return files;
}

function routeFromPage(file) {
  if (!file.startsWith("app/") || !file.endsWith("/page.tsx")) return null;
  let route = file.replace(/^app/, "").replace(/\/page\.tsx$/, "");
  if (route === "") return "/";
  return route;
}

if (!exists("package.json")) {
  report.blockers.push("Missing package.json.");
} else {
  const pkg = JSON.parse(read("package.json"));
  if (!pkg.scripts?.build) report.blockers.push("Missing build script.");
  if (!pkg.scripts?.typecheck) report.warnings.push("Missing typecheck script. Add `tsc --noEmit`.");
  if (!pkg.scripts?.lint) report.warnings.push("Missing lint script.");
}

const actualRoutes = new Set(walk("app").map(routeFromPage).filter(Boolean));
for (const route of expectedRoutes) {
  if (!actualRoutes.has(route)) report.architecture_drift.push(`Expected route missing: ${route}`);
}
for (const route of actualRoutes) {
  if (!expectedRoutes.includes(route)) report.info.push(`Extra route present: ${route}`);
}

const sourceFiles = walk("app").concat(walk("components"), walk("lib"), walk("data"));
const combined = sourceFiles.map(f => `${f}\n${read(f)}`).join("\n");
for (const prefix of FORBIDDEN) {
  if (combined.includes(prefix)) report.blockers.push(`Forbidden DidiDecks API prefix found: ${prefix}`);
}
if (!combined.includes(EXPECTED_PREFIX)) {
  report.architecture_drift.push(`Expected API prefix not found in source: ${EXPECTED_PREFIX}`);
}
for (const secret of SECRET_PATTERNS) {
  if (combined.includes(secret)) report.security_findings.push(`Potential frontend secret marker found: ${secret}`);
}

const typeText = walk("lib").filter(f => f.includes("types") || f.endsWith(".ts")).map(f => read(f)).join("\n");
for (const concept of expectedConcepts) {
  if (!typeText.includes(concept)) report.architecture_drift.push(`Expected concept missing from types/lib: ${concept}`);
}

const hasBlockBinding = combined.includes("dataBindingKey") || combined.includes("data_binding_key");
if (!hasBlockBinding) report.architecture_drift.push("Block model does not appear to support persistent field binding.");

const readiness = report.security_findings.length || report.blockers.length
  ? "NOT_READY"
  : report.architecture_drift.length || report.warnings.length
    ? "PARTIAL"
    : "READY";

console.log("Repository Verification Report");
console.log(JSON.stringify({ readiness_status: readiness, ...report }, null, 2));

if (readiness === "NOT_READY") process.exitCode = 1;
