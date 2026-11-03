from pydantic import BaseModel, Field


class JobCreate(BaseModel):
    title: str = Field("", max_length=200)
    idea: str = Field("", max_length=2000)
    caption: str = Field(min_length=1, max_length=2000)
    lyrics: str = Field("", max_length=10000)
    duration: float = Field(60.0, ge=10, le=600)  # ACE-Step supports 10 s - 10 min
    seed: int = Field(-1, ge=-1, le=2**32 - 1)
    instrumental: bool = False
    vocal_language: str = Field("unknown", max_length=16)


class LyricsRequest(BaseModel):
    idea: str = Field("", max_length=2000)
    style: str = Field("", max_length=2000)
    lyrics: str = Field("", max_length=10000)  # non-empty = tidy up instead of writing anew
    language: str = Field("en", max_length=16)
    instrumental: bool = False
    duration: float = Field(120, ge=10, le=600)
