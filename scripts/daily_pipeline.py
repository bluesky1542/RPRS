"""
GitHub Actions / cron から呼び出すCLIスクリプト
使い方:
    python scripts/daily_pipeline.py            # 収集 + 推薦 + 要約
    python scripts/daily_pipeline.py --notify   # + メール通知
    python scripts/daily_pipeline.py --dry-run  # メール送信なし（確認用）
"""

import argparse
import logging
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models.database import create_tables, SessionLocal
from app.services.collector import collect_papers
from app.services.scorer import generate_recommendations
from app.services.summarizer import fill_missing_summaries
from app.services.notifier import send_notification

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("daily_pipeline")


def main():
    parser = argparse.ArgumentParser(description="RPRS Daily Pipeline")
    parser.add_argument("--notify",  action="store_true", help="メール通知を送信する")
    parser.add_argument("--dry-run", action="store_true", help="メール送信をスキップ（確認用）")
    args = parser.parse_args()

    create_tables()
    db = SessionLocal()

    try:
        logger.info("═" * 50)
        logger.info("RPRS Daily Pipeline 開始")
        logger.info("═" * 50)

        # Step 1: 論文収集（F002/F003/F004）
        logger.info("Step 1: arXiv 論文収集")
        n_collected = collect_papers(db)
        logger.info(f"  → 新規保存: {n_collected} 件")

        # Step 2: 関連度計算・推薦（F005/F006）
        logger.info("Step 2: 関連度計算 & 推薦生成")
        n_recommended = generate_recommendations(db)
        logger.info(f"  → 推薦: {n_recommended} 件")

        # Step 3: 要約生成（F007）
        logger.info("Step 3: 要約生成")
        n_summarized = fill_missing_summaries(db)
        logger.info(f"  → 要約: {n_summarized} 件")

        # Step 4: メール通知（F008）- 任意
        if args.notify or args.dry_run:
            logger.info("Step 4: メール通知")
            n_notified = send_notification(db, dry_run=args.dry_run)
            logger.info(f"  → 通知: {n_notified} 件")

        logger.info("═" * 50)
        logger.info("Pipeline 完了")

    finally:
        db.close()


if __name__ == "__main__":
    main()
