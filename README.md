# Research Paper Recommendation System (RPRS)

> 自身の研究テーマに関連する新着論文を自動収集・推薦・通知するシステム

---

## 概要

論文探索の手間と毎日確認する負担を解消するため、arXiv からの論文収集〜関連度計算〜要約生成〜メール通知を **全自動化** する個人向けシステム。

```
arXiv API
   ↓ 論文収集モジュール（F002）
PostgreSQL / SQLite
   ↓ 重複チェック（F004）
   ↓ 関連度計算 TF-IDF + cos（F005）
   ↓ 要約生成 Gemini API（F007）
   ↓ メール通知（F008）
利用者
```

---

## 機能一覧

| ID   | 機能名         | 概要                                            |
|------|----------------|-------------------------------------------------|
| F001 | 研究テーマ管理 | トピックをDBに登録・削除                        |
| F002 | 論文収集       | arXiv API から毎日定期取得                      |
| F003 | 論文保存       | 新規論文のみ SQLite へ保存                      |
| F004 | 重複除去       | arxiv_id + タイトル類似度（≥0.85）で判定        |
| F005 | 関連度計算     | TF-IDF + コサイン類似度（Sentence-BERT も対応） |
| F006 | 論文推薦       | 関連度 ≥ 70% の論文を抽出                       |
| F007 | 要約生成       | Gemini API で Abstract → 3行日本語要約          |
| F008 | メール通知     | 毎週月曜 07:00 JST に推薦論文をメール送信       |
| F009 | 論文検索       | タイトル / 著者 / 年 / カテゴリで全文検索       |

---

## システム構成

```
rprs/
├── app/
│   ├── main.py                # FastAPI アプリ
│   ├── models/
│   │   └── database.py        # SQLAlchemy モデル (Topic / Paper / Recommendation)
│   ├── schemas/
│   │   └── schemas.py         # Pydantic スキーマ
│   ├── services/
│   │   ├── collector.py       # F002/F003/F004 arXiv収集・保存・重複除去
│   │   ├── scorer.py          # F005/F006 関連度計算・推薦生成
│   │   ├── summarizer.py      # F007 要約生成（Gemini API）
│   │   └── notifier.py        # F008 メール通知
│   └── api/
│       ├── topics.py          # F001 REST API
│       ├── papers.py          # F009 REST API
│       └── recommendations.py # F005〜F008 REST API
├── scripts/
│   ├── daily_pipeline.py      # CLI: 収集→推薦→要約→通知
│   └── seed_topics.py         # 初期トピック登録
├── .github/
│   └── workflows/
│       └── daily_pipeline.yml # GitHub Actions (毎日 JST 07:00)
└── requirements.txt
```

---

## DB設計

### topics

| 列名       | 型           | 説明               |
|------------|--------------|--------------------|
| id         | BIGINT (PK)  | 自動採番           |
| name       | VARCHAR(255) | 研究テーマ名       |
| created_at | DATETIME     | 登録日時           |

### papers

| 列名         | 型      | 説明                     |
|--------------|---------|--------------------------|
| id           | BIGINT  | 自動採番                 |
| arxiv_id     | VARCHAR | arXiv固有ID（重複チェック）|
| title        | TEXT    | 論文タイトル             |
| authors      | TEXT    | 著者（JSON配列）         |
| abstract     | TEXT    | Abstract                 |
| url          | TEXT    | arXiv URL                |
| category     | VARCHAR | arXivカテゴリ            |
| publish_date | DATE    | 公開日                   |
| created_at   | DATETIME| 保存日時                 |

### recommendations

| 列名       | 型      | 説明                  |
|------------|---------|-----------------------|
| id         | BIGINT  | 自動採番              |
| paper_id   | BIGINT  | papers.id (FK)        |
| score      | FLOAT   | 関連度（0.0〜1.0）    |
| summary    | TEXT    | 3行要約               |
| notified   | DATETIME| メール通知日時        |
| created_at | DATETIME| 生成日時              |

---

## セットアップ

### 1. 依存パッケージインストール

```bash
pip install -r requirements.txt
```

### 2. 環境変数設定

`.env` ファイルを作成：

```env
# Gemini API（要約生成に使用）
GEMINI_API_KEY=...

# メール送信（Gmailの場合）
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your@gmail.com
SMTP_PASSWORD=your_app_password
NOTIFY_TO=your@gmail.com
```

### 3. 初期トピック登録

```bash
python scripts/seed_topics.py
```

`scripts/seed_topics.py` の `INITIAL_TOPICS` リストを自分の研究テーマに合わせて編集してください。

### 4. API サーバー起動

```bash
uvicorn app.main:app --reload
# → http://localhost:8000/docs でSwagger UI確認可
```

### 5. 手動パイプライン実行

```bash
# 収集 → 関連度 → 要約
python scripts/daily_pipeline.py

# 上記 + メール通知
python scripts/daily_pipeline.py --notify

# メール送信なし（動作確認）
python scripts/daily_pipeline.py --dry-run
```

---

## GitHub Actions 自動実行

`.github/workflows/daily_pipeline.yml` を設定済み。

| タイミング             | 処理                          |
|------------------------|-------------------------------|
| 毎日 JST 07:00         | 収集 → 関連度計算 → 要約生成  |
| 毎週月曜 JST 07:00     | 上記 + メール通知             |

GitHub リポジトリの **Settings → Secrets** に以下を登録：

- `GEMINI_API_KEY`
- `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD`
- `NOTIFY_TO`

---

## API エンドポイント一覧

| Method | パス                          | 説明                        |
|--------|-------------------------------|-----------------------------|
| GET    | `/api/topics`                 | トピック一覧                |
| POST   | `/api/topics`                 | トピック登録                |
| DELETE | `/api/topics/{id}`            | トピック削除                |
| GET    | `/api/papers?title=&author=`  | 論文検索（F009）            |
| GET    | `/api/papers/{id}`            | 論文詳細                    |
| GET    | `/api/recommendations`        | 推薦論文一覧                |
| POST   | `/api/recommendations/run`    | パイプライン手動実行        |
| POST   | `/api/recommendations/notify` | メール通知送信              |

---

## 技術スタック

| 項目       | 採用技術                              |
|------------|---------------------------------------|
| 言語       | Python 3.11                           |
| API        | FastAPI                               |
| ORM        | SQLAlchemy 2.0                        |
| DB         | SQLite（本番移行時は PostgreSQL対応）  |
| 関連度計算 | TF-IDF + コサイン類似度（scikit-learn）|
| 要約生成   | GEMINI API (gemini-1.5-flash)          |
| 自動実行   | GitHub Actions                        |

---

## 非機能要件

| 項目     | 要件                              |
|----------|-----------------------------------|
| 性能     | 論文 10,000 件保存・検索に対応    |
| 可用性   | GitHub Actions による 24h 自動実行 |
| 拡張性   | Sentence-BERT への切替対応済み    |
