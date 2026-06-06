"""
F002/F003/F004: 論文収集・保存・重複除去サービス
arXiv API を使って論文を取得し、DBへ保存する
"""

import json
import logging
import time
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from typing import List

import requests
import xml.etree.ElementTree as ET
from sqlalchemy.orm import Session

from app.models.database import Paper, Topic

logger = logging.getLogger(__name__)

ARXIV_API_URL = "https://export.arxiv.org/api/query"
NS = {"atom": "http://www.w3.org/2005/Atom"}

SIMILARITY_THRESHOLD = 0.85  # タイトル類似度の閾値（F004）
REQUEST_INTERVAL = 5.0        # arXiv APIへのリクエスト間隔（秒）
MAX_RETRIES = 5               # リトライ最大回数
RETRY_WAIT_BASE = 15          # リトライ初回待機秒数（指数バックオフ）
REQUEST_TIMEOUT = 120         # タイムアウト秒数


# ──────────────────────────────────────────────
# arXiv API クライアント
# ──────────────────────────────────────────────

def _build_query(topics: List[str], days_back: int = 7) -> str:
    """トピックリストからarXiv検索クエリを生成"""
    topic_queries = [f"abs:{t} OR ti:{t}" for t in topics]
    return " OR ".join(topic_queries)


def _request_with_retry(url: str, params: dict) -> requests.Response:
    """
    429 Too Many Requests・タイムアウトに対して
    指数バックオフでリトライするHTTPクライアント。
    15秒 → 30秒 → 60秒 → 120秒 → 240秒 の順で待機。
    """
    for attempt in range(1, MAX_RETRIES + 1):
        time.sleep(REQUEST_INTERVAL)  # 毎回最低5秒待機
        try:
            response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)

            if response.status_code == 429:
                wait = RETRY_WAIT_BASE * (2 ** (attempt - 1))
                logger.warning(f"429 Too Many Requests。{wait}秒後にリトライ ({attempt}/{MAX_RETRIES})")
                time.sleep(wait)
                continue

            response.raise_for_status()
            return response

        except requests.exceptions.Timeout:
            wait = RETRY_WAIT_BASE * (2 ** (attempt - 1))
            logger.warning(f"タイムアウト発生。{wait}秒後にリトライ ({attempt}/{MAX_RETRIES})")
            if attempt < MAX_RETRIES:
                time.sleep(wait)
            else:
                raise

        except requests.exceptions.ConnectionError:
            wait = RETRY_WAIT_BASE * (2 ** (attempt - 1))
            logger.warning(f"接続エラー。{wait}秒後にリトライ ({attempt}/{MAX_RETRIES})")
            if attempt < MAX_RETRIES:
                time.sleep(wait)
            else:
                raise

    raise RuntimeError(f"arXiv APIへのリクエストが{MAX_RETRIES}回失敗しました")


def fetch_arxiv_papers(topics: List[str], max_results: int = 50, days_back: int = 7) -> List[dict]:
    """
    arXiv APIから論文を取得する。
    Args:
        topics: 検索トピックリスト
        max_results: 最大取得件数（タイムアウト対策で100→50に削減）
        days_back: 何日前まで遡るか
    Returns:
        論文情報のリスト
    """
    if not topics:
        logger.warning("トピックが設定されていません")
        return []

    query = _build_query(topics, days_back)
    params = {
        "search_query": query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }

    logger.info(f"arXiv APIへのリクエスト: query={query[:80]}...")
    response = _request_with_retry(ARXIV_API_URL, params)

    return _parse_arxiv_response(response.text, days_back)


def _parse_arxiv_response(xml_text: str, days_back: int) -> List[dict]:
    """arXiv APIのXMLレスポンスをパース"""
    root = ET.fromstring(xml_text)
    entries = root.findall("atom:entry", NS)
    papers = []

    cutoff_date = datetime.utcnow() - timedelta(days=days_back)

    for entry in entries:
        try:
            arxiv_id_raw = entry.find("atom:id", NS).text
            arxiv_id = arxiv_id_raw.split("/abs/")[-1]

            published_str = entry.find("atom:published", NS).text
            published_dt = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
            if published_dt.replace(tzinfo=None) < cutoff_date:
                continue

            title = entry.find("atom:title", NS).text.strip().replace("\n", " ")
            abstract = entry.find("atom:summary", NS).text.strip().replace("\n", " ")

            authors = [
                a.find("atom:name", NS).text
                for a in entry.findall("atom:author", NS)
                if a.find("atom:name", NS) is not None
            ]

            category_el = entry.find("atom:category", NS)
            category = category_el.attrib.get("term", "") if category_el is not None else ""

            papers.append({
                "arxiv_id": arxiv_id,
                "title": title,
                "authors": json.dumps(authors, ensure_ascii=False),
                "abstract": abstract,
                "url": f"https://arxiv.org/abs/{arxiv_id}",
                "category": category,
                "publish_date": published_dt.date(),
            })
        except Exception as e:
            logger.warning(f"論文パースエラー: {e}")
            continue

    logger.info(f"取得論文数: {len(papers)}")
    return papers


# ──────────────────────────────────────────────
# 重複チェック（F004）
# ──────────────────────────────────────────────

def _title_similarity(a: str, b: str) -> float:
    """タイトル類似度をSequenceMatcherで計算"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def is_duplicate(db: Session, paper_data: dict) -> bool:
    """
    重複判定：
    1. arxiv_id の完全一致
    2. タイトル類似度 >= SIMILARITY_THRESHOLD
    """
    exists = db.query(Paper).filter(Paper.arxiv_id == paper_data["arxiv_id"]).first()
    if exists:
        return True

    recent_papers = db.query(Paper.title).order_by(Paper.created_at.desc()).limit(50).all()
    for (existing_title,) in recent_papers:
        if _title_similarity(paper_data["title"], existing_title) >= SIMILARITY_THRESHOLD:
            logger.debug(f"タイトル類似: '{paper_data['title'][:40]}' ≈ '{existing_title[:40]}'")
            return True

    return False


# ──────────────────────────────────────────────
# 保存（F003）
# ──────────────────────────────────────────────

def save_new_papers(db: Session, papers_data: List[dict]) -> int:
    """
    新規論文のみDBへ保存。重複はスキップ。
    Returns: 保存件数
    """
    saved = 0
    for data in papers_data:
        if is_duplicate(db, data):
            logger.debug(f"スキップ（重複）: {data['arxiv_id']}")
            continue

        paper = Paper(**data)
        db.add(paper)
        saved += 1

    db.commit()
    logger.info(f"新規保存: {saved} 件")
    return saved


# ──────────────────────────────────────────────
# メイン収集フロー
# ──────────────────────────────────────────────

def collect_papers(db: Session) -> int:
    """
    DBのトピック一覧を読み込み → arXiv取得 → 保存
    """
    topics = db.query(Topic.name).all()
    topic_names = [t[0] for t in topics]

    if not topic_names:
        logger.warning("トピックが未登録です。先にトピックを登録してください。")
        return 0

    papers_data = fetch_arxiv_papers(topic_names)
    return save_new_papers(db, papers_data)
