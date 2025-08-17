import os
from typing import List, Dict, Any

from langchain_google_genai import ChatGoogleGenerativeAI
from utils.logger import setup_logger, log_error

class SummarizerAgent:
    """LangChain を通じて Google Gemini で記事要約を行うエージェント"""

    def __init__(self, log_level: str = "INFO"):
        self.logger = setup_logger("SummarizerAgent", log_level)

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            self.logger.error(
                "環境変数 GEMINI_API_KEY が設定されていません。Gemini 要約は無効化されます。"
            )
            self.llm = None
            return

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

    def summarize_articles(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """記事リストを要約"""
        self.logger.info(f"記事要約開始: {len(articles)}件")
        summarized_articles = []

        for article in articles:
            try:
                summary = self._summarize_single_article(article)
            except Exception as e:
                log_error(self.logger, e, f"要約エラー: {article.get('title', 'Unknown')}")
                summary = "要約に失敗しました。"

            article_with_summary = article.copy()
            article_with_summary["summary"] = summary
            summarized_articles.append(article_with_summary)

        self.logger.info(f"要約完了: {len(summarized_articles)}件")
        return summarized_articles

    def _summarize_single_article(self, article: Dict[str, Any]) -> str:
        "Gemini を使って要約を生成（500文字程度）"
        content = article.get('content', '').strip()

        if not content:
            return "（本文が空のため要約できません）"

        if not self.llm:
            return "（Geminiモデルが初期化されていません）"

        try:
            prompt = (
                "以下の日本語記事を500文字以内で、要点をわかりやすく自然な文章で要約してください。\n\n"
                f"{content}"
            )
            response = self.llm.invoke(prompt)
            return response.content.strip()
        except Exception as e:
            self.logger.warning(f"Gemini 要約失敗: {str(e)}")
            return "（Geminiによる要約に失敗しました）"
