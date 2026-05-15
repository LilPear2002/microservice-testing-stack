# Redis 学习笔记

> 📅 2026-05-15 | python: 3.11 | redis-py: 7.4.0 | redis: 7-alpine
> 目录结构：src/（脚本）、tests/（测试）

---

## 阶段1：概念入门

> ⏱ ~5 分钟

### 1.1 Redis 是什么

```
Redis = Remote Dictionary Server

一个运行在内存里的键值数据库。
因为数据在内存，读写是微秒级（MySQL 是毫秒级，差 1000 倍）。
```

### 1.2 一句话定位

| 对比 | MySQL | Redis |
|------|-------|-------|
| 数据在哪 | 磁盘 | **内存** |
| 速度 | 毫秒级 | **微秒级** |
| 数据持久 | ✅ 断电不丢 | ⚠️ 有持久化但不保证 |
| 典型用途 | 业务数据（用户、订单） | **缓存**、**计数器**、**会话** |

**结论：** Redis 是 MySQL 的"加速层"，不是替代品。

### 1.3 缓存模式

```
用户请求 → Nginx → 后端服务
                      │
                      ├─ 先查 Redis（微秒）→ 命中？返回 ✅
                      │
                      └─ 未命中 → 查 MySQL（毫秒）
                                      │
                                      └─ 写回 Redis（下次就快了）
```

### 1.4 5 大数据类型速查

| 类型 | 命令 | 用途 | 类比 |
|------|------|------|------|
| **String** | `SET`/`GET` | 缓存对象、计数器 | Python `dict["k"] = "v"` |
| **Hash** | `HSET`/`HGET` | 存对象属性 | Python `dict` of dicts |
| **List** | `LPUSH`/`RPUSH`/`LRANGE` | 消息队列、时间线 | Python `list` |
| **Set** | `SADD`/`SMEMBERS`/`SINTER` | 标签、去重、共同好友 | Python `set` |
| **Sorted Set** | `ZADD`/`ZRANGE` | 排行榜、延迟队列 | Python `sorted([(score, v)])` |

### 1.5 测开关注的三个核心问题

```
1. 缓存穿透  → 查一个不存在的数据，绕过 Redis 打到 MySQL
2. 缓存击穿  → 热点数据过期瞬间，大量请求同时打 MySQL
3. 缓存雪崩  → 大量数据同时过期，MySQL 瞬间被打崩
```

---

## 阶段2：5大数据类型 + 过期机制

> ⏱ ~15 分钟 | 脚本: `src/02_basic_ops.py`

### 2.1 环境启动

```bash
docker run -d --name redis-learn -p 6379:6379 redis:7-alpine
# 镜像: redis 7-alpine, ~10MB
```

### 2.2 String — 最常用

```python
r.set("user:1:name", "小明")
r.get("user:1:name")              # → "小明"

# 原子计数器（并发安全）
r.incr("page:views")              # → 1, 2, 3...

# 设值+过期
r.setex("session:token", 3, "abc123")  # 3秒后自动删除
```

### 2.3 Hash — 存对象

```python
r.hset("user:2", mapping={"name": "小红", "age": "22"})
r.hgetall("user:2")               # → {'name': '小红', 'age': '22'}
r.hincrby("user:2", "age", 1)     # 年龄+1
```

### 2.4 List — 队列

```python
r.rpush("tasks", "A", "B", "C")
r.lpop("tasks")                   # → "A"（FIFO）
```

### 2.5 Set — 去重/交集

```python
r.sadd("A:friends", "张三", "李四", "王五")
r.sadd("B:friends", "李四", "王五", "孙七")
r.sinter("A:friends", "B:friends")  # → {'李四', '王五'}（共同好友）
```

### 2.6 Sorted Set — 排行榜

```python
r.zadd("scores", {"小明": 850, "小红": 920, "小丽": 990})
r.zrevrange("scores", 0, -1, withscores=True)
# → [('小丽', 990.0), ('小红', 920.0), ('小明', 850.0)]
```

### 2.7 TTL 过期

```python
r.setex("temp", 5, "data")
r.ttl("temp")     # → 5（秒）
time.sleep(6)
r.ttl("temp")     # → -2（已过期删除）
```

> **TTL 返回值：** 正数=剩余秒数 / -1=永不过期 / -2=key不存在

---

## 阶段3：Pub/Sub 发布订阅

> ⏱ ~10 分钟 | 脚本: `src/03_pubsub.py`

### 3.1 核心概念

