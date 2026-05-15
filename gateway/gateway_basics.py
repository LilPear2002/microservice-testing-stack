"""
API 网关 核心概念学习

API Gateway = 微服务架构的"统一入口"
  客户端不直接调服务，全部经过网关！

核心功能：
  路由转发    → /api/orders → order-service
  负载均衡    → 请求分发到多个实例
  限流        → Token Bucket 算法
  鉴权        → 统一认证，不重复写
  熔断        → 后端挂了快速失败
  日志        → 统一记录请求日志

真实网关：Spring Cloud Gateway / Kong / APISIX / Nginx
"""

import time
import json
import threading
import hashlib
from collections import defaultdict
from urllib.request import Request, urlopen
from urllib.error import URLError


# ============================================================
# 1. 后端模拟服务
# ============================================================
class BackendService:
    """模拟一个后端微服务（实际是 HTTP Server）"""
    
    def __init__(self, name, instances):
        self.name = name
        self.instances = instances  # ["host:port", ...]
        self._round_robin_idx = 0
        self._lock = threading.Lock()
        self._failure_count = defaultdict(int)
        self._circuit_open = defaultdict(bool)
        self._last_failure_time = defaultdict(float)

    def get_instance(self, strategy="round_robin"):
        """负载均衡：轮询算法"""
        with self._lock:
            idx = self._round_robin_idx % len(self.instances)
            self._round_robin_idx += 1
            return self.instances[idx]

    def get_all_instances(self):
        return list(self.instances)


# ============================================================
# 2. 限流器（Token Bucket）
# ============================================================
class RateLimiter:
    """
    令牌桶算法：
    - 桶每秒补充 N 个令牌
    - 每个请求消耗 1 个令牌
    - 令牌用完 → 拒绝（429 Too Many Requests）
    """

    def __init__(self, rate=10, capacity=20):
        self.rate = rate          # 每秒补充令牌数
        self.capacity = capacity  # 桶容量
        self.tokens = capacity    # 当前令牌数
        self.last_refill = time.time()
        self._lock = threading.Lock()

    def allow(self) -> bool:
        with self._lock:
            now = time.time()
            elapsed = now - self.last_refill
            # 补充令牌
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_refill = now

            if self.tokens >= 1:
                self.tokens -= 1
                return True
            return False


