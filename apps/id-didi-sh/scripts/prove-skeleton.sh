#!/usr/bin/env bash
# ============================================================================
# prove-skeleton.sh — increment 1's acceptance proof, as curl.
#
# Prereqs: server running (mix phx.server), user seeded:
#   mix id.seed alice@example.com "Alice Example"
#
# Proves: magic-link issue → redeem → didi_session cookie → /api/me →
# JWKS → refresh → logout → /api/me rejects.
# ============================================================================
set -euo pipefail

BASE="${BASE:-http://localhost:4000}"
EMAIL="${EMAIL:-alice@example.com}"
JAR="$(mktemp)"
trap 'rm -f "$JAR"' EXIT

step() { printf '\n\033[1m== %s\033[0m\n' "$1"; }
fail() { printf '\033[31mFAIL: %s\033[0m\n' "$1"; exit 1; }

step "1. issue magic link (dev echoes the raw token)"
ISSUE=$(curl -sS -X POST "$BASE/api/magic-links" \
  -H 'content-type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"app\":\"augment-it\",\"next\":\"/curator\"}")
echo "$ISSUE"
TOKEN=$(echo "$ISSUE" | sed -nE 's/.*"dev_token":"([^"]+)".*/\1/p')
[ -n "$TOKEN" ] || fail "no dev_token in response — is the user seeded and MIX_ENV=dev?"

step "2. redeem → session cookie set"
REDEEM=$(curl -sS -c "$JAR" -X POST "$BASE/api/magic-links/redeem" \
  -H 'content-type: application/json' -d "{\"token\":\"$TOKEN\"}")
echo "$REDEEM"
grep -q didi_session "$JAR" || fail "didi_session cookie not set"

step "2b. single-use: second redeem must 401"
CODE=$(curl -sS -o /dev/null -w '%{http_code}' -X POST "$BASE/api/magic-links/redeem" \
  -H 'content-type: application/json' -d "{\"token\":\"$TOKEN\"}")
[ "$CODE" = "401" ] || fail "expected 401 on reuse, got $CODE"
echo "reuse rejected ✓"

step "3. /api/me with the cookie"
ME=$(curl -sS -b "$JAR" "$BASE/api/me")
echo "$ME"
echo "$ME" | grep -q '"didi_id"' || fail "/api/me did not return identity"

step "4. JWKS is served (offline-verify key material)"
JWKS=$(curl -sS "$BASE/.well-known/jwks.json")
echo "$JWKS"
echo "$JWKS" | grep -q '"OKP"' || fail "JWKS missing Ed25519 key"

step "5. refresh re-mints the cookie"
curl -sS -b "$JAR" -c "$JAR" -X POST "$BASE/api/session/refresh" | grep -q refreshed \
  || fail "refresh failed"
echo "refreshed ✓"

step "6. logout, then /api/me must 401"
curl -sS -b "$JAR" -c "$JAR" -X DELETE "$BASE/api/session" >/dev/null
CODE=$(curl -sS -b "$JAR" -o /dev/null -w '%{http_code}' "$BASE/api/me")
[ "$CODE" = "401" ] || fail "expected 401 after logout, got $CODE"
echo "post-logout rejected ✓"

printf '\n\033[32mWALKING SKELETON PROVEN\033[0m\n'
