from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lex_rank import LexRankSummarizer
import nltk
from typing import List, Dict, Any
import logging
import re
import google.generativeai as genai
import os
from utils.logger import setup_logger, log_error

class SummarizerAgent:
    "Google Gemini を用いて記事を要約するエージェント"

    def __init__(self, log_level: str = "INFO"):
        self.logger = setup_logger("SummarizerAgent", log_level)
        self._setup_nltk()
        self.tokenizer = Tokenizer('japanese')
        self.lexrank_summarizer = LexRankSummarizer()
        self.max_sentences = 3

        try:
            genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
            self.gemini_model = genai.GenerativeModel("gemini-pro")
        except Exception as e:
            log_error(self.logger, e, "Gemini API 初期化失敗")
            self.gemini_model = None

    def _setup_nltk(self):
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            self.logger.info("NLTK punkt データをダウンロード中...")
            try:
                nltk.download('punkt', quiet=True)
            except Exception as e:
                log_error(self.logger, e, "NLTK punkt ダウンロード失敗")

    def _clean_text(self, text: str) -> str:
        if not text:
            return ""

        text = re.sub(r'https?://\S+|www\.\S+', '', text)
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'[\u3000\u200b\ufeff]', ' ', text)

        text = re.sub(
            r'application/[\w.+-]+\s*:?\s*schema\s*:?\s*\$ref\s*:?"?#/[^"\s]+"?',
            '',
            text,
            flags=re.IGNORECASE,
        )

        split_word_pattern = re.compile(r"\b(?:[A-Za-z]{1,2}\s+){1,4}[A-Za-z]{1,2}\b")
        text = split_word_pattern.sub(lambda m: m.group().replace(" ", ""), text)

        text = re.sub(r'\b(\w{2,10})(?: \1){2,}\b', r'\1', text)

        words = text.split()
        if words and len(set(words)) <= len(words) * 0.4:
            text = " ".join(sorted(set(words), key=words.index))

        text = re.sub(r'\s+', ' ', text)

        return text.strip()

    def summarize_articles(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        self.logger.info(f"記事要約開始: {len(articles)}件")
        summarized_articles = []

        for article in articles:
            try:
                summary = self._summarize_single_article(article)
                summary = self._clean_text(summary)
                article_with_summary = article.copy()
                article_with_summary['summary'] = summary
                summarized_articles.append(article_with_summary)
            except Exception as e:
                log_error(self.logger, e, f"要約エラー: {article.get('title', 'Unknown')}")
                article_with_summary = article.copy()
                article_with_summary['summary'] = self._fallback_summary(article)
                summarized_articles.append(article_with_summary)

        self.logger.info(f"要約完了: {len(summarized_articles)}件")
        return summarized_articles

    def _summarize_single_article(self, article: Dict[str, Any]) -> str:
        content = self._clean_text(article.get('content', ''))

        if len(content) < 200:
            return self._clean_text(content[:300])

        if self.gemini_model is not None:
            try:
                prompt = f"以下の日本語記事を300文字以内でわかりやすく要約してください。\n\n{content}"
                response = self.gemini_model.generate_content(prompt)
                return response.text.strip()
            except Exception as e:
                self.logger.debug(f"Gemini 要約失敗: {str(e)}")

        return self._fallback_summary(article)

    def _fallback_summary(self, article: Dict[str, Any]) -> str:
        content = self._clean_text(article.get('content', ''))

        if len(content) > 300:
            sentences = content.replace('。', '。\n').split('\n')
            summary = ""
            for sentence in sentences:
                if len(summary + sentence) <= 250:
                    summary += sentence
                else:
                    break
            if not summary:
                summary = content[:250]
            return self._clean_text(summary + "...")
        return self._clean_text(content)
