import argparse
import sys
import time
from pathlib import Path

from app.config import settings
from app.engines import GenerateRequest, get_engine

# Minimum VRAM (GB) per ACE-Step's GPU tier table (docs/en/GPU_COMPATIBILITY.md).
MIN_VRAM_XL_GB = 12
MIN_VRAM_LM_GB = 6


def cmd_download(_: argparse.Namespace) -> int:
    import torch
    from acestep.model_downloader import ensure_dit_model, ensure_lm_model, ensure_main_model

    s = settings
    if not torch.cuda.is_available():
        print("ERROR: CUDA GPU not visible to torch. Check the NVIDIA driver / CUDA build.")
        return 1
    vram = torch.cuda.get_device_properties(0).total_memory / 1024**3
    print(f"GPU: {torch.cuda.get_device_name(0)}, {vram:.1f} GB VRAM")
    if "xl" in s.acestep_dit_model and vram < MIN_VRAM_XL_GB:
        print(
            f"ERROR: {s.acestep_dit_model} needs >= {MIN_VRAM_XL_GB} GB VRAM. "
            "Set ACESTEP_DIT_MODEL=acestep-v15-turbo."
        )
        return 1
    if s.acestep_lm_model and vram < MIN_VRAM_LM_GB:
        print(f"ERROR: the LM needs >= {MIN_VRAM_LM_GB} GB VRAM. Set ACESTEP_LM_MODEL= (empty).")
        return 1

    steps = [ensure_main_model(s.models_dir)]  # turbo DiT + VAE + text encoder + 1.7B LM
    steps.append(ensure_dit_model(s.acestep_dit_model, s.models_dir))
    if s.acestep_lm_model:
        steps.append(ensure_lm_model(s.acestep_lm_model, s.models_dir))
    for ok, msg in steps:
        print(msg)
        if not ok:
            return 1
    print(f"Models ready in {s.models_dir}")
    return 0


def cmd_generate(a: argparse.Namespace) -> int:
    lyrics = Path(a.lyrics_file).read_text(encoding="utf-8") if a.lyrics_file else a.lyrics
    engine = get_engine(settings)
    t = time.perf_counter()
    engine.load()
    print(f"Loaded in {time.perf_counter() - t:.1f}s")
    t = time.perf_counter()
    res = engine.generate(
        GenerateRequest(
            caption=a.caption,
            lyrics=lyrics,
            duration=a.duration,
            seed=a.seed,
            instrumental=a.instrumental,
            vocal_language=a.language,
        ),
        settings.output_dir,
    )
    print(f"Generated in {time.perf_counter() - t:.1f}s -> {res.wav_path} (seed {res.seed})")
    return 0


def cmd_serve(_: argparse.Namespace) -> int:
    import uvicorn

    from app.api import create_app
    from app.db import DB

    app = create_app(get_engine(settings), DB(settings.db_path), settings.output_dir)
    uvicorn.run(app, host=settings.host, port=settings.port)
    return 0


def main() -> None:
    # ACE-Step prints emoji; the Windows console default (cp1251/cp1252) can't encode them.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    p = argparse.ArgumentParser(prog="songgen")
    sub = p.add_subparsers(required=True)

    sub.add_parser("download", help="Download model weights into MODELS_DIR").set_defaults(
        fn=cmd_download
    )

    sub.add_parser("serve", help="Run the API server (model stays loaded)").set_defaults(
        fn=cmd_serve
    )

    g = sub.add_parser("generate", help="Generate one song")
    g.add_argument("--caption", required=True, help="Style / tags, e.g. 'indie rock, female vocal'")
    g.add_argument("--lyrics", default="", help="Lyrics with [Verse]/[Chorus] tags")
    g.add_argument("--lyrics-file", help="Read lyrics from a UTF-8 file instead")
    g.add_argument("--duration", type=float, default=60.0)
    g.add_argument("--seed", type=int, default=-1)
    g.add_argument("--instrumental", action="store_true")
    g.add_argument("--language", default="unknown", help="Vocal language: en, ru, uk, ...")
    g.set_defaults(fn=cmd_generate)

    a = p.parse_args()
    sys.exit(a.fn(a))


if __name__ == "__main__":
    main()
