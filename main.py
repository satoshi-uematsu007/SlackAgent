import os
import sys
from datetime import datetime
from dotenv import load_dotenv
import logging
from typing import List, Dict, Any

from agents.fetcher import FetcherAgent
from agents.classifier import ClassifierAgent
from agents.summarizer import SummarizerAgent
from agents.notifier import NotifierAgent
from utils.logger import setup_logger, log_error

class LeaderAgent:
    """
    リーダーエージェント
    全体のフロー制御・エラーハンドリング・ログ管理
    信頼度スコアに基づく品質管理
    """
    
    def __init__(self):
        # 環境変数読み込み
        load_dotenv()
        
        # ログ設定
        log_level = os.getenv('LOG_LEVEL', 'INFO')
        self.logger = setup_logger("LeaderAgent", log_level)
        
        # Slack Webhook URL
        self.webhook_url = os.getenv('SLACK_WEBHOOK_URL')
        if not self.webhook_url:
            raise ValueError("SLACK_WEBHOOK_URL が設定されていません")
        
        # 品質管理設定
        self.min_trust_score = int(os.getenv('MIN_TRUST_SCORE', '5'))  # 最低信頼度
        self.max_articles_per_category = int(os.getenv('MAX_ARTICLES_PER_CATEGORY', '10'))
        
        # 各エージェントの初期化
        self.fetcher = FetcherAgent(log_level)
        self.classifier = ClassifierAgent(log_level)
        self.summarizer = SummarizerAgent(log_level)
        self.notifier = NotifierAgent(self.webhook_url, log_level)
    
    def run(self) -> bool:
        """
        メイン実行フロー
        """
        start_time = datetime.now()
        self.logger.info("=== ニュース配信システム開始 ===")
        
        try:
            # 1. 記事収集
            self.logger.info("Step 1: 記事収集")
            articles = self.fetcher.fetch_articles()
            
            if not articles:
                self.logger.warning("収集できた記事がありません")
                return True
            
            self.logger.info(f"収集記事数: {len(articles)}件")
            
            # 2. 品質フィルタリング
            self.logger.info("Step 2: 品質フィルタリング")
            quality_articles = self._filter_by_quality(articles)
            
            if not quality_articles:
                self.logger.warning("品質基準を満たす記事がありません")
                return True
            
            # 3. 記事分類
            self.logger.info("Step 3: 記事分類")
            classified_articles = self.classifier.classify_articles(quality_articles)
            
            if not classified_articles:
                self.logger.warning("分類できた記事がありません")
                return True
            
            # 4. 信頼度ベースの記事選択
            self.logger.info("Step 4: 信頼度ベースの記事選択")
            selected_articles = self._select_best_articles(classified_articles)
            
            # 5. 記事要約
            self.logger.info("Step 5: 記事要約")
            summarized_articles = self.summarizer.summarize_articles(selected_articles)
            
            # 6. 信頼度統計の出力
            self._log_trust_analysis(summarized_articles)
            
            # 7. Slack通知
            self.logger.info("Step 6: Slack通知")
            success = self.notifier.send_notification(summarized_articles)
            
            # 実行時間計算
            execution_time = datetime.now() - start_time
            self.logger.info(f"=== 処理完了 (実行時間: {execution_time}) ===")
            
            return success
            
        except Exception as e:
            error_msg = f"システムエラー: {str(e)}"
            log_error(self.logger, e, "LeaderAgent実行エラー")
            
            # エラーをSlackに通知
            try:
                self.notifier.send_error_notification(error_msg)
            except Exception as notify_error:
                log_error(self.logger, notify_error, "エラー通知送信失敗")
            
            return False
    
    def _filter_by_quality(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        信頼度スコアに基づく品質フィルタリング
        """
        quality_articles = []
        
        for article in articles:
            trust_score = article.get('trust_score', 0)
            
            # 最低信頼度チェック
            if trust_score >= self.min_trust_score:
                quality_articles.append(article)
            else:
                self.logger.debug(f"低信頼度記事除外: {article.get('title', 'Unknown')} (信頼度: {trust_score})")
        
        self.logger.info(f"品質フィルタリング結果: {len(quality_articles)}/{len(articles)}件が基準を満たしました")
        
        return quality_articles
    
    def _select_best_articles(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        信頼度スコアに基づく最適記事選択
        """
        # カテゴリ別に分類
        cloud_articles = [a for a in articles if a.get('category') == 'Cloud']
        ai_articles = [a for a in articles if a.get('category') == 'AI']
        
        # 信頼度スコア順でソート
        cloud_articles.sort(key=lambda x: x.get('trust_score', 0), reverse=True)
        ai_articles.sort(key=lambda x: x.get('trust_score', 0), reverse=True)
        
        # 上位記事を選択
        selected_cloud = cloud_articles[:self.max_articles_per_category]
        selected_ai = ai_articles[:self.max_articles_per_category]
        
        selected_articles = selected_cloud + selected_ai
        
        self.logger.info(f"記事選択完了: Cloud {len(selected_cloud)}件, AI {len(selected_ai)}件")
        
        return selected_articles
    
    def _log_trust_analysis(self, articles: List[Dict[str, Any]]):
        """
        信頼度分析結果をログ出力
        """
        if not articles:
            return
        
        trust_scores = [article.get('trust_score', 0) for article in articles]
        
        # 統計計算
        avg_trust = sum(trust_scores) / len(trust_scores)
        max_trust = max(trust_scores)
        min_trust = min(trust_scores)
        
        # 信頼度分布
        high_trust = len([s for s in trust_scores if s >= 9])
        medium_trust = len([s for s in trust_scores if 7 <= s < 9])
        low_trust = len([s for s in trust_scores if 5 <= s < 7])
        unknown_trust = len([s for s in trust_scores if s < 5])
        
        # カテゴリ別分析
        cloud_articles = [a for a in articles if a.get('category') == 'Cloud']
        ai_articles = [a for a in articles if a.get('category') == 'AI']
        
        cloud_avg = sum(a.get('trust_score', 0) for a in cloud_articles) / len(cloud_articles) if cloud_articles else 0
        ai_avg = sum(a.get('trust_score', 0) for a in ai_articles) / len(ai_articles) if ai_articles else 0
        
        # ログ出力
        self.logger.info("=== 信頼度分析結果 ===")
        self.logger.info(f"全体統計 - 平均: {avg_trust:.1f}, 最高: {max_trust}, 最低: {min_trust}")
        self.logger.info(f"信頼度分布 - 高(9+): {high_trust}, 中(7-8): {medium_trust}, 低(5-6): {low_trust}, 不明(<5): {unknown_trust}")
        self.logger.info(f"カテゴリ別平均 - Cloud: {cloud_avg:.1f}, AI: {ai_avg:.1f}")
        
        # 高信頼度記事の詳細
        high_trust_articles = [a for a in articles if a.get('trust_score', 0) >= 9]
        if high_trust_articles:
            self.logger.info("高信頼度記事:")
            for article in high_trust_articles:
                title = article.get('title', 'Unknown')
                score = article.get('trust_score', 0)
                self.logger.info(f"  - {title} (信頼度: {score})")
    
    def health_check(self) -> bool:
        """
        システムヘルスチェック
        """
        try:
            # 設定ファイルの存在チェック
            if not os.path.exists('config/keywords.yaml'):
                self.logger.error("keywords.yaml が見つかりません")
                return False
            
            # 信頼度設定の検証
            if self.min_trust_score < 1 or self.min_trust_score > 10:
                self.logger.error(f"不正な最低信頼度設定: {self.min_trust_score}")
                return False
            
            # 各エージェントの健全性チェック
            if not hasattr(self.fetcher, 'trust_scores'):
                self.logger.error("FetcherAgent の信頼度設定が不正です")
                return False
            
            self.logger.info("ヘルスチェック完了")
            self.logger.info(f"品質設定 - 最低信頼度: {self.min_trust_score}, 最大記事数/カテゴリ: {self.max_articles_per_category}")
            
            return True
            
        except Exception as e:
            log_error(self.logger, e, "ヘルスチェック失敗")
            return False
    
    def run_quality_report(self) -> bool:
        """
        品質レポートの実行
        """
        try:
            self.logger.info("品質レポート生成開始")
            
            # 記事収集（レポート用）
            articles = self.fetcher.fetch_articles()
            
            if not articles:
                self.logger.warning("レポート用記事がありません")
                return True
            
            # 信頼度分析
            self._generate_quality_report(articles)
            
            # 日次サマリーをSlackに送信
            return self.notifier.send_daily_summary(articles)
            
        except Exception as e:
            log_error(self.logger, e, "品質レポート実行エラー")
            return False
    
    def _generate_quality_report(self, articles: List[Dict[str, Any]]):
        """
        品質レポートの生成
        """
        if not articles:
            return
        
        # 信頼度別の記事数
        trust_distribution = {}
        source_analysis = {}
        
        for article in articles:
            trust_score = article.get('trust_score', 0)
            source = article.get('source', 'Unknown')
            
            # 信頼度分布
            trust_range = self._get_trust_range(trust_score)
            trust_distribution[trust_range] = trust_distribution.get(trust_range, 0) + 1
            
            # ソース分析
            source_analysis[source] = source_analysis.get(source, [])
            source_analysis[source].append(trust_score)
        
        # レポート出力
        self.logger.info("=== 品質レポート ===")
        self.logger.info("信頼度分布:")
        for trust_range, count in sorted(trust_distribution.items()):
            self.logger.info(f"  {trust_range}: {count}件")
        
        self.logger.info("ソース別品質:")
        for source, scores in source_analysis.items():
            avg_score = sum(scores) / len(scores)
            self.logger.info(f"  {source}: 平均{avg_score:.1f} ({len(scores)}件)")
    
    def _get_trust_range(self, trust_score: int) -> str:
        """
        信頼度範囲の取得
        """
        if trust_score >= 9:
            return "高 (9-10)"
        elif trust_score >= 7:
            return "中 (7-8)"
        elif trust_score >= 5:
            return "低 (5-6)"
        else:
            return "不明 (<5)"

def main():
    """
    メイン関数
    """
    try:
        leader = LeaderAgent()
        
        # コマンドライン引数チェック
        if len(sys.argv) > 1:
            if sys.argv[1] == "--health":
                success = leader.health_check()
                sys.exit(0 if success else 1)
            elif sys.argv[1] == "--quality-report":
                success = leader.run_quality_report()
                sys.exit(0 if success else 1)
        
        # メイン実行
        success = leader.run()
        sys.exit(0 if success else 1)
        
    except Exception as e:
        print(f"Fatal Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()