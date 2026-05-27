from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.routers import analyze, auth, history, kanji, reibun, search, vocabulary


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response


app = FastAPI(title="JpDict API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["*"],
)

app.add_middleware(SecurityHeadersMiddleware)

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