```
发布者 (Publisher)  →  发布消息到频道
订阅者 (Subscriber) →  监听频道，收到消息后处理

关键特性：
- 解耦：发布者不知道谁在订阅
- 实时：消息发出即推送
- 不持久：订阅者不在线就错过了（≠消息队列）
```

### 3.2 精准订阅 vs 模式订阅

```python
# 精准订阅 — 只收 news:tech
pubsub.subscribe("news:tech")

# 模式订阅 — 收所有 news:* 频道
pubsub.psubscribe("news:*")
```

### 3.3 运行结果

```
订阅者A (news:tech):   2条 — 只收 tech 消息
订阅者B (news:sports): 1条 — 只收 sports 消息
通配符订阅 (news:*):   3条 — 全收！
```

> ⚠️ `subscribe` 的回调 type 是 `"message"`，`psubscribe` 的回调 type 是 `"pmessage"`！

---

## 阶段4：缓存三大问题

> ⏱ ~15 分钟 | 脚本: `src/04_cache_problems.py`

### 4.1 缓存穿透 (Penetration)

```
问题：查不存在的 key → 每次都穿透 Redis → 全部打到 DB

演示结果：
❌ 坏做法（不缓存空值）: 5次查询 → DB被打 5次
✅ 好做法（缓存NULL） : 5次查询 → DB被打 1次

面试话术：
"缓存穿透是查询不存在的数据绕过缓存直接打DB。
解决方案：①缓存空值（短期TTL）②布隆过滤器提前过滤。"
```

### 4.2 缓存击穿 (Breakdown)

```
问题：热点key过期瞬间 → 大量并发同时打到DB

演示结果：
❌ 坏做法（无锁）: 10并发 → DB被打 10次
✅ 好做法（分布式锁）: 10并发 → DB被打 1次

面试话术：
"缓存击穿是热点数据过期那一刻大量请求穿透。
解决方案：①互斥锁（SET NX EX）②永不过期+异步更新③逻辑过期。"
```

### 4.3 缓存雪崩 (Avalanche)

```
问题：大量key同一时间过期 → DB瞬间被洪峰打崩

演示结果：
❌ 坏做法（相同TTL）: 100个key → DB被打 100次
✅ 好做法（随机TTL）: 100个key → DB被打 44次

面试话术：
"缓存雪崩是大面积key同时过期导致DB压力骤增。
解决方案：①TTL加随机值②多级缓存③限流降级④集群高可用。"
```

### 4.4 三者对比

| | 穿透 | 击穿 | 雪崩 |
|---|------|------|------|
| 触发 | 查不存在的数据 | 一个热点key过期 | 大量key同时过期 |
| 现象 | 每次穿过缓存 | 并发打同一个key | 所有key的后端请求 |
| 记忆 | "穿"=打穿不存在 | "击"=击中一个点 | "崩"=大面积崩塌 |
| 方案 | 缓存空值/布隆 | 互斥锁 | 随机TTL |

---

## 🎓 Redis 学习完成！

### 测试成绩

```
16 passed in 2.59s
├── String  ×4   SET/GET / INCR / EXPIRE / TTL
├── Hash    ×2   HSET+HGET / HINCRBY
├── List    ×2   RPUSH+LPOP / 空列表
├── Set     ×2   SADD+SMEMBERS / SINTER
├── ZSet    ×2   ZADD+ZRANGE / ZREVRANK
├── PubSub  ×2   subscribe / psubscribe
└── Cache   ×2   穿透(null缓存) / 击穿(NX锁)
```

### 项目结构

```
/workspace/redis/
├── .venv/
├── README.md
├── src/
│   ├── 02_basic_ops.py        ← 5大数据类型实操
│   ├── 03_pubsub.py           ← Pub/Sub 发布订阅
│   └── 04_cache_problems.py   ← 穿透/击穿/雪崩模拟
└── tests/
    └── test_redis.py          ← 16 个测试用例
```

### Redis 面试核心考点

| 问题 | 要点 |
|------|------|
| Redis 为什么快 | 内存存储、单线程+IO多路复用、C语言实现 |
| 5大数据类型 | String/Hash/List/Set/ZSet + 各自典型场景 |
| 过期策略 | 惰性删除 + 定期删除（不是实时！） |
| 持久化 | RDB（快照）+ AOF（命令日志）|
| 缓存穿透 | 不存在的数据 → 缓存空值/布隆过滤器 |
| 缓存击穿 | 热点过期 → 互斥锁/永不过期 |
| 缓存雪崩 | 大批过期 → TTL加随机值/多级缓存 |

---

**下一个模块：B2. Kafka（消息队列）** 📨
