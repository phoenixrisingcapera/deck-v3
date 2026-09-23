#!/usr/bin/env python3
"""
graphiti_clients.py

Shared construction of the Graphiti stack for this kit: Anthropic for
entity/edge extraction, Ollama for local embeddings, Neo4j for storage.

Importable module (underscored filename) — the ingester and the query
script both build their client from here so they can never drift into
using different embedders against the same graph, which would silently
poison cosine search.

Three things here are load-bearing and non-obvious:

1. `EMBEDDING_DIM` must be in the environment BEFORE `graphiti_core` is
   imported. `graphiti_core/embedder/client.py` reads it at module import
   time into a constant that `search/search.py:152` uses to build the
   zero-vector fallback. Set it late and the fallback is 1024-wide while
   your real vectors are 384-wide.

2. The default cross-encoder is constructed eagerly. `graphiti.py:227`
   does a bare `OpenAIRerankerClient()` when you pass `cross_encoder=None`,
   and that raises on a missing OPENAI_API_KEY even though reranking is
   only ever used at search time. We pass an explicit one to stay off
   OpenAI entirely.

3. Ollama compatibility works because `OpenAIEmbedder.create()` truncates
   client-side (`result.data[0].embedding[: self.config.embedding_dim]`)
   instead of sending a `dimensions` request parameter. Ollama's
   OpenAI-compatible `/v1/embeddings` would reject the latter.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Defaults. Every one is overridable by environment variable; see .env.example.
# ---------------------------------------------------------------------------

DEFAULT_NEO4J_URI = "bolt://localhost:7687"
DEFAULT_NEO4J_USER = "neo4j"
DEFAULT_NEO4J_PASSWORD = "losslessgraph"

# Extraction is a high-volume structured-output job, so Haiku is the right tier.
#
# NOTE: graphiti-core's own DEFAULT_MODEL is `claude-haiku-4-5-latest`
# (llm_client/anthropic_client.py:68) and that alias does NOT resolve — the API
# returns 404 not_found_error on every call. Pin the dated model ID instead.
DEFAULT_ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_ANTHROPIC_SMALL_MODEL = "claude-haiku-4-5-20251001"

# all-minilm is the same 384-dim MiniLM family the Chroma collections
# already use, which keeps the two indexes comparable.
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434/v1"
# Local extraction. Graphiti bills an LLM call per entity/edge extraction and
# per dedup comparison, and dedup context grows with the graph — a full
# changelog pass ran ~$0.58/episode on hosted Haiku. Pointing the LLM at a
# local OpenAI-compatible endpoint (Ollama, LM Studio) makes that free.
# Uses graphiti's *generic* OpenAI client, which does not assume strict
# structured-output support the way the hosted clients do.
DEFAULT_LOCAL_LLM_MODEL = "qwen3-coder:30b"
DEFAULT_EMBED_MODEL = "all-minilm"
DEFAULT_EMBED_DIM = 384


@dataclass
class GraphitiSettings:
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    anthropic_api_key: str | None
    anthropic_model: str
    anthropic_small_model: str
    llm_provider: str
    llm_base_url: str
    embed_base_url: str
    embed_model: str
    embed_dim: int
    cross_encoder: str
    semaphore_limit: int

    @classmethod
    def from_env(cls) -> "GraphitiSettings":
        return cls(
            neo4j_uri=os.getenv("NEO4J_URI", DEFAULT_NEO4J_URI),
            neo4j_user=os.getenv("NEO4J_USER", DEFAULT_NEO4J_USER),
            neo4j_password=os.getenv("NEO4J_PASSWORD", DEFAULT_NEO4J_PASSWORD),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
            anthropic_model=os.getenv("GRAPHITI_LLM_MODEL", DEFAULT_ANTHROPIC_MODEL),
            anthropic_small_model=os.getenv(
                "GRAPHITI_LLM_SMALL_MODEL", DEFAULT_ANTHROPIC_SMALL_MODEL
            ),
            llm_provider=os.getenv("GRAPHITI_LLM_PROVIDER", "anthropic").lower(),
            llm_base_url=os.getenv("GRAPHITI_LLM_BASE_URL", DEFAULT_OLLAMA_BASE_URL),
            embed_base_url=os.getenv("GRAPHITI_EMBED_BASE_URL", DEFAULT_OLLAMA_BASE_URL),
            embed_model=os.getenv("GRAPHITI_EMBED_MODEL", DEFAULT_EMBED_MODEL),
            embed_dim=int(os.getenv("EMBEDDING_DIM", DEFAULT_EMBED_DIM)),
            cross_encoder=os.getenv("GRAPHITI_CROSS_ENCODER", "passthrough").lower(),
            semaphore_limit=int(os.getenv("SEMAPHORE_LIMIT", "8")),
        )


def load_dotenv(path) -> None:
    """Minimal .env reader. Avoids adding python-dotenv for six lines of
    parsing. Existing environment variables always win, so an exported
    ANTHROPIC_API_KEY beats whatever is in the file."""
    from pathlib import Path

    p = Path(path)
    if not p.exists():
        return
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


def quiet_neo4j_notifications() -> None:
    """Neo4j 5.x emits a WARNING-level notification for every query touching a
    property key that doesn't exist yet — `fact_embedding`, `name_embedding`,
    `episodes`. On an empty or freshly-reset graph that is one multi-line dump
    per query leg, which buries the actual output. They are advisory, and they
    stop once data lands. Errors still surface."""
    import logging

    logging.getLogger("neo4j.notifications").setLevel(logging.ERROR)


def load_env_chain(kit_root) -> list:
    """Load .env from the kit, then walk up to the monorepo root.

    Shared secrets in this tree live at the monorepo root .env — that is where
    ANTHROPIC_API_KEY actually is. Reading only the kit's own .env made a key
    that had been present for months look missing.

    Order matters: the kit's .env is read FIRST so a repo-local override wins,
    because `load_dotenv` never clobbers a value already set. An exported shell
    variable still beats both. Returns the files it actually read.
    """
    from pathlib import Path

    kit = Path(kit_root).resolve()
    candidates = [kit / ".env"]
    for parent in kit.parents:
        candidates.append(parent / ".env")
        if (parent / ".git").exists() and parent.name == "lossless-monorepo":
            break

    loaded = []
    for c in candidates:
        if c.exists():
            load_dotenv(c)
            loaded.append(str(c))
    return loaded


def prepare_environment(settings: GraphitiSettings) -> None:
    """Set the env vars graphiti_core reads at import time. MUST be called
    before any `graphiti_core` import — see point 1 in the module docstring."""
    os.environ["EMBEDDING_DIM"] = str(settings.embed_dim)
    os.environ["SEMAPHORE_LIMIT"] = str(settings.semaphore_limit)
    quiet_neo4j_notifications()


def build_llm_client(settings: GraphitiSettings, require_key: bool = True):
    """`require_key=False` is for read-only callers. Search touches the
    embedder, Neo4j and the cross-encoder but never the LLM, so a query should
    not demand an extraction key. Graphiti's constructor still wants a client
    object, so we hand it one wired to a placeholder that is never called."""
    from graphiti_core.llm_client.anthropic_client import AnthropicClient
    from graphiti_core.llm_client.config import LLMConfig

    if settings.llm_provider in ("ollama", "lmstudio", "local", "openai-generic"):
        from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient

        model = os.getenv("GRAPHITI_LLM_MODEL", DEFAULT_LOCAL_LLM_MODEL)
        small = os.getenv("GRAPHITI_LLM_SMALL_MODEL", model)
        return OpenAIGenericClient(
            config=LLMConfig(
                api_key=os.getenv("GRAPHITI_LLM_API_KEY", "local-no-key-needed"),
                base_url=settings.llm_base_url,
                model=model,
                small_model=small,
            )
        )

    if not settings.anthropic_api_key and not require_key:
        return AnthropicClient(
            config=LLMConfig(
                api_key="placeholder-unused-for-read-only-operations",
                model=settings.anthropic_model,
                small_model=settings.anthropic_small_model,
            )
        )

    if not settings.anthropic_api_key:
        raise SystemExit(
            "error: ANTHROPIC_API_KEY is not set.\n"
            "  Graphiti needs a raw Anthropic API key for entity extraction — it\n"
            "  cannot borrow Claude Code's session auth. Put it in\n"
            "  context-vigilance-kit/.env (gitignored) or export it.\n"
            "  Get one at https://console.anthropic.com/settings/keys"
        )

    return AnthropicClient(
        config=LLMConfig(
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_model,
            small_model=settings.anthropic_small_model,
        )
    )


def build_embedder(settings: GraphitiSettings):
    """OpenAIEmbedder pointed at Ollama. The api_key is a required-but-unused
    placeholder — Ollama ignores it, but the OpenAI SDK refuses to construct
    a client without one."""
    from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig

    return OpenAIEmbedder(
        config=OpenAIEmbedderConfig(
            api_key=os.getenv("GRAPHITI_EMBED_API_KEY", "ollama"),
            base_url=settings.embed_base_url,
            embedding_model=settings.embed_model,
            embedding_dim=settings.embed_dim,
        )
    )


def build_cross_encoder(settings: GraphitiSettings):
    """Reranking is a search-time concern that ingest never touches, but
    Graphiti constructs it eagerly. Default to a passthrough so no reranking
    API key is ever required; opt into local BGE with
    GRAPHITI_CROSS_ENCODER=bge if you want real reranking."""
    if settings.cross_encoder == "bge":
        from graphiti_core.cross_encoder.bge_reranker_client import BGERerankerClient

        return BGERerankerClient()

    from graphiti_core.cross_encoder.client import CrossEncoderClient

    class PassthroughCrossEncoder(CrossEncoderClient):
        """Preserves input order with descending scores. Search recipes that
        fuse with RRF or MMR never call this; recipes ending in
        `_cross_encoder` will effectively fall back to the candidate order
        they were given. That is a real limitation, not a hidden one."""

        async def rank(self, query: str, passages: list[str]) -> list[tuple[str, float]]:
            n = len(passages)
            return [(p, (n - i) / n) for i, p in enumerate(passages)]

    return PassthroughCrossEncoder()


def build_graphiti(settings: GraphitiSettings, require_llm: bool = True):
    """Fully-wired Graphiti instance. Call `prepare_environment` first.
    Pass `require_llm=False` for read-only use — see `build_llm_client`."""
    from graphiti_core import Graphiti

    return Graphiti(
        uri=settings.neo4j_uri,
        user=settings.neo4j_user,
        password=settings.neo4j_password,
        llm_client=build_llm_client(settings, require_key=require_llm),
        embedder=build_embedder(settings),
        cross_encoder=build_cross_encoder(settings),
    )


def describe(settings: GraphitiSettings) -> str:
    local = settings.llm_provider in ("ollama", "lmstudio", "local", "openai-generic")
    if local:
        model = os.getenv("GRAPHITI_LLM_MODEL", DEFAULT_LOCAL_LLM_MODEL)
        llm_line = (
            f"  llm:         {settings.llm_provider} / {model} "
            f"@ {settings.llm_base_url}  [local, no billing]"
        )
    else:
        key = "set" if settings.anthropic_api_key else "MISSING"
        llm_line = f"  llm:         anthropic / {settings.anthropic_model}  [api key: {key}]"
    return (
        f"  neo4j:       {settings.neo4j_uri} (user={settings.neo4j_user})\n"
        f"{llm_line}\n"
        f"  embedder:    {settings.embed_model} @ {settings.embed_base_url} "
        f"({settings.embed_dim}-dim)\n"
        f"  reranker:    {settings.cross_encoder}\n"
        f"  concurrency: {settings.semaphore_limit}"
    )
