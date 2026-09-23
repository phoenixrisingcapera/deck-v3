---
name: Chroma Cloud Qwen
description: Chroma's hosted Qwen embedding service
source_root: /Users/mpstaton/code/lossless-monorepo/context-v
source_relative_path: agent-skills/chroma-agent-skills/skills/chroma-cloud/chroma-cloud-qwen/python.md
source_repo_slug: lossless-monorepo
collated_at: '2026-08-24'
source_path: "context-v/agent-skills/chroma-agent-skills/skills/chroma-cloud/chroma-cloud-qwen/python.md"
---

## Chroma Cloud Qwen

Embed documents using Qwen 3.

### Example

```python
from chromadb.utils.embedding_functions import ChromaCloudQwenEmbeddingFunction
from chromadb.utils.embedding_functions.chroma_cloud_qwen_embedding_function import ChromaCloudQwenEmbeddingModel
import os

os.environ["CHROMA_API_KEY"] = "YOUR_API_KEY"
qwen_ef = ChromaCloudQwenEmbeddingFunction(
    model=ChromaCloudQwenEmbeddingModel.QWEN3_EMBEDDING_0p6B,
    task="nl_to_code"
)

texts = ["Hello, world!", "How are you?"]
embeddings = qwen_ef(texts)
```
