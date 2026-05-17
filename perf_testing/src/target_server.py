"""
src/target_server.py — Phase 2 被测服务
=======================================
一个模拟电商 API，刻意加入：
- 正常延迟（模拟 DB 查询）
- 偶尔慢查询（模拟慢 SQL）
- 偶尔报错（模拟服务异常）
- Token 鉴权

这样 Locust 压测结果才真实，不会全是 5ms。

启动：cd /workspace/perf_testing && source .venv/bin/activate && python src/target_server.py
默认端口 8080
"""
import time
import random
import uuid
import hashlib
from flask import Flask, request, jsonify

app = Flask(__name__)

# ── 模拟数据 ──
PRODUCTS = [
    {"id": f"PROD-{i:04d}", "name": f"商品_{i}", "price": round(random.uniform(9.9, 999.9), 2),
     "stock": random.randint(0, 500), "category": random.choice(["电子", "服装", "食品", "图书"])}
    for i in range(1, 201)
]

# 模拟 Token（简化：生成后存内存）
VALID_TOKENS = set()


def simulate_db_query(min_ms=10, max_ms=80):
    """模拟正常 DB 查询延迟"""
    time.sleep(random.uniform(min_ms, max_ms) / 1000)


def simulate_slow_query():
    """模拟偶尔的慢查询（P99 长尾的来源）"""
    if random.random() < 0.05:  # 5% 概率
        time.sleep(random.uniform(0.1, 0.5))


def simulate_error():
    """模拟偶尔的服务异常"""
    if random.random() < 0.02:  # 2% 概率
        return jsonify({"error": "服务暂时不可用"}), 503
    return None


# ═══════════════════════════════════════════════════
# API 端点
# ═══════════════════════════════════════════════════

@app.route("/health", methods=["GET"])
def health():
    """健康检查"""
    return jsonify({"status": "ok"})


@app.route("/api/login", methods=["POST"])
def login():
    """登录 → 返回 Token"""
    simulate_db_query(20, 50)

    data = request.get_json() or {}
    username = data.get("username", "unknown")
    password = data.get("password", "")

    # 简单鉴权（压测时所有用户都能登录）
    if not username:
        return jsonify({"error": "缺少用户名"}), 400

    token = hashlib.md5(f"{username}:{uuid.uuid4()}".encode()).hexdigest()[:16]
    VALID_TOKENS.add(token)
    return jsonify({"token": token, "user_id": username})


def require_auth():
    """鉴权装饰器（简化版）"""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if token not in VALID_TOKENS:
        return jsonify({"error": "未授权"}), 401
    return None


@app.route("/api/products", methods=["GET"])
def list_products():
    """商品列表（带分页）"""
    err = simulate_error()
    if err:
        return err

    auth_err = require_auth()
    if auth_err:
        return auth_err

    simulate_db_query(30, 60)
    simulate_slow_query()

    page = int(request.args.get("page", 1))
    size = min(int(request.args.get("size", 20)), 50)
    category = request.args.get("category")

    products = PRODUCTS
    if category:
        products = [p for p in products if p["category"] == category]

    start = (page - 1) * size
    end = start + size
    page_data = products[start:end]

    return jsonify({
        "total": len(products),
        "page": page,
        "size": size,
        "items": page_data
    })


@app.route("/api/products/<product_id>", methods=["GET"])
def product_detail(product_id):
    """商品详情"""
    err = simulate_error()
    if err:
        return err

    auth_err = require_auth()
    if auth_err:
        return auth_err

    simulate_db_query(50, 100)
    simulate_slow_query()

    product = next((p for p in PRODUCTS if p["id"] == product_id), None)
    if not product:
        return jsonify({"error": "商品不存在"}), 404

    # 模拟关联查询（库存、评价、推荐）
    time.sleep(random.uniform(0.01, 0.03))

    return jsonify({
        **product,
        "reviews_count": random.randint(0, 999),
        "related_products": [p["id"] for p in random.sample(PRODUCTS, 3)]
    })


@app.route("/api/search", methods=["GET"])
def search_products():
    """搜索商品"""
    err = simulate_error()
    if err:
        return err

    auth_err = require_auth()
    if auth_err:
        return auth_err

    simulate_db_query(40, 120)  # 搜索比列表慢
    simulate_slow_query()

    keyword = request.args.get("q", "")
    if not keyword:
        return jsonify({"items": [], "total": 0})

    # 模拟搜索匹配
    results = [p for p in PRODUCTS if keyword in p["name"] or keyword in p["category"]]
    return jsonify({"items": results[:20], "total": len(results)})


@app.route("/api/cart", methods=["POST"])
def add_to_cart():
    """加入购物车"""
    err = simulate_error()
    if err:
        return err

    auth_err = require_auth()
    if auth_err:
        return auth_err

    simulate_db_query(15, 40)

    data = request.get_json() or {}
    return jsonify({
        "status": "added",
        "product_id": data.get("product_id", "unknown"),
        "quantity": data.get("quantity", 1)
    })


@app.route("/api/orders", methods=["POST"])
def create_order():
    """创建订单（最重的接口）"""
    err = simulate_error()
    if err:
        return err

    auth_err = require_auth()
    if auth_err:
        return auth_err

    # 模拟事务：查库存 + 扣款 + 写订单 + 发通知
    simulate_db_query(80, 200)
    simulate_slow_query()
    simulate_slow_query()  # 订单接口双重慢查询概率

    data = request.get_json() or {}
    return jsonify({
        "order_id": f"ORD-{uuid.uuid4().hex[:8].upper()}",
        "status": "created",
        "amount": data.get("amount", 0)
    })


@app.route("/api/user/profile", methods=["GET"])
def user_profile():
    """用户信息"""
    auth_err = require_auth()
    if auth_err:
        return auth_err

    simulate_db_query(10, 30)
    return jsonify({"user_id": "test_user", "name": "测试用户", "level": "VIP"})


if __name__ == "__main__":
    print("=" * 60)
    print("  被测目标服务启动")
    print("  http://0.0.0.0:8080")
    print("  端点：/api/login  /api/products  /api/search")
    print("       /api/cart   /api/orders  /api/user/profile")
    print("=" * 60)
    app.run(host="0.0.0.0", port=8080, debug=False)
