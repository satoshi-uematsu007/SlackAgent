from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lex_rank import LexRankSummarizer
import nltk
from transformers import pipeline
from typing import List, Dict, Any
import logging
import re
from utils.logger import setup_logger, log_error

class SummarizerAgent:
    "AIモデルを用いて記事を要約するエージェント"
    
    def __init__(self, log_level: str = "INFO"):
        self.logger = setup_logger("SummarizerAgent", log_level)
        self._setup_nltk()
        self.tokenizer = Tokenizer('japanese')
        self.lexrank_summarizer = LexRankSummarizer()
        self.max_sentences = 3
        try:
            self.ai_summarizer = pipeline(
                "summarization",
                model="sonoisa/t5-base-japanese",
            )
        except Exception as e:
            log_error(self.logger, e, "AI要約モデルロード失敗")
            self.ai_summarizer = None
    
    def _setup_nltk(self):
        "NLTK データダウンロード"
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            self.logger.info("NLTK punkt データをダウンロード中...")
            try:
                nltk.download('punkt', quiet=True)
            except Exception as e:
                log_error(self.logger, e, "NLTK punkt ダウンロード失敗")

    def _clean_text(self, text: str) -> str:
        """要約前後のテキストを簡易クリーニング"""
        if not text:
            return ""

        # API仕様などで出力されがちなスキーマ表記を除去
        text = re.sub(
            r'application/[\w.+-]+\s*:?\s*schema\s*:?\s*\$ref\s*:?"?#/[^"\s]+"?',
            '',
            text,
            flags=re.IGNORECASE,
        )

        # 分割された英字列を結合 ("l u g e" -> "luge")
        split_word_pattern = re.compile(r"\b(?:[A-Za-z]{1,2}\s+){1,4}[A-Za-z]{1,2}\b")
        text = split_word_pattern.sub(lambda m: m.group().replace(" ", ""), text)

        # 連続する空白を1つに
        text = re.sub(r'\s+', ' ', text)

        return text.strip()
    
    def summarize_articles(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        "記事リストを要約"
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
                # 要約失敗時は元の記事を短縮して使用
                article_with_summary = article.copy()
                article_with_summary['summary'] = self._fallback_summary(article)
                summarized_articles.append(article_with_summary)
        
        self.logger.info(f"要約完了: {len(summarized_articles)}件")
        return summarized_articles
    
    def _summarize_single_article(self, article: Dict[str, Any]) -> str:
        "単一記事の要約"
        content = self._clean_text(article.get('content', ''))
        
        # 本文が短い場合はそのまま返す
        if len(content) < 200:
            return self._clean_text(content[:300])
        
        # まずAIモデルで要約を試みる
        if self.ai_summarizer is not None:
            try:
                result = self.ai_summarizer(
                    content,
                    max_length=150,
                    min_length=50,
                    do_sample=False,
                )
                summary = self._clean_text(result[0]["summary_text"].strip())
                if len(summary) > 300:
                    summary = summary[:297] + "..."
                return summary
            except Exception as e:
                self.logger.debug(f"AI要約失敗: {str(e)}")

        # フォールバックとして LexRank 要約
        try:
            parser = PlaintextParser.from_string(content, self.tokenizer)
            summary_sentences = self.lexrank_summarizer(parser.document, self.max_sentences)
            summary = ' '.join([str(sentence) for sentence in summary_sentences])
            summary = self._clean_text(summary)

            if len(summary) > 300:
                summary = summary[:297] + "..."
            elif len(summary) < 50:
                summary = content[:300]

            return summary
        except Exception as e:
            self.logger.debug(f"LexRank要約失敗: {str(e)}")
            return self._fallback_summary(article)
    
    def _fallback_summary(self, article: Dict[str, Any]) -> str:
        "フォールバック要約（簡単な文字数制限）"
        content = self._clean_text(article.get('content', ''))
        
        if len(content) > 300:
            # 句読点で区切って適切な位置で切る
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
