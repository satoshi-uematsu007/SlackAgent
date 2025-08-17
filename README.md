# 📘 マルチエージェント型Slack配信システム

AWS や GCP などのクラウド技術、GPT/LLM を中心とした AI 技術に関する最新記事を  
1 日 1 回自動で収集・分類・要約し、Slack に通知するシステムです。  
日本語の記事のみを対象にする言語フィルタも備えています。

## 🏗️ システム構成

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FetcherAgent  │────│ ClassifierAgent │────│ SummarizerAgent │
│   (記事収集)    │    │    (記事分類)   │    │    (記事要約)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                        │                        │
         └────────────────────────┼────────────────────────┘
                                  │
                ┌─────────────────┐│┌─────────────────┐
                │   LeaderAgent   │││  NotifierAgent  │
                │   (全体制御)    │││  (Slack通知)    │
                └─────────────────┘│└─────────────────┘
                                  │
                                  ▼
                            📱 Slack通知
```

## 🧠 AIエージェント実装概要

本プロジェクトでは複数のエージェントが Python で実装され、`main.py` 内の `LeaderAgent` がそれらを順番に呼び出して処理します。

```python
# main.py より抜粋
fetcher = FetcherAgent()
classifier = ClassifierAgent()
summarizer = SummarizerAgent()
notifier = NotifierAgent(webhook_url)

articles = fetcher.fetch_articles()
classified = classifier.classify_articles(articles)
summarized = summarizer.summarize_articles(classified)
notifier.send_notification(summarized)
```



| エージェント | 役割 | 主な実装ファイル |
| --- | --- | --- |
| FetcherAgent | RSS 収集と信頼度スコア計算 | `agents/fetcher.py` |
| ClassifierAgent | 記事を「Cloud」「AI」に分類 | `agents/classifier.py` |
| SummarizerAgent | Gemini による要約生成 | `agents/summarizer.py` |
| NotifierAgent | Slack への投稿とコメント生成 | `agents/notifier.py` |

## 🚀 クイックスタート

### 1. 環境構築

```bash
# リポジトリをクローン
git clone <repository-url>
cd SlackAgent

# 仮想環境作成
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 依存関係インストール
pip install -r requirements.txt

# NLTK データダウンロード
python -c "import nltk; nltk.download('punkt')"
```

### 2. 設定

```bash
# .env ファイル作成
cp .env.sample .env

# Slack Webhook URL を設定
vim .env
```

`.env` ファイルの内容:
```
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
LOG_LEVEL=INFO
```

### 3. テスト実行

```bash
# システムテスト
python test_system.py

# 実際の通知テスト
python test_system.py --send-test

