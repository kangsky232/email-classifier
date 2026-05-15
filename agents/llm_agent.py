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
{"category": "分类结果", "confidence": 0.0-1.0, "reason": "分析推理过程", "keywords": ["关键词1", "关键词2", "关键词3"]}"""
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
{"category": "分类结果", "confidence": 0.0-1.0, "reason": "分析推理过程", "keywords": ["关键词1", "关键词2", "关键词3"]}"""
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
{"category": "分类结果", "confidence": 0.0-1.0, "reason": "分析推理过程", "keywords": ["关键词1", "关键词2", "关键词3"]}"""
    }
}

FREE_PROMPTS = {
    "security": {
        "name": "安全专家(自由)",
        "description": "不限定类别，自主判断邮件安全威胁",
        "system_prompt": """你是一名资深的网络安全专家。请分析这封邮件，自由判断它属于什么类别。

分析角度：
1. 是否存在安全威胁（钓鱼、欺诈、恶意链接）
2. 发件人身份是否可信
3. 邮件的真实意图是什么

请自主确定一个最合适的分类名称（如：钓鱼攻击、账户安全警告、营销推广、会议邀请、工作安排、个人邮件等），
不要局限于固定类别列表，用最能描述邮件性质的词语作为 category。

返回 JSON 格式（不要其他内容）：
{"category": "你确定的类别", "confidence": 0.0-1.0, "reason": "分析推理过程", "keywords": ["关键词1", "关键词2", "关键词3"]}"""
    },
    "business": {
        "name": "商务助理(自由)",
        "description": "不限定类别，自主判断邮件商务属性",
        "system_prompt": """你是一名专业的商务助理。请分析这封邮件，自由判断它属于什么类别。

分析角度：
1. 邮件的商务目的是什么
2. 涉及哪些业务场景
3. 对收件人的影响

请自主确定一个最合适的分类名称（如：客户沟通、项目协调、合同签署、招聘面试、财务报销、公司活动等），
不要局限于固定类别列表，用最能描述邮件性质的词语作为 category。

返回 JSON 格式（不要其他内容）：
{"category": "你确定的类别", "confidence": 0.0-1.0, "reason": "分析推理过程", "keywords": ["关键词1", "关键词2", "关键词3"]}"""
    },
    "general": {
        "name": "通用分类(自由)",
        "description": "不限定类别，全面自由分析邮件",
        "system_prompt": """你是一名邮件分类专家。请分析这封邮件，自由判断它的类别和性质。

从发件人、主题、内容、语气、目的等多个维度综合判断，然后给出一个最贴切的分类名称。
分类名称应该简洁明了（2-6个字），如：会议通知、工作汇报、营销推广、客户咨询、内部公告、
安全警告、招聘相关、财务审批、技术讨论、团队建设、投诉反馈、垃圾广告、钓鱼诈骗等。

不要局限于固定类别列表，用最能准确描述邮件性质的词语作为 category。

返回 JSON 格式（不要其他内容）：
{"category": "你确定的类别", "confidence": 0.0-1.0, "reason": "分析推理过程", "keywords": ["关键词1", "关键词2", "关键词3"]}"""
    }
}

GEN_EMAIL_PROMPT = """你是一个邮件生成助手。根据用户提供的关键词，生成一封逼真的商务邮件。

要求：
1. 邮件内容自然、真实，符合职场语境
2. 包含发件人身份暗示、合理的主题和正文
3. 长度适中（50-200字）
4. 不要包含任何解释性文字

