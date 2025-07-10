import yaml
import os
from typing import List, Dict, Any, Set
import logging
from utils.logger import setup_logger, log_error
import re
from langdetect import detect
from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification
import torch
from sentence_transformers import SentenceTransformer
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

class ClassifierAgent:
    """
    AI分類エージェント
    無料のHugging Face Transformersを使用して記事を分類
    日本語記事のみを対象とする
    """
    
    def __init__(self, log_level: str = "INFO"):
        self.logger = setup_logger("AIClassifierAgent", log_level)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.logger.info(f"デバイス: {self.device}")
        
        # 日本語言語検出用の設定
        self.supported_languages = ['ja']
        
        # 分類モデルの初期化
        self._initialize_models()
        
        # カテゴリ定義とサンプル
        self.categories = {
            'AI': {
                'keywords': [
                    'ChatGPT', 'GPT', 'Claude', 'Gemini', 'LLM', '大規模言語モデル',
                    '生成AI', '生成ＡＩ', 'OpenAI', 'Anthropic', 'Google AI',
                    'Machine Learning', '機械学習', 'ML', 'MLOps', 'AI',
                    'Deep Learning', 'ディープラーニング', 'Neural Network',
                    'Transformer', 'BERT', 'ファインチューニング', 'Fine-tuning',
                    'RAG', 'Vector Database', 'Embedding', '埋め込み',
                    'NLP', '自然言語処理', 'Computer Vision', '画像認識',
                    '人工知能', 'Artificial Intelligence', 'SageMaker', 'AI Platform',
                    'Vertex AI', 'Azure Cognitive Services', 'AWS Bedrock'
                ],
                'examples': [
                    "ChatGPTを使用した業務効率化について",
                    "機械学習モデルの精度向上手法",
                    "生成AIの企業導入事例",
                    "LLMを活用したアプリケーション開発"
                ]
            },
            'Cloud': {
                'keywords': [
                    'AWS', 'Amazon Web Services', 'EC2', 'S3', 'RDS', 'Lambda',
                    'GCP', 'Google Cloud Platform', 'Compute Engine', 'Cloud Storage',
                    'Azure', 'Microsoft Azure', 'Virtual Machines', 'App Service',
                    'Kubernetes', 'k8s', 'Docker', 'コンテナ', 'Container',
                    'EKS', 'AKS', 'GKE', 'ECS', 'Cloud Run', 'Cloud Functions',
                    'CloudFormation', 'Terraform', 'CDK', 'ARM Template',
                    'DevOps', 'CI/CD', 'Jenkins', 'GitHub Actions',
                    'サーバーレス', 'Serverless', 'FaaS', 'PaaS', 'IaaS',
                    'クラウド', 'Cloud', 'インフラ', 'Infrastructure'
                ],
                'examples': [
                    "AWSでのサーバーレスアーキテクチャ構築",
                    "Kubernetesを使用したコンテナ管理",
                    "クラウドインフラの運用最適化",
                    "CI/CDパイプラインの実装"
                ]
            }
        }
        
        # 除外パターン
        self.exclusion_patterns = [
            r'採用|求人|recruitment|hiring|career|job',
            r'イベント|セミナー|webinar|conference|勉強会',
            r'PR|広告|advertisement|sponsored',
            r'ニュース|news(?!letter)|press release',
            r'お知らせ|announcement|notice'
        ]
    
    def _initialize_models(self):
        """
        分類モデルの初期化
        """
        try:
            # 1. 日本語対応のembeddingモデル
            self.logger.info("埋め込みモデルを読み込み中...")
            self.embedding_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
            
            # 2. 汎用分類モデル（日本語対応）
            self.logger.info("分類モデルを読み込み中...")
            self.classifier = pipeline(
                "text-classification",
                model="nlptown/bert-base-multilingual-uncased-sentiment",
                device=0 if self.device == "cuda" else -1,
                return_all_scores=True
            )
            
            # 3. カテゴリ別のembeddingを事前計算
            self._compute_category_embeddings()
            
            self.logger.info("モデル初期化完了")
            
        except Exception as e:
            log_error(self.logger, e, "モデル初期化エラー")
            # フォールバック: キーワードベースの分類のみ
            self.embedding_model = None
            self.classifier = None
    
    def _compute_category_embeddings(self):
        """
        カテゴリ別の代表的なembeddingを計算
        """
        self.category_embeddings = {}
        
        if self.embedding_model is None:
            return
        
        try:
            for category, data in self.categories.items():
                # キーワードと例文を組み合わせて埋め込み計算
                texts = data['keywords'] + data['examples']
                embeddings = self.embedding_model.encode(texts)
                
                # 平均埋め込みを計算
                mean_embedding = np.mean(embeddings, axis=0)
                self.category_embeddings[category] = mean_embedding
                
        except Exception as e:
            log_error(self.logger, e, "カテゴリ埋め込み計算エラー")
    
    def classify_articles(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        記事分類メイン処理
        """
        self.logger.info(f"AI分類開始: {len(articles)}件")
        
        # 1. 日本語記事のフィルタリング
        japanese_articles = self._filter_japanese_articles(articles)
        self.logger.info(f"日本語記事: {len(japanese_articles)}件")
        
        # 2. 除外パターンの適用
        filtered_articles = self._apply_exclusion_filters(japanese_articles)
        self.logger.info(f"フィルタ後: {len(filtered_articles)}件")
        
        # 3. AI分類の実行
        classified_articles = []
        for article in filtered_articles:
            try:
                classification_result = self._classify_single_article(article)
                if classification_result['category'] != 'Other':
                    article_with_classification = article.copy()
                    article_with_classification.update(classification_result)
                    classified_articles.append(article_with_classification)
                    
            except Exception as e:
                log_error(self.logger, e, f"分類エラー: {article.get('title', 'Unknown')}")
        
        # 4. 重複除去と最終フィルタリング
        final_articles = self._remove_duplicates_and_rank(classified_articles)
        
        # 5. 統計情報の出力
        self._log_classification_statistics(final_articles)
        
        self.logger.info(f"最終分類済み記事: {len(final_articles)}件")
        return final_articles
    
    def _filter_japanese_articles(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        日本語記事のみをフィルタリング
        """
        japanese_articles = []
        
        for article in articles:
            if self._is_japanese_article(article):
                japanese_articles.append(article)
        
        return japanese_articles
    
    def _is_japanese_article(self, article: Dict[str, Any]) -> bool:
        """
        記事が日本語かどうかを判定
        """
        try:
            # タイトルと本文を結合
            title = article.get('title', '')
            content = article.get('content', '')
            text = f"{title} {content}"
            
            # 短すぎる場合はスキップ
            if len(text.strip()) < 10:
                return False
            
            # 日本語文字が含まれているかチェック
            japanese_chars = re.findall(r'[ひらがなカタカナ漢字]', text)
            if len(japanese_chars) < 3:
                return False
            
            # langdetectで言語検出
            try:
                detected_lang = detect(text)
                if detected_lang != 'ja':
                    return False
            except:
                # 検出失敗時は日本語文字の存在で判定
                pass
            
            # 日本語文字の割合をチェック
            japanese_ratio = len(japanese_chars) / len(text.replace(' ', ''))
            if japanese_ratio < 0.1:  # 10%未満なら除外
                return False
            
            return True
            
        except Exception as e:
            self.logger.debug(f"言語判定エラー: {str(e)}")
            return False
    
    def _apply_exclusion_filters(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        除外パターンを適用
        """
        filtered_articles = []
        
        for article in articles:
            title = article.get('title', '').lower()
            content = article.get('content', '').lower()
            text = f"{title} {content}"
            
            # 除外パターンチェック
            should_exclude = False
            for pattern in self.exclusion_patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    should_exclude = True
                    break
            
            if not should_exclude:
                filtered_articles.append(article)
        
        return filtered_articles
    
    def _classify_single_article(self, article: Dict[str, Any]) -> Dict[str, Any]:
        """
        単一記事の分類
        """
        title = article.get('title', '')
        content = article.get('content', '')
        text = f"{title} {content}"
        
        # 1. キーワードベースのスコア計算
        keyword_scores = self._calculate_keyword_scores(text)
        
        # 2. AI埋め込みベースのスコア計算
        embedding_scores = self._calculate_embedding_scores(text)
        
        # 3. スコアの統合
        combined_scores = self._combine_scores(keyword_scores, embedding_scores)
        
        # 4. 最終分類の決定
        category = self._determine_final_category(combined_scores)
        confidence = self._calculate_confidence(combined_scores)
        
        return {
            'category': category,
            'classification_confidence': confidence,
            'keyword_scores': keyword_scores,
            'embedding_scores': embedding_scores,
            'combined_scores': combined_scores
        }
    
    def _calculate_keyword_scores(self, text: str) -> Dict[str, float]:
        """
        キーワードベースのスコア計算
        """
        scores = {'AI': 0.0, 'Cloud': 0.0}
        text_lower = text.lower()
        
        for category, data in self.categories.items():
            score = 0.0
            for keyword in data['keywords']:
                if keyword.lower() in text_lower:
                    # タイトルに含まれる場合は重み付け
                    weight = 2.0 if keyword.lower() in text[:100].lower() else 1.0
                    score += weight
            
            scores[category] = score
        
        return scores
    
    def _calculate_embedding_scores(self, text: str) -> Dict[str, float]:
        """
        埋め込みベースのスコア計算
        """
        scores = {'AI': 0.0, 'Cloud': 0.0}
        
        if self.embedding_model is None or not self.category_embeddings:
            return scores
        
        try:
            # 記事のembeddingを計算
            text_embedding = self.embedding_model.encode([text])[0]
            
            # 各カテゴリとの類似度を計算
            for category, category_embedding in self.category_embeddings.items():
                similarity = cosine_similarity(
                    [text_embedding], 
                    [category_embedding]
                )[0][0]
                
                # 0-1の類似度を0-10のスコアに変換
                scores[category] = max(0.0, similarity * 10.0)
                
        except Exception as e:
            self.logger.debug(f"埋め込みスコア計算エラー: {str(e)}")
        
        return scores
    
    def _combine_scores(self, keyword_scores: Dict[str, float], 
                       embedding_scores: Dict[str, float]) -> Dict[str, float]:
        """
        スコアの統合
        """
        combined_scores = {}
        
        for category in ['AI', 'Cloud']:
            # キーワードスコア（60%）+ 埋め込みスコア（40%）
            keyword_weight = 0.6
            embedding_weight = 0.4
            
            combined_score = (
                keyword_scores.get(category, 0.0) * keyword_weight +
                embedding_scores.get(category, 0.0) * embedding_weight
            )
            
            combined_scores[category] = combined_score
        
        return combined_scores
    
    def _determine_final_category(self, scores: Dict[str, float]) -> str:
        """
        最終カテゴリの決定
        """
        # 最低スコア閾値
        min_score_threshold = 2.0
        
        # 最高スコアのカテゴリを選択
        max_score = max(scores.values())
        
        if max_score < min_score_threshold:
            return 'Other'
        
        best_category = max(scores.keys(), key=lambda k: scores[k])
        
        # AIとCloudの両方が高い場合の競合解決
        if scores['AI'] >= 3.0 and scores['Cloud'] >= 3.0:
            # AI関連のキーワードが多い場合はAIを優先
            if scores['AI'] > scores['Cloud'] * 1.2:
                return 'AI'
            elif scores['Cloud'] > scores['AI'] * 1.2:
                return 'Cloud'
            else:
                return 'AI'  # 同程度の場合はAIを優先
        
        return best_category
    
    def _calculate_confidence(self, scores: Dict[str, float]) -> float:
        """
        分類の信頼度を計算
        """
        sorted_scores = sorted(scores.values(), reverse=True)
        
        if len(sorted_scores) < 2:
            return 1.0
        
        # 最高スコアと2番目のスコアの差を信頼度とする
        max_score = sorted_scores[0]
        second_score = sorted_scores[1]
        
        if max_score == 0:
            return 0.0
        
        confidence = (max_score - second_score) / max_score
        return min(1.0, max(0.0, confidence))
    
    def _remove_duplicates_and_rank(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        重複除去と信頼度によるランキング
        """
        # URLベースの重複除去
        seen_urls = set()
        unique_articles = []
        
        # 分類信頼度とトラストスコアでソート
        sorted_articles = sorted(articles, 
                               key=lambda x: (x.get('classification_confidence', 0), 
                                            x.get('trust_score', 0)), 
                               reverse=True)
        
        for article in sorted_articles:
            url = article.get('url', '')
            if url not in seen_urls:
                seen_urls.add(url)
                unique_articles.append(article)
        
        return unique_articles
    
    def _log_classification_statistics(self, articles: List[Dict[str, Any]]):
        """
        分類統計情報のログ出力
        """
        if not articles:
            return
        
        # カテゴリ別統計
        category_stats = {}
        confidence_stats = []
        
        for article in articles:
            category = article.get('category', 'Unknown')
            confidence = article.get('classification_confidence', 0.0)
            
            category_stats[category] = category_stats.get(category, 0) + 1
            confidence_stats.append(confidence)
        
        # 統計出力
        self.logger.info("=== AI分類統計 ===")
        for category, count in category_stats.items():
            self.logger.info(f"{category}: {count}件")
        
        if confidence_stats:
            avg_confidence = sum(confidence_stats) / len(confidence_stats)
            self.logger.info(f"平均分類信頼度: {avg_confidence:.3f}")
            
            high_confidence_count = len([c for c in confidence_stats if c >= 0.7])
            self.logger.info(f"高信頼度分類記事: {high_confidence_count}件")
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        使用モデルの情報を取得
        """
        return {
            'device': self.device,
            'embedding_model': 'paraphrase-multilingual-MiniLM-L12-v2' if self.embedding_model else None,
            'classifier_model': 'nlptown/bert-base-multilingual-uncased-sentiment' if self.classifier else None,
            'supported_languages': self.supported_languages,
            'categories': list(self.categories.keys())
        }
