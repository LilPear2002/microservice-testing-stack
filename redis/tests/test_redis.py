"""
Redis pytest 测试 — 覆盖基础操作 + pub/sub + 缓存问题
"""
import pytest
import redis
import time
import threading


@pytest.fixture(scope="module")
def r():
    """连接到 Redis 容器"""
    client = redis.Redis(host="localhost", port=6379, decode_responses=True)
    client.flushall()
    yield client
    client.flushall()
    client.close()


# ====== String 测试 ======
class TestString:
    def test_set_get(self, r):
        r.set("test:key", "hello")
        assert r.get("test:key") == "hello"

    def test_incr(self, r):
        r.set("test:counter", 0)
        r.incr("test:counter")
        r.incr("test:counter")
        assert r.get("test:counter") == "2"

    def test_expire(self, r):
        r.setex("test:tmp", 2, "data")
        assert r.get("test:tmp") == "data"
        time.sleep(2.5)
        assert r.get("test:tmp") is None

    def test_ttl(self, r):
        r.setex("test:ttl", 10, "val")
        ttl = r.ttl("test:ttl")
        assert 0 < ttl <= 10  # TTL 在 0~10 之间


# ====== Hash 测试 ======
class TestHash:
    def test_hset_hget(self, r):
        r.hset("user:1", mapping={"name": "小明", "age": "25"})
        assert r.hget("user:1", "name") == "小明"
        assert r.hgetall("user:1") == {"name": "小明", "age": "25"}

    def test_hincrby(self, r):
        r.hset("user:2", "visits", 5)
        r.hincrby("user:2", "visits", 3)
        assert r.hget("user:2", "visits") == "8"


# ====== List 测试 ======
class TestList:
    def test_push_pop(self, r):
        r.rpush("queue", "A", "B", "C")
        assert r.lpop("queue") == "A"
        assert r.lrange("queue", 0, -1) == ["B", "C"]

    def test_empty(self, r):
        assert r.lpop("nonexistent") is None


# ====== Set 测试 ======
class TestSet:
    def test_sadd_smembers(self, r):
        r.sadd("tags", "python", "redis", "docker")
        assert r.smembers("tags") == {"python", "redis", "docker"}

    def test_sinter(self, r):
        r.sadd("s1", "a", "b", "c")
        r.sadd("s2", "b", "c", "d")
        common = r.sinter("s1", "s2")
        assert common == {"b", "c"}


# ====== Sorted Set 测试 ======
class TestSortedSet:
    def test_zadd_zrange(self, r):
        r.zadd("scores", {"小明": 850, "小红": 920})
        assert r.zrevrange("scores", 0, -1) == ["小红", "小明"]

    def test_zrevrank(self, r):
        r.delete("scores")
        r.zadd("scores", {"A": 100, "B": 200, "C": 50})
        # 降序: B(200) > A(100) > C(50) → B rank=0
        assert r.zrevrank("scores", "B") == 0


# ====== Pub/Sub 测试 ======
class TestPubSub:
    def test_basic_pubsub(self, r):
        sub = redis.Redis(host="localhost", port=6379, decode_responses=True)
        pubsub = sub.pubsub()
        pubsub.subscribe("test:chan")

        # 发一条消息
        r.publish("test:chan", "hello world")

        # 接收
        msg = pubsub.get_message(timeout=1)  # skip subscribe ack
        msg = pubsub.get_message(timeout=1)
        assert msg["type"] == "message"
        assert msg["data"] == "hello world"

        pubsub.unsubscribe("test:chan")
        sub.close()

    def test_pattern_pubsub(self, r):
        sub = redis.Redis(host="localhost", port=6379, decode_responses=True)
        pubsub = sub.pubsub()
        pubsub.psubscribe("news:*")

        r.publish("news:tech", "新版本发布")

        pubsub.get_message(timeout=0.5)  # skip ack
        msg = pubsub.get_message(timeout=1)
        assert msg["type"] == "pmessage"
        assert msg["channel"] == "news:tech"
        assert msg["data"] == "新版本发布"

        pubsub.punsubscribe("news:*")
        sub.close()


# ====== 缓存穿透测试 ======
class TestCachePenetration:
    def test_null_cache(self, r):
        """缓存空值防止穿透"""
        r.flushall()
        hit_count = 0

        for _ in range(3):
            val = r.get("user:nonexist")
            if val is None:
                hit_count += 1
                r.setex("user:nonexist", 60, "NULL")

        assert hit_count == 1  # 只有第一次穿透


# ====== 缓存击穿测试 ======
class TestCacheBreakdown:
    def test_lock_protection(self, r):
        """SET NX EX 原子锁：只有第一个 SET 成功"""
        r.delete("lock:key")
        # 第一个 SET 成功
        ok1 = r.set("lock:key", "1", nx=True, ex=3)
        # 第二个 SET 失败（key 已存在）
        ok2 = r.set("lock:key", "2", nx=True, ex=3)
        assert ok1 is True
        assert ok2 is None  # NX 失败返回 None（不是 False！）
        r.delete("lock:key")
