#!/usr/bin/env bash
# ingest-all.sh — run every Chroma ingester in the kit, in sequence.
#
# Default (no flags): runs the two safe-to-rerun rollups.
#   - ingest-to-chroma.py                    → context-vigilance-corpus
#                                              (context-v rollup, sources.md-driven)
#   - ingest-changelogs-to-chroma.py         → lossless-changelog
#                                              (every <repo>/changelog/ across the tree)
#
# Opt-in (privacy-sensitive — uses ~/.claude/projects transcripts):
#   --with-sessions                          → claude-code-sessions
#                                              (one doc per message turn)
#   --with-traces                            → claude-code-tool-traces
#                                              (one doc per tool invocation)
#   --with-claude                            → both of the above
#
# All collections live in the same .chroma/ persistent client, so the
# MCP server in .mcp.json exposes them all to Claude Code at once.
#
# Usage:
#   ./scripts/ingest-all.sh                            # changelog + context-v
#   ./scripts/ingest-all.sh --with-claude              # + sessions + traces
#   ./scripts/ingest-all.sh --reset                    # drop+recreate every selected collection
#   ./scripts/ingest-all.sh --dry-run                  # changelog + claude only
#   ./scripts/ingest-all.sh --only-context-v
#   ./scripts/ingest-all.sh --only-changelog
#   ./scripts/ingest-all.sh --only-claude              # sessions + traces, skip the others
#   PYTHON=python3.11 ./scripts/ingest-all.sh          # override interpreter

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KIT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

PYTHON="${PYTHON:-python3}"
if [[ -x "$KIT_ROOT/.venv/bin/python" ]]; then
    PYTHON="$KIT_ROOT/.venv/bin/python"
fi

RESET_FLAG=""
DRY_RUN_FLAG=""
SKIP_CONTEXT_V=0
SKIP_CHANGELOG=0
WITH_SESSIONS=0
WITH_TRACES=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --reset)
            RESET_FLAG="--reset"
            ;;
        --dry-run)
            DRY_RUN_FLAG="--dry-run"
            ;;
        --only-context-v)
            SKIP_CHANGELOG=1
            ;;
        --only-changelog)
            SKIP_CONTEXT_V=1
            ;;
        --only-claude)
            SKIP_CONTEXT_V=1
            SKIP_CHANGELOG=1
            WITH_SESSIONS=1
            WITH_TRACES=1
            ;;
        --with-sessions)
            WITH_SESSIONS=1
            ;;
        --with-traces)
            WITH_TRACES=1
            ;;
        --with-claude)
            WITH_SESSIONS=1
            WITH_TRACES=1
            ;;
        -h|--help)
            sed -n '2,30p' "$0"
            exit 0
            ;;
        *)
            echo "unknown option: $1" >&2
            echo "see --help" >&2
            exit 2
            ;;
    esac
    shift
done

if [[ $SKIP_CONTEXT_V -eq 0 ]]; then
    echo "==> context-v rollup     → collection: context-vigilance-corpus"
    # The existing context-v ingester doesn't support --dry-run, so we
    # only forward --reset to it.
    "$PYTHON" "$SCRIPT_DIR/ingest-to-chroma.py" $RESET_FLAG
    echo
fi

if [[ $SKIP_CHANGELOG -eq 0 ]]; then
    echo "==> changelog rollup     → collection: lossless-changelog"
    "$PYTHON" "$SCRIPT_DIR/ingest-changelogs-to-chroma.py" $RESET_FLAG $DRY_RUN_FLAG
    echo
fi

if [[ $WITH_SESSIONS -eq 1 && $WITH_TRACES -eq 1 ]]; then
    echo "==> claude transcripts   → collections: claude-code-sessions, claude-code-tool-traces"
    "$PYTHON" "$SCRIPT_DIR/ingest-claude-sessions-to-chroma.py" $RESET_FLAG $DRY_RUN_FLAG
    echo
elif [[ $WITH_SESSIONS -eq 1 ]]; then
    echo "==> claude sessions      → collection: claude-code-sessions"
    "$PYTHON" "$SCRIPT_DIR/ingest-claude-sessions-to-chroma.py" $RESET_FLAG $DRY_RUN_FLAG --only sessions
    echo
elif [[ $WITH_TRACES -eq 1 ]]; then
    echo "==> claude tool traces   → collection: claude-code-tool-traces"
    "$PYTHON" "$SCRIPT_DIR/ingest-claude-sessions-to-chroma.py" $RESET_FLAG $DRY_RUN_FLAG --only traces
    echo
fi

echo "==> done"
