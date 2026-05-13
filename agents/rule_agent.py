from agents.base_agent import BaseAgent

class RuleAgent(BaseAgent):
    def __init__(self):
        super().__init__("Agent A", "rule_engine")
        self.rules = {
            "会议通知": ["会议", "通知", "开会", "研讨", "汇报", "参加", "会议室", "准时", "下午", "上午"],
            "垃圾邮件": ["免费", "领奖", "中奖", "优惠", "广告", "促销", "大奖", "恭喜", "领取", "限时"],
            "工作汇报": ["报告", "总结", "汇报", "进度", "绩效", "考核", "任务", "完成", "提交", "deadline"],
            "可疑邮件": ["验证", "账户", "密码", "安全", "点击", "链接", "异常", "登录", "确认", "更新"]
        }
    
    def classify(self, sender, subject, content):
        result, elapsed = self._measure_time(self._do_classify, sender, subject, content)
        self.log.append({
            "action": "classify",
            "result": result,
            "elapsed_ms": elapsed
        })
        return result
    
    def _do_classify(self, sender, subject, content):
        text = f"{sender} {subject} {content}".lower()
        scores = {}
        
        for category, keywords in self.rules.items():
            score = 0
            matched = []
            for keyword in keywords:
                if keyword in text:
                    score += 1
                    matched.append(keyword)
            scores[category] = {"score": score, "matched": matched}
        
        if not any(scores[c]["score"] > 0 for c in scores):
            text = f"{sender} {subject} {content}".lower()
            has_urgency = any(w in text for w in ["赶紧", "立即", "马上", "尽快", "紧急", "务必", "点击", "链接"])
            has_url = any(p in text for p in ["http", "www.", ".com", ".cn"])
            if has_url or has_urgency:
                return {"category": "可疑邮件", "confidence": 0.41, "details": scores}
            if any(w in text for w in ["你好", "您好", "请", "谢谢"]):
                return {"category": "工作汇报", "confidence": 0.38, "details": scores}
            return {"category": "会议通知", "confidence": 0.35, "details": scores}
        
        best_category = max(scores, key=lambda c: scores[c]["score"])
        max_score = scores[best_category]["score"]
        total_keywords = len(self.rules[best_category])
        confidence = min(0.5 + (max_score / total_keywords) * 0.5, 0.99)
        
        return {
            "category": best_category,
            "confidence": round(confidence, 2),
            "details": scores
        }
