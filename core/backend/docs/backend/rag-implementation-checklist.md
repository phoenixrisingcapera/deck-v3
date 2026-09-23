# RAG implementation checklist

This checklist turns the backend RAG plan into concrete work items for `deck-backend-rescue`.
The backend owns retrieval truth. The frontend only consumes readiness, answers, and citations.

## 1. Core architecture

- [ ] Keep RAG as two flows: ingestion and query
- [ ] Keep parsing, chunking, embedding, indexing, retrieval, reranking, and answer generation separate
- [ ] Use backend workers for expensive work; do not do embedding or indexing inline in request handlers
- [ ] Preserve provenance for every chunk and answer
- [ ] Keep Smart Deck generation independent from retrieval ingestion

### 1.1. RAG layer output contract

- [ ] Return a grounded retrieval package, not raw unstructured text
- [ ] Include final answer text
- [ ] Include source citations for every supported claim
- [ ] Include retrieval trace and document references
- [ ] Include confidence or fallback reason when retrieval is weak
- [ ] Include deck-scoped metadata and source-version references
- [ ] Keep query rewriting, retrieval, reranking, and response formatting behind the backend contract
- [ ] Make empty-result and low-confidence states explicit so the UI can show a real fallback

## 2. Data model

- [ ] Add `rag_documents`
- [ ] Add `rag_chunks`
- [ ] Add `rag_embeddings`
- [ ] Add `rag_queries`
- [ ] Add `rag_query_results`
- [ ] Add `rag_feedback`
- [ ] Include deck/workspace scope on every retrieval record
- [ ] Include source version and source reference fields on every retrieval record
- [ ] Include chunk hash, embedding status, and retrieval metadata
- [ ] Add indexes for `deck_id`, `workspace_id`, `document_type`, and `source_version`

## 3. Backend services

- [ ] Add `rag_document_service`
- [ ] Add `rag_chunk_service`
- [ ] Add `rag_embedding_service`
- [ ] Add `rag_index_service`
- [ ] Add `rag_retrieval_service`
- [ ] Add `rag_answer_service`
- [ ] Add `rag_feedback_service`
- [ ] Make services callable from workers and API routes
- [ ] Keep the heavy indexing work in workers only

## 4. API routes

- [ ] Add `GET /api/products/deck-aistack-codes/decks/{deck_id}/rag-state`
- [ ] Add `POST /api/products/deck-aistack-codes/decks/{deck_id}/rag/reindex`
- [ ] Add `POST /api/products/deck-aistack-codes/decks/{deck_id}/rag/query`
- [ ] Add `GET /api/rag-jobs/{job_id}`
- [ ] Return `202 Accepted` for async reindex/query commands
- [ ] Return typed errors for missing provider, empty index, stale embeddings, and job conflicts

## 5. Worker split

- [ ] Add `worker-rag-ingestion`
- [ ] Add `worker-rag-embedding`
- [ ] Add `worker-rag-index-sync`
- [ ] Add `worker-rag-query-auditor`
- [ ] Add `worker-rag-reranker`
- [ ] Make each worker write only its own result rows
- [ ] Keep jobs idempotent so retries do not duplicate chunks or embeddings
- [ ] Repair stale or missing index entries in a dedicated worker

## 6. Query flow

- [ ] Rewrite the query to retrieval intent before search
- [ ] Filter by deck/workspace scope first
- [ ] Rank by semantic similarity second
- [ ] Apply provenance filters before top-k selection
- [ ] Rerank when the query or corpus justifies the extra latency
- [ ] Assemble answers with source citations and retrieval trace
- [ ] Persist query traces for auditability
- [ ] Mark low-confidence or empty-result behavior explicitly

## 7. Railway deployment

- [ ] Keep the backend API thin and orchestration-oriented
- [ ] Create separate Railway worker services for the RAG jobs
- [ ] Wire `DATABASE_URL` and storage/provider credentials into the RAG services
- [ ] Add `RAG_PROVIDER`
- [ ] Add `RAG_EMBEDDING_MODEL`
- [ ] Add `RAG_INDEX_BACKEND`
- [ ] Add `RAG_VECTOR_DIMENSION`
- [ ] Add `RAG_TOP_K`
- [ ] Add `RAG_RERANK_TOP_K`
- [ ] Add `RAG_CHUNK_SIZE`
- [ ] Add `RAG_CHUNK_OVERLAP`
- [ ] Add `RAG_QUERY_TIMEOUT_SECONDS`
- [ ] Add `RAG_QUERY_MAX_CANDIDATES`
- [ ] Add `RAG_QUALITY_THRESHOLD`

