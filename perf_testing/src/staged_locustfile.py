"""
src/staged_locustfile.py — Phase 4：阶梯加压实战
================================================
自定义 LoadTestShape 实现阶梯加压：
  预热(10并发) → 基准(50) → 中等(100) → 高压(200) → 极限(300)

配合 --csv 和 --html 生成完整数据集

运行：
  # 先启动目标服务
  python src/target_server.py &

  cd /workspace/perf_testing && source .venv/bin/activate
  locust -f src/staged_locustfile.py --headless \
      --host http://localhost:8080 \
      --html reports/phase4_report.html \
      --csv reports/phase4

  # Web UI 模式（能看到实时阶梯曲线）
  locust -f src/staged_locustfile.py --host http://localhost:8080
"""
import random
from locust import HttpUser, task, between, LoadTestShape, events


# ═══════════════════════════════════════════════
# 1. 阶梯加压策略
# ═══════════════════════════════════════════════

class StagedLoadShape(LoadTestShape):
    """
    四档阶梯加压：

    阶段 1: 0-60s  → 10 users   (预热，确认环境)
    阶段 2: 60-120s → 50 users  (基准线)
    阶段 3: 120-180s→ 100 users (中等负载)
    阶段 4: 180-240s→ 200 users (高负载)
    阶段 5: 240-300s→ 300 users (极限测试)

    每阶段自动记录：
    - 阶段名称
    - 并发数
    - 持续时间
    """

    stages = [
        {"name": "预热",    "duration": 60,  "users": 10,  "spawn_rate": 5},
        {"name": "基准",    "duration": 60,  "users": 50,  "spawn_rate": 10},
        {"name": "中等负载", "duration": 60,  "users": 100, "spawn_rate": 10},
        {"name": "高负载",   "duration": 60,  "users": 200, "spawn_rate": 20},
        {"name": "极限测试", "duration": 60,  "users": 300, "spawn_rate": 30},
    ]

    current_stage_index = -1

    def tick(self):
        run_time = self.get_run_time()
        cumulative = 0

        for i, stage in enumerate(self.stages):
            cumulative += stage["duration"]
            if run_time <= cumulative:
                if self.current_stage_index != i:
                    self.current_stage_index = i
                    print(f"\n{'='*50}")
                    print(f"  【阶段 {i+1}】{stage['name']}")
                    print(f"  并发: {stage['users']} | 速率: {stage['spawn_rate']}/s")
                    print(f"{'='*50}")
                return (stage["users"], stage["spawn_rate"])

        return None  # 压测结束


# ═══════════════════════════════════════════════
# 2. 测试数据
# ═══════════════════════════════════════════════

USERS = [f"user_{i:04d}" for i in range(1, 1001)]
PRODUCT_IDS = [f"PROD-{i:04d}" for i in range(1, 201)]


def random_user():
    return random.choice(USERS)


def random_product():
    return random.choice(PRODUCT_IDS)


# ═══════════════════════════════════════════════
# 3. 压测事件监控
# ═══════════════════════════════════════════════

@events.test_start.add_listener
def on_start(environment, **kwargs):
    print("=" * 60)
    print("  阶梯加压压测开始")
    print("  预热 10 → 基准 50 → 中等 100 → 高压 200 → 极限 300")
    print("  每档 60 秒，共 300 秒")
    print(f"  目标: {environment.host}")
    print("=" * 60)


@events.test_stop.add_listener
def on_stop(environment, **kwargs):
    stats = environment.stats
    print("\n" + "=" * 60)
    print("  阶梯加压压测结束")
    print(f"  总请求: {stats.total.num_requests}")
    print(f"  总失败: {stats.total.num_failures}")
    print(f"  平均 RT: {stats.total.avg_response_time:.0f}ms")
    print(f"  P50: {stats.total.get_response_time_percentile(0.5):.0f}ms")
    print(f"  P95: {stats.total.get_response_time_percentile(0.95):.0f}ms")
    print(f"  P99: {stats.total.get_response_time_percentile(0.99):.0f}ms")
    print(f"  峰值 RPS: {stats.total.total_rps:.1f}")
    print("=" * 60)


# ═══════════════════════════════════════════════
# 4. 压测用户
# ═══════════════════════════════════════════════

class EcommerceUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        resp = self.client.post(
            "/api/login",
            json={"username": random_user(), "password": "test123"},
            name="/api/login"
        )
        if resp.status_code == 200:
            self.client.headers["Authorization"] = f"Bearer {resp.json()['token']}"

    @task(5)
    def browse(self):
        resp = self.client.get(
            f"/api/products?page={random.randint(1,5)}",
            name="/api/products"
        )

    @task(3)
    def search(self):
        resp = self.client.get(
            f"/api/search?q={random.choice(['手机','衣服','Python'])}",
            name="/api/search"
        )

    @task(2)
    def detail(self):
        resp = self.client.get(
            f"/api/products/{random_product()}",
            name="/api/products[详情]"
        )

    @task(1)
    def checkout(self):
        self.client.get("/api/user/profile", name="/api/user/profile")
        resp = self.client.post(
            "/api/orders",
            json={"product_id": random_product(), "amount": random.randint(10, 500)},
            name="/api/orders"
        )
