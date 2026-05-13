from agents.base_agent import BaseAgent
import requests
import json
import os

ROLE_PROMPTS = {
    "security": {
        "name": "安全专家",
        "description": "专注识别钓鱼邮件、欺诈邮件、可疑链接和账户安全威胁",
        "system_prompt": """你是一名资深的网络安全专家，专注邮件安全分析。你的任务是检查邮件是否存在安全威胁。

请从以下角度分析邮件：
1. 发件人是否伪装成银行、支付平台、政府机构等可信实体
2. 是否包含可疑链接、附件或要求点击
3. 是否存在账户验证、密码修改、紧急安全提醒等话术
4. 语言是否制造紧迫感或恐吓（如"立即处理""账户将被冻结"）

分类选项：可疑邮件、垃圾邮件、会议通知、工作汇报

返回 JSON 格式（不要其他内容）：
{"category": "分类结果", "confidence": 0.0-1.0, "reason": "分析推理过程"}"""
    },
    "business": {
        "name": "商务助理",
        "description": "专注识别会议通知、工作汇报、商务沟通邮件",
        "system_prompt": """你是一名专业的商务助理，擅长处理工作邮件。你的任务是识别邮件的商务属性。

请从以下角度分析邮件：
1. 是否涉及会议安排、时间地点、参会人员
2. 是否是工作汇报、进度报告、绩效考核相关
3. 是否包含任务分配、deadline、工作安排
4. 是否为团队通知、公司公告、行政事务

分类选项：会议通知、工作汇报、垃圾邮件、可疑邮件

返回 JSON 格式（不要其他内容）：
{"category": "分类结果", "confidence": 0.0-1.0, "reason": "分析推理过程"}"""
    },
    "general": {
        "name": "通用分类",
        "description": "综合各种维度全面分析邮件内容",
        "system_prompt": """你是一名邮件分类专家，需要综合判断邮件的类型。

请从以下角度全面分析：
1. 邮件的首要目的是什么（通知、汇报、推销、诈骗）
2. 发件人身份和邮件语气
3. 内容的关键特征
4. 邮件的紧急程度和重要性

分类选项：会议通知、垃圾邮件、工作汇报、可疑邮件

返回 JSON 格式（不要其他内容）：
{"category": "分类结果", "confidence": 0.0-1.0, "reason": "分析推理过程"}"""
    }
}

FALLBACK_RULES = {
    "security": {
        "可疑邮件": ["验证", "账户", "密码", "点击", "链接", "异常", "登录", "冻结", "安全",
                    "银行", "支付宝", "微信", "官方", "系统", "订单", "退款", "涉嫌", "立即",
                    "确认", "身份", "到期", "锁", "盗", "风险", "警报", "紧急", "限时处理",
                    "更新信息", "异常活动", "IT部门", "权限", "受限"],
        "会议通知": ["会议", "开会", "通知", "参加", "培训", "讨论"],
        "工作汇报": ["报告", "总结", "汇报", "进度", "任务", "提交", "完成"],
        "垃圾邮件": ["免费", "中奖", "优惠", "广告", "促销", "领取"],
    },
    "business": {
        "会议通知": ["会议", "开会", "研讨", "培训", "讨论", "会议室", "参会", "议程",
                    "通知", "参加", "准时", "下午", "上午", "明天", "今天", "召开",
                    "例会", "汇报会", "项目", "部门"],
        "工作汇报": ["报告", "总结", "汇报", "进度", "绩效", "考核", "任务", "完成", "提交",
                    "deadline", "KPI", "周报", "月报", "计划", "安排", "工作"],
        "可疑邮件": ["验证", "账户", "密码", "点击", "链接", "异常", "登录", "冻结"],
        "垃圾邮件": ["免费", "中奖", "优惠", "广告", "促销", "领取"],
    },
    "general": {
        "会议通知": ["会议", "通知", "开会", "研讨", "汇报", "参加", "会议室", "准时",
                    "下午", "上午", "明天", "召开", "例会", "参会", "议程", "培训"],
        "垃圾邮件": ["免费", "领奖", "中奖", "优惠", "广告", "促销", "大奖", "恭喜", "限时",
                    "抢购", "折扣", "特价", "点击领取", "机会难得"],
        "工作汇报": ["报告", "总结", "汇报", "进度", "绩效", "考核", "任务", "提交",
                    "完成", "计划", "安排", "周报", "月报", "工作"],
        "可疑邮件": ["验证", "账户", "密码", "点击", "链接", "异常", "登录", "冻结",
                    "安全", "银行", "官方", "系统", "订单", "退款", "涉嫌", "确认身份"],
    }
}


