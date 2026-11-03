"""Song writer (title + style caption + tagged lyrics) via Claude.

Two backends: the Anthropic API (ANTHROPIC_API_KEY) or the local Claude Code CLI,
which reuses whatever account `claude` is logged into — no key needed.
"""

import json
import re
import shutil
import subprocess
import tempfile

from pydantic import BaseModel, ValidationError

from app.config import Settings

LANGUAGES = {"ru": "Russian", "uk": "Ukrainian", "en": "English"}

SYSTEM = """You are a songwriter preparing input for the ACE-Step 1.5 music model.
Return ONLY a JSON object: {"title": str, "caption": str, "lyrics": str}.

caption: English, comma-separated style tags: genre/era, vocal (gender, timbre, delivery),
key instruments, mood, production, tempo like "95 bpm". 15-40 words. Never name real artists:
describe their sound instead.

lyrics: in the requested language, natural and singable, with rhyme and a memorable hook.
Mark every section on its own line with an English tag in square brackets:
[Intro] [Verse 1] [Pre-Chorus] [Chorus] [Verse 2] [Bridge] [Outro]. A short performance hint
may follow a dash, e.g. [Chorus - shouted, group vocals] or [Outro - whispered].
Blank line between sections. No other commentary, no markdown.
If instrumental, lyrics is "[Instrumental]" (optionally with tags like [Guitar Solo]).
Size the lyrics to the target duration: about one sung line per 4 seconds (rap: per 2.5 s)."""


class Song(BaseModel):
    title: str
    caption: str
    lyrics: str


class LyricsError(RuntimeError):
    pass


def provider(s: Settings) -> str | None:
    if s.lyrics_provider in ("auto", "api") and s.anthropic_api_key:
        return "api"
    if s.lyrics_provider in ("auto", "cli") and shutil.which(s.claude_cli):
        return "cli"
    return None


def build_prompt(
    idea: str, language: str, instrumental: bool, style: str, duration: float, lyrics: str
) -> str:
    parts = [
        f"Idea: {idea or '(none — invent one that fits the style)'}",
        f"Language: {LANGUAGES.get(language, language)}",
        f"Target duration: {int(duration)} seconds",
        f"Instrumental: {'yes' if instrumental else 'no'}",
    ]
    if style:
        parts.append(f"Desired style (keep its intent, rewrite as tags): {style}")
    if lyrics.strip():
        parts.append(
            "Existing lyrics — keep the words, fix structure/tags only:\n" + lyrics.strip()
        )
    return "\n".join(parts)


def write_song(
    s: Settings,
    idea: str,
    language: str = "en",
    instrumental: bool = False,
    style: str = "",
    duration: float = 120,
    lyrics: str = "",
) -> Song:
    prompt = build_prompt(idea, language, instrumental, style, duration, lyrics)
    match provider(s):
        case "api":
            return _api(s, prompt)
        case "cli":
            return parse_song(_cli(s, prompt))
        case _:
            raise LyricsError(
                "Claude is not configured: set ANTHROPIC_API_KEY or log in to `claude`"
            )


def parse_song(text: str) -> Song:
    # The CLI returns free text; take the outermost {...} in case it adds a code fence.
    m = re.search(r"\{.*\}", text, re.S)
    try:
        return Song.model_validate(json.loads(m.group(0) if m else text))
    except (json.JSONDecodeError, ValidationError) as e:
        raise LyricsError(f"Claude returned malformed song JSON: {text[:300]}") from e


def _api(s: Settings, prompt: str) -> Song:
    import anthropic

    client = anthropic.Anthropic(api_key=s.anthropic_api_key)
    try:
        resp = client.messages.parse(
            model=s.anthropic_model,
            max_tokens=16000,
            system=SYSTEM,
            messages=[{"role": "user", "content": prompt}],
            output_format=Song,
        )
    except anthropic.APIError as e:
        raise LyricsError(f"Anthropic API error: {e}") from e
    if resp.stop_reason == "refusal" or resp.parsed_output is None:
        raise LyricsError(f"Claude declined or returned no song (stop_reason={resp.stop_reason})")
    return resp.parsed_output


def _cli(s: Settings, prompt: str) -> str:
    exe = shutil.which(s.claude_cli)
    assert exe, "provider() checked this"
    # Bare session: no tools, MCP, plugins or project settings (~1k tokens instead of ~60k).
    cmd = [
        exe,
        "-p",
        "--output-format",
        "json",
        "--tools",
        "",
        "--strict-mcp-config",
        "--disable-slash-commands",
        "--setting-sources",
        "",
        "--system-prompt",
        SYSTEM,
    ]
    if s.claude_cli_model:
        cmd += ["--model", s.claude_cli_model]
    try:
        r = subprocess.run(
            cmd,
            input=prompt.encode("utf-8"),
            capture_output=True,
            timeout=300,
            cwd=tempfile.gettempdir(),  # keep the repo's CLAUDE.md out of the prompt
        )
    except subprocess.TimeoutExpired as e:
        raise LyricsError("Claude CLI timed out") from e
    try:
        out = json.loads(r.stdout.decode("utf-8"))
    except json.JSONDecodeError as e:
        err = (r.stderr or r.stdout).decode("utf-8", "replace").strip()
        raise LyricsError(f"Claude CLI failed (is `claude` logged in?): {err[:300]}") from e
    if out.get("is_error"):
        raise LyricsError(f"Claude CLI error: {out.get('result')}")
    return out["result"]
