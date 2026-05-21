from pydantic import BaseModel, Field

from app.services.nlp.classifier import QueryType


class AnalyzeRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    language: str = Field(..., pattern="^(jp|cn)$")


class TokenResult(BaseModel):
    surface: str
    dictionary_form: str | None = None
    reading: str | None = None
    pos: str
    jlpt_level: int | None = None
    hsk_level: int | None = None
    pinyin: str | None = None


class LevelBreakdown(BaseModel):
    # For Japanese: keys are "N5" … "N1" + "unknown"
    # For Chinese:  keys are "HSK1" … "HSK6" + "unknown"
    distribution: dict[str, int]
    leveled_count: int
    total_count: int


class AnalyzeResponse(BaseModel):
    query: str
    language: str
    query_type: QueryType
    tokens: list[TokenResult]
    level_breakdown: LevelBreakdown | None = None
