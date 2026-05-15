"""
D2: Apache Doris — OLAP 分析型数据库
D3: DataBus — 数据总线（CDC 数据同步管道）

⚠️ 两者均是分布式系统，2C2G 机器无法运行
  本文件用 Python 模拟 + 架构图 + 面试话术学习
"""

import time
import json
from collections import defaultdict
from dataclasses import dataclass, field
from typing import List, Dict, Optional


# ╔══════════════════════════════════════════════════════════╗
# ║              D2: Apache Doris — OLAP 数据库              ║
# ╚══════════════════════════════════════════════════════════╝

print("=" * 60)
print("D2: Apache Doris — MPP 分析型数据库")
print("=" * 60)

# ============================================================
# Phase 1: 架构概念
# ============================================================
print("""
┌─────────────────────────────────────────────────────┐
│              Doris 架构（MPP 无共享）                │
│                                                     │
│  MySQL 协议 ← 兼容！用 MySQL 客户端连接              │
│     │                                               │
│  ┌──▼──────────────────────────────────────────┐   │
│  │         FE（Frontend）— 元数据 + 查询规划     │   │
│  │         类似 MySQL 的"大脑"                  │   │
│  │         - 存储元数据（表结构/分区信息）       │   │
│  │         - SQL 解析 → 执行计划                 │   │
│  │         - 多 FE 主从，类似 ZK 选主            │   │
│  └──┬──────────┬──────────┬────────────────────┘   │
│     │          │          │                        │
│  ┌──▼────┐ ┌──▼────┐ ┌──▼────┐                    │
│  │ BE #1 │ │ BE #2 │ │ BE #3 │  ← Backend 节点    │
│  │┌─────┐│ │┌─────┐│ │┌─────┐│                    │
│  ││数据  ││ ││数据  ││ ││数据  ││  每 BE 负责一部分│
│  ││分片1 ││ ││分片2 ││ ││分片3 ││  数据分片（Tablet）│
│  │└─────┘│ │└─────┘│ │└─────┘│                    │
│  └───────┘ └───────┘ └───────┘                    │
│                                                     │
│  核心设计：                                         │
│  - 每个 BE 独立存储 + 计算自己的分片                │
│  - 查询时 BE 并行计算 → FE 汇总结果                 │
│  - 列式存储 + 压缩 → 扫描快 10~100x                │
└─────────────────────────────────────────────────────┘
""")

# ============================================================
# Phase 2: 列式存储 vs 行式存储
# ============================================================
print("\n📊 Phase 2: 列式存储 vs 行式存储")

# 模拟数据
rows = [
    {"date": "2026-01-01", "user": "u1", "city": "杭州", "amount": 99.9},
    {"date": "2026-01-01", "user": "u2", "city": "北京", "amount": 199.0},
    {"date": "2026-01-02", "user": "u1", "city": "杭州", "amount": 49.9},
    {"date": "2026-01-02", "user": "u3", "city": "上海", "amount": 299.0},
]

# 行式存储（MySQL/PostgreSQL）
row_layout = [
    "u1,杭州,99.9",
    "u2,北京,199.0",
    "u1,杭州,49.9",
    "u3,上海,299.0",
]
print("   行式存储（MySQL）：", row_layout)
print("   → 查 SUM(amount): 要扫描所有行，读全部字段")

# 列式存储（Doris/ClickHouse）
col_layout = {
    "user":  ["u1", "u2", "u1", "u3"],
    "city":  ["杭州", "北京", "杭州", "上海"],
    "amount": [99.9, 199.0, 49.9, 299.0],
}
print(f"   列式存储（Doris）： amount = {col_layout['amount']}")
print("   → 查 SUM(amount): 只读 amount 列，跳过 user/city！10~100x 加速")


# ============================================================
# Phase 3: 数据模型
# ============================================================
print("\n📊 Phase 3: Doris 三种数据模型")

print("""
  1. Duplicate（明细模型）
     保留所有原始数据，不去重
     适用：日志、事件流水
     CREATE TABLE log (...) DUPLICATE KEY(date, user_id)

  2. Unique（主键模型）
     主键唯一，新数据覆盖旧数据
     适用：用户画像、订单状态（需要更新）
     CREATE TABLE users (...) UNIQUE KEY(user_id)

  3. Aggregate（聚合模型）
     写入时自动聚合（SUM/MAX/MIN/REPLACE）
     适用：报表、指标汇总
     CREATE TABLE metrics (...) AGGREGATE KEY(date, dim)
     写入：(2026-01-01, 杭州, 100) + (2026-01-01, 杭州, 200)
     → 自动合并为 (2026-01-01, 杭州, 300)
""")


# ============================================================
# Phase 4: 聚合模型模拟
# ============================================================
print("📊 Phase 4: Aggregate 模型模拟")

class AggregateTable:
    """模拟 Doris Aggregate 模型"""
    def __init__(self):
        self.data = defaultdict(lambda: defaultdict(float))

    def insert(self, date, city, amount):
        """插入时自动聚合 SUM"""
        self.data[date][city] += amount

    def query(self, date=None):
        """查询（已预聚合）"""
        result = []
        for d, cities in self.data.items():
            if date and d != date:
                continue
            for city, total in cities.items():
                result.append({"date": d, "city": city, "amount": total})
        return result

table = AggregateTable()
table.insert("2026-01-01", "杭州", 100)
table.insert("2026-01-01", "杭州", 200)  # 自动合并
table.insert("2026-01-01", "北京", 150)
table.insert("2026-01-02", "杭州", 300)

results = table.query()
print("   写入 4 条，查询结果（自动聚合）:")
for r in results:
    print(f"     {r['date']} {r['city']}: ¥{r['amount']}")


