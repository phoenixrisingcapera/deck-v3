#!/usr/bin/env bash
#
# generate-og.sh — id-didi-sh OG-image generation, locked recipe.
#
# Wraps the Ideogram v3 generate API per id-didi-sh/splash/DESIGN.md's
# imagery: block. The locked channels (style_type, magic_prompt,
# rendering_speed, seed, color_palette, negative_prompt, style_reference)
# are baked into this script verbatim from DESIGN.md. The only two
# variables per invocation are the format and (optionally) a custom
# prompt. Each format has a canonical prompt baked in.
#
# Usage:
#   ./scripts/generate-og.sh <format> [custom-prompt]
#
# Formats (must match imagery.aspect_ratios in DESIGN.md):
#   banner            16x9   — OG / Twitter / Slack default
#   banner_tall       3x4    — WhatsApp / iMessage default (priority)
#   banner_tall_max   2x3    — extra-dramatic vertical
#   portrait          4x5    — LinkedIn portrait / IG feed
#   portrait_tall     9x16   — Stories / Reels / TikTok
#   square            1x1    — avatars / square fallbacks
#
# Requires:
#   - IDEOGRAM_API_KEY in env (from ~/.secrets)
#   - curl, jq
#   - Run from splash/ (the parent of scripts/, public/, DESIGN.md)
#
# Notes on style reference:
#   id-didi-sh is self-anchored on public/ogimage__Id-Didi-Sh--Default.jpg
#   (its own winning generation — see DESIGN.md's "Bootstrap — the first
#   run" section for why this project does NOT fall back to the shared
#   context-vigilance-kit reference: that image is a text-heavy poster
#   and contaminated every candidate with garbled pseudo-text).

set -euo pipefail

# ─── arg parsing ──────────────────────────────────────────────────────
if [[ $# -lt 1 ]]; then
  cat <<'EOF' >&2
Usage: ./scripts/generate-og.sh <format> [custom-prompt]

Formats:
  banner            16x9   — OG / Twitter / Slack default
  banner_tall       3x4    — WhatsApp / iMessage default (priority)
  banner_tall_max   2x3    — extra-dramatic vertical
  portrait          4x5    — LinkedIn portrait / IG feed
  portrait_tall     9x16   — Stories / Reels / TikTok
  square            1x1    — avatars / square fallbacks

Examples:
  ./scripts/generate-og.sh banner_tall
  ./scripts/generate-og.sh banner "Top 1/3 of frame is empty negative space, dark guilloche-etched sky. Bottom 2/3 contains <custom subject>."
EOF
  exit 2
fi

FORMAT="$1"
CUSTOM_PROMPT="${2:-}"

# ─── prerequisites ───────────────────────────────────────────────────
: "${IDEOGRAM_API_KEY:?IDEOGRAM_API_KEY not set in env. Run \`source ~/.secrets\` first (or invoke this script in a shell where the key is already exported).}"

command -v curl >/dev/null || { echo "curl not found" >&2; exit 1; }
command -v jq   >/dev/null || { echo "jq not found"   >&2; exit 1; }

if [[ ! -f DESIGN.md ]]; then
  echo "DESIGN.md not found. Run from splash/ directory." >&2
  exit 1
fi

# ─── format → aspect_ratio + canonical prompt ────────────────────────
#
# Prompts follow the generate-consistent-og-images skill canonical:
#   "Top 1/3 of frame is empty negative space, dark guilloche-etched
#    sky. Bottom 2/3 contains {short subject noun phrase}."
#
# Empty-region-first framing is the load-bearing rule — without it,
# the subject expands to fill the canvas and there's no overlay zone
# left for SVG site branding.
#
# Forbidden in prompts (already encoded via style_reference and
# color_palette — repeating them dilutes attention budget):
#   - color words ("copper", "verdigris", "dark" beyond the sky descriptor)
#   - texture descriptors ("guilloche", "engraved", "intaglio")
#   - aesthetic adjectives
#   - brand names
#
# Target ≤220 chars per prompt. Subject canon: safety-deposit-box-in-a-
# vault (see DESIGN.md imagery.subject_canon for the full per-format
# framing table).
case "$FORMAT" in
  banner)
    ASPECT_RATIO="16x9"
    DEFAULT_PROMPT="Top 1/3 of frame is empty negative space, dark guilloche-etched sky. Bottom 2/3 contains a vault wall lined with rows of brass deposit boxes, one open box in the foreground spilling gold coins and diamonds, a key in the lock."
    ;;
  banner_tall)
    ASPECT_RATIO="3x4"
    DEFAULT_PROMPT="Top 1/3 of frame is empty negative space, dark guilloche-etched sky. Bottom 2/3 contains an open brass safety deposit box overflowing with gold coins and loose diamonds, a key hanging from the lock, a vault wall of matching boxes at the edges."
    ;;
  banner_tall_max)
    ASPECT_RATIO="2x3"
    DEFAULT_PROMPT="Top 1/3 of frame is empty negative space, dark guilloche-etched sky. Bottom 2/3 contains a tall vault wall of brass deposit boxes converging on one open box overflowing with gold coins and diamonds, a key in the lock."
    ;;
  portrait)
    ASPECT_RATIO="4x5"
    DEFAULT_PROMPT="Top 1/3 of frame is empty negative space, dark guilloche-etched sky. Bottom 2/3 contains a close-up open brass safety deposit box overflowing with gold coins and loose diamonds, a key in the lock."
    ;;
  portrait_tall)
    ASPECT_RATIO="9x16"
    DEFAULT_PROMPT="Top 1/3 of frame is empty negative space, dark guilloche-etched sky. Bottom 2/3 contains a stacked vault wall of brass deposit boxes thinning down to one open box overflowing with gold coins and diamonds at the bottom."
    ;;
  square)
    ASPECT_RATIO="1x1"
    DEFAULT_PROMPT="Top 1/3 of frame is empty negative space, dark guilloche-etched sky. Bottom 2/3 contains an open brass safety deposit box overflowing with gold coins and loose diamonds, one neighboring vault box visible at the edge."
    ;;
  *)
    echo "Unknown format: $FORMAT" >&2
    echo "Valid formats: banner banner_tall banner_tall_max portrait portrait_tall square" >&2
    exit 2
    ;;
