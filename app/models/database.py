"""
DB接続設定 & SQLAlchemyモデル定義
SQLite + SQLAlchemy ORM
"""

from datetime import date
from sqlalchemy import (
    create_engine, Column, Integer, String,
    Text, Float, Date, DateTime, ForeignKey, func
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

DATABASE_URL = "sqlite:///./rprs.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # SQLite用
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ──────────────────────────────────────────────
# テーブル定義
# ──────────────────────────────────────────────

class Topic(Base):
    """F001: 研究テーマ管理"""
    __tablename__ = "topics"

    id   = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), unique=True, nullable=False)
    created_at = Column(DateTime, default=func.now())


class Paper(Base):
    """F002/F003: 論文収集・保存"""
    __tablename__ = "papers"

    id           = Column(Integer, primary_key=True, index=True, autoincrement=True)
    arxiv_id     = Column(String(50), unique=True, nullable=False, index=True)   # 重複チェック用 (F004)
    title        = Column(Text, nullable=False)
    authors      = Column(Text, nullable=False)           # JSON文字列で保存
    abstract     = Column(Text, nullable=False)
    url          = Column(Text, nullable=False)
    category     = Column(String(50))
    publish_date = Column(Date, nullable=False)
    created_at   = Column(DateTime, default=func.now())

    recommendations = relationship("Recommendation", back_populates="paper", cascade="all, delete")


class Recommendation(Base):
    """F005/F006: 関連度計算・論文推薦"""
    __tablename__ = "recommendations"

    id        = Column(Integer, primary_key=True, index=True, autoincrement=True)
    paper_id  = Column(Integer, ForeignKey("papers.id", ondelete="CASCADE"), nullable=False)
    score     = Column(Float, nullable=False)             # 0.0 ~ 1.0
    summary   = Column(Text)                              # F007: 3行要約
    notified  = Column(DateTime, nullable=True)           # F008: メール通知済み日時
    created_at = Column(DateTime, default=func.now())

    paper = relationship("Paper", back_populates="recommendations")


# ──────────────────────────────────────────────
# ユーティリティ
# ──────────────────────────────────────────────

def create_tables():
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI依存性注入用DBセッション"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
