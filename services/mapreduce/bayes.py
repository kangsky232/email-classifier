"""
MapReduce 朴素贝叶斯分类器
- Map 阶段：各节点并行计算词频
- Reduce 阶段：汇总统计，计算后验概率
"""

import re
import math
import logging
from typing import Dict, List, Tuple
from collections import defaultdict, Counter
import threading

logger = logging.getLogger(__name__)


class NaiveBayesClassifier:
    """朴素贝叶斯分类器"""

    def __init__(self):
        self.word_counts: Dict[str, Counter] = defaultdict(Counter)  # category -> word counts
        self.category_counts: Counter = Counter()
        self.total_docs = 0
        self.vocabulary: set = set()
        self.lock = threading.RLock()

    def tokenize(self, text: str) -> List[str]:
        """分词"""
        # 简单分词：中文按字符，英文按单词
        text = text.lower()
        # 英文单词
        en_words = re.findall(r'[a-z]+', text)
        # 中文字符（2-4字组合）
        cn_chars = re.findall(r'[一-鿿]', text)
        cn_ngrams = []
        for i in range(len(cn_chars)):
            for n in [2, 3]:
                if i + n <= len(cn_chars):
                    cn_ngrams.append(''.join(cn_chars[i:i+n]))

        return en_words + cn_ngrams

    def train(self, documents: List[Tuple[str, str]]):
        """训练模型
        documents: [(text, category), ...]
        """
        with self.lock:
            for text, category in documents:
                words = self.tokenize(text)
                self.word_counts[category].update(words)
                self.category_counts[category] += 1
                self.total_docs += 1
                self.vocabulary.update(words)

    def train_single(self, text: str, category: str):
        """单条训练"""
        with self.lock:
            words = self.tokenize(text)
            self.word_counts[category].update(words)
            self.category_counts[category] += 1
            self.total_docs += 1
            self.vocabulary.update(words)

    def predict(self, text: str) -> Tuple[str, float, Dict[str, float]]:
        """预测分类，返回 (category, confidence, all_scores)"""
        with self.lock:
            if not self.category_counts:
                return "unknown", 0.0, {}

            words = self.tokenize(text)
            scores = {}

            for category in self.category_counts:
                # 先验概率 P(category)
                prior = math.log(self.category_counts[category] / self.total_docs)

                # 似然概率 P(words|category)
                total_words_in_cat = sum(self.word_counts[category].values())
                vocab_size = len(self.vocabulary)

                likelihood = 0
                for word in words:
                    word_count = self.word_counts[category].get(word, 0)
                    # 拉普拉斯平滑
                    prob = (word_count + 1) / (total_words_in_cat + vocab_size)
                    likelihood += math.log(prob)

                scores[category] = prior + likelihood

            # 转换为概率
            max_score = max(scores.values())
            exp_scores = {k: math.exp(v - max_score) for k, v in scores.items()}
            total = sum(exp_scores.values())
            probabilities = {k: v / total for k, v in exp_scores.items()}

            best_category = max(probabilities, key=probabilities.get)
            confidence = probabilities[best_category]

            return best_category, confidence, probabilities

    def get_stats(self) -> dict:
        """获取统计信息"""
        with self.lock:
            return {
                "total_docs": self.total_docs,
                "categories": dict(self.category_counts),
                "vocabulary_size": len(self.vocabulary),
                "word_counts": {cat: len(words) for cat, words in self.word_counts.items()}
            }

    def merge(self, other: 'NaiveBayesClassifier'):
        """合并另一个分类器的统计数据（用于 Reduce 阶段）"""
        with self.lock:
            for category, counter in other.word_counts.items():
                self.word_counts[category] += counter
            self.category_counts += other.category_counts
            self.total_docs += other.total_docs
            self.vocabulary |= other.vocabulary


class MapReduceBayes:
    """MapReduce 贝叶斯分布式计算"""

    def __init__(self):
        self.global_model = NaiveBayesClassifier()
        self.node_models: Dict[str, NaiveBayesClassifier] = {}
        self.lock = threading.RLock()

    def map_phase(self, node_id: str, documents: List[Tuple[str, str]]) -> dict:
        """Map 阶段：节点本地训练"""
        with self.lock:
            if node_id not in self.node_models:
                self.node_models[node_id] = NaiveBayesClassifier()

            model = self.node_models[node_id]
            model.train(documents)

            logger.info(f"Map phase on {node_id}: {len(documents)} documents")
            return {
                "node_id": node_id,
                "docs_processed": len(documents),
                "stats": model.get_stats()
            }

    def reduce_phase(self) -> dict:
        """Reduce 阶段：汇总所有节点的模型"""
        with self.lock:
            self.global_model = NaiveBayesClassifier()

            for node_id, model in self.node_models.items():
                self.global_model.merge(model)
                logger.info(f"Merged model from {node_id}")

            stats = self.global_model.get_stats()
            logger.info(f"Reduce phase complete: {stats['total_docs']} total docs")
            return stats

    def predict(self, text: str) -> Tuple[str, float, Dict[str, float]]:
        """使用全局模型预测"""
        return self.global_model.predict(text)

    def get_node_stats(self) -> Dict[str, dict]:
        """获取各节点统计"""
        with self.lock:
            return {
                node_id: model.get_stats()
                for node_id, model in self.node_models.items()
            }

    def get_global_stats(self) -> dict:
        """获取全局统计"""
        return self.global_model.get_stats()


# 全局 MapReduce 贝叶斯实例
mapreduce_bayes = MapReduceBayes()
