"""
Pydanticスキーマ定義（リクエスト/レスポンス）
"""

from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, Field


# ──── Topic ────

class TopicCreate(BaseModel):
    name: str = Field(..., example="LLM")

class TopicResponse(BaseModel):
    id: int
    name: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ──── Paper ────

class PaperResponse(BaseModel):
    id: int
    arxiv_id: str
    title: str
    authors: str
    abstract: str
    url: str
    category: Optional[str]
    publish_date: date
    created_at: datetime

    model_config = {"from_attributes": True}


class PaperSearchParams(BaseModel):
    title: Optional[str] = None
    author: Optional[str] = None
    year: Optional[int] = None
    category: Optional[str] = None


# ──── Recommendation ────

class RecommendationResponse(BaseModel):
    id: int
    paper_id: int
    score: float
    summary: Optional[str]
    notified: Optional[datetime]
    created_at: datetime
    paper: PaperResponse

    model_config = {"from_attributes": True}


class RecommendationWithPaper(BaseModel):
    paper_title: str
    paper_url: str
    authors: str
    publish_date: date
    score_percent: float
    summary: Optional[str]

    model_config = {"from_attributes": True}
