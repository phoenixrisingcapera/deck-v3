#!/usr/bin/env python3
"""
ingest-claude-sessions-to-chroma.py

Single-pass JSONL ingestion of Claude Code session transcripts. Produces
two Chroma collections from the same parse:

  - claude-code-sessions       one document per user/assistant message turn
                               metadata: session_id, project_path, turn_role,
                               timestamp, cwd, git_branch
  - claude-code-tool-traces    one document per tool invocation
                               metadata: tool_name, is_error, session_id,
                               tool_use_id, timestamp, cwd

Source: ~/.claude/projects/<encoded>/*.jsonl

Privacy
-------
Conservative regex redaction runs before any text is embedded:
  - lines matching ENV_VAR_NAME=value     value replaced
  - known token prefixes                  sk-, sk-ant-, ghp_, AKIA, Bearer
  - x-api-key headers                     value replaced
  - Read/Edit/Write of .env*/.secrets*    output replaced wholesale

The redactor is intentionally over-eager — false positives are fine.
Anything matching an env-var-shaped line is replaced even if it was just
documentation.

Idempotency
-----------
Session IDs:  {session_id}::{message_uuid}
Trace IDs:    {tool_use_id}
Both are stable across re-runs. Upsert handles edited / regenerated
transcripts the same as new ones.

Usage
-----
    python scripts/ingest-claude-sessions-to-chroma.py
    python scripts/ingest-claude-sessions-to-chroma.py --reset
    python scripts/ingest-claude-sessions-to-chroma.py --dry-run
    python scripts/ingest-claude-sessions-to-chroma.py --only sessions
    python scripts/ingest-claude-sessions-to-chroma.py --only traces
    python scripts/ingest-claude-sessions-to-chroma.py --project-filter ai-labs
    python scripts/ingest-claude-sessions-to-chroma.py --query "git rebase failure"
    python scripts/ingest-claude-sessions-to-chroma.py --query "git rebase failure" \
        --collection claude-code-tool-traces
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

import chromadb


KIT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CHROMA_PATH = KIT_ROOT / ".chroma"
DEFAULT_PROJECTS_DIR = Path.home() / ".claude" / "projects"
SESSIONS_COLLECTION = "claude-code-sessions"
TRACES_COLLECTION = "claude-code-tool-traces"
EMBED_TEXT_CAP = 6000  # chars; the default embedder caps tokens around 512 anyway

# ─────── Redaction ──────────────────────────────────────────────────────

# ENV_VAR_NAME=value lines (KEY in screaming snake case + assignment).
# Replaces only the value, leaving the name visible so the record is still
# informative ("we read NEXT_PUBLIC_FOO" is fine to keep).
ENV_VAR_LINE_RE = re.compile(
    r"(?m)^([A-Z][A-Z0-9_]{2,})\s*=\s*[^\n]+$"
)

# Specific token prefixes. Order: more specific first (sk-ant- before sk-).
TOKEN_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"), "[REDACTED_ANTHROPIC_KEY]"),
    (re.compile(r"sk-proj-[A-Za-z0-9_\-]{20,}"), "[REDACTED_OPENAI_KEY]"),
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), "[REDACTED_OPENAI_KEY]"),
    (re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"), "[REDACTED_GITHUB_TOKEN]"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "[REDACTED_AWS_ACCESS_KEY]"),
    (re.compile(r"Bearer\s+[A-Za-z0-9._\-]+"), "Bearer [REDACTED]"),
    (re.compile(r"(?i)x-api-key:\s*\S+"), "x-api-key: [REDACTED]"),
]

# Path detection for env / secrets files. Matches `.env`, `.env.local`,
# `.env.production`, `.secrets`, `secrets/file`.
ENV_PATH_RE = re.compile(r"(?:^|/)\.(?:env|secrets)(?:\.[^/\s]+)?(?:/|$)")
SECRETS_DIR_RE = re.compile(r"(?:^|/)secrets/")


def redact(text: str) -> str:
    if not text:
        return text
    text = ENV_VAR_LINE_RE.sub(lambda m: f"{m.group(1)}=[REDACTED]", text)
    for pat, repl in TOKEN_PATTERNS:
        text = pat.sub(repl, text)
    return text


def looks_like_secret_path(p) -> bool:
    if not isinstance(p, str) or not p:
        return False
    return bool(ENV_PATH_RE.search(p) or SECRETS_DIR_RE.search(p))


def tool_call_reads_secrets(tool_name: str, raw_input) -> bool:
    """True when the tool invocation is reading/writing a likely-secret
    file. Triggers wholesale redaction of the tool_result content."""
    if tool_name not in ("Read", "Edit", "Write", "NotebookEdit"):
        return False
    if not isinstance(raw_input, dict):
        return False
    return looks_like_secret_path(raw_input.get("file_path"))


# ─────── JSONL parsing ──────────────────────────────────────────────────


def iter_jsonl(path: Path):
    """Yield (line_no, parsed_obj) for each non-empty, JSON-parseable line."""
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield line_no, json.loads(line)
            except json.JSONDecodeError:
                continue


def extract_text_items(content) -> str:
    """Concatenate text-typed items from a message.content list (or
    return the string directly when content is already a string)."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for c in content:
        if not isinstance(c, dict):
            continue
        if c.get("type") == "text":
            t = c.get("text", "")
            if isinstance(t, str) and t:
                parts.append(t)
    return "\n\n".join(parts)


