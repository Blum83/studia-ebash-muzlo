from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    engine: str = "acestep"
    models_dir: Path = ROOT / "models"
    output_dir: Path = ROOT / "data" / "outputs"
    db_path: Path = ROOT / "data" / "songgen.db"
    device: str = "cuda"
    host: str = "127.0.0.1"  # no auth: reach a remote box through an SSH tunnel
    port: int = 8000
    allowed_hosts: list[str] = ["localhost", "127.0.0.1"]  # Host header allow-list

    # Song writer: "auto" = API key if set, else the logged-in `claude` CLI; "off" hides it.
    lyrics_provider: str = "auto"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-5-5"
    claude_cli: str = "claude"
    claude_cli_model: str = ""  # empty = the CLI's default model

    # ACE-Step 1.5 — defaults are its GPU tier 5 (12-16 GB) profile.
    acestep_dit_model: str = "acestep-v15-turbo"
    acestep_lm_model: str = "acestep-5Hz-lm-0.6B"  # empty string disables the LM
    acestep_lm_backend: str = "pt"  # "vllm" on Linux
    acestep_quantization: str = "int8_weight_only"  # or "none"
    acestep_compile: bool = False
    offload_to_cpu: bool = True
    offload_dit_to_cpu: bool = False


settings = Settings()