## 8. Rollout order

- [ ] Phase 1: define retrieval tables and migrations
- [ ] Phase 1: add document/chunk services
- [ ] Phase 1: add job model and state endpoint
- [ ] Phase 2: add embedding worker
- [ ] Phase 2: add index sync worker
- [ ] Phase 2: wire retrieval into Smart Deck backend logic
- [ ] Phase 3: add citations, audit logs, and feedback
- [ ] Phase 3: remove remaining frontend assumptions about retrieval

## 9. Acceptance criteria

- [ ] Retrieval is backend-owned
- [ ] Queries are grounded in deck-scoped sources
- [ ] Citations are returned with answers
- [ ] Failed retrieval is visible and retryable where appropriate
- [ ] Index repair is possible without reprocessing the whole deck
- [ ] Frontend never performs retrieval orchestration directly

## 10. FastAPI and model task list

### API surfaces

- [ ] Add `app/api/routes/rag.py`
- [ ] Add `app/api/routes/rag_jobs.py`
- [ ] Register the routes in `app/main.py`
- [ ] Add route-level auth and deck ownership checks
- [ ] Return `202 Accepted` for async RAG commands
- [ ] Return typed error payloads for provider/index/job failures

### Schemas

- [ ] Add `app/schemas/rag.py`
- [ ] Add response models for `rag-state`
- [ ] Add response models for `rag-jobs/{job_id}`
- [ ] Add request models for `rag/reindex`
- [ ] Add request models for `rag/query`
- [ ] Add enums for query status, document status, chunk status, and retrieval mode

### Models and migrations

- [ ] Add SQLAlchemy models for `RagDocument`
- [ ] Add SQLAlchemy models for `RagChunk`
- [ ] Add SQLAlchemy models for `RagEmbedding`
- [ ] Add SQLAlchemy models for `RagQuery`
- [ ] Add SQLAlchemy models for `RagQueryResult`
- [ ] Add SQLAlchemy models for `RagFeedback`
- [ ] Create Alembic migrations for retrieval tables and indexes
- [ ] Add provenance and source-version indexes
- [ ] Add vector/index repair metadata fields

### Services

- [ ] Add `app/services/rag_document_service.py`
- [ ] Add `app/services/rag_chunk_service.py`
- [ ] Add `app/services/rag_embedding_service.py`
- [ ] Add `app/services/rag_index_service.py`
- [ ] Add `app/services/rag_retrieval_service.py`
- [ ] Add `app/services/rag_answer_service.py`
- [ ] Add `app/services/rag_feedback_service.py`
- [ ] Add backend-only query rewriting and reranking helpers

### Workers

- [ ] Add `app/workers/rag_ingestion_worker.py`
- [ ] Add `app/workers/rag_embedding_worker.py`
- [ ] Add `app/workers/rag_index_sync_worker.py`
- [ ] Add `app/workers/rag_query_auditor_worker.py`
- [ ] Add `app/workers/rag_reranker_worker.py`
- [ ] Register worker handlers in the worker bootstrap

## 11. Railway service and env matrix

### Backend API

- [ ] Service name: `deck-backend-api`
- [ ] Start command: `python scripts/start_railway.py`
- [ ] Role: `api`
- [ ] Env: `DATABASE_URL`
- [ ] Env: storage credentials
- [ ] Env: auth/session config
- [ ] Env: provider credentials used by retrieval or generation

### RAG workers

- [ ] Service name: `worker-rag-ingestion`
- [ ] Role: `worker-rag-ingestion`
- [ ] Service name: `worker-rag-embedding`
- [ ] Role: `worker-rag-embedding`
- [ ] Service name: `worker-rag-index-sync`
- [ ] Role: `worker-rag-index-sync`
- [ ] Service name: `worker-rag-query-auditor`
- [ ] Role: `worker-rag-query-auditor`
- [ ] Service name: `worker-rag-reranker`
- [ ] Role: `worker-rag-reranker`
- [ ] Wire the shared `DATABASE_URL` into each service
- [ ] Wire storage credentials into each service
- [ ] Wire embedding/rerank provider credentials into the relevant services
- [ ] Set worker lease, heartbeat, and retry env vars explicitly

### Retrieval env vars

- [ ] `RAG_PROVIDER`
- [ ] `RAG_EMBEDDING_MODEL`
- [ ] `RAG_INDEX_BACKEND`
- [ ] `RAG_VECTOR_DIMENSION`
- [ ] `RAG_TOP_K`
- [ ] `RAG_RERANK_TOP_K`
- [ ] `RAG_CHUNK_SIZE`
- [ ] `RAG_CHUNK_OVERLAP`
- [ ] `RAG_QUERY_TIMEOUT_SECONDS`
- [ ] `RAG_QUERY_MAX_CANDIDATES`
- [ ] `RAG_QUALITY_THRESHOLD`