esac

PROMPT="${CUSTOM_PROMPT:-$DEFAULT_PROMPT}"

# ─── locked channels (from DESIGN.md imagery: block) ─────────────────
SEED="20260706"
STYLE_TYPE="AUTO"
MAGIC_PROMPT="OFF"
RENDERING_SPEED="QUALITY"
NUM_IMAGES="4"

NEGATIVE_PROMPT="text, typography, lettering, sign, plaque, banner, poster, label, logos, watermarks, central subject filling frame, photorealistic human faces, saturated, rainbow, vibrant, oversized subject, subject in top half"

# id-didi-sh credential palette — 5 weighted members. Vault-deep ground,
# copper (gold/brass) as the dominant pop, verdigris + teal as accents.
COLOR_PALETTE_JSON='{"members":[{"color_hex":"#060a08","color_weight":0.40},{"color_hex":"#d29a62","color_weight":0.25},{"color_hex":"#f3f6f2","color_weight":0.10},{"color_hex":"#4ecf95","color_weight":0.15},{"color_hex":"#4fbfae","color_weight":0.10}]}'

# ─── style reference — self-anchored, no shared bootstrap ────────────
CANONICAL_REF="public/ogimage__Id-Didi-Sh--Default.jpg"

if [[ ! -f "$CANONICAL_REF" ]]; then
  echo "Canonical style reference ($CANONICAL_REF) doesn't exist." >&2
  echo "Generate a bootstrap pass with NO style_reference_images first" >&2
  echo "(color_palette + prompt only, style_type=GENERAL), pick a winner," >&2
  echo "and save it to $CANONICAL_REF before running this script normally." >&2
  exit 1
fi
STYLE_REF_PATH="$CANONICAL_REF"

