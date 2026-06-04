"""
F007: 要約生成サービス
Abstractから3行要約を生成する
（Google Gemini API 無料版を使用）
"""
 
import logging
import os
 
import google.generativeai as genai
from sqlalchemy.orm import Session
 
from app.models.database import Recommendation
 
logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
 
SUMMARY_PROMPT = """\
以下の論文Abstractを日本語で3行に要約してください。
形式は必ず以下のとおりにしてください：
1行目：本研究では〜。
2行目：従来法より〜（または提案手法として〜）。
3行目：実験結果として〜。
 
Abstract:
{abstract}
 
3行要約:"""
 
 
def generate_summary(abstract: str) -> str:
    """
    Gemini APIを使ってAbstractから3行要約を生成。
    APIキーが未設定の場合はルールベースのフォールバックを使用。
    """
    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY が未設定。ルールベース要約を使用します。")
        return _fallback_summary(abstract)
 
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-1.5-flash")  # 無料枠対応モデル
        response = model.generate_content(SUMMARY_PROMPT.format(abstract=abstract))
        return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini API エラー: {e}")
        return _fallback_summary(abstract)
 
 
def _fallback_summary(abstract: str) -> str:
    """APIが使えない場合の簡易要約（先頭文を抽出）"""
    sentences = [s.strip() for s in abstract.split(". ") if s.strip()]
    if len(sentences) >= 3:
        return f"本研究では{sentences[0]}。\n従来法より{sentences[1]}。\n実験結果として{sentences[2]}。"
    return abstract[:200] + "..."
 
 
def fill_missing_summaries(db: Session) -> int:
    """
    要約が未生成の推薦論文に対して要約を生成・保存する。
    Returns: 処理件数
    """
    recs = (
        db.query(Recommendation)
        .filter(Recommendation.summary.is_(None))
        .all()
    )
 
    count = 0
    for rec in recs:
        summary = generate_summary(rec.paper.abstract)
        rec.summary = summary
        count += 1
        logger.debug(f"要約生成: recommendation_id={rec.id}")
 
    db.commit()
    logger.info(f"要約生成完了: {count} 件")
    return count
