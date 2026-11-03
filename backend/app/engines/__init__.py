from app.config import Settings
from app.engines.base import GenerateRequest, GenerateResult, MusicEngine

__all__ = ["GenerateRequest", "GenerateResult", "MusicEngine", "get_engine"]


def get_engine(settings: Settings) -> MusicEngine:
    # Imported lazily: engine modules pull in torch.
    if settings.engine == "acestep":
        from app.engines.acestep import AceStepEngine

        return AceStepEngine(settings)
    raise ValueError(f"Unknown engine: {settings.engine!r}")
