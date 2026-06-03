"""
F009: 論文検索 API
保存済み論文をタイトル / 著者 / 年 / カテゴリで検索
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import extract

from app.models.database import Paper, get_db
from app.schemas.schemas import PaperResponse

router = APIRouter()


@router.get("/", response_model=List[PaperResponse], summary="論文一覧 / 検索 (F009)")
def search_papers(
    title:    Optional[str] = Query(None, description="タイトルで部分一致検索"),
    author:   Optional[str] = Query(None, description="著者名で部分一致検索"),
    year:     Optional[int] = Query(None, description="公開年"),
    category: Optional[str] = Query(None, description="arXivカテゴリ (例: cs.AI)"),
    limit:    int = Query(50, le=200),
    offset:   int = Query(0),
    db: Session = Depends(get_db),
):
    query = db.query(Paper)

    if title:
        query = query.filter(Paper.title.ilike(f"%{title}%"))
    if author:
        query = query.filter(Paper.authors.ilike(f"%{author}%"))
    if year:
        query = query.filter(extract("year", Paper.publish_date) == year)
    if category:
        query = query.filter(Paper.category.ilike(f"%{category}%"))

    return query.order_by(Paper.publish_date.desc()).offset(offset).limit(limit).all()


@router.get("/{paper_id}", response_model=PaperResponse, summary="論文詳細取得")
def get_paper(paper_id: int, db: Session = Depends(get_db)):
    from fastapi import HTTPException
    paper = db.query(Paper).filter(Paper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="論文が見つかりません")
    return paper
