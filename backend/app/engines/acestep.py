import os
import re
from dataclasses import asdict
from pathlib import Path

from app.config import Settings
from app.engines.base import GenerateRequest, GenerateResult, MusicEngine

BPM_MIN, BPM_MAX = 30, 300  # acestep/constants.py


def caption_bpm(caption: str) -> int | None:
    m = re.search(r"(\d{2,3})\s*bpm", caption, re.I)
    return int(m.group(1)) if m and BPM_MIN <= int(m.group(1)) <= BPM_MAX else None


class AceStepEngine(MusicEngine):
    name = "acestep"

    def __init__(self, settings: Settings) -> None:
        self.s = settings
        # ACE-Step resolves its checkpoint dir from this env var.
        os.environ["ACESTEP_CHECKPOINTS_DIR"] = str(settings.models_dir)

    def load(self) -> None:
        from acestep.handler import AceStepHandler
        from acestep.llm_inference import LLMHandler

        s = self.s
        self.dit = AceStepHandler()
        msg, ok = self.dit.initialize_service(
            project_root=str(s.models_dir.parent),
            config_path=s.acestep_dit_model,
            device=s.device,
            compile_model=s.acestep_compile,
            offload_to_cpu=s.offload_to_cpu,
            offload_dit_to_cpu=s.offload_dit_to_cpu,
            quantization=None if s.acestep_quantization == "none" else s.acestep_quantization,
        )
        if not ok:
            raise RuntimeError(f"ACE-Step DiT init failed: {msg}")
        print(msg)

        self.llm = LLMHandler()
        if s.acestep_lm_model:
            msg, ok = self.llm.initialize(
                checkpoint_dir=str(s.models_dir),
                lm_model_path=s.acestep_lm_model,
                backend=s.acestep_lm_backend,
                device=s.device,
                offload_to_cpu=s.offload_to_cpu,
            )
            if not ok:
                raise RuntimeError(f"ACE-Step LM init failed: {msg}")
            print(msg)

    def generate(self, req: GenerateRequest, out_dir: Path) -> GenerateResult:
        from acestep.inference import GenerationConfig, GenerationParams, generate_music

        lyrics = "[Instrumental]" if req.instrumental and not req.lyrics.strip() else req.lyrics
        extra = dict(req.extra)
        # The 0.6B LM ignores "NNN bpm" in the caption and drifts to the 30/300 range edges;
        # pass it as an explicit hint so the LM keeps it.
        if "bpm" not in extra and (bpm := caption_bpm(req.caption)):
            extra["bpm"] = bpm
        params = GenerationParams(
            task_type=req.task,
            caption=req.caption,
            lyrics=lyrics,
            instrumental=req.instrumental,
            vocal_language=req.vocal_language,
            duration=req.duration,
            seed=req.seed,
            thinking=bool(self.s.acestep_lm_model),
            **extra,
        )
        config = GenerationConfig(
            batch_size=1,
            use_random_seed=req.seed < 0,
            seeds=None if req.seed < 0 else [req.seed],
            audio_format="wav",
        )
        out_dir.mkdir(parents=True, exist_ok=True)
        result = generate_music(self.dit, self.llm, params, config, save_dir=str(out_dir))
        if not result.success or not result.audios:
            reason = result.error or result.status_message
            raise RuntimeError(f"ACE-Step generation failed: {reason}")

        audio = result.audios[0]
        p = audio["params"]
        return GenerateResult(
            wav_path=Path(audio["path"]),
            seed=int(p["seed"]),
            meta={
                "dit_model": self.s.acestep_dit_model,
                "lm_model": self.s.acestep_lm_model or None,
                "sample_rate": audio["sample_rate"],
                # LM-planned values (bpm/key/...) when thinking is on.
                "bpm": p.get("bpm") or p.get("cot_bpm"),
                "keyscale": p.get("keyscale") or p.get("cot_keyscale"),
                "request": asdict(req),
            },
        )