# ╔══════════════════════════════════════════════════════════╗
# ║           D3: DataBus — CDC 数据同步管道                 ║
# ╚══════════════════════════════════════════════════════════╝

print("\n\n" + "=" * 60)
print("D3: DataBus — CDC 数据总线")
print("=" * 60)

print("""
┌──────────────────────────────────────────────────────────┐
│              DataBus = CDC 数据同步管道                   │
│                                                          │
│  用什么同步？                                            │
│    业务 DB (MySQL) ──Canal──→ Kafka ──→ 下游消费         │
│                                                          │
│  Canal 原理：                                            │
│    把自己伪装成 MySQL Slave                             │
│    MySQL Master 把 binlog 推给 Canal                    │
│    Canal 解析 binlog → 转成 JSON → 发到 Kafka           │
│                                                          │
│  为什么不用定时 SELECT？                                 │
│    ❌ 无法感知 DELETE                                   │
│    ❌ 对业务库有查询压力                                 │
│    ❌ 延迟：定时 1 分钟 = 最差 1 分钟延迟               │
│    ✅ Binlog：实时、完整、无业务压力                     │
└──────────────────────────────────────────────────────────┘
""")

# ============================================================
# CDC 模拟（Canal → Kafka → Consumer）
# ============================================================
print("📊 CDC 数据变更捕获模拟")

@dataclass
class BinlogEvent:
    """模拟一条 binlog 事件"""
    op: str          # INSERT / UPDATE / DELETE
    table: str
    before: dict     # 变更前（UPDATE/DELETE）
    after: dict      # 变更后（INSERT/UPDATE）
    timestamp: float = field(default_factory=time.time)


class CanalSimulator:
    """模拟 Canal：解析 binlog → 结构化事件"""

    def __init__(self):
        self.events: List[BinlogEvent] = []

    def capture_insert(self, table, row):
        self.events.append(BinlogEvent("INSERT", table, {}, row))

    def capture_update(self, table, before, after):
        self.events.append(BinlogEvent("UPDATE", table, before, after))

    def capture_delete(self, table, row):
        self.events.append(BinlogEvent("DELETE", table, row, {}))


class DataBusPipeline:
    """
    数据总线管道：
    MySQL → Canal → Kafka → [Flink/Doris/ES/Redis]
    """

    def __init__(self):
        self.sinks = defaultdict(list)  # target → [(table, handler)]

    def add_sink(self, target_name, table, handler):
        """添加数据目标：如 Doris / ES / Redis"""
        self.sinks[target_name].append((table, handler))

    def process(self, event: BinlogEvent):
        """一条 binlog 事件 → 扇出到所有目标"""
        results = []
        for target, handlers in self.sinks.items():
            for table, handler in handlers:
                if event.table == table or table == "*":
                    handler(event, target)
                    results.append(target)
        return results


# 演示
canal = CanalSimulator()
pipeline = DataBusPipeline()

# 添加目标：Doris（分析）、ES（搜索）、Redis（缓存）
doris_data = []
es_data = []
redis_cache = {}

def sink_doris(event, _):
    doris_data.append(event.after)

def sink_es(event, _):
    if event.op != "DELETE":
        es_data.append(event.after)

def sink_redis(event, _):
    if event.op == "DELETE":
        redis_cache.pop(event.before.get("id"), None)
    else:
        redis_cache[event.after["id"]] = event.after

pipeline.add_sink("Doris", "orders", sink_doris)
pipeline.add_sink("ES", "orders", sink_es)
pipeline.add_sink("Redis", "orders", sink_redis)

# 模拟业务操作
canal.capture_insert("orders", {"id": 1, "user": "u1", "amount": 99.9})
canal.capture_insert("orders", {"id": 2, "user": "u2", "amount": 199.0})
canal.capture_update("orders", {"id": 1, "amount": 99.9}, {"id": 1, "amount": 129.9})
canal.capture_delete("orders", {"id": 2, "user": "u2", "amount": 199.0})

print(f"\n   Canal 捕获 {len(canal.events)} 条 binlog:")
for e in canal.events:
    print(f"     {e.op:6s} {e.table}: {e.after if e.after else e.before}")

# 扇出到各目标
for e in canal.events:
    targets = pipeline.process(e)
    print(f"     → 扇出到: {targets}")

print(f"\n   最终状态:")
print(f"     Doris (全量): {doris_data}")
print(f"     ES (可搜索):  {es_data}")
print(f"     Redis (缓存): {redis_cache}")

# ============================================================
# 面试速记卡
# ============================================================
print("\n" + "=" * 60)
print("Doris + DataBus 面试速记卡")
print("=" * 60)
print("""
  Doris 核心:
    MPP架构 = FE(主) + BE(计算+存储), 无共享
    列式存储 → 聚合查询快100x（只读需要的列）
    三种模型 → Duplicate/Unique/Aggregate
    兼容 MySQL 协议 → 直接用 MySQL 客户端！

  DataBus 核心:
    数据同步 = Canal + Kafka + 下游
    Canal 原理 → 伪装 MySQL Slave, 解析 binlog
    Binlog 三种操作 → INSERT / UPDATE / DELETE
    实时性 → 毫秒级（vs 定时任务分钟级）
    完整性 → 包含 DELETE（vs SELECT 做不到）

  典型链路:
    业务 MySQL → Canal → Kafka
                         ├→ Flink 实时计算 → Doris
                         ├→ 同步到 ES（全文搜索）
                         ├→ 同步到 Redis（热数据缓存）
                         └→ 归档到 HDFS/OSS
""")

print("✅ 大数据链路 3 模块全部通关！")
