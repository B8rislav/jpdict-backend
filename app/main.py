from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import analyze, auth, history, kanji, reibun, search, vocabulary


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="JpDict API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "PATCH"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(analyze.router)
app.include_router(search.router)
app.include_router(kanji.router)
app.include_router(reibun.router)
app.include_router(vocabulary.router)
app.include_router(history.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
