"""
Research Paper Recommendation System (RPRS)
メインアプリケーションエントリーポイント
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.models.database import create_tables
from app.api import papers, topics, recommendations


@asynccontextmanager
async def lifespan(app: FastAPI):
    """アプリケーション起動時にDBテーブルを作成"""
    create_tables()
    yield


app = FastAPI(
    title="Research Paper Recommendation System",
    description="研究テーマに関連する新着論文を自動収集・推薦するシステム",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(topics.router, prefix="/api/topics", tags=["Topics"])
app.include_router(papers.router, prefix="/api/papers", tags=["Papers"])
app.include_router(recommendations.router, prefix="/api/recommendations", tags=["Recommendations"])


@app.get("/", tags=["Health"])
def health_check():
    return {"status": "ok", "system": "RPRS v1.0.0"}
