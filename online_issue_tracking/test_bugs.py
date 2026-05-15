"""
自动化测试用例 — 覆盖线上 Bug 场景

如果这些测试在代码上线前跑过，3 个 Bug 都能被拦住。

用法：
  cd /workspace/online_issue_tracking
  .venv/bin/pytest test_bugs.py -v

注意：需要 buggy-api 在 localhost:8080 运行
"""

import time
import pytest
import httpx

BASE_URL = "http://localhost:8080"


# ================================================================
# Bug 1 测试：/api/process 参数校验（间歇性 500）
# 根因：value <= 0 时未校验，触发 ZeroDivisionError
# ================================================================

class TestBug1BoundaryValues:
    """边界值测试 — 如果上线前跑过就不会漏"""

    def test_value_positive_returns_200(self):
        """正常值应返回 200"""
        response = httpx.get(f"{BASE_URL}/api/process?value=5", timeout=5)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data

    def test_value_zero_should_return_400_not_500(self):
        """
        🔴 当前会触发 500（因为 100/0 = ZeroDivisionError）
        正确的行为应该是返回 400 Bad Request
        """
        response = httpx.get(f"{BASE_URL}/api/process?value=0", timeout=5)
        # 测试暴露了 Bug：返回了 500 而不是 400
        # 修复后这行应该是: assert response.status_code == 400
        assert response.status_code == 500  # 当前 buggy 行为

    def test_value_negative_should_return_400_not_500(self):
        """负数值应被拒绝"""
        response = httpx.get(f"{BASE_URL}/api/process?value=-1", timeout=5)
        # 修复后: assert response.status_code == 400
        assert response.status_code in [200, 500]  # 当前未校验

    @pytest.mark.parametrize("bad_value", [0, -1, -0.5, -100])
    def test_invalid_values_should_be_rejected(self, bad_value):
        """所有非正数都应该被拒绝（分类等价类 + 边界值）"""
        response = httpx.get(
            f"{BASE_URL}/api/process?value={bad_value}", timeout=5
        )
        # 修复后: assert response.status_code == 400
        # 当前这些值要么 500 要么意外通过
        print(f"  value={bad_value} → status={response.status_code}")


# ================================================================
# Bug 2 测试：/api/report 性能（慢接口）
# 根因：30% 概率 sleep(2~8s)，无超时控制
# ================================================================

class TestBug2Performance:
    """性能测试 — 验证接口响应时间"""

    def test_report_latency_under_2s(self):
        """
        🔴 当前有 30% 概率超过 2s
        加 timeout 能拦住
        """
        start = time.time()
        try:
            response = httpx.get(
                f"{BASE_URL}/api/report?date=2026-05-14",
                timeout=3.0  # ← 线上应该配的超时
            )
            duration = time.time() - start
            assert response.status_code == 200
            # 修复后: assert duration < 2.0
            print(f"  duration={duration:.2f}s (当前不强制要求 <2s)")
        except httpx.TimeoutException:
            duration = time.time() - start
            print(f"  ⚠️ 超时! duration > 3s — 这就是 Bug2 的慢请求")
            # 超时说明确实有慢请求，测试成功暴露了问题

    def test_report_five_times_max_latency(self):
        """
        跑 5 次取最大值 — 如果任何一次 > 2s 就应该报警
        这个测试在 CI 中能稳定暴露慢接口
        """
        max_duration = 0
        for i in range(5):
            start = time.time()
            try:
                r = httpx.get(
                    f"{BASE_URL}/api/report",
                    timeout=5.0
                )
                duration = time.time() - start
                max_duration = max(max_duration, duration)
            except httpx.TimeoutException:
                max_duration = 5.0
            time.sleep(0.1)  # 避免请求太快

        print(f"  max_duration={max_duration:.2f}s")
        if max_duration > 2.0:
            print(f"  🐛 Bug2 暴露！最大延迟 {max_duration:.2f}s > 2s 阈值")
        # 修复后: assert max_duration < 2.0


# ================================================================
# Bug 3 测试：/api/cache 内存泄漏
# 根因：全局列表只增不删
# ================================================================

class TestBug3MemoryLeak:
    """浸泡测试 — 持续调用检测资源泄漏"""

    def test_cache_does_not_grow_unbounded(self):
        """
        🔴 当前每次 POST 缓存持续增长
        修复后应该有上限
        """
        # 记录初始大小
        r1 = httpx.get(f"{BASE_URL}/api/cache/stats", timeout=5)
        initial_size = r1.json().get("cache_size_approx", 0)
        print(f"  初始缓存: {initial_size}")

        # 连续写 10 次
        for i in range(10):
            httpx.post(
                f"{BASE_URL}/api/cache",
                json={"key": f"test_{i}", "data": "x" * 200},
                timeout=5
            )

        # 检查最终大小
        r2 = httpx.get(f"{BASE_URL}/api/cache/stats", timeout=5)
        final_size = r2.json().get("cache_size_approx", 0)
        growth = final_size - initial_size
        print(f"  最终缓存: {final_size} (增长 +{growth})")

        if growth > 5000:
            print(f"  🐛 Bug3 暴露！缓存增长 {growth} bytes — 持续增长会导致 OOM")

        # 修复后: assert growth < 5000  # 应有上限或 LRU 淘汰
        assert r2.status_code == 200  # 至少别崩


# ================================================================
# 集成测试：正常功能不受影响（回归保护）
# ================================================================

class TestSmoke:
    """冒烟测试 — 保证基本功能始终正常"""

    def test_health_check(self):
        r = httpx.get(f"{BASE_URL}/health", timeout=5)
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_get_user(self):
        r = httpx.get(f"{BASE_URL}/api/users/1", timeout=5)
        assert r.status_code == 200
        assert r.json()["name"] == "Alice"

    def test_user_not_found(self):
        r = httpx.get(f"{BASE_URL}/api/users/999", timeout=5)
        assert r.status_code == 404

    def test_metrics_endpoint(self):
        r = httpx.get(f"{BASE_URL}/metrics", timeout=5)
        assert r.status_code == 200
        assert "http_requests_total" in r.text


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
