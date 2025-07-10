import os
import logging
from typing import List, Dict, Any
import google.generativeai as genai
from utils.logger import setup_logger, log_error

class SummarizerAgent:
    "Google Gemini を用いて記事を要約するエージェント"

    def __init__(self, log_level: str = "INFO"):
        self.logger = setup_logger("SummarizerAgent", log_level)

        try:
            genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
            self.gemini_model = genai.GenerativeModel("gemini-pro")
        except Exception as e:
            log_error(self.logger, e, "Gemini API 初期化失敗")
            self.gemini_model = None

    def summarize_articles(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        "記事リストを要約"
        self.logger.info(f"記事要約開始: {len(articles)}件")
        summarized_articles = []

        for article in articles:
            try:
                summary = self._summarize_single_article(article)
                article_with_summary = article.copy()
                article_with_summary['summary'] = summary
                summarized_articles.append(article_with_summary)
            except Exception as e:
                log_error(self.logger, e, f"要約エラー: {article.get('title', 'Unknown')}")
                article_with_summary = article.copy()
                article_with_summary['summary'] = "要約に失敗しました。"
                summarized_articles.append(article_with_summary)

        self.logger.info(f"要約完了: {len(summarized_articles)}件")
        return summarized_articles

    def _summarize_single_article(self, article: Dict[str, Any]) -> str:
        "Gemini を使って要約を生成（500文字程度）"
        content = article.get('content', '')

        if not content.strip():
            return "（本文が空のため要約できません）"

        if self.gemini_model is not None:
            try:
                prompt = (
                    "以下の日本語記事を500文字以内で、要点をわかりやすく自然な文章で要約してください。\n\n"
                    f"{content}"
                )
                response = self.gemini_model.generate_content(prompt)
                return response.text.strip()
            except Exception as e:
                self.logger.debug(f"Gemini 要約失敗: {str(e)}")

        return "（Geminiによる要約に失敗しました）"
