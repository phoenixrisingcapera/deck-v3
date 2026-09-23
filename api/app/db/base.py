from sqlalchemy.orm import DeclarativeBase


class CoreBase(DeclarativeBase):
    """Metadata registry for product and authentication persistence."""

    pass


class AiBase(DeclarativeBase):
    """Metadata registry for AI, vector, and provider telemetry persistence."""

    pass


# Compatibility alias for existing product imports. New code should select an
# explicit registry (CoreBase or AiBase) instead of relying on this alias.
Base = CoreBase
