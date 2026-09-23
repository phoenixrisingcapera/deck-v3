# pgvector Dependency Isolation

## Problem
The application failed to start if `pgvector` was not installed or had import issues, blocking all core functionality even though vector search is an optional feature.

## Solution
Made `pgvector` an optional dependency with graceful degradation:

1. **Optional Import**: Wrapped `pgvector.sqlalchemy.Vector` import in try/except
2. **Runtime Flag**: Added `PGVECTOR_AVAILABLE` boolean to track availability
3. **Conditional Model**: `VectorChunk` model defined differently based on pgvector presence
4. **Fallback Type**: Uses JSON column instead of Vector(1536) when pgvector unavailable

## Code Changes

### Before
```python
from pgvector.sqlalchemy import Vector

class VectorChunk(Base):
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
```

### After
```python
try:
    from pgvector.sqlalchemy import Vector
    PGVECTOR_AVAILABLE = True
except ImportError:
    PGVECTOR_AVAILABLE = False
    Vector = None

if PGVECTOR_AVAILABLE:
    class VectorChunk(Base):
        embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
else:
    class VectorChunk(Base):
        embedding: Mapped[list[float] | None] = mapped_column(JSON, nullable=True)
```

## Impact

### Core Features (Always Available)
- Deck upload and processing
- Brand profile extraction
- Smart Deck generation
- Workflow management
- All API routes (277 routes load successfully)

### Optional Features (Require pgvector)
- Vector chunk storage
- Embedding-based search
- Semantic similarity queries

## Testing

### Without pgvector
```bash
$ pip uninstall pgvector
$ python -c "from app.main import app; print(len(app.routes))"
277
```

### With pgvector
```bash
$ pip install pgvector
$ python -c "from app.main import app; from app.db.models.entities import PGVECTOR_AVAILABLE; print(PGVECTOR_AVAILABLE)"
True
```

## Migration Notes

- No database schema changes required
- Existing `vector_chunks` table continues to work
- New deployments can skip pgvector installation if vector search not needed
- Railway deployment: pgvector remains in requirements.txt but app won't crash if installation fails

## Related
- Commit: `98661a7`
- Tag: `v0.4.1-pgvector-isolation`
- Issue: App initialization blocked by pgvector dependency
