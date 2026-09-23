class AiOrchestrationError(ValueError):
    """Raised when an orchestration run cannot safely complete."""


class SceneGraphValidationError(AiOrchestrationError):
    """Raised when generated scene graph JSON fails validation."""