# ─── archive paths ────────────────────────────────────────────────────
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
SUBJECT_SLUG="safety-deposit-box"
RUN_DIR=".ideogram-candidates/${SUBJECT_SLUG}-${FORMAT}-${TIMESTAMP}"
mkdir -p "$RUN_DIR"

# ─── log invocation ──────────────────────────────────────────────────
echo "→ POST https://api.ideogram.ai/v1/ideogram-v3/generate"
echo "    format:          $FORMAT  ($ASPECT_RATIO)"
echo "    style_reference: $STYLE_REF_PATH"
echo "    seed:            $SEED"
echo "    num_images:      $NUM_IMAGES"
echo "    prompt:          $PROMPT"
echo "    candidates →     $RUN_DIR/"
echo ""

# ─── construct + send ────────────────────────────────────────────────
RESPONSE="$(curl -sS \
  -H "Api-Key: $IDEOGRAM_API_KEY" \
  -F "prompt=$PROMPT" \
  -F "aspect_ratio=$ASPECT_RATIO" \
  -F "style_type=$STYLE_TYPE" \
  -F "magic_prompt=$MAGIC_PROMPT" \
  -F "rendering_speed=$RENDERING_SPEED" \
  -F "seed=$SEED" \
  -F "num_images=$NUM_IMAGES" \
  -F "negative_prompt=$NEGATIVE_PROMPT" \
  -F "color_palette=$COLOR_PALETTE_JSON" \
  -F "style_reference_images=@${STYLE_REF_PATH}" \
  https://api.ideogram.ai/v1/ideogram-v3/generate)"

# Surface API errors clearly.
if echo "$RESPONSE" | jq -e '.error // .detail // .message' >/dev/null 2>&1; then
  echo "Ideogram API returned an error:" >&2
  echo "$RESPONSE" | jq . >&2
  exit 1
fi

NUM_RETURNED="$(echo "$RESPONSE" | jq '.data | length')"
if [[ "$NUM_RETURNED" -lt 1 ]]; then
  echo "Unexpected response (no images):" >&2
  echo "$RESPONSE" | jq . >&2
  exit 1
fi

# Download each image immediately — Ideogram URLs expire.
for i in $(seq 0 $((NUM_RETURNED - 1))); do
  URL="$(echo "$RESPONSE" | jq -r ".data[$i].url")"
  OUT="${RUN_DIR}/candidate-${i}.png"
  echo "→ saving $OUT"
  curl -sS -L "$URL" -o "$OUT"
done

# Save metadata so we know what was actually run.
echo "$RESPONSE" | jq . > "${RUN_DIR}/response.json"
cat > "${RUN_DIR}/request.txt" <<EOF
prompt:           $PROMPT
aspect_ratio:     $ASPECT_RATIO
style_type:       $STYLE_TYPE
magic_prompt:     $MAGIC_PROMPT
rendering_speed:  $RENDERING_SPEED
seed:             $SEED
num_images:       $NUM_IMAGES
negative_prompt:  $NEGATIVE_PROMPT
color_palette:    $COLOR_PALETTE_JSON
style_reference:  $STYLE_REF_PATH
timestamp:        $TIMESTAMP
EOF

echo ""
echo "Done. $NUM_RETURNED candidates saved to $RUN_DIR/"
echo ""
echo "Next steps:"
echo "  1. Open $RUN_DIR/ and pick a winner."
echo "  2. Save the winner as the format's canonical file:"
echo "       ffmpeg -y -i $RUN_DIR/candidate-N.png -q:v 2 -update 1 public/ogimage__Id-Didi-Sh--{Format}.jpg"
echo "       (where {Format} matches the format name above — Banner / BannerTall / Portrait / etc.)"
echo "  3. If you replace an existing canonical, archive the old one first:"
echo "       mv public/ogimage__Id-Didi-Sh--{Format}.jpg .ogimage-archive/ogimage__Id-Didi-Sh--{Format}--\$(date +%Y-%m-%d).jpg"
echo "  4. Re-run the overlay-svg-text skill to composite the eyebrow/h1/note back on."
