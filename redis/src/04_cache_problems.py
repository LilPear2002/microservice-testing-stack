"""
阶段4: 缓存三大问题 — 穿透/击穿/雪崩 模拟与解决
每个问题：模拟坏做法 → 看伤害 → 展示正确做法
"""
import redis
import time
import random
import threading

r = redis.Redis(host="localhost", port=6379, decode_responses=True)
r.flushall()  # 清空测试

db_hits = {"count": 0}  # 模拟 DB 被打了多少次


def query_db(key):
    """模拟查数据库（耗时 50ms）"""
    time.sleep(0.05)
    db_hits["count"] += 1
    return f"db_value_of_{key}"


def cache_get_or_fetch(key, ttl=None):
    """标准缓存读取：先查 Redis，未命中查 DB 并回写"""
    val = r.get(key)
    if val is not None:
        return val
    val = query_db(key)
    if ttl:
        r.setex(key, ttl, val)
    else:
        r.set(key, val)
    return val


# =============================================
print("=" * 60)
print("💥 1. 缓存穿透 (Cache Penetration)")
print("=" * 60)
print("场景: 查询不存在的数据 → 每次都穿透缓存打 DB")
print()

db_hits["count"] = 0
r.flushall()

# 坏做法：不存在的 key 也不缓存
print("❌ 坏做法: 不缓存空值")
for i in range(5):
    val = r.get("user:99999")  # 数据库里根本没有99999号用户
    if val is None:
        val = query_db("user:99999")  # 每次都查DB!
print(f"   5次查询不存在用户 → DB被打了 {db_hits['count']} 次 (应该缓存空值!)")

db_hits["count"] = 0
r.flushall()

# 好做法：缓存一个特殊值（如 "NULL"）
print("✅ 好做法: 缓存空值，短期过期")
NULL_TTL = 10
for i in range(5):
    val = r.get("user:99999")
    if val is None:
        val = query_db("user:99999")
        r.setex("user:99999", NULL_TTL, "NULL")  # 缓存"不存在"这个事实
    # 后续请求命中 Redis 中的 "NULL"，不再打 DB
print(f"   5次查询不存在用户 → DB被打了 {db_hits['count']} 次 (只有第1次穿透!)")
print()
print("💡 面试: 布隆过滤器是更彻底的方案——提前判断key是否可能存在")
print()

# =============================================
time.sleep(0.5)
print("=" * 60)
print("⚡ 2. 缓存击穿 (Cache Breakdown)")
print("=" * 60)
print("场景: 热点key过期瞬间，大量并发请求同时打DB")
print()

db_hits["count"] = 0
r.flushall()

# 先预热
r.set("hot:item:stock", "100", ex=2)  # 2秒过期
print("预置 hot:item:stock=100 (2秒过期)")
time.sleep(2.5)  # 等它过期

# 坏做法：10个并发线程同时抢
print("❌ 坏做法: 过期瞬间10个并发请求")
db_hits["count"] = 0
barrier = threading.Barrier(10)

def bad_fetch():
    barrier.wait()  # 同时开始
    val = r.get("hot:item:stock")
    if val is None:
        query_db("hot:item:stock")
        r.set("hot:item:stock", "100")

threads = [threading.Thread(target=bad_fetch) for _ in range(10)]
for t in threads:
    t.start()
for t in threads:
    t.join()
print(f"   10并发 → DB被打了 {db_hits['count']} 次 (都穿透了!)")

# 好做法：分布式锁
db_hits["count"] = 0
r.flushall()
r.set("hot:item:stock", "100", ex=2)
time.sleep(2.5)

lock = threading.Lock()
print("✅ 好做法: 用锁保护，只有第一个请求查DB")

def good_fetch():
    barrier.wait()
    val = r.get("hot:item:stock")
    if val is None:
        # 尝试获取锁（SETNX = SET if Not eXists）
        if r.setnx("lock:hot:item:stock", "1"):
            r.expire("lock:hot:item:stock", 3)
            try:
                val = r.get("hot:item:stock")  # double check
                if val is None:
                    query_db("hot:item:stock")
                    r.set("hot:item:stock", "100")
            finally:
                r.delete("lock:hot:item:stock")
        else:
            time.sleep(0.05)  # 等锁持有者写完
            val = r.get("hot:item:stock")

threads = [threading.Thread(target=good_fetch) for _ in range(10)]
for t in threads:
    t.start()
for t in threads:
    t.join()
print(f"   10并发 → DB被打了 {db_hits['count']} 次 (只有1次!)")
print()
print("💡 面试: 互斥锁 / 永不过期+异步更新 / 逻辑过期 三种方案")
print()

# =============================================
time.sleep(0.5)
print("=" * 60)
print("❄️  3. 缓存雪崩 (Cache Avalanche)")
print("=" * 60)
print("场景: 大量key在同一时间过期 → DB瞬间承受所有流量")
print()

db_hits["count"] = 0
r.flushall()

# 坏做法：所有key同一TTL
print("❌ 坏做法: 100个key全部 TTL=3秒")
keys = [f"item:{i}" for i in range(100)]
for k in keys:
    r.setex(k, 3, f"val_{k}")
time.sleep(3.5)  # 全部同时过期

for k in keys:
    val = r.get(k)
    if val is None:
        query_db(k)
print(f"   100个key同时过期后查询 → DB被打 {db_hits['count']} 次")

# 好做法：TTL加随机偏移
db_hits["count"] = 0
r.flushall()

print("✅ 好做法: 每个key的TTL加随机偏移(3~6秒)")
for k in keys:
    ttl = 3 + random.randint(0, 3)  # 3~6秒
    r.setex(k, ttl, f"val_{k}")
time.sleep(3.5)  # 有些已过期，有些还没

for k in keys:
    val = r.get(k)
    if val is None:
        query_db(k)
print(f"   加随机TTL后同时查询 → DB被打 {db_hits['count']} 次 (分散了!)")
print()
print("💡 面试: TTL加随机值 / 多级缓存 / 限流降级")
print()
print("=" * 60)
print("🎓 缓存三大问题演示完毕!")
print("=" * 60)
