"""
配置中心
- 集中化配置管理
- 配置热更新
- 配置版本管理
- 配置监听
"""

import json
import time
import threading
import logging
from typing import Dict, List, Optional, Callable
from collections import defaultdict

logger = logging.getLogger(__name__)


class ConfigItem:
    """配置项"""

    def __init__(self, key: str, value: any, namespace: str = "default"):
        self.key = key
        self.value = value
        self.namespace = namespace
        self.version = 1
        self.created_at = time.time()
        self.updated_at = time.time()
        self.listeners: List[Callable] = []

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "value": self.value,
            "namespace": self.namespace,
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }


class ConfigCenter:
    """配置中心"""

    def __init__(self):
        self.configs: Dict[str, Dict[str, ConfigItem]] = defaultdict(dict)
        self.lock = threading.RLock()
        self.watchers: Dict[str, List[Callable]] = defaultdict(list)

    def set(self, key: str, value: any, namespace: str = "default"):
        """设置配置"""
        with self.lock:
            if namespace in self.configs and key in self.configs[namespace]:
                item = self.configs[namespace][key]
                item.value = value
                item.version += 1
                item.updated_at = time.time()
            else:
                item = ConfigItem(key, value, namespace)
                self.configs[namespace][key] = item

            # 通知监听者
            self._notify_watchers(namespace, key, value)
            logger.info(f"Config set: {namespace}/{key}")

    def get(self, key: str, namespace: str = "default", default: any = None) -> any:
        """获取配置"""
        with self.lock:
            if namespace in self.configs and key in self.configs[namespace]:
                return self.configs[namespace][key].value
            return default

    def delete(self, key: str, namespace: str = "default"):
        """删除配置"""
        with self.lock:
            if namespace in self.configs:
                self.configs[namespace].pop(key, None)
                logger.info(f"Config deleted: {namespace}/{key}")

    def get_all(self, namespace: str = "default") -> Dict[str, any]:
        """获取命名空间下所有配置"""
        with self.lock:
            return {
                key: item.value
                for key, item in self.configs.get(namespace, {}).items()
            }

    def get_namespaces(self) -> List[str]:
        """获取所有命名空间"""
        with self.lock:
            return list(self.configs.keys())

    def watch(self, namespace: str, key: str, callback: Callable):
        """监听配置变化"""
        with self.lock:
            watch_key = f"{namespace}/{key}"
            self.watchers[watch_key].append(callback)

    def _notify_watchers(self, namespace: str, key: str, value: any):
        """通知监听者"""
        watch_key = f"{namespace}/{key}"
        for callback in self.watchers.get(watch_key, []):
            try:
                callback(key, value)
            except Exception as e:
                logger.error(f"Watcher callback error: {e}")

    def export_json(self, namespace: str = "default") -> str:
        """导出配置为 JSON"""
        configs = self.get_all(namespace)
        return json.dumps(configs, indent=2, ensure_ascii=False)

    def import_json(self, json_str: str, namespace: str = "default"):
        """从 JSON 导入配置"""
        configs = json.loads(json_str)
        for key, value in configs.items():
            self.set(key, value, namespace)


# 全局配置中心
config_center = ConfigCenter()
