"""
API 网关 pytest 测试
覆盖：路由 / 鉴权 / 负载均衡 / 限流 / 熔断 / 日志
"""
import json
import time
import sys
sys.path.insert(0, "/workspace/gateway")

import pytest
from gateway_basics import MiniGateway, BackendService, RateLimiter, CircuitBreaker


@pytest.fixture
def gw():
    """创建预配置的网关"""
    g = MiniGateway()
    order = BackendService("order-svc", ["10.0.0.1:8080", "10.0.0.2:8080"])
    payment = BackendService("payment-svc", ["10.0.1.1:9090"])
    g.add_route("/api/orders", order)
    g.add_route("/api/payments", payment)
    return g


def auth_headers(key="test-key-123"):
    return {"X-API-Key": key}


# ============================================================
# 1. 路由测试
# ============================================================
class TestRouting:
    """路由匹配与转发"""

    def test_match_exact_prefix(self, gw):
        """匹配 /api/orders 前缀"""
        resp = gw.handle("GET", "/api/orders/123", headers=auth_headers())
        assert resp["status"] == 200
        data = json.loads(resp["body"])
        assert data["service"] == "order-svc"

    def test_match_payments(self, gw):
        """匹配 /api/payments 前缀"""
        resp = gw.handle("GET", "/api/payments/456", headers=auth_headers())
        assert resp["status"] == 200
        data = json.loads(resp["body"])
        assert data["service"] == "payment-svc"

    def test_no_route_404(self, gw):
        """无匹配路由返回 404"""
        resp = gw.handle("GET", "/api/unknown", headers=auth_headers())
        assert resp["status"] == 404

    def test_root_path_no_route(self, gw):
        """根路径无路由"""
        resp = gw.handle("GET", "/", headers=auth_headers())
        assert resp["status"] == 404


# ============================================================
# 2. 鉴权测试
# ============================================================
class TestAuth:
    """API Key 鉴权"""

    def test_valid_key(self, gw):
        """有效 Key 通过"""
        resp = gw.handle("GET", "/api/orders/1",
                         headers={"X-API-Key": "test-key-123"})
        assert resp["status"] == 200

    def test_invalid_key(self, gw):
        """无效 Key 返回 401"""
        resp = gw.handle("GET", "/api/orders/1",
                         headers={"X-API-Key": "wrong-key"})
        assert resp["status"] == 401

    def test_missing_key(self, gw):
        """缺少 Key 返回 401"""
        resp = gw.handle("GET", "/api/orders/1", headers={})
        assert resp["status"] == 401

    def test_admin_key(self, gw):
        """管理员 Key"""
        resp = gw.handle("GET", "/api/orders/1",
                         headers={"X-API-Key": "admin-key-456"})
        assert resp["status"] == 200
        data = json.loads(resp["body"])
        assert data["user"] == "admin"


# ============================================================
# 3. 负载均衡测试
# ============================================================
class TestLoadBalancing:
    """轮询负载均衡"""

    def test_round_robin_distribution(self, gw):
        """轮询把请求分发到不同实例"""
        targets = []
        for _ in range(6):
            resp = gw.handle("GET", "/api/orders/1", headers=auth_headers())
            data = json.loads(resp["body"])
            targets.append(data["target"])

        # 6次请求 → .1 → .2 → .1 → .2 → .1 → .2
        expected = ["10.0.0.1:8080", "10.0.0.2:8080"] * 3
        assert targets == expected, f"轮询失败: {targets}"

    def test_single_instance(self, gw):
        """单实例服务每次都返回同一个"""
        targets = []
        for _ in range(3):
            resp = gw.handle("GET", "/api/payments/1", headers=auth_headers())
            data = json.loads(resp["body"])
            targets.append(data["target"])
        assert all(t == "10.0.1.1:9090" for t in targets)


