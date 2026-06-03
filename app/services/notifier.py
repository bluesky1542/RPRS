"""
F008: メール通知サービス
関連度の高い論文をメールで週次通知する
"""

import logging
import os
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List

from sqlalchemy.orm import Session

from app.models.database import Recommendation

logger = logging.getLogger(__name__)

# 環境変数から取得
SMTP_HOST     = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT     = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER     = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
NOTIFY_TO     = os.environ.get("NOTIFY_TO", "")


# ──────────────────────────────────────────────
# メール本文生成
# ──────────────────────────────────────────────

def _build_email_body(recommendations: List[Recommendation]) -> str:
    """
    推薦論文リストからメール本文を生成。
    F008 仕様: タイトル / 関連度 / 要約 / URL
    """
    lines = [
        "=" * 60,
        "Research Paper Recommendation System (RPRS)",
        f"配信日時: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"推薦論文数: {len(recommendations)} 件",
        "=" * 60,
        "",
    ]

    for i, rec in enumerate(recommendations, 1):
        paper = rec.paper
        score_pct = f"{rec.score * 100:.1f}%"
        summary = rec.summary or "（要約未生成）"

        lines += [
            f"【{i}】{paper.title}",
            f"　著者    : {paper.authors[:80]}",
            f"　公開日  : {paper.publish_date}",
            f"　関連度  : {score_pct}",
            f"　要約    :",
            *[f"　　{line}" for line in summary.split("\n")],
            f"　URL     : {paper.url}",
            "",
            "-" * 60,
            "",
        ]

    lines.append("このメールはRPRSにより自動送信されました。")
    return "\n".join(lines)


# ──────────────────────────────────────────────
# メール送信
# ──────────────────────────────────────────────

def send_notification(db: Session, dry_run: bool = False) -> int:
    """
    未通知の推薦論文をメールで送信する。
    Args:
        dry_run: Trueの場合、メールを送信せずに本文を標準出力へ表示
    Returns:
        通知対象件数
    """
    recs = (
        db.query(Recommendation)
        .filter(Recommendation.notified.is_(None))
        .filter(Recommendation.summary.isnot(None))
        .order_by(Recommendation.score.desc())
        .all()
    )

    if not recs:
        logger.info("通知対象の論文はありません")
        return 0

    body = _build_email_body(recs)

    if dry_run:
        print("=" * 60)
        print("[DRY RUN] 以下の内容でメールを送信する予定です:")
        print(body)
        _mark_as_notified(db, recs)
        return len(recs)

    if not all([SMTP_USER, SMTP_PASSWORD, NOTIFY_TO]):
        logger.warning("SMTP設定が未完了。dry_run=Trueで実行してください。")
        return 0

    try:
        msg = MIMEMultipart()
        msg["From"]    = SMTP_USER
        msg["To"]      = NOTIFY_TO
        msg["Subject"] = f"[RPRS] 推薦論文 {len(recs)}件 ({datetime.now().strftime('%Y-%m-%d')})"
        msg.attach(MIMEText(body, "plain", "utf-8"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)

        _mark_as_notified(db, recs)
        logger.info(f"メール送信完了: {len(recs)} 件")

    except Exception as e:
        logger.error(f"メール送信エラー: {e}")
        raise

    return len(recs)


def _mark_as_notified(db: Session, recs: List[Recommendation]) -> None:
    now = datetime.now(timezone.utc)
    for rec in recs:
        rec.notified = now
    db.commit()