# 本番実行
python main.py
```

### 4. Expo モバイルアプリ配布

App Store 配布にあたり、先に `mobile-app/app.json` の `ios.bundleIdentifier` を自分の App ID に設定してください。

```bash
cd mobile-app
npm install
npx expo login               # Expoアカウントでログイン
npx eas build -p android --profile production
npx eas build -p ios --profile production
npx eas submit -p ios --latest
```

Expo のダッシュボードから生成されたビルドを確認し、`eas submit` で App Store Connect へアップロードできます。

## 📂 ディレクトリ構成

```
SlackAgent/
├── main.py                    # LeaderAgent (メイン実行)
├── agents/
│   ├── __init__.py
│   ├── fetcher.py            # 記事収集
│   ├── classifier.py         # 記事分類
│   ├── summarizer.py         # 記事要約
│   └── notifier.py           # Slack通知
├── config/
│   └── keywords.yaml         # 分類キーワード
├── utils/
│   └── logger.py             # ログ管理
├── mobile-app/               # Expoベースのモバイルアプリ
├── .env                      # 環境変数
├── requirements.txt          # 依存関係
├── test_system.py            # テストスクリプト
├── setup.sh                  # セットアップスクリプト
└── README.md                 # このファイル
```

## 🔧 各エージェントの詳細

### FetcherAgent (記事収集)
- **機能**: RSS/スクレイピングによる記事収集
- **対象サイト**: Zenn, Qiita, ClassMethod など
- **フィルタリング**: 事前定義キーワードによる絞り込み
- **重複除去**: URL ベースの重複チェック
- **補助AI**: Gemini を利用したタグ抽出（オプション）

### ClassifierAgent (記事分類)
- **機能**: 記事を「Cloud」「AI」カテゴリに分類
- **手法**: Gemini によるLLM分類
- **出力**: カテゴリと信頼度スコアをJSONで返却

### SummarizerAgent (記事要約)
- **機能**: Gemini を用いた日本語要約生成
- **フォールバック**: モデル初期化失敗時は固定メッセージを返却

### NotifierAgent (Slack通知)
- **機能**: Slack Webhook による通知
- **フォーマット**: カテゴリ別整理、要約付き
- **コメント生成**: Gemini による一言コメント
- **エラー通知**: システムエラー時の通知機能
- **制限**: 記事数制限（カテゴリ別最大5件）

### LeaderAgent (全体制御)
- **機能**: 全体フロー制御、エラーハンドリング
- **ログ管理**: 統一ログフォーマット
- **ヘルスチェック**: システム動作確認
- **エラー通知**: 失敗時のSlack通知

## 📅 定期実行設定

### GitHub Actions（推奨）

`.github/workflows/news-agent.yml`:
```yaml
name: Daily News Agent
on:
  schedule:
    - cron: '0 0 * * *'  # 毎日 UTC 00:00 (JST 09:00)
  workflow_dispatch:

jobs:
  run-news-agent:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    - run: |
        pip install -r requirements.txt
        python main.py
      env:
        SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
```

### cron（Linux/macOS）

```bash
# crontab -e
0 9 * * * cd /path/to/SlackAgent && python main.py >> /var/log/SlackAgent.log 2>&1
```

## 🛠️ カスタマイズ

### キーワード追加
`config/keywords.yaml` を編集:
```yaml
cloud:
  - AWS
  - Lambda
  - your-keyword

ai:
  - GPT
  - LLM
  - your-ai-keyword
```

### RSS フィード追加
`agents/fetcher.py` の `self.rss_feeds` に追加:
```python
self.rss_feeds = [
    "https://example.com/feed.xml",
    # 新しいフィードを追加
]
```

### 通知フォーマット変更
`agents/notifier.py` の `_create_message` メソッドを編集

## 🔍 トラブルシューティング

### よくある問題

1. **記事が収集されない**
   - RSS フィードの URL を確認
   - キーワードフィルタを確認
   - ログでエラーを確認: `python main.py`

2. **要約が期待通りでない**
   - 記事本文が取得できているか確認
   - `sumy` の設定を調整
   - フォールバック要約が使用されていないか確認

3. **Slack通知が届かない**
   - Webhook URL が正しいか確認
   - Slack ワークスペースの設定を確認
   - テスト通知: `python test_system.py --send-test`

### ログ確認

```bash
# 詳細ログ
LOG_LEVEL=DEBUG python main.py

# ヘルスチェック
python main.py --health
```

## 💰 コスト

- **完全無料**: 使用ライブラリ、API はすべて無料
- **GitHub Actions**: 月2000分まで無料
- **Slack**: Webhook は無料プランでも利用可能

## 🔒 セキュリティ

- **認証情報**: `.env` ファイルで管理
- **GitHub Secrets**: GitHub Actions 使用時
- **スクレイピング**: robots.txt を遵守
- **レート制限**: 適切な間隔でリクエスト

## 📈 拡張可能性

- **新しいエージェント**: agents/ に追加
- **新しいデータソース**: FetcherAgent に追加
- **新しい通知先**: NotifierAgent を拡張
- **新しい要約手法**: SummarizerAgent を拡張

## 🤝 貢献

1. Fork
2. Feature Branch作成
3. Commit
4. Push
5. Pull Request

## 📄 ライセンス

MIT License

## 🙋‍♂️ サポート

- Issues: GitHub Issues
- 質問: Discussions
- 緊急: Slack通知のエラー通知機能を活用

---

**Happy Coding! 🚀**
