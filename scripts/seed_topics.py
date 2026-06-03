"""
初期データ投入スクリプト
研究テーマ（topics）をDBへ登録する

使い方:
    python scripts/seed_topics.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models.database import create_tables, SessionLocal, Topic

INITIAL_TOPICS = [
    "LLM",
    "Interpretable",
    "Explainability",
    "Transformer",
]


def seed():
    create_tables()
    db = SessionLocal()
    try:
        added = 0
        for name in INITIAL_TOPICS:
            exists = db.query(Topic).filter(Topic.name == name).first()
            if not exists:
                db.add(Topic(name=name))
                added += 1
        db.commit()
        print(f"トピック登録完了: {added} 件追加")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
