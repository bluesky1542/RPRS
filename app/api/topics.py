"""
F001: 研究テーマ管理 API
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.models.database import Topic, get_db
from app.schemas.schemas import TopicCreate, TopicResponse

router = APIRouter()


@router.get("/", response_model=List[TopicResponse], summary="トピック一覧取得")
def list_topics(db: Session = Depends(get_db)):
    return db.query(Topic).order_by(Topic.id).all()


@router.post("/", response_model=TopicResponse, status_code=status.HTTP_201_CREATED, summary="トピック登録")
def create_topic(body: TopicCreate, db: Session = Depends(get_db)):
    existing = db.query(Topic).filter(Topic.name == body.name).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"'{body.name}' は既に登録済みです")
    topic = Topic(name=body.name)
    db.add(topic)
    db.commit()
    db.refresh(topic)
    return topic


@router.delete("/{topic_id}", status_code=status.HTTP_204_NO_CONTENT, summary="トピック削除")
def delete_topic(topic_id: int, db: Session = Depends(get_db)):
    topic = db.query(Topic).filter(Topic.id == topic_id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="トピックが見つかりません")
    db.delete(topic)
    db.commit()
