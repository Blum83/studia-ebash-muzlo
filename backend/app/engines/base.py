from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class GenerateRequest:
    caption: str
    lyrics: str = ""
    duration: float = 60.0
    seed: int = -1  # -1 = random
    instrumental: bool = False
    vocal_language: str = "unknown"
    task: str = "text2music"  # later: cover / repaint
    extra: dict[str, Any] = field(default_factory=dict)  # engine-specific knobs (LoRA, steps...)


@dataclass
class GenerateResult:
    wav_path: Path
    seed: int
    meta: dict[str, Any] = field(default_factory=dict)


class MusicEngine(ABC):
    name: str

    @abstractmethod
    def load(self) -> None:
        """Load weights onto the device. Called once; the engine then stays warm."""

    @abstractmethod
    def generate(self, req: GenerateRequest, out_dir: Path) -> GenerateResult:
        """Blocking generation of one song into out_dir."""
