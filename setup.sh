setup_script = """
#!/bin/bash
# setup.sh - 初期セットアップスクリプト

echo "📘 マルチエージェント型Slack配信システム セットアップ"

# Python バージョンチェック
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python version: $python_version"

# 仮想環境作成
echo "仮想環境を作成中..."
python3 -m venv venv
source venv/bin/activate

# 依存関係インストール
echo "依存関係をインストール中..."
pip install --upgrade pip
pip install -r requirements.txt

# 設定ファイル作成
echo "設定ファイルを作成中..."
if [ ! -f .env ]; then
    echo "SLACK_WEBHOOK_URL=YOUR_WEBHOOK_URL_HERE" > .env
    echo "LOG_LEVEL=INFO" >> .env
    echo "⚠️  .env ファイルを編集してSlack Webhook URLを設定してください"
fi

# ディレクトリ作成
mkdir -p logs
mkdir -p config
mkdir -p agents
mkdir -p utils

# NLTK データダウンロード
echo "NLTK データをダウンロード中..."
python3 -c "import nltk; nltk.download('punkt')"

echo "✅ セットアップ完了!"
echo "次のステップ:"
echo "1. .env ファイルでSlack Webhook URLを設定"
echo "2. python main.py でテスト実行"
echo "3. crontab または GitHub Actions で定期実行設定"
"""