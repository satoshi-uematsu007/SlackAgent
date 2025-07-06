test_script = """
#!/usr/bin/env python3
# test_system.py - システムテスト用スクリプト

import os
import sys
from dotenv import load_dotenv
from agents.fetcher import FetcherAgent
from agents.classifier import ClassifierAgent
from agents.summarizer import SummarizerAgent
from agents.notifier import NotifierAgent

def test_fetcher():
    \"\"\"FetcherAgentのテスト\"\"\"
    print("🔍 FetcherAgent テスト中...")
    fetcher = FetcherAgent()
    
    # 少数の記事で テスト
    articles = fetcher.fetch_articles(hours_back=72)  # 3日分
    print(f"✅ 収集記事数: {len(articles)}件")
    
    if articles:
        print(f"📄 最初の記事: {articles[0].get('title', 'No Title')}")
    
    return articles

def test_classifier(articles):
    \"\"\"ClassifierAgentのテスト\"\"\"
    print("🏷️  ClassifierAgent テスト中...")
    classifier = ClassifierAgent()
    
    classified = classifier.classify_articles(articles)
    print(f"✅ 分類記事数: {len(classified)}件")
    
    # カテゴリ別集計
    cloud_count = len([a for a in classified if a.get('category') == 'Cloud'])
    ai_count = len([a for a in classified if a.get('category') == 'AI'])
    print(f"📊 Cloud: {cloud_count}件, AI: {ai_count}件")
    
    return classified

def test_summarizer(articles):
    \"\"\"SummarizerAgentのテスト\"\"\"
    print("📝 SummarizerAgent テスト中...")
    summarizer = SummarizerAgent()
    
    # 最初の3記事のみでテスト
    test_articles = articles[:3]
    summarized = summarizer.summarize_articles(test_articles)
    print(f"✅ 要約記事数: {len(summarized)}件")
    
    for article in summarized:
        print(f"📄 {article.get('title', 'No Title')}")
        print(f"📝 要約: {article.get('summary', 'No Summary')[:100]}...")
        print("-" * 50)
    
    return summarized

def test_notifier(articles):
    \"\"\"NotifierAgentのテスト\"\"\"
    print("📱 NotifierAgent テスト中...")
    
    webhook_url = os.getenv('SLACK_WEBHOOK_URL')
    if not webhook_url:
        print("❌ SLACK_WEBHOOK_URL が設定されていません")
        return False
    
    notifier = NotifierAgent(webhook_url)
    
    # テスト通知（実際には送信しない）
    print("✅ NotifierAgent 初期化完了")
    print("⚠️  実際の通知テストは --send-test オプションで実行してください")
    
    return True

def send_test_notification():
    \"\"\"テスト通知送信\"\"\"
    print("📱 テスト通知送信中...")
    
    webhook_url = os.getenv('SLACK_WEBHOOK_URL')
    if not webhook_url:
        print("❌ SLACK_WEBHOOK_URL が設定されていません")
        return False
    
    notifier = NotifierAgent(webhook_url)
    
    # ダミー記事でテスト
    test_articles = [
        {
            'title': 'テスト記事: AWS Lambda の新機能',
            'url': 'https://example.com/test-article',
            'summary': 'これはテスト用の記事要約です。AWS Lambda の新機能について説明しています。',
            'category': 'Cloud'
        },
        {
            'title': 'テスト記事: GPT-4 の活用法',
            'url': 'https://example.com/test-article-2',
            'summary': 'これもテスト用の記事要約です。GPT-4 の活用法について説明しています。',
            'category': 'AI'
        }
    ]
    
    success = notifier.send_notification(test_articles)
    
    if success:
        print("✅ テスト通知送信完了")
    else:
        print("❌ テスト通知送信失敗")
    
    return success

def main():
    \"\"\"メイン関数\"\"\"
    load_dotenv()
    
    print("🚀 システムテスト開始")
    print("=" * 50)
    
    # コマンドライン引数チェック
    if len(sys.argv) > 1 and sys.argv[1] == "--send-test":
        send_test_notification()
        return
    
    try:
        # 1. 記事収集テスト
        articles = test_fetcher()
        if not articles:
            print("❌ 記事収集失敗")
            return
        
        print()
        
        # 2. 分類テスト
        classified = test_classifier(articles)
        if not classified:
            print("❌ 記事分類失敗")
            return
        
        print()
        
        # 3. 要約テスト
        summarized = test_summarizer(classified)
        if not summarized:
            print("❌ 記事要約失敗")
            return
        
        print()
        
        # 4. 通知テスト
        test_notifier(summarized)
        
        print()
        print("✅ 全テスト完了!")
        print("📝 実際の通知テストは: python test_system.py --send-test")
        
    except Exception as e:
        print(f"❌ テスト中にエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
"""