# ============================================================
# 3. 熔断器（Circuit Breaker）
# ============================================================
class CircuitBreaker:
    """
    熔断器三种状态：
      CLOSED    → 正常转发（计数失败）
      OPEN      → 直接拒绝（快速失败）
      HALF_OPEN → 试探性放行一个请求
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(self, failure_threshold=3, timeout=5):
        self.threshold = failure_threshold  # 连续失败 N 次 → 熔断
        self.timeout = timeout              # 熔断后 N 秒尝试恢复
        self.failures = 0
        self.state = self.CLOSED
        self.last_failure_time = 0

    def call(self, fn, *args, **kwargs):
        """执行调用，自动熔断"""
        if self.state == self.OPEN:
            if time.time() - self.last_failure_time > self.timeout:
                self.state = self.HALF_OPEN
                print("     ⚡ 熔断器 → HALF_OPEN（试探）")
            else:
                raise Exception("熔断器打开，快速失败")

        try:
            result = fn(*args, **kwargs)
            # 成功 → 恢复
            if self.state == self.HALF_OPEN:
                self.state = self.CLOSED
                self.failures = 0
                print("     ✅ 熔断器 → CLOSED（恢复）")
            self.failures = 0
            return result
        except Exception as e:
            self.failures += 1
            self.last_failure_time = time.time()
            if self.failures >= self.threshold:
                self.state = self.OPEN
                print(f"     🔥 熔断器 → OPEN（连续{self.failures}次失败）")
            raise e


# ============================================================
# 4. 网关核心
# ============================================================
class MiniGateway:
    """
    迷你 API 网关
    功能：路由 → 负载均衡 → 鉴权 → 限流 → 熔断 → 转发
    """

    def __init__(self):
        self.routes = {}           # path → BackendService
        self.api_keys = {"test-key-123": "user1", "admin-key-456": "admin"}
        self.rate_limiter = RateLimiter(rate=5, capacity=10)
        self.circuit_breaker = CircuitBreaker(failure_threshold=3, timeout=3)
        self.request_log = []

    def add_route(self, path_prefix, backend: BackendService):
        """添加路由规则"""
        self.routes[path_prefix] = backend

    def authenticate(self, api_key: str) -> tuple:
        """鉴权：验证 API Key"""
        if api_key in self.api_keys:
            return True, self.api_keys[api_key]
        return False, None

    def handle(self, method, path, headers=None, body=None) -> dict:
        """处理一个请求（模拟网关流程）"""
        headers = headers or {}
        start = time.time()
        
        # ─── Step 1: 路由匹配 ─────────────────
        backend = None
        matched_prefix = ""
        for prefix in sorted(self.routes.keys(), key=len, reverse=True):
            if path.startswith(prefix):
                backend = self.routes[prefix]
                matched_prefix = prefix
                break

        if not backend:
            return {"status": 404, "body": json.dumps({"error": "no route"})}

        # ─── Step 2: 鉴权 ─────────────────────
        api_key = headers.get("X-API-Key", "")
        ok, user = self.authenticate(api_key)
        if not ok:
            return {"status": 401, "body": json.dumps({"error": "unauthorized"})}

        # ─── Step 3: 限流 ─────────────────────
        if not self.rate_limiter.allow():
            return {"status": 429, "body": json.dumps({"error": "rate limited"})}

        # ─── Step 4: 负载均衡 → 转发 ──────────
        target = backend.get_instance()
        # 如果是转发到 /api/orders/123 → strip prefix → /123

        # ─── Step 5: 熔断器执行 ───────────────
        try:
            def forward():
                # 实际会 HTTP 调用后端，这里简化模拟
                return {
                    "status": 200,
                    "body": json.dumps({
                        "service": backend.name,
                        "target": target,
                        "path": path,
                        "user": user,
                        "result": "ok"
                    })
                }

            result = self.circuit_breaker.call(forward)
        except Exception as e:
            result = {"status": 503, "body": json.dumps({"error": str(e)})}

        # ─── Step 6: 日志 ─────────────────────
        elapsed = (time.time() - start) * 1000
        log_entry = {
            "method": method, "path": path, "user": user,
            "target": target, "status": result["status"],
            "elapsed_ms": round(elapsed, 2)
        }
        self.request_log.append(log_entry)
        
        return result


# ============================================================
# 演示
# ============================================================
def demo():
    gw = MiniGateway()

    # 配置路由
    order_backend = BackendService("order-service",
                                   ["10.0.1.10:8080", "10.0.1.11:8080"])
    payment_backend = BackendService("payment-service",
                                     ["10.0.2.10:9090"])
    gw.add_route("/api/orders", order_backend)
    gw.add_route("/api/payments", payment_backend)

    # ─── Phase 1: 基本路由 ──────────────────
    print("=" * 60)
    print("Phase 1: 路由转发")
    print("=" * 60)
    
    resp = gw.handle("GET", "/api/orders/123",
                     headers={"X-API-Key": "test-key-123"})
    print(f"✅ GET /api/orders/123 → {resp['status']} : {resp['body'][:80]}")

    resp = gw.handle("GET", "/api/unknown",
                     headers={"X-API-Key": "test-key-123"})
    print(f"❌ GET /api/unknown → {resp['status']} (无路由)")

    # ─── Phase 2: 鉴权 ──────────────────────
    print("\n" + "=" * 60)
    print("Phase 2: 鉴权（API Key）")
    print("=" * 60)

    resp = gw.handle("GET", "/api/orders/1",
                     headers={"X-API-Key": "bad-key"})
    print(f"🔒 错误Key → {resp['status']} : {resp['body']}")

    resp = gw.handle("GET", "/api/orders/1",
                     headers={"X-API-Key": "admin-key-456"})
    print(f"🔑 管理员Key → {resp['status']} user=admin")

    # ─── Phase 3: 负载均衡 ──────────────────
    print("\n" + "=" * 60)
    print("Phase 3: 负载均衡（轮询）")
    print("=" * 60)

    targets = []
    for i in range(4):
        resp = gw.handle("GET", "/api/orders/1",
                         headers={"X-API-Key": "test-key-123"})
        data = json.loads(resp["body"])
        targets.append(data["target"])
        print(f"   请求{i+1} → {data['target']}")

    assert targets[:2] == ["10.0.1.10:8080", "10.0.1.11:8080"], "轮询失败"
    print("✅ 轮询正常: .10 → .11 → .10 → .11")

    # ─── Phase 4: 限流 ──────────────────────
    print("\n" + "=" * 60)
    print("Phase 4: 限流（Token Bucket）")
    print("=" * 60)

    # 快速发 12 个请求（rate=5, capacity=10）
    results = []
    for i in range(12):
        resp = gw.handle("GET", "/api/payments/1",
                         headers={"X-API-Key": "test-key-123"})
        results.append(resp["status"])
    
    ok_count = results.count(200)
    limited_count = results.count(429)
    print(f"   12个请求 → {ok_count} OK, {limited_count} 被限流(429)")
    assert limited_count > 0, "限流未生效"
    print("✅ 限流生效")

    # ─── Phase 5: 熔断 ──────────────────────
    print("\n" + "=" * 60)
    print("Phase 5: 熔断器（Circuit Breaker）")
    print("=" * 60)

    cb = CircuitBreaker(failure_threshold=3, timeout=2)
    fail_count = 0

    def always_fail():
        raise Exception("后端挂了")

    for i in range(5):
        try:
            cb.call(always_fail)
        except Exception as e:
            fail_count += 1
            print(f"   第{i+1}次调用: {e} (熔断状态: {cb.state})")

    print(f"\n✅ 熔断验证: {fail_count}次失败后熔断器状态={cb.state}")

    # ─── 访问日志 ────────────────────────────
    print("\n" + "=" * 60)
    print("Phase 6: 访问日志")
    print("=" * 60)
    for log in gw.request_log[-5:]:
        print(f"   {log['method']:4s} {log['path']:20s} → {log['status']} "
              f"({log['elapsed_ms']}ms) [{log['user']}]")

    print("\n✅ API 网关 6 阶段全部通关！")


if __name__ == "__main__":
    demo()
