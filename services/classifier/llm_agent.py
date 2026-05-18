from services.classifier.base_agent import BaseAgent
from infrastructure.cloud_native.circuit_breaker import circuit_breaker
import requests
import json
import logging
import os

logger = logging.getLogger(__name__)

ROLE_PROMPTS = {
    "llm1": {
        "name": "LLM1",
        "system_prompt": """你是一个严格的邮件分类器（严格模式）。你的分类标准非常高，宁可归为"可疑邮件"也不放过任何风险。

重点关注：
- 发件人域名是否可信
- 是否包含链接、附件、索要个人信息
- 语气是否异常紧急或威胁

用最能描述邮件性质的词语作为 category，不要局限于固定列表。

返回 JSON 格式（不要其他内容）：
{"category": "你确定的类别", "confidence": 0.0-1.0, "reason": "分析过程", "keywords": ["关键词1", "关键词2"]}"""
    },
    "llm2": {
        "name": "LLM2",
        "system_prompt": """你是一个语义分析型邮件分类器。你擅长从邮件的深层语义和上下文推断类别。

重点关注：
- 邮件的核心目的和意图
- 发件人与收件人的关系推断
- 隐含的请求或行动项

用最能描述邮件性质的词语作为 category，不要局限于固定列表。

返回 JSON 格式（不要其他内容）：
{"category": "你确定的类别", "confidence": 0.0-1.0, "reason": "分析过程", "keywords": ["关键词1", "关键词2"]}"""
    },
    "llm3": {
        "name": "LLM3",
        "system_prompt": """你是一个关键词驱动的邮件分类器。你通过提取和分析关键词来判断邮件类别。

重点关注：
- 高频出现的核心词汇
- 行业术语和专业词汇
- 时间、地点、数字等实体信息

用最能描述邮件性质的词语作为 category，不要局限于固定列表。

返回 JSON 格式（不要其他内容）：
{"category": "你确定的类别", "confidence": 0.0-1.0, "reason": "分析过程", "keywords": ["关键词1", "关键词2"]}"""
    },
    "llm4": {
        "name": "LLM4",
        "system_prompt": """你是一个宽松的邮件分类器（宽松模式）。你倾向于给予邮件正面分类，除非有明确的负面信号。

重点关注：
- 邮件的表面内容和格式
- 是否符合正常商务沟通模式
- 整体语气和礼貌程度

用最能描述邮件性质的词语作为 category，不要局限于固定列表。

返回 JSON 格式（不要其他内容）：
{"category": "你确定的类别", "confidence": 0.0-1.0, "reason": "分析过程", "keywords": ["关键词1", "关键词2"]}"""
    }
}

VOTE_PROMPT = """你是一个邮件分类判断者。请判断以下提议的分类是否合理。

邮件内容：
{content}

提议的分类：{proposed_category}
提议的理由：{proposed_reason}

请根据你自己的判断，决定是否同意这个分类。

返回 JSON 格式（不要其他内容）：
{{"agree": true/false, "reason": "你的判断理由"}}"""

GEN_EMAIL_PROMPT = """你是一个邮件生成助手。根据用户提供的关键词，生成一封逼真的商务邮件。

要求：
1. 邮件内容自然、真实，符合职场语境
2. 包含发件人身份暗示、合理的主题和正文
3. 长度适中（50-200字）
4. 不要包含任何解释性文字

返回 JSON 格式（不要其他内容）：
{"sender": "发件人邮箱", "subject": "邮件主题", "content": "邮件正文"}"""

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

_ollama_cache = {"available": False, "ts": 0}
_OLLAMA_CACHE_TTL = 30


