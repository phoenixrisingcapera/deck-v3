from __future__ import annotations

import time

from sqlalchemy import inspect, text

from app.core.config import settings
from app.db.base import AiBase, CoreBase
from app.db.session import get_ai_engine, get_engine


def _probe(engine, *, version_table: str) -> dict:
    started = time.perf_counter()
    with engine.connect() as connection:
        database = connection.execute(text("select current_database()")).scalar_one()
        server_address = connection.execute(text("select inet_server_addr()::text")).scalar_one_or_none()
        server_port = connection.execute(text("select inet_server_port()")).scalar_one_or_none()
        server_version = connection.execute(text("show server_version")).scalar_one()
        tables = set(inspect(connection).get_table_names(schema="public"))
        migration_heads = tuple(connection.execute(
            text(f"select version_num from {version_table} order by version_num")
        ).scalars())
    return {
        "reachable": True,
        "database": database,
        "serverAddress": server_address,
        "serverPort": server_port,
        "serverVersion": server_version,
        "migrationTable": version_table,
        "migrationHeads": list(migration_heads),
        "tables": sorted(tables),
        "latencyMs": round((time.perf_counter() - started) * 1000, 2),
    }


def get_database_topology() -> dict:
    core = _probe(get_engine(), version_table="alembic_version_core")
    ai = _probe(get_ai_engine(), version_table="alembic_version_ai")
    with get_ai_engine().connect() as connection:
        ai["vectorExtension"] = connection.execute(
            text("select extversion from pg_extension where extname='vector'")
        ).scalar_one_or_none()
        ai["vectorDimension"] = connection.execute(
            text(
                "select format_type(a.atttypid, a.atttypmod) "
                "from pg_attribute a join pg_class c on c.oid=a.attrelid "
                "join pg_namespace n on n.oid=c.relnamespace "
                "where n.nspname='public' and c.relname='vector_chunks' "
                "and a.attname='embedding' and a.attnum > 0 and not a.attisdropped"
            )
        ).scalar_one_or_none()

    core_tables = set(core["tables"])
    ai_tables = set(ai["tables"])
    core_model_tables = set(CoreBase.metadata.tables)
    ai_model_tables = set(AiBase.metadata.tables)
    ownership = {
        "coreMissing": sorted(core_model_tables - core_tables),
        "aiMissing": sorted(ai_model_tables - ai_tables),
        "coreContainsAiTables": sorted(core_tables & ai_model_tables),
        "aiContainsCoreTables": sorted(ai_tables & core_model_tables),
        "databasesDistinct": (
            core.get("serverAddress"), core.get("serverPort"), core.get("database")
        ) != (
            ai.get("serverAddress"), ai.get("serverPort"), ai.get("database")
        ),
    }
    return {
        "status": "ok" if all(not values for key, values in ownership.items() if key != "databasesDistinct") and ownership["databasesDistinct"] and ai["vectorExtension"] and ai["vectorDimension"] == "vector(1024)" else "degraded",
        "core": core,
        "ai": ai,
        "ownership": ownership,
        "configured": {
            "coreUrlPresent": bool(settings.database_url),
            "aiUrlPresent": bool(settings.ai_database_url),
        },
    }
