"""
阶段2: Redis 5大数据类型 + 过期机制 实操
"""
import redis
import time

r = redis.Redis(host="localhost", port=6379, decode_responses=True)

print("=" * 50)
print("🔤 1. String — 最常用")
print("=" * 50)

# SET/GET
r.set("user:1:name", "小明")
r.set("user:1:age", 25)
print(f"GET user:1:name → {r.get('user:1:name')}")
print(f"GET user:1:age → {r.get('user:1:age')}")

# INCR 原子计数器
r.set("page:views", 0)
for _ in range(3):
    r.incr("page:views")
print(f"页面访问量(INCR×3) → {r.get('page:views')}")

# SETEX: 设值 + 过期（秒）
r.setex("session:token", 3, "abc123")  # 3秒过期
print(f"token (立即查) → {r.get('session:token')}")
time.sleep(4)
print(f"token (4秒后查) → {r.get('session:token')} (已过期=空!)")

print()
print("=" * 50)
print("📦 2. Hash — 存对象")
print("=" * 50)

r.hset("user:2", mapping={"name": "小红", "age": "22", "city": "杭州"})
print(f"HGETALL user:2 → {r.hgetall('user:2')}")
print(f"HGET user:2 name → {r.hget('user:2', 'name')}")
r.hincrby("user:2", "age", 1)  # 年龄+1
print(f"年龄+1后 → {r.hget('user:2', 'age')}")

print()
print("=" * 50)
print("📋 3. List — 消息队列/时间线")
print("=" * 50)

r.delete("tasks")
r.rpush("tasks", "任务A", "任务B", "任务C")
print(f"RPUSH 3个 → {r.lrange('tasks', 0, -1)}")
task = r.lpop("tasks")
print(f"LPOP → {task}")
print(f"剩余 → {r.lrange('tasks', 0, -1)}")

print()
print("=" * 50)
print("🔢 4. Set — 去重/共同好友")
print("=" * 50)

r.delete("user:A:friends", "user:B:friends")
r.sadd("user:A:friends", "张三", "李四", "王五", "赵六")
r.sadd("user:B:friends", "李四", "王五", "孙七")
print(f"A的好友 → {r.smembers('user:A:friends')}")
print(f"B的好友 → {r.smembers('user:B:friends')}")
common = r.sinter("user:A:friends", "user:B:friends")
print(f"共同好友(SINTER) → {common}")

print()
print("=" * 50)
print("🏆 5. Sorted Set — 排行榜")
print("=" * 50)

r.delete("game:score")
r.zadd("game:score", {"小明": 850, "小红": 920, "小刚": 760, "小丽": 990})
print(f"全部排名 ZRANGE → {r.zrange('game:score', 0, -1)}")
print(f"带分数 ZREVRANGE WITHSCORES → {r.zrevrange('game:score', 0, -1, withscores=True)}")
rank = r.zrevrank("game:score", "小明")
print(f"小明的排名(ZREVRANK) → 第{rank + 1}名")

print()
print("=" * 50)
print("⏰ 6. 过期机制")
print("=" * 50)

r.set("temp:key", "临时的", ex=5)  # 5秒过期
print(f"TTL temp:key → {r.ttl('temp:key')}秒")
time.sleep(6)
print(f"TTL temp:key (6秒后) → {r.ttl('temp:key')}秒")  # -2 = 已过期不存在

print()
print("✅ 5大数据类型 + 过期全部演示完毕！")