### Deployment policy

- [ ] Keep the API thin and orchestration-oriented
- [ ] Keep ingestion, embedding, indexing, and reranking in workers
- [ ] Keep frontend unaware of the retrieval backend implementation
- [ ] Confirm Railway branch points at the pushed backend commit before deploy

## 12. Backend PR plan

### PR 1: retrieval contract and storage

- [ ] Add the RAG schemas and models
- [ ] Add the migrations
- [ ] Add the `rag-state` and `rag-jobs` routes
- [ ] Add the document/chunk services
- [ ] Add the initial ingestion worker

### PR 2: embeddings and index sync

- [ ] Add the embedding worker
- [ ] Add the index sync worker
- [ ] Add vector storage/index backend wiring
- [ ] Add repair and retry behavior

### PR 3: query flow and answer assembly

- [ ] Add retrieval and reranking logic
- [ ] Add answer assembly with citations
- [ ] Add query audit logging
- [ ] Add feedback capture

### PR 4: rollout and verification

- [ ] Add backend smoke checks for RAG state and query routes
- [ ] Add worker wiring checks for the RAG services
- [ ] Add deployment notes to the backend README
- [ ] Verify Railway service split before promoting to production

## 13. Code-level file map

### New API files

- `app/api/routes/rag.py`
  - deck-scoped RAG state
  - async reindex/query command entrypoints
  - auth and ownership checks
- `app/api/routes/rag_jobs.py`
  - job status lookup
  - job event and artifact projection

### New schema files

- `app/schemas/rag.py`
  - request models
  - response models
  - status and mode enums

### New service files

- `app/services/rag_document_service.py`
  - document persistence and source version tracking
- `app/services/rag_chunk_service.py`
  - chunk creation, cleanup, and chunk metadata
- `app/services/rag_embedding_service.py`
  - embedding batching and vector writes
- `app/services/rag_index_service.py`
  - index repair and sync helpers
- `app/services/rag_retrieval_service.py`
  - deck-scoped retrieval and filtering
- `app/services/rag_answer_service.py`
  - answer assembly and citation formatting
- `app/services/rag_feedback_service.py`
  - query feedback capture and quality signals

### New worker files

- `app/workers/rag_ingestion_worker.py`
  - normalize documents and chunk records
- `app/workers/rag_embedding_worker.py`
  - generate embeddings
- `app/workers/rag_index_sync_worker.py`
  - repair stale vectors and missing records
- `app/workers/rag_query_auditor_worker.py`
  - sample retrieval queries and log traces
- `app/workers/rag_reranker_worker.py`
  - rerank candidate chunks when needed

### Existing files that will need wiring

- `app/main.py`
  - register the new RAG routes
- `app/workers/job_handlers.py`
  - map new worker job types to handlers
- `app/workers/deck_queue_worker.py`
  - bootstrap the worker roles cleanly
- `app/db/models/entities.py`
  - add the retrieval models
- `alembic/versions/`
  - add the migration files

## 14. Suggested PR sequence

### PR A: retrieval contract and persistence

- [ ] Add `app/schemas/rag.py`
- [ ] Add the retrieval SQLAlchemy models
- [ ] Add Alembic migrations
- [ ] Add `app/api/routes/rag.py`
- [ ] Add `app/api/routes/rag_jobs.py`
- [ ] Add the document and chunk services
- [ ] Add the initial ingestion worker

Suggested commit message:

- `feat(rag): add retrieval contract and persistence`

### PR B: embedding and index repair

- [ ] Add the embedding service
- [ ] Add the embedding worker
- [ ] Add the index sync service
- [ ] Add the index sync worker
- [ ] Add retry and repair behavior

Suggested commit message:

- `feat(rag): add embedding and index repair workers`

### PR C: retrieval and answer assembly

- [ ] Add retrieval service logic
- [ ] Add reranking helper
- [ ] Add answer assembly service
- [ ] Add query feedback capture
- [ ] Add audit logging for retrieval queries

Suggested commit message:

- `feat(rag): add retrieval and answer assembly`

### PR D: rollout and operationalization

- [ ] Add RAG smoke tests
- [ ] Add worker wiring verification
- [ ] Add Railway deployment notes
- [ ] Add README references to the new RAG plan

Suggested commit message:

