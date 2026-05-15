"""
Nacos 注册配置中心 pytest 测试
覆盖：服务注册 / 服务发现 / 订阅 / 配置管理 / 热更新 / 健康检查
"""
import threading
import time

import pytest

# 导入我们的 MiniNacos（模拟真实 Nacos SDK 行为）
import sys
sys.path.insert(0, "/workspace/nacos")
from nacos_basics import MiniNacos, Instance


@pytest.fixture
def nacos():
    """每个测试独立 Nacos 实例"""
    return MiniNacos()


# ============================================================
# 1. 服务注册
# ============================================================
class TestServiceRegistry:
    """服务注册功能"""

    def test_register_single_instance(self, nacos):
        """注册单个服务实例"""
        nacos.register_instance("svc-a", "10.0.0.1", 8080)
        instances = nacos.get_all_instances("svc-a")
        assert len(instances) == 1
        assert instances[0].ip == "10.0.0.1"
        assert instances[0].port == 8080

    def test_register_multiple_instances(self, nacos):
        """同一服务的多个实例"""
        nacos.register_instance("svc-b", "10.0.0.1", 8080)
        nacos.register_instance("svc-b", "10.0.0.2", 8080)
        nacos.register_instance("svc-b", "10.0.0.3", 8080)
        instances = nacos.get_all_instances("svc-b")
        assert len(instances) == 3

    def test_register_with_metadata(self, nacos):
        """注册带元数据的实例"""
        nacos.register_instance("svc-c", "10.0.0.1", 9090,
                                metadata={"version": "2.0", "weight": "5"})
        inst = nacos.get_all_instances("svc-c")[0]
        assert inst.metadata["version"] == "2.0"
        assert inst.metadata["weight"] == "5"

    def test_deregister_instance(self, nacos):
        """注销实例"""
        nacos.register_instance("svc-d", "10.0.0.1", 8080)
        nacos.register_instance("svc-d", "10.0.0.2", 8080)
        nacos.deregister_instance("svc-d", "10.0.0.1", 8080)
        instances = nacos.get_all_instances("svc-d")
        assert len(instances) == 1
        assert instances[0].ip == "10.0.0.2"

    def test_get_empty_service(self, nacos):
        """未注册的服务返回空列表"""
        instances = nacos.get_all_instances("no-such-service")
        assert instances == []


# ============================================================
# 2. 服务发现 & 订阅
# ============================================================
class TestServiceDiscovery:
    """服务发现 + 订阅通知"""

    def test_subscribe_immediate_callback(self, nacos):
        """订阅后立即回调当前实例列表"""
        nacos.register_instance("svc-e", "10.0.0.1", 8080)
        received = []

        def callback(instances):
            received.append([f"{i.ip}:{i.port}" for i in instances])

        nacos.subscribe("svc-e", callback)
        time.sleep(0.05)
        assert len(received) >= 1
        assert "10.0.0.1:8080" in received[0]

    def test_subscribe_on_new_instance(self, nacos):
        """新实例注册时订阅者收到通知"""
        nacos.register_instance("svc-f", "10.0.0.1", 8080)
        changes = []

        def callback(instances):
            changes.append(len(instances))

        nacos.subscribe("svc-f", callback)
        time.sleep(0.05)
        nacos.register_instance("svc-f", "10.0.0.2", 8080)
        time.sleep(0.1)
        # 应该有至少2次回调：订阅时的1个 + 新增后的2个
        assert len(changes) >= 2
        assert 2 in changes

    def test_subscribe_on_deregister(self, nacos):
        """实例注销时订阅者收到通知"""
        nacos.register_instance("svc-g", "10.0.0.1", 8080)
        nacos.register_instance("svc-g", "10.0.0.2", 8080)
        changes = []

        def callback(instances):
            changes.append(len(instances))

        nacos.subscribe("svc-g", callback)
        time.sleep(0.05)
        nacos.deregister_instance("svc-g", "10.0.0.1", 8080)
        time.sleep(0.1)
        assert 1 in changes  # 注销后剩1个


# ============================================================
# 3. 配置管理
# ============================================================
class TestConfigManagement:
    """配置的发布、获取、监听"""

    def test_publish_and_get_config(self, nacos):
        """发布配置并获取"""
        nacos.publish_config("app.yaml", "server.port: 8080")
        config = nacos.get_config("app.yaml")
        assert config == "server.port: 8080"

    def test_update_config(self, nacos):
        """更新已有配置"""
        nacos.publish_config("db.yaml", "host: old")
        nacos.publish_config("db.yaml", "host: new")
        assert nacos.get_config("db.yaml") == "host: new"

    def test_get_nonexistent_config(self, nacos):
        """获取不存在的配置返回 None"""
        assert nacos.get_config("no-such.yaml") is None

    def test_config_change_listener(self, nacos):
        """配置变更时监听器收到通知"""
        nacos.publish_config("test.yaml", "v1")
        updates = []

        def on_change(content):
            updates.append(content)

        nacos.add_config_listener("test.yaml", on_change)
        nacos.publish_config("test.yaml", "v2")
        time.sleep(0.05)
        assert "v2" in updates


# ============================================================
# 4. 健康检查 & 故障摘除
# ============================================================
class TestHealthCheck:
    """健康检查过滤不健康实例"""

    def test_unhealthy_filtered(self, nacos):
        """不健康实例被过滤"""
        nacos.register_instance("svc-h", "10.0.0.1", 8080)
        nacos.register_instance("svc-h", "10.0.0.2", 8080)
        # 标记第一个不健康
        inst = nacos.get_all_instances("svc-h")[0]
        inst.healthy = False
        healthy = nacos.get_all_instances("svc-h")
        assert len(healthy) == 1
        assert healthy[0].healthy is True

    def test_all_unhealthy_returns_empty(self, nacos):
        """全部不健康时返回空列表"""
        nacos.register_instance("svc-i", "10.0.0.1", 8080)
        for inst in nacos.get_all_instances("svc-i"):
            inst.healthy = False
        assert nacos.get_all_instances("svc-i") == []


# ============================================================
# 5. 负载均衡
# ============================================================
class TestLoadBalance:
    """客户端负载均衡"""

    def test_get_one_instance(self, nacos):
        """获取一个实例（轮询/随机）"""
        nacos.register_instance("svc-j", "10.0.0.1", 8080)
        nacos.register_instance("svc-j", "10.0.0.2", 8080)
        inst = nacos.get_one_instance("svc-j")
        assert inst is not None
        assert inst.ip in ["10.0.0.1", "10.0.0.2"]

    def test_get_one_instance_empty(self, nacos):
        """没有实例时返回 None"""
        assert nacos.get_one_instance("no-svc") is None


# ============================================================
# 6. 边界条件
# ============================================================
class TestEdgeCases:
    """边界情况"""

    def test_deregister_last_instance(self, nacos):
        """注销最后一个实例"""
        nacos.register_instance("svc-k", "10.0.0.1", 8080)
        nacos.deregister_instance("svc-k", "10.0.0.1", 8080)
        assert nacos.get_all_instances("svc-k") == []

    def test_register_same_instance_twice(self, nacos):
        """同一 IP:Port 重复注册（应该生成两个实例）"""
        nacos.register_instance("svc-l", "10.0.0.1", 8080)
        nacos.register_instance("svc-l", "10.0.0.1", 8080)
        assert len(nacos.get_all_instances("svc-l")) == 2

    def test_empty_config_content(self, nacos):
        """空配置内容"""
        nacos.publish_config("empty.yaml", "")
        assert nacos.get_config("empty.yaml") == ""
