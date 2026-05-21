from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse

from app.schemas.analyze import (
    AnalyzeRequest,
    AnalyzeResponse,
    LevelBreakdown,
    TokenResult,
)
from app.services.nlp.classifier import QueryType, classify
from app.services.nlp.chinese import tokenize_chinese
from app.services.nlp.japanese import tokenize_japanese

router = APIRouter(prefix="/api", tags=["analyze"])

_COMPLEXITY_MIN_LEVELED = 3


def _build_breakdown(tokens: list[TokenResult], language: str) -> LevelBreakdown:
    if language == "jp":
        keys = ["N5", "N4", "N3", "N2", "N1"]
        dist: dict[str, int] = {k: 0 for k in keys}
        dist["unknown"] = 0
        for t in tokens:
            lvl = t.jlpt_level
            if lvl is not None:
                dist[f"N{lvl}"] += 1
            else:
                dist["unknown"] += 1
    else:
        keys = ["HSK1", "HSK2", "HSK3", "HSK4", "HSK5", "HSK6"]
        dist = {k: 0 for k in keys}
        dist["unknown"] = 0
        for t in tokens:
            lvl = t.hsk_level
            if lvl is not None:
                dist[f"HSK{lvl}"] += 1
            else:
                dist["unknown"] += 1

    leveled = sum(v for k, v in dist.items() if k != "unknown")
    return LevelBreakdown(distribution=dist, leveled_count=leveled, total_count=len(tokens))


@router.post("/analyze")
async def analyze(request: AnalyzeRequest, response: Response) -> AnalyzeResponse:
    query = request.query.strip()

    try:
        query_type = classify(query, request.language)
    except ValueError:
        return JSONResponse(status_code=400, content={"detail": "Empty or invalid query"})

    if request.language == "jp":
        raw_tokens = tokenize_japanese(query)
    else:
        raw_tokens = tokenize_chinese(query)

    tokens = [TokenResult(**t) for t in raw_tokens]
    breakdown = _build_breakdown(tokens, request.language)

    if breakdown.leveled_count < _COMPLEXITY_MIN_LEVELED:
        response.status_code = 206
        breakdown_out = None
    else:
        breakdown_out = breakdown

    return AnalyzeResponse(
        query=query,
        language=request.language,
        query_type=query_type,
        tokens=tokens,
        level_breakdown=breakdown_out,
    )