- `docs(rag): add rollout and verification notes`

## 15. Railway variable checklist

### Backend API service

- [ ] `DATABASE_URL`
- [ ] `UPLOAD_STORAGE_BACKEND`
- [ ] `UPLOAD_STORAGE_S3_BUCKET` or `RAILWAY_BUCKET_NAME`
- [ ] `UPLOAD_STORAGE_S3_REGION` or `RAILWAY_BUCKET_REGION`
- [ ] `UPLOAD_STORAGE_S3_ENDPOINT` or `RAILWAY_BUCKET_ENDPOINT`
- [ ] `UPLOAD_STORAGE_S3_ACCESS_KEY` or `RAILWAY_BUCKET_ACCESS_KEY`
- [ ] `UPLOAD_STORAGE_S3_SECRET_KEY` or `RAILWAY_BUCKET_SECRET_KEY`
- [ ] existing auth/session variables
- [ ] existing AI/provider variables used by Smart Deck

### RAG ingestion worker

- [ ] `DATABASE_URL`
- [ ] `RAG_PROVIDER`
- [ ] `RAG_CHUNK_SIZE`
- [ ] `RAG_CHUNK_OVERLAP`
- [ ] `RAG_QUERY_TIMEOUT_SECONDS`
- [ ] `UPLOAD_STORAGE_BACKEND`
- [ ] storage bucket credentials

### RAG embedding worker

- [ ] `DATABASE_URL`
- [ ] `RAG_PROVIDER`
- [ ] `RAG_EMBEDDING_MODEL`
- [ ] `RAG_VECTOR_DIMENSION`
- [ ] `RAG_TOP_K`
- [ ] provider API key or model access token

### RAG index sync worker

- [ ] `DATABASE_URL`
- [ ] `RAG_INDEX_BACKEND`
- [ ] `RAG_QUALITY_THRESHOLD`
- [ ] storage credentials if index repair needs source revalidation

### RAG query auditor worker

- [ ] `DATABASE_URL`
- [ ] `RAG_TOP_K`
- [ ] `RAG_RERANK_TOP_K`
- [ ] tracing/logging variables

### RAG reranker worker

- [ ] `DATABASE_URL`
- [ ] `RAG_RERANK_TOP_K`
- [ ] rerank provider credentials

### Deployment rule for variables

- [ ] Set retrieval-related variables per worker service, not globally by accident
- [ ] Keep the API service lean
- [ ] Confirm Railway branch mappings before rollout
- [ ] Validate that each RAG worker can start with its dedicated job type only

## 16. Base RAG stack decisions for this product

The product does need the base stack described in the reference note, but not every technique as a default.
Use the following as the product decision record:

### Required

- [ ] Parsing for PDF, PPTX, DOCX, HTML, and markdown-like source material
- [ ] Chunking with provenance preserved on each chunk
- [ ] Dense embeddings for semantic retrieval
- [ ] Indexing in a backend-owned retrieval store
- [ ] Query rewriting so retrieval intent is separated from user instruction
- [ ] Reranking before answer assembly when the candidate set is noisy
- [ ] Metadata filters so deck/workspace/source-version constraints stay strict
- [ ] Citations and traceability in every answer
- [ ] Empty-result and low-confidence behavior that is explicit to the user

### Required as a fallback

- [ ] OCR for scanned or image-based documents when text extraction fails
- [ ] VLM-based parsing only when classical parsers fail or the layout is unusually complex
- [ ] Keyword or hybrid search for exact-match tokens, typos, identifiers, brand names, and compliance-sensitive lookups

### Not default behavior

- [ ] Do not send all raw document text directly to the LLM
- [ ] Do not make VLM parsing the first choice for ordinary documents
- [ ] Do not make the frontend responsible for query rewriting or retrieval filtering
- [ ] Do not couple retrieval quality to a single worker or a single prompt

### Product-specific implications

- [ ] Slide decks should be treated as multimodal source documents, not plain text blobs
- [ ] Slide thumbnails, slide text, slide blocks, and brand assets should be separate retrieval sources
- [ ] PowerPoint and PDF parsing should share the same downstream retrieval schema
- [ ] Brand and Smart Deck retrieval should stay deck-scoped and version-aware
- [ ] Retrieval quality should be measured per deck and per source version

### Practical recommendation

- [ ] Use parser-first ingestion
- [ ] Use chunking + embeddings + indexing as the default path
- [ ] Use reranking before generation
- [ ] Keep OCR/VLM/hybrid search as controlled fallbacks
- [ ] Prefer deterministic backend parsing over frontend inference
