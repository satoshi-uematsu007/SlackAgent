import os
import json
import requests
from datetime import datetime
from typing import List, Dict, Any

from langchain_google_genai import ChatGoogleGenerativeAI
from utils.logger import setup_logger, log_error

class NotifierAgent:
    def __init__(self, webhook_url: str, log_level: str = "INFO"):
        self.logger = setup_logger("NotifierAgent", log_level)
        self.webhook_url = webhook_url
        self.session = requests.Session()

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            self.logger.error(
                "環境変数 GEMINI_API_KEY が設定されていません。コメント生成は無効化されます。"
            )
            self.llm = None
        else:
            try:
                self.llm = ChatGoogleGenerativeAI(
                    model="gemini-1.5-flash", google_api_key=api_key
                )
                self.logger.info(
                    "Gemini モデル（gemini-1.5-flash）を LangChain 経由で初期化しました。"
                )
            except Exception as e:
                log_error(self.logger, e, "Gemini API 初期化失敗")
                self.llm = None

    def send_notification(self, articles: List[Dict[str, Any]]) -> bool:
        if not articles:
            self.logger.info("送信する記事がありません")
            return True

        try:
            cloud_articles = [a for a in articles if a.get('category') == 'Cloud']
            ai_articles = [a for a in articles if a.get('category') == 'AI']
            cloud_articles.sort(key=lambda x: x.get('trust_score', 0), reverse=True)
            ai_articles.sort(key=lambda x: x.get('trust_score', 0), reverse=True)

            blocks = self._create_blocks(cloud_articles, ai_articles)
            success = self._send_to_slack(blocks)

            if success:
                self.logger.info(f"Slack通知成功: {len(articles)}件")
                self._log_trust_statistics(articles)
            else:
                self.logger.error("Slack通知失敗")

            return success

        except Exception as e:
            log_error(self.logger, e, "通知エラー")
            return False

    def _create_blocks(self, cloud_articles: List[Dict], ai_articles: List[Dict]) -> List[Dict]:
        today = datetime.now().strftime('%Y-%m-%d')
        blocks = []

        header_block = {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*■今日のクラウド & AI記事まとめ（{today}）*"
            }
        }
        blocks.append(header_block)

        def add_article_blocks(label: str, articles: List[Dict]):
            if not articles:
                return
            blocks.append({"type": "divider"})
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*■{label}関連記事*"}
            })

            for i, article in enumerate(articles[:5], 1):
                title = self._sanitize_text(article.get("title", "No Title"))
                url = article.get("url", "#")
                summary = self._sanitize_text(article.get("summary", "No Summary"))
                comment = self._sanitize_text(
                    self._generate_comment(summary, tone="friendly")
                )
                trust_score = article.get("trust_score", 0)
                emoji = self._get_trust_emoji(trust_score)

                # ✅ 要約の長さを 600文字に制限
                if len(summary) > 600:
                    summary = summary[:597] + "..."

                text = f"{i}. {emoji} *<{url}|{title}>* (信頼度: {trust_score})\n　・{summary}"
                if comment:
                    text += f"\n　・{comment}"
                blocks.append({
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": text}
                })

        add_article_blocks("クラウド", cloud_articles)
        add_article_blocks("AI", ai_articles)

        blocks.append({"type": "divider"})
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*■信頼度スコア*\n⭐⭐⭐ 10-9: 公式・企業公式\n⭐⭐ 8-7: 信頼性の高い技術メディア\n⭐ 6-5: 一般的な技術ブログ"
            }
        })

        return blocks

    def _generate_comment(self, summary: str, tone: str = "friendly") -> str:
        """要約からSlack向けのコメントを生成"""
        if not self.llm or not summary:
            return ""
        prompt = (
            f"以下の要約を基に、Slack向けに{tone}な一文コメントを日本語で作成してください。\n\n{summary}"
        )
        try:
            response = self.llm.invoke(prompt)
            return response.content.strip()
        except Exception as e:
            self.logger.debug(f"コメント生成失敗: {e}")
            return ""

    def _sanitize_text(self, text: str) -> str:
        if not text:
            return ""
        text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return ''.join(char for char in text if ord(char) >= 32 or char in '\n\t')

    def _send_to_slack(self, blocks: List[Dict]) -> bool:
        try:
            payload = {
                "blocks": blocks,
                "username": "NewsBot",
                "icon_emoji": ":newspaper:"
            }

            self.logger.debug("Slack Payload:\n" + json.dumps(payload, ensure_ascii=False, indent=2))

            response = self.session.post(
                self.webhook_url,
                json=payload,
                timeout=30
            )

            self.logger.debug(f"Slack response: {response.status_code} {response.text}")
            response.raise_for_status()
            return True

        except requests.RequestException as e:
            self.logger.error("Slack送信エラー: " + str(e))
            if e.response is not None:
                self.logger.error(f"Status: {e.response.status_code}, Body: {e.response.text}")
            log_error(self.logger, e, "Slack送信エラー")
            return False

    def _get_trust_emoji(self, trust_score: int) -> str:
        if trust_score >= 9:
            return "⭐⭐⭐"
        elif trust_score >= 7:
            return "⭐⭐"
        elif trust_score >= 5:
            return "⭐"
        else:
            return "❓"

    def _log_trust_statistics(self, articles: List[Dict[str, Any]]):
        scores = [a.get('trust_score', 0) for a in articles]
        if not scores:
            return

        self.logger.info(f"信頼度統計 - 平均: {sum(scores)/len(scores):.1f}")
        self.logger.info(f"高: {len([s for s in scores if s >= 9])}, 中: {len([s for s in scores if 7 <= s < 9])}, 低: {len([s for s in scores if 5 <= s < 7])}, 不明: {len([s for s in scores if s < 5])}")

    def test_webhook(self) -> bool:
        try:
            payload = {"text": "✅ Webhookテスト送信 - 通信成功"}
            response = self.session.post(self.webhook_url, json=payload, timeout=10)
            self.logger.info(f"テスト送信ステータス: {response.status_code}, レスポンス: {response.text}")
            response.raise_for_status()
            return True
        except requests.RequestException as e:
            self.logger.error(f"Webhookテストエラー: {e}")
            return False