返回 JSON 格式（不要其他内容）：
{"sender": "发件人邮箱", "subject": "邮件主题", "content": "邮件正文"}"""

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

OPENAI_COMPATIBLE_API = {
    "path": "/v1/chat/completions",
    "headers": lambda key: {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    "parse": lambda resp: resp.json()["choices"][0]["message"]["content"].strip()
}

BUILTIN_PROVIDERS = {
    "ollama": {
        "name": "Ollama(本地)", "base_url": "http://localhost:11434",
        "model": os.getenv("OLLAMA_MODEL", "gpt-oss:120b-cloud"),
        "env_key": None, "protocol": "ollama", "no_auth": True
    },
    "deepseek": {
        "name": "DeepSeek", "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat", "env_key": "DEEPSEEK_API_KEY",
        "protocol": "openai_compatible"
    },
    "qwen": {
        "name": "通义千问", "base_url": "https://dashscope.aliyuncs.com/compatible-mode",
        "model": "qwen-turbo", "env_key": "DASHSCOPE_API_KEY",
        "protocol": "openai_compatible"
    },
    "openai": {
        "name": "ChatGPT", "base_url": "https://api.openai.com",
        "model": "gpt-3.5-turbo", "env_key": "OPENAI_API_KEY",
        "protocol": "openai_compatible"
    },
    "ernie": {
        "name": "文心一言", "base_url": "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/completions_pro",
        "model": "ERNIE-Speed-128K", "env_key": "ERNIE_API_KEY",
        "extra_env": "ERNIE_SECRET_KEY", "protocol": "ernie"
    },
    "spark": {
        "name": "讯飞星火", "base_url": "https://spark-api-open.xf-yun.com/v1",
        "model": "generalv3.5", "env_key": "SPARK_API_KEY",
        "protocol": "openai_compatible"
    },
    "glm": {
        "name": "ChatGLM", "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model": "glm-4-flash", "env_key": "ZHIPU_API_KEY",
        "protocol": "openai_compatible"
    }
}

CUSTOM_LLM_URL = os.getenv("CUSTOM_LLM_URL", "")
CUSTOM_LLM_KEY = os.getenv("CUSTOM_LLM_KEY", "")
CUSTOM_LLM_MODEL = os.getenv("CUSTOM_LLM_MODEL", "default-model")
CUSTOM_LLM_NAME = os.getenv("CUSTOM_LLM_NAME", "自定义模型")


def _load_providers_from_env():
    providers = {}
    # Ollama: auto-detect locally, no API key needed
    try:
        resp = requests.get("http://localhost:11434/api/tags", timeout=3)
        if resp.status_code == 200:
            providers["ollama"] = {
                **BUILTIN_PROVIDERS["ollama"],
                "api_key": "ollama"
            }
    except Exception:
        pass

    for pid, cfg in BUILTIN_PROVIDERS.items():
        if pid == "ollama" or cfg.get("env_key") is None:
            continue
        key = os.getenv(cfg["env_key"], "")
        if key:
            providers[pid] = {**cfg, "api_key": key}

    if CUSTOM_LLM_URL and CUSTOM_LLM_KEY:
        providers["custom"] = {
            "name": CUSTOM_LLM_NAME,
            "base_url": CUSTOM_LLM_URL.rstrip("/"),
            "model": CUSTOM_LLM_MODEL,
            "api_key": CUSTOM_LLM_KEY,
            "protocol": "openai_compatible"
        }
    return providers


class LLMAgent(BaseAgent):
    def __init__(self, role="general"):
        role_config = ROLE_PROMPTS.get(role, ROLE_PROMPTS["general"])
        name = role_config["name"]
        self.role = role
        self.role_description = role_config["description"]
        self._system_prompt = role_config["system_prompt"]

        super().__init__(name, f"llm_{role}")

        self.categories = ["会议通知", "垃圾邮件", "工作汇报", "可疑邮件"]
        self._fallback_rules = FALLBACK_RULES.get(role, FALLBACK_RULES["general"])
        self._providers = []
        self._refresh_providers()

    def _refresh_providers(self):
        self._providers = list(_load_providers_from_env().values())

    def _get_free_prompt(self):
        role_cfg = FREE_PROMPTS.get(self.role, FREE_PROMPTS["general"])
        return role_cfg["system_prompt"]

    def classify_free(self, sender, subject, content):
        """自由分类：不限固定类别，LLM 自主确定最合适的分类名"""
        if not self._providers:
            # 没有LLM可用，仍然走降级但标注为自由模式
            fallback = self._fallback_classify(sender, subject, content)
            fallback["mode"] = "free_fallback"
            return fallback

        for provider in self._providers:
            protocol = provider.get("protocol", "openai_compatible")
            user_msg = f"发件人: {sender}\n主题: {subject}\n内容: {content}"
            free_prompt = self._get_free_prompt()

            if protocol == "ernie":
                result = self._call_ernie_with_prompt(provider, free_prompt, user_msg)
            elif protocol == "ollama":
                result = self._call_ollama_with_prompt(provider, free_prompt, user_msg)
            else:
                result = self._call_openai_with_prompt(provider, free_prompt, user_msg)

            if result:
                result["mode"] = "free"
                result["source"] = provider["name"]
                return result

        fallback = self._fallback_classify(sender, subject, content)
        fallback["mode"] = "free_fallback"
        return fallback

    def _call_openai_with_prompt(self, provider, system_prompt, user_msg):
        url = f"{provider['base_url'].rstrip('/')}{OPENAI_COMPATIBLE_API['path']}"
        if provider.get("no_auth"):
            headers = {"Content-Type": "application/json"}
        else:
            headers = OPENAI_COMPATIBLE_API["headers"](provider["api_key"])
        payload = {
            "model": provider["model"],
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg}
            ],
            "temperature": 0.3,
            "max_tokens": 300
        }
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=30)
            if resp.status_code == 200:
                reply = OPENAI_COMPATIBLE_API["parse"](resp)
                return self._parse_free_response(reply)
        except Exception as e:
            print(f"  [{provider['name']}] 自由分类请求失败: {e}")
        return None

    def _call_ollama_with_prompt(self, provider, system_prompt, user_msg):
        payload = {
            "model": provider["model"],
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg}
            ],
            "stream": False,
            "options": {"temperature": 0.3}
        }
        try:
            resp = requests.post(
                f"{provider['base_url']}/api/chat",
                json=payload, timeout=60
            )
            if resp.status_code == 200:
                data = resp.json()
                reply = data.get("message", {}).get("content", "")
                if reply:
                    return self._parse_free_response(reply)
        except Exception as e:
            print(f"  [Ollama] 自由分类请求失败: {e}")
        return None

    def _call_ernie_with_prompt(self, provider, system_prompt, user_msg):
        ernie_secret = os.getenv("ERNIE_SECRET_KEY", "")
        if not ernie_secret:
            return None
        token_url = f"https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id={provider['api_key']}&client_secret={ernie_secret}"
        try:
            token_resp = requests.get(token_url, timeout=10)
            if token_resp.status_code != 200:
                return None
            access_token = token_resp.json().get("access_token", "")
            if not access_token:
                return None
        except Exception:
            return None
        url = f"{provider['base_url']}?access_token={access_token}"
        payload = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg}
            ],
            "temperature": 0.3,
        }
        try:
            resp = requests.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                reply = data.get("result", "")
                return self._parse_free_response(reply)
        except Exception as e:
            print(f"  [文心一言] 自由分类请求失败: {e}")
        return None

    def _parse_free_response(self, reply):
        try:
            json_start = reply.find('{')
            json_end = reply.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                result = json.loads(reply[json_start:json_end])
                category = result.get("category", "未分类")
                confidence = float(result.get("confidence", 0.7))
                reason = result.get("reason", "")
                keywords = result.get("keywords", [])
                if isinstance(keywords, str):
                    keywords = [k.strip() for k in keywords.split(",") if k.strip()]
                return {
                    "category": category.strip(),
                    "confidence": round(min(max(confidence, 0.1), 0.99), 2),
                    "reason": reason,
                    "keywords": keywords[:10] if isinstance(keywords, list) else [],
                    "source": "llm_free"
                }
        except (json.JSONDecodeError, KeyError, ValueError):
            pass
        return None

    @staticmethod
    def generate_email(keywords, provider=None):
        """根据关键词生成邮件"""
        providers = list(_load_providers_from_env().values())
        if provider:
            providers = [p for p in providers if p["name"] == provider or provider in str(p)]
        if not providers:
            return None

        for p in providers:
            protocol = p.get("protocol", "openai_compatible")
            user_msg = f"关键词: {keywords}"

            if protocol == "ernie":
                ernie_secret = os.getenv("ERNIE_SECRET_KEY", "")
                if not ernie_secret:
                    continue
                token_url = f"https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id={p['api_key']}&client_secret={ernie_secret}"
                try:
                    token_resp = requests.get(token_url, timeout=10)
                    if token_resp.status_code != 200:
                        continue
                    access_token = token_resp.json().get("access_token", "")
                    if not access_token:
                        continue
                except Exception:
                    continue
                url = f"{p['base_url']}?access_token={access_token}"
                body = {
                    "messages": [
                        {"role": "user", "content": GEN_EMAIL_PROMPT + "\n" + user_msg}
                    ],
                    "temperature": 0.7,
                }
                try:
                    resp = requests.post(url, headers={"Content-Type": "application/json"}, json=body, timeout=30)
                    if resp.status_code == 200:
                        data = resp.json()
                        reply = data.get("result", "")
                        return LLMAgent._parse_gen_response(reply)
                except Exception:
                    continue
            elif protocol == "ollama":
                body = {
                    "model": p["model"],
                    "messages": [
                        {"role": "user", "content": GEN_EMAIL_PROMPT + "\n" + user_msg}
                    ],
                    "stream": False,
                    "options": {"temperature": 0.7}
                }
                try:
                    resp = requests.post(
                        f"{p['base_url']}/api/chat",
                        json=body, timeout=60
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        reply = data.get("message", {}).get("content", "")
                        return LLMAgent._parse_gen_response(reply)
                except Exception:
                    continue
            else:
                url = f"{p['base_url'].rstrip('/')}{OPENAI_COMPATIBLE_API['path']}"
                body = {
                    "model": p["model"],
                    "messages": [
                        {"role": "user", "content": GEN_EMAIL_PROMPT + "\n" + user_msg}
                    ],
                    "temperature": 0.8,
                    "max_tokens": 500
                }
                try:
                    resp = requests.post(url, headers=OPENAI_COMPATIBLE_API["headers"](p["api_key"]), json=body, timeout=30)
                    if resp.status_code == 200:
                        reply = OPENAI_COMPATIBLE_API["parse"](resp)
                        return LLMAgent._parse_gen_response(reply)
                except Exception:
                    continue
        return None

    @staticmethod
    def _parse_gen_response(reply):
        try:
            json_start = reply.find('{')
            json_end = reply.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                result = json.loads(reply[json_start:json_end])
                return {
                    "sender": result.get("sender", "unknown@example.com"),
                    "subject": result.get("subject", "无主题"),
                    "content": result.get("content", "无内容")
                }
        except (json.JSONDecodeError, KeyError, ValueError):
            pass
        return None

    @staticmethod
    def get_all_providers():
        configs = _load_providers_from_env()
        result = {}
        for pid, cfg in BUILTIN_PROVIDERS.items():
            has_key = bool(os.getenv(cfg["env_key"], ""))
            key = os.getenv(cfg["env_key"], "")
            preview = ""
            if key and len(key) > 10:
                preview = f"{key[:6]}...{key[-4:]}"
            elif key:
                preview = "***"
            result[pid] = {
                "name": cfg["name"], "model": cfg["model"],
                "base_url": cfg["base_url"], "active": has_key,
                "key_preview": preview
            }
        result["custom"] = {
            "name": CUSTOM_LLM_NAME if CUSTOM_LLM_KEY else "自定义模型(未配置)",
            "model": CUSTOM_LLM_MODEL,
            "base_url": CUSTOM_LLM_URL or "未设置",
            "active": bool(CUSTOM_LLM_KEY),
            "key_preview": ""
        }
        return result

    def classify(self, sender, subject, content):
        result, elapsed = self._measure_time(self._do_classify, sender, subject, content)
        self.log.append({
            "action": "classify",
            "result": result,
            "elapsed_ms": elapsed
        })
        return result

    def _do_classify(self, sender, subject, content):
        for provider in self._providers:
            result = self._call_provider(provider, sender, subject, content)
            if result:
                return result
        return self._fallback_classify(sender, subject, content)

    def _call_provider(self, provider, sender, subject, content):
        protocol = provider.get("protocol", "openai_compatible")
        if protocol == "ernie":
            return self._call_ernie(provider, sender, subject, content)
        if protocol == "ollama":
            return self._call_ollama(provider, sender, subject, content)
        return self._call_openai_compatible(provider, sender, subject, content)

    def _call_openai_compatible(self, provider, sender, subject, content):
        user_msg = f"发件人: {sender}\n主题: {subject}\n内容: {content}"
        url = f"{provider['base_url'].rstrip('/')}{OPENAI_COMPATIBLE_API['path']}"
        if provider.get("no_auth"):
            headers = {"Content-Type": "application/json"}
        else:
            headers = OPENAI_COMPATIBLE_API["headers"](provider["api_key"])
        payload = {
            "model": provider["model"],
            "messages": [
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": user_msg}
            ],
            "temperature": 0.1,
            "max_tokens": 300
        }
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=30)
            if resp.status_code == 200:
                reply = OPENAI_COMPATIBLE_API["parse"](resp)
                return self._parse_response(reply, provider["name"])
            else:
                print(f"  [{provider['name']}] HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            print(f"  [{provider['name']}] 请求失败: {e}")
        return None

    def _call_ernie(self, provider, sender, subject, content):
        user_msg = f"发件人: {sender}\n主题: {subject}\n内容: {content}"
        ernie_secret = os.getenv("ERNIE_SECRET_KEY", "")
        if not ernie_secret:
            return None
        token_url = f"https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id={provider['api_key']}&client_secret={ernie_secret}"
        try:
            token_resp = requests.get(token_url, timeout=10)
            if token_resp.status_code != 200:
                return None
            access_token = token_resp.json().get("access_token", "")
            if not access_token:
                return None
        except Exception:
            return None

        url = f"{provider['base_url']}?access_token={access_token}"
        payload = {
            "messages": [
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": user_msg}
            ],
            "temperature": 0.1,
        }
        headers = {"Content-Type": "application/json"}
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                reply = data.get("result", "")
                return self._parse_response(reply, provider["name"])
        except Exception as e:
            print(f"  [文心一言] 请求失败: {e}")
        return None

    def _call_ollama(self, provider, sender, subject, content):
        user_msg = f"发件人: {sender}\n主题: {subject}\n内容: {content}"
        payload = {
            "model": provider["model"],
            "messages": [
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": user_msg}
            ],
            "stream": False,
            "options": {"temperature": 0.1}
        }
        try:
            resp = requests.post(
                f"{provider['base_url']}/api/chat",
                json=payload, timeout=60
            )
            if resp.status_code == 200:
                data = resp.json()
                reply = data.get("message", {}).get("content", "")
                if reply:
                    return self._parse_response(reply, provider["name"])
            else:
                print(f"  [Ollama] HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            print(f"  [Ollama] 请求失败: {e}")
        return None

    def _parse_response(self, reply, provider_name):
        try:
            json_start = reply.find('{')
            json_end = reply.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                result = json.loads(reply[json_start:json_end])
                category = result.get("category", "未分类")
                confidence = float(result.get("confidence", 0.8))
                reason = result.get("reason", "")
                keywords = result.get("keywords", [])
                if isinstance(keywords, str):
                    keywords = [k.strip() for k in keywords.split(",") if k.strip()]
                if category not in self.categories:
                    category = self._match_category(category)
                return {
                    "category": category,
                    "confidence": round(min(max(confidence, 0.1), 0.99), 2),
                    "reason": reason,
                    "keywords": keywords[:10] if isinstance(keywords, list) else [],
                    "source": provider_name
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

        # 提取关键词：从所有规则关键词中匹配
        all_rules_keywords = set()
        for kws in self._fallback_rules.values():
            all_rules_keywords.update(kws)
        matched_keywords = [kw for kw in all_rules_keywords if kw.lower() in text.lower()]

        if scores[best] > 0:
            confidence = min(0.5 + scores[best] * 0.08, 0.88)
            return {
                "category": best,
                "confidence": round(confidence, 2),
                "reason": f"降级模式-关键词匹配({scores[best]}个)",
                "keywords": matched_keywords[:10],
                "source": "fallback"
            }

        url_patterns = ["http://", "https://", "www.", ".com", ".cn", ".net"]
        has_url = any(p in text for p in url_patterns)
        has_urgency = any(w in text for w in ["赶紧", "立即", "马上", "尽快", "紧急", "务必"])

        if has_url or has_urgency:
            return {"category": "可疑邮件", "confidence": 0.41, "reason": "降级模式-启发式(含链接或紧迫词)", "keywords": matched_keywords[:10], "source": "fallback_heuristic"}

        if any(w in text for w in ["你好", "您好", "请", "谢谢", "麻烦"]):
            return {"category": "工作汇报", "confidence": 0.38, "reason": "降级模式-启发式(礼貌用语)", "keywords": matched_keywords[:10], "source": "fallback_heuristic"}

        return {"category": "会议通知", "confidence": 0.35, "reason": "降级模式-无特征匹配的默认判断", "keywords": matched_keywords[:10], "source": "fallback_default"}

    def get_status(self):
        return {
            "name": self.name,
            "role": self.role,
            "description": self.role_description,
            "available": len(self._providers) > 0,
            "active_providers": [p["name"] for p in self._providers],
            "provider_count": len(self._providers)
        }
