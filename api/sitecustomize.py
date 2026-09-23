from __future__ import annotations

try:
    from app.core.railway_env import apply_railway_env_aliases

    apply_railway_env_aliases()
except Exception:
    # Do not make Python startup fail before the app logger/settings exist.
    # Production settings validation will still fail loudly if required values
    # are genuinely missing after alias normalisation.
    pass
