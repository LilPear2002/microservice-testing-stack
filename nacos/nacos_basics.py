"""
Nacos 注册配置中心 —— 核心概念学习

Nacos = Service Registry + Configuration Center（注册中心 + 配置中心）

核心概念：
  服务注册   → 服务启动时向 Nacos 注册（IP:Port + 元数据）
  服务发现   → 消费者从 Nacos 拉取服务列表 + 订阅变更
  配置管理   → 配置存 Nacos，应用启动时拉取，变更时热更新
  命名空间   → 租户隔离（dev/test/prod 环境隔离）
  分组       → 同一命名空间内进一步分组

Nacos SDK 模式（真实代码风格）：
  - 注册服务：naming_client.register_instance(service_name, ip, port)
  - 发现服务：naming_client.get_all_instances(service_name)
  - 订阅服务：naming_client.subscribe(service_name, listener)
  - 获取配置：config_client.get_config(data_id, group)
  - 监听配置：config_client.add_listener(data_id, group, callback)

本文件用 Python 实现一个迷你 Nacos，演示所有核心 API + 概念
"""

import json
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Callable, Optional


# ============================================================
# 迷你 Nacos 服务端（模拟注册中心 + 配置中心）
# ============================================================
@dataclass
class Instance:
    """一个服务实例"""
    ip: str
    port: int
    metadata: dict = field(default_factory=dict)
    healthy: bool = True


class MiniNacos:
    """
    迷你 Nacos —— 实现注册中心 + 配置中心核心功能
    API 风格对齐真实 Nacos SDK
    """

    def __init__(self):
        # 注册中心：服务名 → 实例列表
        self._services: Dict[str, List[Instance]] = {}
        # 服务订阅者：服务名 → [回调函数]
        self._subscribers: Dict[str, List[Callable]] = {}
        # 配置中心：data_id → 配置内容
        self._configs: Dict[str, str] = {}
        # 配置监听器：data_id → [回调函数]
        self._config_listeners: Dict[str, List[Callable]] = {}
        self._lock = threading.Lock()

    # ─── 服务注册 ──────────────────────────────
    def register_instance(self, service_name: str, ip: str, port: int,
                          metadata: dict = None):
        """注册一个服务实例（对齐 naming_client.register_instance）"""
        with self._lock:
            if service_name not in self._services:
                self._services[service_name] = []
            inst = Instance(ip=ip, port=port, metadata=metadata or {})
            self._services[service_name].append(inst)
            print(f"📝 [注册] {service_name} ← {ip}:{port}")

        # 通知订阅者
        self._notify_subscribers(service_name)

    def deregister_instance(self, service_name: str, ip: str, port: int):
        """注销服务实例"""
        with self._lock:
            if service_name in self._services:
                self._services[service_name] = [
                    i for i in self._services[service_name]
                    if not (i.ip == ip and i.port == port)
                ]
                print(f"🗑️  [注销] {service_name} ← {ip}:{port}")
        self._notify_subscribers(service_name)

    def get_all_instances(self, service_name: str) -> List[Instance]:
        """获取服务所有实例（对齐 naming_client.get_all_instances）"""
        with self._lock:
            healthy = [i for i in self._services.get(service_name, []) if i.healthy]
            return healthy

    def get_one_instance(self, service_name: str) -> Optional[Instance]:
        """获取一个实例（客户端负载均衡）"""
        instances = self.get_all_instances(service_name)
        if not instances:
            return None
        # 简单轮询（真实 Nacos 支持权重、就近路由）
        idx = hash(time.time()) % len(instances)
        return instances[idx]

    # ─── 服务订阅（服务发现核心） ──────────────
    def subscribe(self, service_name: str, callback: Callable):
        """订阅服务变更（对齐 naming_client.subscribe）"""
        with self._lock:
            if service_name not in self._subscribers:
                self._subscribers[service_name] = []
            self._subscribers[service_name].append(callback)
        # 立即回调当前状态
        instances = self.get_all_instances(service_name)
        callback(instances)

    def _notify_subscribers(self, service_name: str):
        """服务变更时通知所有订阅者"""
        instances = self.get_all_instances(service_name)
        for cb in self._subscribers.get(service_name, []):
            try:
                cb(instances)
            except Exception as e:
                print(f"⚠️ 订阅者回调异常: {e}")

    # ─── 配置管理 ──────────────────────────────
    def publish_config(self, data_id: str, content: str):
        """发布配置（对齐 config_client.publish_config）"""
        with self._lock:
            old = self._configs.get(data_id)
            self._configs[data_id] = content
            print(f"⚙️  [配置] {data_id}: {content[:50]}...")

        # 配置变更通知
        if old != content:
            for cb in self._config_listeners.get(data_id, []):
                try:
                    cb(content)
                except Exception as e:
                    print(f"⚠️ 配置监听异常: {e}")

    def get_config(self, data_id: str) -> Optional[str]:
        """获取配置（对齐 config_client.get_config）"""
        return self._configs.get(data_id)

    def add_config_listener(self, data_id: str, callback: Callable):
        """监听配置变更（对齐 config_client.add_listener）"""
        with self._lock:
            if data_id not in self._config_listeners:
                self._config_listeners[data_id] = []
            self._config_listeners[data_id].append(callback)


