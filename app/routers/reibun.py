from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["reibun"])


@router.get("/reibun/search/{word_id}")
async def reibun_search(word_id: str):
    # Example sentences are not yet stored in the DB.
    # Returns an empty list so the frontend renders gracefully.
    return {"result_count": 0, "pg": 1, "perPage": 10, "reibuns": []}