def stringify_tool_output(raw) -> str:
    """tool_result content can be a string or a list of typed items."""
    if isinstance(raw, str):
        return raw
    if isinstance(raw, list):
        out: list[str] = []
        for item in raw:
            if isinstance(item, dict):
                t = item.get("text") or item.get("content") or ""
                out.append(t if isinstance(t, str) else str(t))
            else:
                out.append(str(item))
        return "\n".join(out)
    return "" if raw is None else str(raw)


def parse_file(path: Path):
    """Yield (session_records, trace_records) for one JSONL file."""
    pending: dict[str, dict] = {}  # tool_use_id → in-flight trace record
    sessions: list[dict] = []
    traces: list[dict] = []

    for line_no, obj in iter_jsonl(path):
        kind = obj.get("type")
        if kind not in ("user", "assistant"):
            continue

        msg = obj.get("message") or {}
        if not isinstance(msg, dict):
            continue
        role = msg.get("role", kind)
        content = msg.get("content")

        common = {
            "session_id": obj.get("sessionId") or "",
            "cwd": obj.get("cwd") or "",
            "timestamp": obj.get("timestamp") or "",
            "git_branch": obj.get("gitBranch") or "",
            "line_no": line_no,
        }

        text = extract_text_items(content)
        text = redact(text).strip()
        if text:
            sessions.append({
                "uuid": obj.get("uuid") or "",
                "role": role,
                "text": text[:EMBED_TEXT_CAP],
                **common,
            })

        if not isinstance(content, list):
            continue

        for c in content:
            if not isinstance(c, dict):
                continue
            ct = c.get("type")
            if ct == "tool_use":
                tool_use_id = c.get("id") or ""
                if not tool_use_id:
                    continue
                tool_name = c.get("name") or ""
                raw_input = c.get("input")
                redact_result = tool_call_reads_secrets(tool_name, raw_input)
                input_text = redact(
                    json.dumps(raw_input, default=str, ensure_ascii=False)
                )
                pending[tool_use_id] = {
                    "tool_use_id": tool_use_id,
                    "tool_name": tool_name,
                    "input": input_text[:EMBED_TEXT_CAP],
                    "redact_result": redact_result,
                    **common,
                }
            elif ct == "tool_result":
                tu_id = c.get("tool_use_id")
                if not tu_id or tu_id not in pending:
                    continue
                record = pending.pop(tu_id)
                is_error = bool(c.get("is_error"))
                output_text = stringify_tool_output(c.get("content"))
                if record["redact_result"]:
                    output_text = "[REDACTED_SECRETS_FILE_CONTENTS]"
                else:
                    output_text = redact(output_text)
                record.update({
                    "output": output_text[:EMBED_TEXT_CAP],
                    "is_error": is_error,
                    "result_timestamp": obj.get("timestamp") or "",
                })
                # Strip the internal-only flag before emission
                record.pop("redact_result", None)
                traces.append(record)

    # Any tool_use without a matching tool_result (mid-session truncation).
    # Emit them with empty output so the invocation is still searchable.
    for tu_id, record in pending.items():
        record.update({"output": "", "is_error": False, "result_timestamp": ""})
        record.pop("redact_result", None)
        traces.append(record)

    return sessions, traces


# ─────── Doc / metadata builders ────────────────────────────────────────