def _load_providers_from_env():
    import time as _time
    providers = {}

    now = _time.time()
    if now - _ollama_cache["ts"] > _OLLAMA_CACHE_TTL:
        try:
            resp = requests.get("http://localhost:11434/api/tags", timeout=0.5)
            _ollama_cache["available"] = resp.status_code == 200
        except Exception:
            _ollama_cache["available"] = False
        _ollama_cache["ts"] = now

    if _ollama_cache["available"]:
        providers["ollama"] = {
            **BUILTIN_PROVIDERS["ollama"],
            "api_key": "ollama"
        }

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
    def __init__(self, role="llm1"):
        role_config = ROLE_PROMPTS.get(role, ROLE_PROMPTS["llm1"])
        name = role_config["name"]
        self.role = role
        self._system_prompt = role_config["system_prompt"]

        super().__init__(name, f"llm_{role}")

        self._providers = []
        self._refresh_providers()

    def _refresh_providers(self):
        all_providers = _load_providers_from_env()
        agent_config = self._load_agent_config()
        if agent_config and agent_config.get("provider_id"):
            pid = agent_config["provider_id"]
            if pid == "custom" and agent_config.get("base_url") and agent_config.get("api_key"):
                custom_provider = {
                    "name": agent_config.get("custom_name", "自定义模型"),
                    "base_url": agent_config["base_url"].rstrip("/"),
                    "model": agent_config.get("model", "default-model"),
                    "api_key": agent_config["api_key"],
                    "protocol": "openai_compatible"
                }
                self._providers = [custom_provider] + list(all_providers.values())
            elif pid in all_providers:
                self._providers = [all_providers[pid]] + [p for k, p in all_providers.items() if k != pid]
            else:
                self._providers = list(all_providers.values())
        else:
            self._providers = list(all_providers.values())

    def _load_agent_config(self):
        try:
            from infrastructure.database.models import SystemConfig
            import json as _json
            raw = SystemConfig.get(f"agent_{self.role}_provider")
            if raw and isinstance(raw, str):
                return _json.loads(raw)
        except Exception:
            pass
        return None

    @staticmethod
    def _call_llm(provider, system_prompt, user_msg, temperature=0.1, max_tokens=800):
        provider_name = provider.get("name", "unknown")
        breaker = circuit_breaker.get_or_create(
            f"llm-{provider_name}", failure_threshold=3, recovery_timeout=60
        )
        try:
            return breaker.call(LLMAgent._do_call_llm, provider, system_prompt, user_msg, temperature, max_tokens)
        except Exception:
            return None

    @staticmethod
    def _do_call_llm(provider, system_prompt, user_msg, temperature, max_tokens):
        protocol = provider.get("protocol", "openai_compatible")
        base_url = provider.get("base_url", "")
        api_key = provider.get("api_key", "")
        model = provider.get("model", "")

        if protocol == "ollama":
            return LLMAgent._call_ollama(base_url, model, system_prompt, user_msg, temperature)
        elif protocol == "ernie":
            return LLMAgent._call_ernie(base_url, api_key, provider.get("extra_env", ""), model, system_prompt, user_msg, temperature)
        else:
            return LLMAgent._call_openai_compatible(base_url, api_key, model, system_prompt, user_msg, temperature, max_tokens)

    @staticmethod
    def _call_openai_compatible(base_url, api_key, model, system_prompt, user_msg, temperature, max_tokens):
        url = f"{base_url.rstrip('/')}/v1/chat/completions"
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_msg})
        payload = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
        try:
            resp = requests.post(url, headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, json=payload, timeout=30)
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"].strip()
            logger.warning("[OpenAI] HTTP %s: %s", resp.status_code, resp.text[:200])
        except Exception as e:
            logger.warning("[OpenAI] Request failed: %s", e)
        return None

    @staticmethod
    def _call_ollama(base_url, model, system_prompt, user_msg, temperature):
        url = f"{base_url.rstrip('/')}/api/chat"
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_msg})
        payload = {"model": model, "messages": messages, "stream": False, "options": {"temperature": temperature}}
        try:
            resp = requests.post(url, json=payload, timeout=60)
            if resp.status_code == 200:
                return resp.json()["message"]["content"].strip()
            logger.warning("[Ollama] HTTP %s: %s", resp.status_code, resp.text[:200])
        except Exception as e:
            logger.warning("[Ollama] Request failed: %s", e)
        return None

    @staticmethod
    def _call_ernie(base_url, api_key, secret_key_env, model, system_prompt, user_msg, temperature):
        secret_key = os.getenv(secret_key_env, "")
        url = f"{base_url}?access_token={api_key}&secret_key={secret_key}"
        messages = []
        if system_prompt:
            messages.append({"role": "user", "content": f"[系统指令]{system_prompt}\n\n{user_msg}"})
        else:
            messages.append({"role": "user", "content": user_msg})
        payload = {"messages": messages, "temperature": temperature}
        try:
            resp = requests.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=30)
            if resp.status_code == 200:
                return resp.json().get("result", "")
            logger.warning("[Ernie] HTTP %s: %s", resp.status_code, resp.text[:200])
        except Exception as e:
            logger.warning("[Ernie] Request failed: %s", e)
        return None

    def _parse_json_response(self, reply):
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
                return {
                    "category": category.strip(),
                    "confidence": round(min(max(confidence, 0.1), 0.99), 2),
                    "reason": reason,
                    "keywords": keywords[:10] if isinstance(keywords, list) else [],
                    "source": "llm"
                }
        except (json.JSONDecodeError, KeyError, ValueError):
            pass
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

    def classify(self, sender, subject, content):
        result, elapsed = self._measure_time(self._do_classify, sender, subject, content)
        self.log.append({"action": "classify", "result": result, "elapsed_ms": elapsed})
        return result

    def _do_classify(self, sender, subject, content):
        user_msg = f"发件人: {sender}\n主题: {subject}\n内容: {content}"
        for provider in self._providers:
            reply = self._call_llm(provider, self._system_prompt, user_msg, temperature=0.3)
            if reply:
                result = self._parse_json_response(reply)
                if result:
                    result["source"] = provider["name"]
                    return result
        return {"category": "未知", "confidence": 0, "reason": "无可用 LLM Provider", "keywords": [], "source": "error"}

    def vote(self, content, proposed_category, proposed_reason):
        """判断是否同意提议的分类"""
        user_msg = VOTE_PROMPT.format(
            content=content[:1000],
            proposed_category=proposed_category,
            proposed_reason=proposed_reason
        )
        for provider in self._providers:
            reply = self._call_llm(provider, "", user_msg, temperature=0.1, max_tokens=200)
            if reply:
                try:
                    json_start = reply.find('{')
                    json_end = reply.rfind('}') + 1
                    if json_start >= 0 and json_end > json_start:
                        result = json.loads(reply[json_start:json_end])
                        return {
                            "agree": bool(result.get("agree", False)),
                            "reason": result.get("reason", "")
                        }
                except (json.JSONDecodeError, KeyError, ValueError):
                    pass
        return {"agree": False, "reason": "无法解析响应"}

    @staticmethod
    def generate_email(keywords, provider=None):
        providers = list(_load_providers_from_env().values())
        if provider:
            providers = [p for p in providers if p["name"] == provider or provider in str(p)]
        if not providers:
            return None

        user_msg = f"{GEN_EMAIL_PROMPT}\n关键词: {keywords}"
        for p in providers:
            reply = LLMAgent._call_llm(p, "", user_msg, temperature=0.7, max_tokens=500)
            if reply:
                result = LLMAgent._parse_gen_response(reply)
                if result:
                    return result
        return None

    def get_status(self):
        return {
            "name": self.name,
            "role": self.role,
            "available": len(self._providers) > 0,
            "active_providers": [p["name"] for p in self._providers],
            "provider_count": len(self._providers)
        }
