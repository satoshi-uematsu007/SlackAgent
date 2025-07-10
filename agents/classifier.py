from typing import List, Dict, Any

import yaml

from utils.logger import setup_logger, log_error


class ClassifierAgent:
    """キーワード辞書を用いたルールベースの記事分類エージェント"""

    def __init__(self, log_level: str = "INFO"):
        self.logger = setup_logger("ClassifierAgent", log_level)

        # キーワード辞書読み込み
        try:
            with open("config/keywords.yaml", "r") as f:
                data = yaml.safe_load(f)
        except Exception as e:
            log_error(self.logger, e, "キーワード読み込み失敗")
            data = {}

        self.keyword_dict = {
            "Cloud": [kw.lower() for kw in data.get("cloud", [])],
            "AI": [kw.lower() for kw in data.get("ai", [])],
        }

    def classify_articles(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """キーワードルールに基づき記事を分類する"""

        self.logger.info(f"記事分類開始: {len(articles)}件")

        classified: List[Dict[str, Any]] = []
        processed_urls = set()

        for article in articles:
            url = article.get("url", "")
            if url in processed_urls:
                continue

            text = f"{article.get('title', '')} {article.get('content', '')}".lower()

            cloud_count = sum(1 for kw in self.keyword_dict["Cloud"] if kw.lower() in text)
            ai_count = sum(1 for kw in self.keyword_dict["AI"] if kw.lower() in text)

            if cloud_count == 0 and ai_count == 0:
                continue

            if cloud_count >= ai_count:
                label = "Cloud"
                score = cloud_count / max(1, cloud_count + ai_count)
            else:
                label = "AI"
                score = ai_count / max(1, cloud_count + ai_count)

            article_classified = article.copy()
            article_classified["category"] = label
            article_classified["classification_confidence"] = min(1.0, score)
            classified.append(article_classified)
            processed_urls.add(url)

        self._log_classification_statistics(classified)
        return classified

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