def build_session_doc(rec: dict, project_dir: str) -> tuple[str, str, dict]:
    sid = rec.get("session_id") or "?"
    uuid = rec.get("uuid") or f"line{rec.get('line_no', 0)}"
    cid = f"{sid}::{uuid}"
    document = f"[{rec.get('role', 'user')}] {rec.get('text', '')}"
    metadata = {
        "session_id": sid,
        "project_dir_encoded": project_dir,
        "project_path": rec.get("cwd") or "",
        "turn_role": rec.get("role") or "",
        "timestamp": rec.get("timestamp") or "",
        "git_branch": rec.get("git_branch") or "",
        "line_no": rec.get("line_no", 0),
        "kind": "session-turn",
    }
    return cid, document[:EMBED_TEXT_CAP], metadata


def build_trace_doc(rec: dict, project_dir: str) -> tuple[str, str, dict]:
    sid = rec.get("session_id") or "?"
    tu_id = rec.get("tool_use_id") or f"line{rec.get('line_no', 0)}"
    cid = tu_id if tu_id != f"line{rec.get('line_no', 0)}" else f"{sid}::{tu_id}::trace"
    outcome = "error" if rec.get("is_error") else "ok"
    document = (
        f"tool: {rec.get('tool_name', '')}\n"
        f"outcome: {outcome}\n"
        f"input: {rec.get('input', '')}\n"
        f"output: {rec.get('output', '')}"
    )
    metadata = {
        "tool_use_id": tu_id,
        "tool_name": rec.get("tool_name") or "",
        "is_error": bool(rec.get("is_error")),
        "session_id": sid,
        "project_dir_encoded": project_dir,
        "project_path": rec.get("cwd") or "",
        "timestamp": rec.get("timestamp") or "",
        "result_timestamp": rec.get("result_timestamp") or "",
        "git_branch": rec.get("git_branch") or "",
        "line_no": rec.get("line_no", 0),
        "kind": "tool-trace",
    }
    return cid, document[:EMBED_TEXT_CAP], metadata


# ─────── Tree walk ──────────────────────────────────────────────────────


def find_jsonl_files(projects_dir: Path, project_filter: str | None):
    """Return list of (jsonl_path, project_encoded_dir_name)."""
    out: list[tuple[Path, str]] = []
    if not projects_dir.exists():
        return out
    for project_subdir in sorted(projects_dir.iterdir()):
        if not project_subdir.is_dir():
            continue
        encoded = project_subdir.name
        if project_filter and project_filter not in encoded:
            continue
        for jf in sorted(project_subdir.glob("*.jsonl")):
            out.append((jf, encoded))
    return out


# ─────── Ingest orchestration ───────────────────────────────────────────


def ingest(args) -> dict:
    files = find_jsonl_files(args.projects_dir, args.project_filter)
    if not files:
        print(f"warn: no JSONL files under {args.projects_dir}", file=sys.stderr)
        return {"files_processed": 0}

    want_sessions = args.only != "traces"
    want_traces = args.only != "sessions"

    client = None
    sessions_col = None
    traces_col = None
    if not args.dry_run:
        client = chromadb.PersistentClient(path=str(args.chroma_path))
        if args.reset:
            if want_sessions:
                try: client.delete_collection(SESSIONS_COLLECTION)
                except Exception: pass
            if want_traces:
                try: client.delete_collection(TRACES_COLLECTION)
                except Exception: pass
        if want_sessions:
            sessions_col = client.get_or_create_collection(
                SESSIONS_COLLECTION,
                metadata={"description": "Claude Code session transcripts — one doc per message turn."},
            )
        if want_traces:
            traces_col = client.get_or_create_collection(
                TRACES_COLLECTION,
                metadata={"description": "Claude Code per-tool-call records — debugging memory."},
            )

    today = dt.date.today().isoformat()
    files_processed = 0
    sessions_emitted = 0
    traces_emitted = 0
    sessions_buf: list = []
    traces_buf: list = []
    sample_session = None
    sample_trace = None

    def flush(col, buf):
        if not buf or args.dry_run:
            n = len(buf)
            buf.clear()
            return n
        for _, _, m in buf:
            m["ingested_at"] = today
        col.upsert(
            ids=[r[0] for r in buf],
            documents=[r[1] for r in buf],
            metadatas=[r[2] for r in buf],
        )
        n = len(buf)
        buf.clear()
        return n

    for path, project_dir in files:
        try:
            session_recs, trace_recs = parse_file(path)
        except Exception as e:
            print(f"warn: failed to parse {path}: {e}", file=sys.stderr)
            continue
        files_processed += 1

        if want_sessions:
            for rec in session_recs:
                doc = build_session_doc(rec, project_dir)
                sessions_buf.append(doc)
                if sample_session is None:
                    sample_session = doc
                if len(sessions_buf) >= args.batch_size:
                    sessions_emitted += flush(sessions_col, sessions_buf)
        if want_traces:
            for rec in trace_recs:
                doc = build_trace_doc(rec, project_dir)
                traces_buf.append(doc)
                if sample_trace is None:
                    sample_trace = doc
                if len(traces_buf) >= args.batch_size:
                    traces_emitted += flush(traces_col, traces_buf)

    sessions_emitted += flush(sessions_col, sessions_buf)
    traces_emitted += flush(traces_col, traces_buf)

    stats: dict = {
        "files_processed": files_processed,
        "sessions_emitted": sessions_emitted,
        "traces_emitted": traces_emitted,
    }
    if args.dry_run:
        stats["dry_run"] = True
        stats["sample_session"] = sample_session
        stats["sample_trace"] = sample_trace
    else:
        if sessions_col is not None:
            stats["sessions_collection_size"] = sessions_col.count()
        if traces_col is not None:
            stats["traces_collection_size"] = traces_col.count()
    return stats


