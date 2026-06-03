"""
F005/F006/F007/F008: 推薦・要約・通知 API
"""

from typing import List
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from app.models.database import Recommendation, get_db
from app.schemas.schemas import RecommendationResponse
from app.services.scorer import generate_recommendations
from app.services.summarizer import fill_missing_summaries
from app.services.notifier import send_notification
from app.services.collector import collect_papers

router = APIRouter()


@router.get("/", response_model=List[RecommendationResponse], summary="推薦論文一覧")
def list_recommendations(
    min_score: float = 0.0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    return (
        db.query(Recommendation)
        .filter(Recommendation.score >= min_score)
        .order_by(Recommendation.score.desc())
        .limit(limit)
        .all()
    )


@router.post("/run", summary="パイプライン手動実行（収集→関連度→要約）")
def run_pipeline(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    収集 → 関連度計算 → 要約生成 を一括実行（バックグラウンド）
    """
    def _pipeline():
        n_collected = collect_papers(db)
        n_recommended = generate_recommendations(db)
        n_summarized = fill_missing_summaries(db)
        return n_collected, n_recommended, n_summarized

    background_tasks.add_task(_pipeline)
    return {"message": "パイプラインをバックグラウンドで開始しました"}


@router.post("/notify", summary="メール通知送信 (F008)")
def notify(dry_run: bool = True, db: Session = Depends(get_db)):
    count = send_notification(db, dry_run=dry_run)
    return {"notified_count": count, "dry_run": dry_run}
