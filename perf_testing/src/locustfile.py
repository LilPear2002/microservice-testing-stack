"""
src/locustfile.py — Phase 2：Locust 进阶实战
=============================================
生产级压测脚本，覆盖 Locust 核心特性

特性                        → 代码体现
─────────────────────────────────────────
HttpUser                    → EcommerceUser(HttpUser)
@task(weight) 任务权重       → browse=5, search=3, detail=2, cart=1, order=1
wait_time(between)          → 模拟用户思考时间 1~3 秒
on_start 初始化              → 登录获取 Token
SequentialTaskSet           → CheckoutFlow 多步骤顺序执行
参数化                      → products[0~199], users[]
自定义事件 hooks             → @events.test_start/stop
断言/检查点                  → assert resp.status_code
环境变量                    → os.getenv("TARGET_HOST")

运行：
  # 先启动目标服务
  python src/target_server.py &

  # 命令行模式（无 Web UI）
  cd /workspace/perf_testing && source .venv/bin/activate
  locust -f src/locustfile.py --headless -u 50 -r 10 -t 30s \
      --host http://localhost:8080 --html reports/report.html

  # Web UI 模式（浏览器看实时图表）
  locust -f src/locustfile.py --host http://localhost:8080
  # 浏览器打开 http://localhost:8089
"""
import os
import random
from locust import HttpUser, task, between, SequentialTaskSet, events


# ═══════════════════════════════════════════════════════════
# 1. 测试数据参数化
# ═══════════════════════════════════════════════════════════

USERS = [f"user_{i:04d}" for i in range(1, 501)]
PRODUCT_IDS = [f"PROD-{i:04d}" for i in range(1, 201)]
CATEGORIES = ["电子", "服装", "食品", "图书"]
SEARCH_KEYWORDS = ["手机", "衣服", "零食", "Python", "电脑", "鞋子", "咖啡", "数据"]


def random_product():
    return random.choice(PRODUCT_IDS)


def random_user():
    return random.choice(USERS)


# ═══════════════════════════════════════════════════════════
# 2. 自定义事件监控
# ═══════════════════════════════════════════════════════════

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    print("=" * 60)
    print(f"  压测开始！用户数: {environment.runner.target_user_count}")
    print(f"  目标地址: {environment.host}")
    print("=" * 60)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    print("=" * 60)
    print("  压测结束！")
    stats = environment.stats
    print(f"  总请求数: {stats.total.num_requests}")
    print(f"  失败数: {stats.total.num_failures}")
    print(f"  平均响应时间: {stats.total.avg_response_time:.0f}ms")
    print(f"  P95 响应时间: {stats.total.get_response_time_percentile(0.95):.0f}ms")
    print(f"  RPS: {stats.total.total_rps:.1f}")
    print("=" * 60)


# ═══════════════════════════════════════════════════════════
# 3. 多步骤任务集：下单流程（SequentialTaskSet）
# ═══════════════════════════════════════════════════════════

class CheckoutFlow(SequentialTaskSet):
    """
    下单流程 —— 多步骤按顺序执行
    浏览商品 → 看详情 → 加购物车 → 下单
    """

    def on_start(self):
        self.product_id = random_product()

    @task
    def step1_view_list(self):
        resp = self.client.get(
            f"/api/products?page={random.randint(1, 5)}&size=10",
            name="/api/products[列表]"
        )
        assert resp.status_code == 200

    @task
    def step2_view_detail(self):
        resp = self.client.get(
            f"/api/products/{self.product_id}",
            name="/api/products[详情]"
        )
        assert resp.status_code in [200, 404]

    @task
    def step3_add_to_cart(self):
        resp = self.client.post(
            "/api/cart",
            json={"product_id": self.product_id, "quantity": 1},
            name="/api/cart"
        )
        assert resp.status_code == 200

    @task
    def step4_create_order(self):
        amount = round(random.uniform(9.9, 999.9), 2)
        resp = self.client.post(
            "/api/orders",
            json={"product_id": self.product_id, "amount": amount},
            name="/api/orders"
        )
        assert resp.status_code == 200
        self.interrupt()  # 流程结束，退回主任务循环


# ═══════════════════════════════════════════════════════════
# 4. 主用户类
# ═══════════════════════════════════════════════════════════

class EcommerceUser(HttpUser):
    """
    电商用户模拟

    HttpUser: 内置 HTTP client (self.client)
    wait_time: 两次任务之间的等待
    host: 目标地址（命令行 --host 传入）
    """

    # 思考时间：1~3 秒（模拟真实用户）
    wait_time = between(1, 3)

    token = None

    def on_start(self):
        """每个虚拟用户启动时执行一次：登录获取 Token"""
        username = random_user()
        resp = self.client.post(
            "/api/login",
            json={"username": username, "password": "test123"},
            name="/api/login"
        )
        if resp.status_code == 200:
            self.token = resp.json().get("token", "")
            self.client.headers.update({
                "Authorization": f"Bearer {self.token}"
            })

    # ── 任务定义 ──
    # weight 比例：浏览 5 : 搜索 3 : 详情 2 : 购物车 1 : 下单 1

    @task(5)
    def browse_products(self):
        """浏览商品列表（最高频）"""
        page = random.randint(1, 5)
        category = random.choice(CATEGORIES + [None])
        params = {"page": page, "size": 10}
        if category:
            params["category"] = category
        resp = self.client.get("/api/products", params=params, name="/api/products[列表]")
        assert resp.status_code == 200

    @task(3)
    def search_products(self):
        """搜索商品（中频）"""
        keyword = random.choice(SEARCH_KEYWORDS)
        resp = self.client.get("/api/search", params={"q": keyword}, name="/api/search")
        assert resp.status_code == 200

    @task(2)
    def view_product_detail(self):
        """商品详情"""
        product_id = random_product()
        resp = self.client.get(f"/api/products/{product_id}", name="/api/products[详情]")
        assert resp.status_code in [200, 404]

    @task(1)
    def add_to_cart(self):
        """加入购物车（低频）"""
        resp = self.client.post(
            "/api/cart",
            json={"product_id": random_product(), "quantity": 1},
            name="/api/cart"
        )
        assert resp.status_code == 200

    @task(1)
    def checkout(self):
        """下单流程（低频，最重）"""
        self.client.get("/api/user/profile", name="/api/user/profile")
        CheckoutFlow(self).run()
