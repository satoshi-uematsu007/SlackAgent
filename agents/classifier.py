import yaml
import os
from typing import List, Dict, Any, Set
import logging
from utils.logger import setup_logger

class ClassifierAgent:
    """
    記事分類エージェント
    ルールベースで記事を「Cloud」「AI」「Other」に分類
    """
    
    def __init__(self, log_level: str = "INFO"):
        self.logger = setup_logger("ImprovedClassifierAgent", log_level)
        self.keywords = self._load_keywords()
        self.classification_rules = self._load_classification_rules()
        
        # 分類優先度設定
        self.category_priority = {
            'AI': 1,      # AIが最優先
            'Cloud': 2,   # クラウドが次
            'Other': 3    # その他は最後
        }
    
    def _load_keywords(self) -> Dict[str, Dict[str, List[str]]]:
        """
        改善されたキーワード辞書を読み込み
        """
        try:
            with open('config/keywords.yaml', 'r', encoding='utf-8') as f:
                base_keywords = yaml.safe_load(f)
            
            # 重複を避けるための詳細キーワード定義
            enhanced_keywords = {
                'ai': {
                    'primary': [
                        'GPT', 'ChatGPT', 'Claude', 'Gemini', 'LLM', '大規模言語モデル',
                        '生成AI', '生成ＡＩ', 'OpenAI', 'Anthropic', 'Google AI',
                        'Machine Learning', '機械学習', 'ML', 'MLOps',
                        'Deep Learning', 'ディープラーニング', 'Neural Network',
                        'Transformer', 'BERT', 'ファインチューニング', 'Fine-tuning',
                        'RAG', 'Vector Database', 'Embedding', '埋め込み',
                        'NLP', '自然言語処理', 'Computer Vision', '画像認識',
                        'AI', '人工知能', 'Artificial Intelligence'
                    ],
                    'cloud_ai': [
                        # クラウドAIサービス（AIカテゴリに優先分類）
                        'SageMaker', 'AI Platform', 'Machine Learning Studio',
                        'Vertex AI', 'Azure Cognitive Services', 'AWS Bedrock',
                        'Amazon Comprehend', 'Google Cloud AI', 'Azure OpenAI'
                    ]
                },
                'cloud': {
                    'primary': [
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
                    'infrastructure': [
                        'Load Balancer', 'Auto Scaling', 'VPC', 'Security Group',
                        'IAM', 'CloudWatch', 'Monitoring', 'Logging'
                    ]
                }
            }
            
            return enhanced_keywords
            
        except Exception as e:
            self.logger.error(f"キーワード設定読み込みエラー: {e}")
            return self._get_default_keywords()
    
    def _load_classification_rules(self) -> Dict[str, Any]:
        """
        分類ルールの読み込み
        """
        return {
            'ai_priority_keywords': [
                'GPT', 'ChatGPT', 'LLM', '生成AI', 'Machine Learning', 'ML',
                'Deep Learning', 'Neural Network', 'AI', '人工知能'
            ],
            'cloud_ai_services': [
                'SageMaker', 'AI Platform', 'Vertex AI', 'Azure Cognitive Services',
                'AWS Bedrock', 'Google Cloud AI', 'Azure OpenAI'
            ],
            'exclusion_patterns': [
                # 除外パターン（ノイズ除去）
                'recruitment', '採用', 'job', '求人', 'career', 'hiring',
                'event', 'イベント', 'webinar', 'セミナー', 'conference'
            ]
        }
    
    def classify_articles(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        改善された記事分類（重複除去機能付き）
        """
        self.logger.info(f"記事分類開始: {len(articles)}件")
        
        # 1. 各記事の分類スコアを計算
        scored_articles = []
        for article in articles:
            scores = self._calculate_category_scores(article)
            article_with_scores = article.copy()
            article_with_scores['category_scores'] = scores
            scored_articles.append(article_with_scores)
        
        # 2. 重複チェックと優先度ベースの分類
        classified_articles = self._resolve_duplicates_and_classify(scored_articles)
        
        # 3. 統計情報の出力
        self._log_classification_statistics(classified_articles)
        
        return classified_articles
    
    def _calculate_category_scores(self, article: Dict[str, Any]) -> Dict[str, float]:
        """
        記事の各カテゴリに対するスコアを計算
        """
        title = article.get('title', '').lower()
        content = article.get('content', '').lower()
        text = f"{title} {content}"
        
        scores = {
            'AI': 0.0,
            'Cloud': 0.0,
            'Other': 0.0
        }
        
        # AIスコア計算
        ai_score = 0.0
        
        # AI primary keywords
        for keyword in self.keywords['ai']['primary']:
            if keyword.lower() in text:
                # タイトルに含まれる場合は重み付け
                weight = 2.0 if keyword.lower() in title else 1.0
                ai_score += weight
        
        # Cloud AI services (AIカテゴリに優先分類)
        for keyword in self.keywords['ai']['cloud_ai']:
            if keyword.lower() in text:
                weight = 3.0 if keyword.lower() in title else 2.0
                ai_score += weight
        
        scores['AI'] = ai_score
        
        # Cloudスコア計算
        cloud_score = 0.0
        
        # Cloud primary keywords
        for keyword in self.keywords['cloud']['primary']:
            if keyword.lower() in text:
                # ただし、AI関連の文脈では重みを下げる
                weight = 1.0 if keyword.lower() in title else 0.5
                
                # AI関連の文脈かチェック
                if self._is_ai_context(text, keyword):
                    weight *= 0.3  # AI文脈では重みを大幅に下げる
                
                cloud_score += weight
        
        scores['Cloud'] = cloud_score
        
        # 除外パターンチェック
        if self._should_exclude(text):
            scores['Other'] = 10.0  # 除外対象は"Other"に高スコア
        
        return scores
    
    def _is_ai_context(self, text: str, cloud_keyword: str) -> bool:
        """
        クラウドキーワードがAI文脈で使用されているかチェック
        """
        # クラウドキーワードの周辺テキストをチェック
        keyword_pos = text.find(cloud_keyword.lower())
        if keyword_pos == -1:
            return False
        
        # 前後50文字のコンテキストを確認
        start = max(0, keyword_pos - 50)
        end = min(len(text), keyword_pos + len(cloud_keyword) + 50)
        context = text[start:end]
        
        # AI関連キーワードが近くにあるかチェック
        ai_indicators = ['ai', 'ml', 'machine learning', 'deep learning', 
                        'neural', 'model', 'training', 'prediction']
        
        for indicator in ai_indicators:
            if indicator in context:
                return True
        
        return False
    
    def _should_exclude(self, text: str) -> bool:
        """
        除外対象の記事かチェック
        """
        for pattern in self.classification_rules['exclusion_patterns']:
            if pattern.lower() in text:
                return True
        return False
    
    def _resolve_duplicates_and_classify(self, scored_articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        重複解決と分類の実行
        """
        classified_articles = []
        processed_urls = set()
        
        # 信頼度とスコアでソート
        sorted_articles = sorted(scored_articles, 
                               key=lambda x: (x.get('trust_score', 0), 
                                            max(x['category_scores'].values())), 
                               reverse=True)
        
        for article in sorted_articles:
            url = article.get('url', '')
            
            # 重複チェック
            if url in processed_urls:
                self.logger.debug(f"重複記事をスキップ: {article.get('title', 'Unknown')}")
                continue
            
            # 分類決定
            category = self._determine_category(article['category_scores'])
            
            # "Other"は除外
            if category != 'Other':
                article_classified = article.copy()
                article_classified['category'] = category
                article_classified['classification_confidence'] = self._calculate_confidence(article['category_scores'])
                classified_articles.append(article_classified)
                processed_urls.add(url)
        
        return classified_articles
    
    def _determine_category(self, scores: Dict[str, float]) -> str:
        """
        スコアに基づいてカテゴリを決定
        """
        # スコアが低すぎる場合は除外
        max_score = max(scores.values())
        if max_score < 1.0:
            return 'Other'
        
        # 最高スコアのカテゴリを選択
        best_category = max(scores.keys(), key=lambda k: scores[k])
        
        # AIとCloudの両方が高スコアの場合はAIを優先
        if scores['AI'] >= 3.0 and scores['Cloud'] >= 3.0:
            return 'AI'
        
        return best_category
    
    def _calculate_confidence(self, scores: Dict[str, float]) -> float:
        """
        分類の信頼度を計算
        """
        sorted_scores = sorted(scores.values(), reverse=True)
        if len(sorted_scores) < 2:
            return 1.0
        
        # 最高スコアと2番目のスコアの差を信頼度とする
        confidence = (sorted_scores[0] - sorted_scores[1]) / max(sorted_scores[0], 1.0)
        return min(1.0, max(0.0, confidence))
    
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
        self.logger.info("=== 分類統計 ===")
        for category, count in category_stats.items():
            self.logger.info(f"{category}: {count}件")
        
        if confidence_stats:
            avg_confidence = sum(confidence_stats) / len(confidence_stats)
            self.logger.info(f"平均分類信頼度: {avg_confidence:.2f}")
        
        # 高信頼度記事の詳細
        high_confidence_articles = [a for a in articles if a.get('classification_confidence', 0) >= 0.7]
        self.logger.info(f"高信頼度分類記事: {len(high_confidence_articles)}件")
    
    def _get_default_keywords(self) -> Dict[str, Dict[str, List[str]]]:
        """
        デフォルトキーワード
        """
        return {
            'ai': {
                'primary': ['GPT', 'LLM', '生成AI', '機械学習', 'ML', 'AI', '人工知能'],
                'cloud_ai': ['SageMaker', 'AI Platform', 'Vertex AI']
            },
            'cloud': {
                'primary': ['AWS', 'GCP', 'Azure', 'Kubernetes', 'Docker', 'クラウド'],
                'infrastructure': ['Load Balancer', 'Auto Scaling', 'VPC']
            }
        }
    
    def validate_classification(self, articles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        分類結果の検証
        """
        validation_report = {
            'total_articles': len(articles),
            'categories': {},
            'potential_duplicates': [],
            'low_confidence': [],
            'quality_issues': []
        }
        
        seen_titles = {}
        
        for article in articles:
            category = article.get('category', 'Unknown')
            title = article.get('title', '')
            confidence = article.get('classification_confidence', 0.0)
            
            # カテゴリ統計
            validation_report['categories'][category] = validation_report['categories'].get(category, 0) + 1
            
            # 重複チェック
            if title in seen_titles:
                validation_report['potential_duplicates'].append({
                    'title': title,
                    'urls': [seen_titles[title], article.get('url', '')]
                })
            else:
                seen_titles[title] = article.get('url', '')
            
            # 低信頼度記事
            if confidence < 0.5:
                validation_report['low_confidence'].append({
                    'title': title,
                    'category': category,
                    'confidence': confidence
                })
        
        return validation_report
