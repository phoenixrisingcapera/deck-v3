"""Optional LangChain adapter behind Deck V2's retrieval domain interface."""
from __future__ import annotations

from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from pydantic import ConfigDict

from app.services.llm.ai_vc_retrieval import AIVCRetrievalRouter, RetrievalRequest


class DeckV2RetrieverAdapter(BaseRetriever):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    router: AIVCRetrievalRouter
    purpose: str
    max_results: int = 6

    def _get_relevant_documents(self, query: str, *, run_manager=None) -> list[Document]:
        results = self.router.retrieve(RetrievalRequest(
            purpose=self.purpose, query=query, max_results=self.max_results,
        ))
        return [Document(page_content=item.content, metadata={
            "source_type": item.source_type, "source_id": item.source_id,
            "evidence_class": item.evidence_class, "url": item.url,
            "provenance": item.provenance, "confidence": item.confidence,
        }) for item in results]
