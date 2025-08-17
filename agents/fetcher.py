import os
import json
import feedparser
import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any
import logging
from utils.logger import setup_logger, log_error
import re
from urllib.parse import urlparse
from langchain_google_genai import ChatGoogleGenerativeAI
from google.api_core.exceptions import ResourceExhausted

class FetcherAgent:
    """
    記事収集エージェント（信頼度計算機能付き）
    RSSやスクレイピングによる記事収集
    """
    
    def __init__(self, log_level: str = "INFO"):
        self.logger = setup_logger("FetcherAgent", log_level)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; NewsBot/1.0; +https://example.com/bot)'
        })

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            self.logger.error(
                "環境変数 GEMINI_API_KEY が設定されていません。タグ抽出は無効化されます。"
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
        
        # RSS フィード一覧（信頼性の高いソース）
        self.rss_feeds = [
            # 公式・企業系
            "https://aws.amazon.com/jp/blogs/news/feed/",
            "https://cloud.google.com/blog/ja/rss",
            "https://azure.microsoft.com/ja-jp/blog/feed/",
            "https://kubernetes.io/feed.xml",
            "https://www.docker.com/blog/feed/",
            
            # 技術系メディア
            "https://dev.classmethod.jp/feed/",
            "https://tech.mercari.com/rss",
            "https://engineering.linecorp.com/ja/blog/rss2",
            "https://techblog.yahoo.co.jp/rss/",
            "https://developers.cyberagent.co.jp/blog/feed/",
            "https://tech.recruit-mp.co.jp/rss",
            "https://blog.cloudflare.com/rss/",
            
            # 個人技術ブログ（厳選）
            "https://zenn.dev/feed",
            "https://qiita.com/tags/aws/feed",
            "https://qiita.com/tags/gcp/feed", 
            "https://qiita.com/tags/azure/feed",
            "https://qiita.com/tags/kubernetes/feed",
            
            # AI/ML系
            "https://ai.googleblog.com/feeds/posts/default",
            "https://openai.com/blog/rss.xml",
            "https://blog.research.google/feeds/posts/default",
        ]
        
        # 信頼性スコア辞書（詳細版）
        self.trust_scores = {
            # 公式ドキュメント・企業公式ブログ（最高レベル）
            "aws.amazon.com": 10,
            "cloud.google.com": 10,
            "azure.microsoft.com": 10,
            "kubernetes.io": 10,
            "docker.com": 9,
            "openai.com": 10,
            "ai.googleblog.com": 10,
            "blog.research.google": 10,
            
            # 大手企業の技術ブログ（高信頼性）
            "dev.classmethod.jp": 9,
            "tech.mercari.com": 9,
            "engineering.linecorp.com": 9,
            "techblog.yahoo.co.jp": 9,
            "developers.cyberagent.co.jp": 9,
            "tech.recruit-mp.co.jp": 9,
            "blog.cloudflare.com": 9,
            
            # 技術系メディア（中〜高信頼性）
            "zenn.dev": 7,
            "qiita.com": 6,
            "dev.to": 6,
            "medium.com": 5,
            "hackernoon.com": 6,
            "towards-ai.net": 6,
            "towardsdatascience.com": 7,
            
            # 個人ブログ（デフォルト）
            "github.io": 5,
            "herokuapp.com": 4,
            "netlify.app": 4,
            "vercel.app": 4,
        }
        
        # 記事品質を評価する要因
        self.quality_factors = {
            'author_indicators': [
                'author', 'by', '著者', '執筆者', 'written by', 'posted by'
            ],
            'technical_indicators': [
                'github', 'api', 'sdk', 'terraform', 'yaml', 'json', 'code',
                'implementation', '実装', 'サンプル', 'example', 'tutorial'
            ],
            'reliability_indicators': [
                'official', 'documentation', 'guide', 'best practices',
                '公式', 'ドキュメント', 'ガイド', 'ベストプラクティス'
            ]
        }
        
        # キーワードフィルタ
        self.keywords = [
            "AWS", "GCP", "Azure", "Kubernetes", "Docker", "クラウド",
            "GPT", "LLM", "生成AI", "機械学習", "ML", "AI", "人工知能",
            "DevOps", "CI/CD", "サーバーレス", "Lambda", "インフラ"
        ]
    
    def fetch_articles(self, hours_back: int = 24) -> List[Dict[str, Any]]:
        """
        記事を収集し、信頼度を計算
        """
        self.logger.info(f"記事収集開始: 過去{hours_back}時間")
        articles = []
        
        # RSS フィードから記事収集
        for feed_url in self.rss_feeds:
            try:
                feed_articles = self._fetch_rss_feed(feed_url, hours_back)
                articles.extend(feed_articles)
                self.logger.info(f"{feed_url}から{len(feed_articles)}件の記事を収集")
                time.sleep(1)  # レート制限対策
            except Exception as e:
                log_error(self.logger, e, f"RSS取得エラー: {feed_url}")
        
        # 重複除去
        unique_articles = self._remove_duplicates(articles)
        
        # 信頼度計算
        for article in unique_articles:
            trust_score = self._calculate_comprehensive_trust_score(article)
            article['trust_score'] = trust_score
            article['trust_level'] = self._get_trust_level(trust_score)
        
        # 信頼度順でソート
        unique_articles.sort(key=lambda x: x.get('trust_score', 0), reverse=True)
        
        # 統計情報をログ出力
        self._log_trust_statistics(unique_articles)
        
        self.logger.info(f"重複除去後: {len(unique_articles)}件の記事")
        
        return unique_articles
    
    def _calculate_comprehensive_trust_score(self, article: Dict[str, Any]) -> int:
        """
        包括的な信頼度スコアを計算
        """
        url = article.get('url', '')
        title = article.get('title', '').lower()
        content = article.get('content', '').lower()
        
        # 1. ドメインベースの基本スコア
        base_score = self._calculate_domain_trust_score(url)
        
        # 2. 記事品質スコア
        quality_score = self._calculate_quality_score(title, content)
        
        # 3. 技術的深度スコア
        technical_score = self._calculate_technical_depth_score(title, content)
        
        # 4. 公式性スコア
        official_score = self._calculate_official_score(title, content, url)
        
        # 5. 記事の長さスコア
        length_score = self._calculate_length_score(content)
        
        # 重み付き合計（最大10点）
        total_score = (
            base_score * 0.4 +          # ドメイン信頼性：40%
            quality_score * 0.2 +       # 記事品質：20%
            technical_score * 0.2 +     # 技術的深度：20%
            official_score * 0.1 +      # 公式性：10%
            length_score * 0.1          # 記事の長さ：10%
        )
        
        # 1-10の範囲に正規化
        normalized_score = max(1, min(10, round(total_score)))
        
        return normalized_score
    
    def _calculate_domain_trust_score(self, url: str) -> int:
        """
        ドメインベースの信頼性スコアを計算
        """
        try:
            domain = urlparse(url).netloc.lower()
            
            # 完全一致
            for trusted_domain, score in self.trust_scores.items():
                if trusted_domain in domain:
                    return score
            
            # 部分一致（サブドメイン等）
            if any(td in domain for td in ['github.io', 'googleapis.com', 'microsoft.com']):
                return 7
            
            # 不明なドメインのデフォルト
            return 5
            
        except Exception:
            return 5
    
    def _calculate_quality_score(self, title: str, content: str) -> int:
        """
        記事品質スコアを計算
        """
        score = 5  # ベーススコア
        
        # 著者情報の存在
        if any(indicator in content for indicator in self.quality_factors['author_indicators']):
            score += 1
        
        # 技術的な内容
        tech_count = sum(1 for indicator in self.quality_factors['technical_indicators'] 
                        if indicator in content)
        score += min(2, tech_count // 2)  # 最大2点
        
        # 信頼性指標
        reliability_count = sum(1 for indicator in self.quality_factors['reliability_indicators'] 
                              if indicator in content)
        score += min(2, reliability_count)  # 最大2点
        
        return min(10, score)
    
    def _calculate_technical_depth_score(self, title: str, content: str) -> int:
        """
        技術的深度スコアを計算
        """
        score = 5  # ベーススコア
        
        # コードスニペットの存在
        if any(indicator in content for indicator in ['```', '<code>', 'github.com']):
            score += 2
        
        # API/SDK言及
        if any(keyword in content for keyword in ['api', 'sdk', 'cli', 'terraform']):
            score += 1
        
        # 実装詳細
        if any(keyword in content for keyword in ['implementation', '実装', 'configure', '設定']):
            score += 1
        
        # チュートリアル/ハンズオン
        if any(keyword in content for keyword in ['tutorial', 'hands-on', 'step-by-step', 'ハンズオン']):
            score += 1
        
        return min(10, score)
    
    def _calculate_official_score(self, title: str, content: str, url: str) -> int:
        """
        公式性スコアを計算
        """
        score = 5  # ベーススコア
        
        # 公式ドメイン
        official_domains = [
            'aws.amazon.com', 'cloud.google.com', 'azure.microsoft.com',
            'kubernetes.io', 'docker.com', 'openai.com'
        ]
        
        domain = urlparse(url).netloc.lower()
        if any(od in domain for od in official_domains):
            score += 3
        
        # 公式ブログ/ドキュメント
        if any(keyword in url.lower() for keyword in ['blog', 'docs', 'documentation']):
            score += 1
        
        # 公式アナウンス
        if any(keyword in title.lower() for keyword in ['announcing', 'release', 'リリース', '発表']):
            score += 1
        
        return min(10, score)
    
    def _calculate_length_score(self, content: str) -> int:
        """
        記事の長さスコアを計算
        """
        length = len(content)
        
        if length < 200:
            return 3  # 短すぎる
        elif length < 500:
            return 5  # 普通
        elif length < 1500:
            return 7  # 適切
        elif length < 3000:
            return 9  # 詳細
        else:
            return 10  # 非常に詳細
    
    def _get_trust_level(self, trust_score: int) -> str:
        """
        信頼度スコアを文字列レベルに変換
        """
        if trust_score >= 9:
            return "非常に高い"
        elif trust_score >= 7:
            return "高い"
        elif trust_score >= 5:
            return "普通"
        elif trust_score >= 3:
            return "低い"
        else:
            return "非常に低い"
    
    def _log_trust_statistics(self, articles: List[Dict[str, Any]]):
        """
        信頼度統計情報をログ出力
        """
        if not articles:
            return
        
        trust_scores = [article.get('trust_score', 0) for article in articles]
        
        stats = {
            'total': len(articles),
            'avg_trust': sum(trust_scores) / len(trust_scores),
            'max_trust': max(trust_scores),
            'min_trust': min(trust_scores),
            'high_trust': len([s for s in trust_scores if s >= 7]),
            'medium_trust': len([s for s in trust_scores if 5 <= s < 7]),
            'low_trust': len([s for s in trust_scores if s < 5])
        }
        
        self.logger.info(f"信頼度統計: 平均={stats['avg_trust']:.1f}, "
                        f"高信頼度={stats['high_trust']}件, "
                        f"中信頼度={stats['medium_trust']}件, "
                        f"低信頼度={stats['low_trust']}件")
    
    def _fetch_rss_feed(self, feed_url: str, hours_back: int) -> List[Dict[str, Any]]:
        """
        RSS フィードから記事を取得
        """
        articles = []
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        
        try:
            feed = feedparser.parse(feed_url)
            
            for entry in feed.entries:
                # 日付チェック
                if hasattr(entry, 'published_parsed'):
                    pub_date = datetime(*entry.published_parsed[:6])
                    if pub_date < cutoff_time:
                        continue
                
                # キーワードフィルタ
                title = entry.get('title', '')
                summary = entry.get('summary', '')
                content = f"{title} {summary}"
                
                if self._matches_keywords(content):
                    # 本文取得試行
                    full_content = self._fetch_full_content(entry.link)

                    # 日本語記事のみを抽出
                    combined = f"{title} {full_content or summary}"
                    if not self._is_japanese(combined):
                        continue

                    article = {
                        'title': title,
                        'url': entry.link,
                        'content': full_content or summary,
                        'published_at': entry.get('published', ''),
                        'source': feed_url,
                        'author': entry.get('author', ''),
                        'tags': self._extract_tags_with_llm(full_content or summary),
                    }
                    articles.append(article)
                    
        except Exception as e:
            log_error(self.logger, e, f"RSS解析エラー: {feed_url}")
        
        return articles
    
    def _fetch_full_content(self, url: str) -> str:
        """
        記事の本文を取得
        """
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 一般的な記事コンテンツのセレクタ
            content_selectors = [
                'article', '.article-content', '.entry-content', 
                '.post-content', '.content', 'main', '.main-content'
            ]
            
            for selector in content_selectors:
                content_elem = soup.select_one(selector)
                if content_elem:
                    # スクリプトやスタイルを削除
                    for script in content_elem(["script", "style"]):
                        script.decompose()
                    
                    text = content_elem.get_text(strip=True)
                    if len(text) > 200:  # 十分な長さの場合のみ返す
                        return text[:2000]  # 2000文字に制限
            
            return ""
            
        except Exception as e:
            self.logger.debug(f"本文取得失敗: {url}, {str(e)}")
            return ""

    def _extract_tags_with_llm(self, text: str) -> List[str]:
        """Gemini を使って記事のタグを抽出"""
        if not self.llm or not text:
            return []
        prompt = (
            "以下の日本語テキストから技術的なキーワードを最大5つ抽出し、"
            'JSON形式で{"tags": ["tag1", "tag2"]}のみを出力してください。\n\n'
            f"{text}"
        )
        try:
            response = self.llm.invoke(prompt)
            data = json.loads(response.content)
            tags = data.get("tags", []) if isinstance(data, dict) else data
            return [str(t) for t in tags][:5]
        except ResourceExhausted as e:
            self.logger.warning(f"タグ抽出でGemini APIのクォータを超過しました: {e}")
            return []
        except Exception as e:
            self.logger.debug(f"タグ抽出失敗: {e}")
            return []
    
    def _matches_keywords(self, content: str) -> bool:
        """
        キーワードマッチング
        """
        content_lower = content.lower()
        for keyword in self.keywords:
            if keyword.lower() in content_lower:
                return True
        return False
    
    def _remove_duplicates(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        重複記事を除去
        """
        seen_urls = set()
        unique_articles = []
        
        for article in articles:
            url = article.get('url', '')
            if url not in seen_urls:
                seen_urls.add(url)
                unique_articles.append(article)

        return unique_articles

    def _is_japanese(self, text: str) -> bool:
        """簡易的な日本語判定"""
        if not text:
            return False
        japanese_chars = re.findall("[぀-ヿ㐀-䶿一-鿿]", text)
        return len(japanese_chars) >= max(1, int(len(text) * 0.1))