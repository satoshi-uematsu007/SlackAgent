import requests
from datetime import datetime
from typing import List, Dict, Any
import logging
from utils.logger import setup_logger, log_error

class NotifierAgent:
    """
    Slack通知エージェント（Block Kit対応、信頼度付き、太字＋リンク表示）
    """

    def __init__(self, webhook_url: str, log_level: str = "INFO"):
        self.logger = setup_logger("NotifierAgent", log_level)
        self.webhook_url = webhook_url
        self.session = requests.Session()

    def send_notification(self, articles: List[Dict[str, Any]]) -> bool:
        if not articles:
            self.logger.info("送信する記事がありません")
            return True

        try:
            cloud_articles = [a for a in articles if a.get('category') == 'Cloud']
            ai_articles = [a for a in articles if a.get('category') == 'AI']

            cloud_articles.sort(key=lambda x: x.get('trust_score', 0), reverse=True)
            ai_articles.sort(key=lambda x: x.get('trust_score', 0), reverse=True)

            message = self._create_message(cloud_articles, ai_articles)

            success = self._send_to_slack(message)

            if success:
                self.logger.info(f"Slack通知成功: {len(articles)}件の記事")
                self._log_trust_statistics(articles)
            else:
                self.logger.error("Slack通知失敗")

            return success

        except Exception as e:
            log_error(self.logger, e, "通知エラー")
            return False

    def _create_message(self, cloud_articles: List[Dict], ai_articles: List[Dict]) -> str:
        today = datetime.now().strftime('%Y-%m-%d')
        lines = [f"*📰 今日のクラウド & AI記事まとめ（{today}）*\n"]

        if cloud_articles:
            lines.append("*☁️ クラウド関連記事*")
            for i, article in enumerate(cloud_articles[:5], 1):
                title = article.get('title', 'No Title')
                url = article.get('url', '#')
                summary = article.get('summary', 'No Summary')
                trust_score = article.get('trust_score', 0)
                trust_emoji = self._get_trust_emoji(trust_score)

                if len(summary) > 130:
                    summary = summary[:127] + "..."

                lines.append(f"{i}. {trust_emoji} *<{url}|{title}>* (信頼度: {trust_score})")
                lines.append(f"　・{summary}\n")

        if ai_articles:
            lines.append("*🤖 AI関連記事*")
            for i, article in enumerate(ai_articles[:5], 1):
                title = article.get('title', 'No Title')
                url = article.get('url', '#')
                summary = article.get('summary', 'No Summary')
                trust_score = article.get('trust_score', 0)
                trust_emoji = self._get_trust_emoji(trust_score)

                if len(summary) > 130:
                    summary = summary[:127] + "..."

                lines.append(f"{i}. {trust_emoji} *<{url}|{title}>* (信頼度: {trust_score})")
                lines.append(f"　・{summary}\n")

        total_articles = len(cloud_articles) + len(ai_articles)
        avg_trust_cloud = self._calculate_average_trust(cloud_articles)
        avg_trust_ai = self._calculate_average_trust(ai_articles)

        lines.append("*📊 今日の記事統計*")
        lines.append(f"• クラウド: {len(cloud_articles)}件 (平均信頼度: {avg_trust_cloud:.1f})")
        lines.append(f"• AI: {len(ai_articles)}件 (平均信頼度: {avg_trust_ai:.1f})")
        lines.append(f"• 合計: {total_articles}件\n")

        lines.append("*🔍 信頼度スコア*")
        lines.append("⭐⭐⭐ 10-9: 公式・企業公式")
        lines.append("⭐⭐ 8-7: 信頼性の高い技術メディア")
        lines.append("⭐ 6-5: 一般的な技術ブログ")

        return "\n".join(lines)

    def _send_to_slack(self, message: str) -> bool:
        """
        Block Kit を使ってメッセージを送信
        """
        try:
            payload = {
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": message
                        }
                    }
                ],
                "username": "NewsBot",
                "icon_emoji": ":newspaper:"
            }

            response = self.session.post(
                self.webhook_url,
                json=payload,
                timeout=30
            )

            response.raise_for_status()
            return True

        except requests.RequestException as e:
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

    def _calculate_average_trust(self, articles: List[Dict]) -> float:
        if not articles:
            return 0.0
        return sum(a.get('trust_score', 0) for a in articles) / len(articles)

    def _log_trust_statistics(self, articles: List[Dict[str, Any]]):
        if not articles:
            return

        trust_scores = [a.get('trust_score', 0) for a in articles]
        high = len([s for s in trust_scores if s >= 9])
        medium = len([s for s in trust_scores if 7 <= s < 9])
        low = len([s for s in trust_scores if 5 <= s < 7])
        unknown = len([s for s in trust_scores if s < 5])

        self.logger.info(f"信頼度統計 - 平均: {sum(trust_scores)/len(trust_scores):.1f}")
        self.logger.info(f"高: {high}, 中: {medium}, 低: {low}, 不明: {unknown}")