# ============================================================
# 4. 限流测试
# ============================================================
class TestRateLimiting:
    """令牌桶限流"""

    def test_token_bucket_allows_burst(self, gw):
        """桶内有令牌时允许突发"""
        # 重置限流器
        gw.rate_limiter = RateLimiter(rate=100, capacity=10)
        results = []
        for _ in range(10):
            resp = gw.handle("GET", "/api/orders/1", headers=auth_headers())
            results.append(resp["status"])
        assert all(s == 200 for s in results)

    def test_token_bucket_blocks(self, gw):
        """令牌耗尽后拒绝"""
        # 极低速率
        gw.rate_limiter = RateLimiter(rate=1, capacity=3)
        results = []
        for _ in range(10):
            resp = gw.handle("GET", "/api/orders/1", headers=auth_headers())
            results.append(resp["status"])
        assert 429 in results, "应该有限流拒绝"

    def test_token_bucket_refill(self, gw):
        """令牌随时间补充"""
        limiter = RateLimiter(rate=5, capacity=5)
        # 消耗所有令牌
        for _ in range(5):
            assert limiter.allow() is True
        # 令牌耗尽
        assert limiter.allow() is False
        # 等待 0.3 秒（应补充约 1.5 个令牌）
        time.sleep(0.3)
        assert limiter.allow() is True


# ============================================================
# 5. 熔断器测试
# ============================================================
class TestCircuitBreaker:
    """熔断器状态转换"""

    def test_closed_to_open(self, gw):
        """连续失败 N 次后 → OPEN"""
        cb = CircuitBreaker(failure_threshold=3, timeout=5)
        
        def fail():
            raise Exception("error")
        
        for _ in range(3):
            try:
                cb.call(fail)
            except:
                pass
        assert cb.state == "open"

    def test_open_fast_fail(self, gw):
        """OPEN 状态直接抛异常"""
        cb = CircuitBreaker(failure_threshold=2, timeout=10)
        
        def fail():
            raise Exception("error")
        
        # 触发熔断
        for _ in range(2):
            try:
                cb.call(fail)
            except:
                pass
        assert cb.state == "open"

        # 快速失败（不执行函数）
        with pytest.raises(Exception) as exc:
            cb.call(fail)
        assert "快速失败" in str(exc.value) or "熔断" in str(exc.value)

    def test_recovery(self, gw):
        """成功后恢复 CLOSED"""
        cb = CircuitBreaker(failure_threshold=2, timeout=0.1)
        
        def fail():
            raise Exception("error")
        
        # 触发熔断
        for _ in range(2):
            try:
                cb.call(fail)
            except:
                pass
        assert cb.state == "open"
        
        # 等待超时
        time.sleep(0.2)
        
        def success():
            return "ok"
        
        result = cb.call(success)
        assert result == "ok"
        assert cb.state == "closed"


# ============================================================
# 6. 日志测试
# ============================================================
class TestLogging:
    """请求日志"""

    def test_logs_recorded(self, gw):
        """请求后日志被记录"""
        before = len(gw.request_log)
        gw.handle("GET", "/api/orders/1", headers=auth_headers())
        gw.handle("POST", "/api/payments/2", headers=auth_headers())
        assert len(gw.request_log) == before + 2

    def test_log_contains_fields(self, gw):
        """日志包含必要字段"""
        gw.handle("GET", "/api/orders/99", headers=auth_headers())
        log = gw.request_log[-1]
        assert log["method"] == "GET"
        assert log["path"] == "/api/orders/99"
        assert "status" in log
        assert "elapsed_ms" in log
        assert log["user"] == "user1"


# ============================================================
# 7. HTTP 方法测试
# ============================================================
class TestHTTPMethods:
    """不同 HTTP 方法"""

    def test_post_routing(self, gw):
        """POST 请求也能路由"""
        resp = gw.handle("POST", "/api/orders", headers=auth_headers())
        assert resp["status"] == 200

    def test_put_routing(self, gw):
        """PUT 请求也能路由"""
        resp = gw.handle("PUT", "/api/orders/123", headers=auth_headers())
        assert resp["status"] == 200

    def test_delete_routing(self, gw):
        """DELETE 请求也能路由"""
        resp = gw.handle("DELETE", "/api/orders/123", headers=auth_headers())
        assert resp["status"] == 200
