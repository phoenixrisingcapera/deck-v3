from datetime import date, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import AiBase
from app.services.ai_vc.memory import load_memory_context, persist_memory_record
from app.services.ai_vc.models import AIVCMemoryRecord


def test_memory_is_workspace_and_company_isolated_and_stale_research_is_excluded():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    AiBase.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        persist_memory_record(session, AIVCMemoryRecord(
            workspace_id="workspace-a", company_identity="company-a", memory_type="accepted_strategy",
            content="Lead with the customer workflow", source_artifact_id="artifact-a",
        ), user_id="user")
        persist_memory_record(session, AIVCMemoryRecord(
            workspace_id="workspace-b", company_identity="company-b", memory_type="accepted_strategy",
            content="A different company's thesis", source_artifact_id="artifact-b",
        ), user_id="other")
        persist_memory_record(session, AIVCMemoryRecord(
            workspace_id="workspace-a", company_identity="company-a", memory_type="research_fact",
            content="An old market claim", source_artifact_id="artifact-old",
            expires_at=date.today() - timedelta(days=1),
        ), user_id="user")
        session.commit()

        context = load_memory_context(
            session, workspace_id="workspace-a", company_identity_value="company-a", user_id="user",
        )
        assert [item["content"] for item in context["memories"]] == ["Lead with the customer workflow"]
        assert context["memories"][0]["authority"] == "accepted_decision"
        assert context["policy"]["workspaceIsolation"] is True
    finally:
        session.close()
        engine.dispose()
