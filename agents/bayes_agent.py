from agents.base_agent import BaseAgent
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
import numpy as np

class BayesAgent(BaseAgent):
    def __init__(self):
        super().__init__("Agent B", "naive_bayes")
        self.vectorizer = TfidfVectorizer(max_features=1000, token_pattern=r"(?u)\b\w+\b")
        self.model = MultinomialNB()
        self._train_model()
    
    def _train_model(self):
        training_data = [
            ("请各位明天下午3点准时到会议室参加项目进度汇报会", "会议通知"),
            ("关于下周一部门例会的通知，请大家准时参加", "会议通知"),
            ("公司年会将于本周五举行，请各部门做好准备", "会议通知"),
            ("培训通知：新员工入职培训将于明天上午9点开始", "会议通知"),
            ("免费领取大奖，恭喜您中奖了，点击链接领取", "垃圾邮件"),
            ("限时优惠，全场商品五折起，赶快抢购", "垃圾邮件"),
            ("恭喜您获得iPhone15，立即领取", "垃圾邮件"),
            ("低价促销，买一送一，仅限今天", "垃圾邮件"),
            ("本周工作总结及下周工作计划", "工作汇报"),
            ("Q3季度绩效考核报告已提交，请查收", "工作汇报"),
            ("项目进度汇报：目前已完成80%的开发任务", "工作汇报"),
            ("年度工作总结及明年规划", "工作汇报"),
            ("您的账户存在异常，请点击链接验证身份", "可疑邮件"),
            ("系统检测到您的账号在异地登录，请确认是否是本人", "可疑邮件"),
            ("密码即将过期，请尽快更新您的密码", "可疑邮件"),
            ("您的订单出现异常，请点击链接查看详情", "可疑邮件"),
        ]
        
        texts = [t[0] for t in training_data]
        labels = [t[1] for t in training_data]
        
        X = self.vectorizer.fit_transform(texts)
        self.model.fit(X, labels)
        self.categories = list(set(labels))
    
    def classify(self, sender, subject, content):
        result, elapsed = self._measure_time(self._do_classify, sender, subject, content)
        self.log.append({
            "action": "classify",
            "result": result,
            "elapsed_ms": elapsed
        })
        return result
    
    def _do_classify(self, sender, subject, content):
        text = f"{subject} {content}"
        X = self.vectorizer.transform([text])
        prediction = self.model.predict(X)[0]
        probabilities = self.model.predict_proba(X)[0]
        confidence = float(np.max(probabilities))
        
        category_probs = {}
        for i, cat in enumerate(self.model.classes_):
            category_probs[cat] = round(float(probabilities[i]), 2)
        
        return {
            "category": prediction,
            "confidence": round(confidence, 2),
            "probabilities": category_probs
        }
