"""
F005/F006: 関連度計算・論文推薦サービス
TF-IDF + コサイン類似度（または Sentence-BERT）を使って
ユーザの研究テーマと論文Abstractの関連度を計算する
"""

import logging
from typing import List, Optional

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy.orm import Session

from app.models.database import Paper, Topic, Recommendation

logger = logging.getLogger(__name__)

RECOMMEND_THRESHOLD = 0.70  # F006: 関連度 > 70% の論文を推薦


# ──────────────────────────────────────────────
# 関連度計算（F005）
# ──────────────────────────────────────────────

def compute_relevance_tfidf(topic_texts: List[str], abstract: str) -> float:
    """
    TF-IDF + コサイン類似度で関連度を計算。
    Args:
        topic_texts: 研究テーマのリスト（例: ["LLM", "Interpretable"]）
        abstract: 論文のAbstract
    Returns:
        関連度スコア（0.0 ~ 1.0）
    """
    topic_query = " ".join(topic_texts)
    corpus = [topic_query, abstract]

    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
    try:
        tfidf_matrix = vectorizer.fit_transform(corpus)
        score = float(cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0])
    except ValueError:
        # 語彙が空の場合など
        score = 0.0

    return min(score, 1.0)


def compute_relevance(topics: List[str], abstract: str, method: str = "tfidf") -> float:
    """
    関連度計算のエントリポイント。
    method: "tfidf" | "sbert"（Sentence-BERTはオプション）
    """
    if method == "sbert":
        try:
            return _compute_relevance_sbert(topics, abstract)
        except ImportError:
            logger.warning("sentence-transformers が未インストール。TF-IDFにフォールバック。")

    return compute_relevance_tfidf(topics, abstract)


def _compute_relevance_sbert(topics: List[str], abstract: str) -> float:
    """
    Sentence-BERT を使った関連度計算（オプション）。
    pip install sentence-transformers が必要。
    """
    from sentence_transformers import SentenceTransformer, util  # type: ignore

    model = SentenceTransformer("all-MiniLM-L6-v2")
    topic_text = " ".join(topics)
    embeddings = model.encode([topic_text, abstract], convert_to_tensor=True)
    score = float(util.cos_sim(embeddings[0], embeddings[1]))
    return max(0.0, min(score, 1.0))


# ──────────────────────────────────────────────
# 推薦生成（F006）
# ──────────────────────────────────────────────

def generate_recommendations(db: Session, threshold: float = RECOMMEND_THRESHOLD) -> int:
    """
    未処理の論文に対して関連度を計算し、閾値を超えたものを推薦テーブルへ保存。
    Returns: 推薦件数
    """
    topics = db.query(Topic.name).all()
    topic_names = [t[0] for t in topics]
    if not topic_names:
        logger.warning("トピックが未登録です")
        return 0

    # 未推薦論文のみ対象
    recommended_ids = db.query(Recommendation.paper_id).subquery()
    papers = db.query(Paper).filter(~Paper.id.in_(recommended_ids)).all()

    count = 0
    for paper in papers:
        score = compute_relevance(topic_names, paper.abstract)
        if score >= threshold:
            rec = Recommendation(paper_id=paper.id, score=score)
            db.add(rec)
            count += 1
            logger.debug(f"推薦: {paper.arxiv_id} score={score:.3f}")

    db.commit()
    logger.info(f"推薦生成: {count} 件 (threshold={threshold:.0%})")
    return count
