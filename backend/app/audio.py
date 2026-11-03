import subprocess
from pathlib import Path


def to_mp3(wav: Path, bitrate: str = "192k") -> Path:
    mp3 = wav.with_suffix(".mp3")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-b:a", bitrate, str(mp3)]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except FileNotFoundError as e:
        raise RuntimeError("ffmpeg not found on PATH (see README troubleshooting)") from e
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffmpeg failed: {e.stderr.strip()}") from e
    return mp3
