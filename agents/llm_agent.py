from agents.base_agent import BaseAgent
import requests
import json
import os
import time

class LLMAgent(BaseAgent):
    PROVIDERS = {
        "qwen": {
            "name": "通义千问",
            "url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
            "model": "qwen-turbo",
            "env_key": "DASHSCOPE_API_KEY"
        },
        "openai": {
            "name": "ChatGPT",
            "url": "https://api.openai.com/v1/chat/completions",
            "model": "gpt-3.5-turbo",
            "env_key": "OPENAI_API_KEY"
        },
        "ernie": {
            "name": "文心一言",
            "url": "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/ernie-speed-128k",
            "model": "ernie-speed-128k",
            "env_key": "ERNIE_API_KEY",
            "secret_key": "ERNIE_SECRET_KEY"
        },
        "spark": {
            "name": "讯飞星火",
            "url": "https://spark-api-open.xf-yun.com/v1/chat/completions",
            "model": "generalv3.5",
            "env_key": "SPARK_API_KEY"
        },
        "glm": {
            "name": "智谱ChatGLM",
            "url": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
            "model": "glm-4-flash",
            "env_key": "ZHIPU_API_KEY"
        }
    }

    def __init__(self):
        super().__init__("Agent D", "llm_multi")
        self.categories = ["会议通知", "垃圾邮件", "工作汇报", "可疑邮件"]
        self.active_providers = []
        self._system_prompt = f"""你是一个邮件分类助手。请将邮件分类为以下类别之一：
{', '.join(self.categories)}

请严格按照以下JSON格式返回结果，不要输出其他内容：
{{"category": "分类名称", "confidence": 0.95, "reason": "分类理由"}}"""
        self._init_providers()

    def _init_providers(self):
        for pid, cfg in self.PROVIDERS.items():
            api_key = os.getenv(cfg["env_key"], "")
            if api_key:
                provider_info = {
                    "id": pid,
                    "name": cfg["name"],
                    "api_key": api_key,
                    "url": cfg["url"],
                    "model": os.getenv(f"{cfg['env_key'].replace('_API_KEY', '')}_MODEL", cfg["model"]),
                    "available": True
                }
                if pid == "ernie":
                    provider_info["secret_key"] = os.getenv(cfg.get("secret_key", ""), "")
                    provider_info["access_token"] = None
                self.active_providers.append(provider_info)
                print(f"大模型已配置: {cfg['name']} ({cfg['model']})")

        if not self.active_providers:
            print("未检测到任何大模型API Key，将使用降级分类方案")

    def classify(self, sender, subject, content):
        result, elapsed = self._measure_time(self._do_classify, sender, subject, content)
        self.log.append({
            "action": "classify",
            "result": result,
            "elapsed_ms": elapsed
        })
        return result

    def _do_classify(self, sender, subject, content):
        if not self.active_providers:
            return self._fallback_classify(sender, subject, content)

        user_msg = f"发件人: {sender}\n主题: {subject}\n内容: {content}"

        for provider in self.active_providers:
            if not provider["available"]:
                continue
            try:
                result = self._call_provider(provider, user_msg)
                if result:
                    return result
            except Exception as e:
                print(f"[{provider['name']}] 调用失败: {e}")
                continue

        return self._fallback_classify(sender, subject, content)

    def _call_provider(self, provider, user_msg):
        pid = provider["id"]
        if pid == "qwen":
            return self._call_openai_compatible(provider, user_msg, "qwen_api")
        elif pid == "openai":
            return self._call_openai_compatible(provider, user_msg, "openai_api")
        elif pid == "spark":
            return self._call_openai_compatible(provider, user_msg, "spark_api")
        elif pid == "glm":
            return self._call_openai_compatible(provider, user_msg, "glm_api")
        elif pid == "ernie":
            return self._call_ernie(provider, user_msg)
        return None

    def _call_openai_compatible(self, provider, user_msg, source_tag):
        headers = {
            "Authorization": f"Bearer {provider['api_key']}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": provider["model"],
            "messages": [
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": user_msg}
            ],
            "temperature": 0.1,
            "max_tokens": 200
        }

        resp = requests.post(provider["url"], headers=headers, json=payload, timeout=15)

        if resp.status_code == 200:
            data = resp.json()
            reply = data["choices"][0]["message"]["content"].strip()
            return self._parse_response(reply, source_tag)
        else:
            print(f"[{provider['name']}] HTTP {resp.status_code}: {resp.text[:200]}")
            return None

    def _call_ernie(self, provider, user_msg):
        access_token = self._get_ernie_token(provider)
        if not access_token:
            return None

        url = f"{provider['url']}?access_token={access_token}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "messages": [
                {"role": "user", "content": f"{self._system_prompt}\n\n{user_msg}"}
            ],
            "temperature": 0.1,
            "max_output_tokens": 200
        }

        resp = requests.post(url, headers=headers, json=payload, timeout=15)

        if resp.status_code == 200:
            data = resp.json()
            reply = data.get("result", "")
            return self._parse_response(reply, "ernie_api")
        else:
            print(f"[文心一言] HTTP {resp.status_code}: {resp.text[:200]}")
            return None

    def _get_ernie_token(self, provider):
        if provider.get("access_token"):
            return provider["access_token"]
        try:
            url = "https://aip.baidubce.com/oauth/2.0/token"
            params = {
                "grant_type": "client_credentials",
                "client_id": provider["api_key"],
                "client_secret": provider.get("secret_key", "")
            }
            resp = requests.post(url, params=params, timeout=10)
            if resp.status_code == 200:
                token = resp.json().get("access_token")
                provider["access_token"] = token
                return token
        except Exception as e:
            print(f"[文心一言] 获取token失败: {e}")
        return None

    def _parse_response(self, reply, source_tag):
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
                    "source": source_tag
                }
        except (json.JSONDecodeError, KeyError, ValueError):
            pass

        return self._fallback_classify("", "", reply)

    def _match_category(self, text):
        for cat in self.categories:
            if cat in text:
                return cat
        keyword_map = {
            "会议": "会议通知", "开会": "会议通知", "通知": "会议通知",
            "垃圾": "垃圾邮件", "广告": "垃圾邮件", "促销": "垃圾邮件",
            "汇报": "工作汇报", "总结": "工作汇报", "报告": "工作汇报",
            "可疑": "可疑邮件", "密码": "可疑邮件", "验证": "可疑邮件", "钓鱼": "可疑邮件"
        }
        for keyword, cat in keyword_map.items():
            if keyword in text:
                return cat
        return "未分类"

    def _fallback_classify(self, sender, subject, content):
        rules = {
            "会议通知": ["会议", "通知", "开会", "研讨", "汇报", "参加", "会议室"],
            "垃圾邮件": ["免费", "领奖", "中奖", "优惠", "广告", "促销", "大奖"],
            "工作汇报": ["报告", "总结", "汇报", "进度", "绩效", "考核", "任务"],
            "可疑邮件": ["验证", "账户", "密码", "安全", "点击", "链接", "异常"]
        }

        text = f"{sender} {subject} {content}".lower()
        scores = {}
        for cat, keywords in rules.items():
            score = sum(1 for kw in keywords if kw in text)
            scores[cat] = score

        best = max(scores, key=scores.get)
        if scores[best] == 0:
            return {"category": "未分类", "confidence": 0.5, "reason": "所有大模型不可用，关键词无匹配", "source": "fallback"}

        confidence = min(0.5 + scores[best] * 0.1, 0.9)
        return {
            "category": best,
            "confidence": round(confidence, 2),
            "reason": f"大模型降级，关键词匹配({scores[best]}个)",
            "source": "fallback"
        }

    def get_status(self):
        providers_info = {}
        for pid, cfg in self.PROVIDERS.items():
            api_key = os.getenv(cfg["env_key"], "")
            key_preview = ""
            if api_key:
                key_preview = f"{api_key[:6]}...{api_key[-4:]}" if len(api_key) > 10 else "***"
            providers_info[pid] = {
                "name": cfg["name"],
                "model": cfg["model"],
                "active": bool(api_key),
                "key_preview": key_preview
            }
        return {
            "available": len(self.active_providers) > 0,
            "total_providers": len(self.PROVIDERS),
            "active_providers": len(self.active_providers),
            "providers": providers_info,
            "available_list": [p["name"] for p in self.active_providers]
        }

    def get_stats(self):
        stats = super().get_stats()
        stats["providers"] = [
            {
                "id": p["id"],
                "name": p["name"],
                "model": p["model"],
                "available": p["available"]
            }
            for p in self.active_providers
        ]
        stats["active_count"] = len([p for p in self.active_providers if p["available"]])
        return stats
