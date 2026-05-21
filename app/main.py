from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.routers import analyze, auth


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="JpDict API", lifespan=lifespan)
app.include_router(auth.router)
app.include_router(analyze.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
