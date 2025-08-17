import os
import json
from typing import List, Dict, Any

from langchain_google_genai import ChatGoogleGenerativeAI
from utils.logger import setup_logger, log_error
from google.api_core.exceptions import ResourceExhausted


class ClassifierAgent:
    """Gemini を利用して記事をカテゴリ分類するエージェント"""

    def __init__(self, log_level: str = "INFO"):
        self.logger = setup_logger("ClassifierAgent", log_level)

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            self.logger.error(
                "環境変数 GEMINI_API_KEY が設定されていません。Gemini 分類は無効化されます。"
            )
            self.llm = None
            return

        try:
            self.llm = ChatGoogleGenerativeAI(
                model="gemini-2.5-flash", google_api_key=api_key
            )
            self.logger.info(
                "Gemini モデル（gemini-2.5-flash）を LangChain 経由で初期化しました。"
            )
        except Exception as e:
            log_error(self.logger, e, "Gemini API 初期化失敗")
            self.llm = None

    def classify_articles(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Gemini を使って記事を Cloud または AI に分類する"""

        self.logger.info(f"記事分類開始: {len(articles)}件")

        classified: List[Dict[str, Any]] = []
        processed_urls = set()

        for article in articles:
            url = article.get("url", "")
            if url in processed_urls:
                continue

            result = self._classify_single_article(article)
            if not result:
                continue

            article_classified = article.copy()
            article_classified["category"] = result.get("category", "Unknown")
            article_classified["classification_confidence"] = result.get("confidence", 0.0)
            classified.append(article_classified)
            processed_urls.add(url)

        self._log_classification_statistics(classified)
        return classified

    def _classify_single_article(self, article: Dict[str, Any]) -> Dict[str, Any]:
        """単一記事を Gemini により分類"""
        if not self.llm:
            return {}

        title = article.get("title", "")
        content = article.get("content", "")

        prompt = (
            "次の日本語記事を 'Cloud' または 'AI' のカテゴリに分類し、"
            "0から1の範囲で信頼度を数値で返してください。"
            "JSON 形式で {\"category\": \"Cloud or AI\", \"confidence\": 0-1} のみを出力してください。\n\n"
            f"タイトル: {title}\n本文: {content}"
        )

        try:
            response = self.llm.invoke(prompt)
            data = json.loads(response.content)
            category = data.get("category", "Unknown")
            confidence = float(data.get("confidence", 0.0))
            return {"category": category, "confidence": confidence}
        except ResourceExhausted as e:
            self.logger.warning(f"分類でGemini APIのクォータを超過しました: {e}")
            return {}
        except Exception as e:
            self.logger.debug(f"分類失敗: {e}")
            return {}

    def _log_classification_statistics(self, articles: List[Dict[str, Any]]):
        if not articles:
            self.logger.info("分類結果なし")
            return

        category_stats: Dict[str, int] = {}
        confidence_scores = []

        for article in articles:
            category = article.get("category", "Unknown")
            confidence = article.get("classification_confidence", 0.0)

            category_stats[category] = category_stats.get(category, 0) + 1
            confidence_scores.append(confidence)

        self.logger.info("=== 分類統計 ===")
        for category, count in category_stats.items():
            self.logger.info(f"{category}: {count}件")

        avg_conf = sum(confidence_scores) / len(confidence_scores)
        self.logger.info(f"平均分類信頼度: {avg_conf:.2f}")

    def validate_classification(self, articles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分類結果の簡易検証"""

        report = {
            "total_articles": len(articles),
            "categories": {},
            "potential_duplicates": [],
            "low_confidence": [],
        }

        seen_titles: Dict[str, str] = {}

        for article in articles:
            category = article.get("category", "Unknown")
            title = article.get("title", "")
            confidence = article.get("classification_confidence", 0.0)

            report["categories"][category] = report["categories"].get(category, 0) + 1

            if title in seen_titles:
                report["potential_duplicates"].append(
                    {"title": title, "urls": [seen_titles[title], article.get("url", "")]}
                )
            else:
                seen_titles[title] = article.get("url", "")

            if confidence < 0.5:
                report["low_confidence"].append(
                    {"title": title, "category": category, "confidence": confidence}
                )

        return report

