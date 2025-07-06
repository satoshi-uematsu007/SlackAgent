import yaml
import os
from typing import List, Dict, Any
import logging
from utils.logger import setup_logger

class ClassifierAgent:
    """
    記事分類エージェント
    ルールベースで記事を「Cloud」「AI」「Other」に分類
    """
    
    def __init__(self, log_level: str = "INFO"):
        self.logger = setup_logger("ClassifierAgent", log_level)
        self.keywords = self._load_keywords()
    
    def _load_keywords(self) -> Dict[str, List[str]]:
        """
        キーワード辞書を読み込み
        """
        try:
            with open('config/keywords.yaml', 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            self.logger.error(f"キーワード設定読み込みエラー: {e}")
            # デフォルトキーワード
            return {
                'cloud': ['AWS', 'GCP', 'Azure', 'Kubernetes', 'Docker', 'クラウド'],
                'ai': ['GPT', 'LLM', '生成AI', '機械学習', 'ML', 'AI', '人工知能']
            }
    
    def classify_articles(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        記事を分類
        """
        self.logger.info(f"記事分類開始: {len(articles)}件")
        
        classified_articles = []
        cloud_count = 0
        ai_count = 0
        other_count = 0
        
        for article in articles:
            categories = self._classify_single_article(article)
            
            if categories:
                # 複数カテゴリに該当する場合は両方に分類
                for category in categories:
                    classified_article = article.copy()
                    classified_article['category'] = category
                    classified_articles.append(classified_article)
                    
                    if category == 'Cloud':
                        cloud_count += 1
                    elif category == 'AI':
                        ai_count += 1
            else:
                # どのカテゴリにも該当しない場合は除外
                other_count += 1
        
        self.logger.info(f"分類結果 - Cloud: {cloud_count}, AI: {ai_count}, Other: {other_count}")
        return classified_articles
    
    def _classify_single_article(self, article: Dict[str, Any]) -> List[str]:
        """
        単一記事の分類
        """
        title = article.get('title', '').lower()
        content = article.get('content', '').lower()
        text = f"{title} {content}"
        
        categories = []
        
        # Cloud カテゴリチェック
        if self._matches_category(text, 'cloud'):
            categories.append('Cloud')
        
        # AI カテゴリチェック  
        if self._matches_category(text, 'ai'):
            categories.append('AI')
        
        return categories
    
    def _matches_category(self, text: str, category: str) -> bool:
        """
        カテゴリのキーワードマッチング
        """
        keywords = self.keywords.get(category, [])
        
        for keyword in keywords:
            if keyword.lower() in text:
                return True
        
        return False
"""

# =============================================================================
# agents/summarizer.py
# =============================================================================
summarizer_py = """
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lex_rank import LexRankSummarizer
from sumy.summarizers.text_rank import TextRankSummarizer
import nltk
from typing import List, Dict, Any
import logging
from utils.logger import setup_logger, log_error

class SummarizerAgent:
    """
    記事要約エージェント
    無料ライブラリ(sumy)を使用して記事を要約
    """
    
    def __init__(self, log_level: str = "INFO"):
        self.logger = setup_logger("SummarizerAgent", log_level)
        self._setup_nltk()
        self.summarizer = LexRankSummarizer()
        self.tokenizer = Tokenizer('japanese')
        self.max_sentences = 3
    
    def _setup_nltk(self):
        """
        NLTK データダウンロード
        """
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            self.logger.info("NLTK punkt データをダウンロード中...")
            try:
                nltk.download('punkt', quiet=True)
            except Exception as e:
                log_error(self.logger, e, "NLTK punkt ダウンロード失敗")
    
    def summarize_articles(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        記事リストを要約
        """
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
                # 要約失敗時は元の記事を短縮して使用
                article_with_summary = article.copy()
                article_with_summary['summary'] = self._fallback_summary(article)
                summarized_articles.append(article_with_summary)
        
        self.logger.info(f"要約完了: {len(summarized_articles)}件")
        return summarized_articles
    
    def _summarize_single_article(self, article: Dict[str, Any]) -> str:
        """
        単一記事の要約
        """
        content = article.get('content', '')
        
        # 本文が短い場合はそのまま返す
        if len(content) < 200:
            return content[:300]
        
        try:
            # sumy を使用した要約
            parser = PlaintextParser.from_string(content, self.tokenizer)
            summary_sentences = self.summarizer(parser.document, self.max_sentences)
            
            summary = ' '.join([str(sentence) for sentence in summary_sentences])
            
            # 文字数制限
            if len(summary) > 300:
                summary = summary[:297] + "..."
            elif len(summary) < 50:
                # 要約が短すぎる場合は元の記事を使用
                summary = content[:300]
            
            return summary
            
        except Exception as e:
            self.logger.debug(f"sumy要約失敗: {str(e)}")
            return self._fallback_summary(article)
    
    def _fallback_summary(self, article: Dict[str, Any]) -> str:
        """
        フォールバック要約（簡単な文字数制限）
        """
        content = article.get('content', '')
        
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
            
            return summary + "..."
        
        return content