class LLMAgent(BaseAgent):
    PROVIDER = {
        "name": "DeepSeek",
        "url": "https://api.deepseek.com/v1/chat/completions",
        "model": "deepseek-chat",
        "env_key": "DEEPSEEK_API_KEY"
    }

    def __init__(self, role="general"):
        role_config = ROLE_PROMPTS.get(role, ROLE_PROMPTS["general"])
        name = role_config["name"]
        self.role = role
        self.role_description = role_config["description"]
        self._system_prompt = role_config["system_prompt"]

        super().__init__(name, f"llm_{role}")

        self.categories = ["会议通知", "垃圾邮件", "工作汇报", "可疑邮件"]
        self.api_key = None
        self._fallback_rules = FALLBACK_RULES.get(role, FALLBACK_RULES["general"])
        self._init_provider()

    def _init_provider(self):
        self.api_key = os.getenv(self.PROVIDER["env_key"], "")
        if self.api_key:
            print(f"  [LLM] DeepSeek API Key 已配置")

    def classify(self, sender, subject, content):
        result, elapsed = self._measure_time(self._do_classify, sender, subject, content)
        self.log.append({
            "action": "classify",
            "result": result,
            "elapsed_ms": elapsed
        })
        return result

    def _do_classify(self, sender, subject, content):
        if self.api_key:
            result = self._call_deepseek(sender, subject, content)
            if result:
                return result
        return self._fallback_classify(sender, subject, content)

    def _call_deepseek(self, sender, subject, content):
        user_msg = f"发件人: {sender}\n主题: {subject}\n内容: {content}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.PROVIDER["model"],
            "messages": [
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": user_msg}
            ],
            "temperature": 0.1,
            "max_tokens": 300
        }
        try:
            resp = requests.post(self.PROVIDER["url"], headers=headers, json=payload, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                reply = data["choices"][0]["message"]["content"].strip()
                return self._parse_response(reply)
            else:
                print(f"  [DeepSeek] HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            print(f"  [DeepSeek] 请求失败: {e}")
        return None

    def _parse_response(self, reply):
        try:
            json_start = reply.find('{')
            json_end = reply.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                result = json.loads(reply[json_start:json_end])
                category = result.get("category", "未分类")
                confidence = float(result.get("confidence", 0.8))
                reason = result.get("reason", "")
                if category not in self.categories:
                    category = self._match_category(category)
                return {
                    "category": category,
                    "confidence": round(min(max(confidence, 0.1), 0.99), 2),
                    "reason": reason,
                    "source": "deepseek_api"
                }
        except (json.JSONDecodeError, KeyError, ValueError):
            pass
        return None

    def _match_category(self, text):
        for cat in self.categories:
            if cat in text:
                return cat
        return "未分类"

    def _fallback_classify(self, sender, subject, content):
        text = f"{sender} {subject} {content}".lower()

        scores = {}
        for cat, keywords in self._fallback_rules.items():
            score = sum(1 for kw in keywords if kw in text)
            scores[cat] = score

        best = max(scores, key=scores.get)

        if scores[best] > 0:
            confidence = min(0.5 + scores[best] * 0.08, 0.88)
            return {
                "category": best,
                "confidence": round(confidence, 2),
                "reason": f"降级模式-关键词匹配({scores[best]}个)",
                "source": "fallback"
            }

        # 完全无匹配时的启发式判断
        url_patterns = ["http://", "https://", "www.", ".com", ".cn", ".net"]
        has_url = any(p in text for p in url_patterns)
        has_urgency = any(w in text for w in ["赶紧", "立即", "马上", "尽快", "紧急", "务必"])

        if has_url or has_urgency:
            return {"category": "可疑邮件", "confidence": 0.41, "reason": "降级模式-启发式(含链接或紧迫词)", "source": "fallback_heuristic"}

        if any(w in text for w in ["你好", "您好", "请", "谢谢", "麻烦"]):
            return {"category": "工作汇报", "confidence": 0.38, "reason": "降级模式-启发式(礼貌用语)", "source": "fallback_heuristic"}

        return {"category": "会议通知", "confidence": 0.35, "reason": "降级模式-无特征匹配的默认判断", "source": "fallback_default"}

    def get_status(self):
        return {
            "name": self.name,
            "role": self.role,
            "description": self.role_description,
            "available": bool(self.api_key),
            "provider": "deepseek"
        }
