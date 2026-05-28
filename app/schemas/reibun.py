from typing import Literal

from pydantic import BaseModel


class Reibun(BaseModel):
    id: int
    sentence_jp: str
    reading_jp: str | None
    translation: str
    translation_lang: Literal["ru", "en"]


class ReibunSearchResponse(BaseModel):
    result_count: int
    pg: int
    perPage: int
    reibuns: list[Reibun]