# ============================================================
# 使用示例：模拟微服务
# ============================================================
def demo():
    nacos = MiniNacos()
    print("🏗️  MiniNacos 启动（模拟 Nacos Server）\n")

    # ─── Phase 1: 服务注册 ────────────────────
    print("=" * 60)
    print("Phase 1: 服务注册")
    print("=" * 60)

    # 订单服务启动，注册到 Nacos
    nacos.register_instance("order-service", "10.0.1.10", 8080,
                            metadata={"version": "1.0", "region": "cn-hangzhou"})
    nacos.register_instance("order-service", "10.0.1.11", 8080,
                            metadata={"version": "1.0", "region": "cn-hangzhou"})

    # 支付服务
    nacos.register_instance("payment-service", "10.0.2.10", 9090,
                            metadata={"version": "2.0"})

    # 列出所有实例
    for svc in ["order-service", "payment-service"]:
        instances = nacos.get_all_instances(svc)
        print(f"\n📋 {svc} 实例列表:")
        for inst in instances:
            print(f"   {inst.ip}:{inst.port} | 健康:{inst.healthy} | {inst.metadata}")

    # ─── Phase 2: 服务发现 + 订阅 ─────────────
    print("\n" + "=" * 60)
    print("Phase 2: 服务发现 + 订阅")
    print("=" * 60)

    updates = []

    def on_order_change(instances):
        addresses = [f"{i.ip}:{i.port}" for i in instances]
        updates.append(addresses)
        print(f"📡 [订阅回调] order-service 实例变更: {addresses}")

    nacos.subscribe("order-service", on_order_change)

    # 模拟服务上下线
    time.sleep(0.3)
    nacos.register_instance("order-service", "10.0.1.12", 8080)  # 扩容
    time.sleep(0.3)
    nacos.deregister_instance("order-service", "10.0.1.10", 8080)  # 下线

    # ─── Phase 3: 配置管理 ────────────────────
    print("\n" + "=" * 60)
    print("Phase 3: 配置管理")
    print("=" * 60)

    # 发布数据库配置
    nacos.publish_config("order-service.yaml", 
        "spring.datasource.url=jdbc:mysql://10.0.3.10:3306/orders\n"
        "spring.datasource.username=admin")

    # 获取配置
    config = nacos.get_config("order-service.yaml")
    print(f"📖 获取配置:\n{config}")

    # ─── Phase 4: 配置热更新 ──────────────────
    print("\n" + "=" * 60)
    print("Phase 4: 配置热更新（配置变更监听）")
    print("=" * 60)

    hot_updates = []

    def on_config_change(content):
        hot_updates.append(content)
        print(f"🔥 [热更新] 新配置: {content[:60]}...")

    nacos.add_config_listener("order-service.yaml", on_config_change)

    # 运维修改数据库地址（无需重启服务！）
    time.sleep(0.3)
    nacos.publish_config("order-service.yaml",
        "spring.datasource.url=jdbc:mysql://10.0.3.20:3306/orders\n"
        "spring.datasource.username=admin\n"
        "spring.datasource.password=NEW_PASSWORD")

    # ─── Phase 5: 负载均衡 + 故障摘除 ─────────
    print("\n" + "=" * 60)
    print("Phase 5: 健康检查 & 故障摘除")
    print("=" * 60)

    # 标记一个实例不健康（模拟健康检查失败）
    inst = nacos.get_all_instances("order-service")[0]
    inst.healthy = False
    print(f"🏥 {inst.ip}:{inst.port} 标记为不健康")
    
    healthy = nacos.get_all_instances("order-service")
    print(f"📋 健康实例: {[f'{i.ip}:{i.port}' for i in healthy]}")
    print(f"   不健康实例已自动被客户端过滤")

    print("\n✅ MiniNacos 5 阶段通关！")


if __name__ == "__main__":
    demo()