# ─────── Query helper ───────────────────────────────────────────────────


def query_demo(chroma_path: Path, collection_name: str, q: str, n: int = 5,
               where: dict | None = None) -> None:
    client = chromadb.PersistentClient(path=str(chroma_path))
    collection = client.get_collection(collection_name)
    result = collection.query(query_texts=[q], n_results=n, where=where)
    print(f"\nquery: {q!r}   collection: {collection_name}")
    for rank, (doc_id, dist, meta) in enumerate(
        zip(result["ids"][0], result["distances"][0], result["metadatas"][0])
    ):
        if collection_name == TRACES_COLLECTION:
            label = f"[{meta.get('tool_name')}] err={meta.get('is_error')}"
        else:
            label = f"[{meta.get('turn_role')}]"
        print(
            f"  #{rank + 1}  d={dist:.4f}  {label}  "
            f"{meta.get('project_dir_encoded', '')[:60]}  "
            f"@{(meta.get('timestamp') or '')[:19]}"
        )


# ─────── CLI ────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chroma-path", type=Path, default=DEFAULT_CHROMA_PATH)
    parser.add_argument("--projects-dir", type=Path, default=DEFAULT_PROJECTS_DIR)
    parser.add_argument("--project-filter", type=str, default=None,
                        help="Substring filter on encoded project dir name.")
    parser.add_argument("--only", choices=["sessions", "traces"], default=None,
                        help="Only write one of the two collections.")
    parser.add_argument("--reset", action="store_true",
                        help="Drop and recreate the target collection(s).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse and report counts without writing to Chroma.")
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--query", type=str, default=None,
                        help="Skip ingest; query an existing collection.")
    parser.add_argument("--collection", type=str, default=SESSIONS_COLLECTION,
                        help=f"Which collection to query (default: {SESSIONS_COLLECTION}).")
    args = parser.parse_args()

    if args.query:
        query_demo(args.chroma_path, args.collection, args.query)
        return 0

    if not args.projects_dir.exists():
        print(f"error: projects dir does not exist: {args.projects_dir}",
              file=sys.stderr)
        return 2

    stats = ingest(args)

    if stats.get("dry_run"):
        print(f"[dry-run] files processed:        {stats['files_processed']}")
        print(f"[dry-run] sessions extracted:     {stats['sessions_emitted']}")
        print(f"[dry-run] traces extracted:       {stats['traces_emitted']}")
        if stats.get("sample_session"):
            sid, sdoc, smeta = stats["sample_session"]
            print(f"\n[dry-run] sample session record:")
            print(f"  id:       {sid}")
            print(f"  metadata: {smeta}")
            print(f"  doc[0:300]: {sdoc[:300]!r}")
        if stats.get("sample_trace"):
            tid, tdoc, tmeta = stats["sample_trace"]
            print(f"\n[dry-run] sample trace record:")
            print(f"  id:       {tid}")
            print(f"  metadata: {tmeta}")
            print(f"  doc[0:400]: {tdoc[:400]!r}")
        return 0

    print(f"\ningested Claude Code transcripts into Chroma at {args.chroma_path}")
    print(f"  files processed:       {stats['files_processed']}")
    print(f"  sessions upserted:     {stats['sessions_emitted']}")
    print(f"  traces upserted:       {stats['traces_emitted']}")
    if "sessions_collection_size" in stats:
        print(f"  sessions collection:   {stats['sessions_collection_size']}")
    if "traces_collection_size" in stats:
        print(f"  traces collection:     {stats['traces_collection_size']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
