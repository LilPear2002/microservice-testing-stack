"""
Apache Flink 流计算 —— 核心概念学习

Flink = 有状态的分布式流处理引擎
  核心能力：实时处理无限数据流，毫秒级延迟
  对比 Spark Streaming：Flink 是"真流"，Spark 是"微批"

⚠️ Flink 是 Java/Scala 引擎，2C2G 机器跑不动
  本文件用 Python 模拟核心概念：DataStream / Window / Watermark / Checkpoint

核心概念：
  DataStream  → 无限数据流（Kafka Topic 那样的）
  Operator    → 对流做变换（map/filter/keyBy/window）
  Window      → 把无限流切成有限窗口（Tumbling/Sliding/Session）
  Watermark   → 处理乱序数据的"水位线"
  Checkpoint  → 状态快照，故障恢复
  Exactly-Once → 精确一次语义
"""

import time
import random
import json
from collections import defaultdict
from dataclasses import dataclass, field
from typing import List, Callable, Dict


# ============================================================
# Phase 1: DataStream API 模拟
# ============================================================
@dataclass
class Event:
    """模拟一条数据流事件"""
    user_id: str
    action: str       # click / purchase / login
    amount: float = 0
    timestamp: float = field(default_factory=time.time)


class DataStream:
    """
    模拟 Flink DataStream
    核心操作：map / filter / keyBy / window / sink
    """

    def __init__(self, events: List[Event]):
        self.events = list(events)

    def filter(self, fn: Callable) -> "DataStream":
        """过滤（类似 SQL WHERE）"""
        self.events = [e for e in self.events if fn(e)]
        return self

    def map(self, fn: Callable) -> "DataStream":
        """转换（类似 SELECT expr）"""
        self.events = [fn(e) for e in self.events]
        return self

    def key_by(self, fn: Callable) -> Dict:
        """分组（类似 GROUP BY key）"""
        groups = defaultdict(list)
        for e in self.events:
            key = fn(e)
            groups[key].append(e)
        return dict(groups)


# ============================================================
# Phase 2: 窗口（Window）
# ============================================================
class TumblingWindow:
    """
    滚动窗口（Tumbling Window）
    固定大小，无重叠
    |──W1──|──W2──|──W3──|
    特点：每个事件只属于一个窗口
    用途：每分钟 UV 统计、每 5 秒交易额
    """

    def __init__(self, size_seconds: float):
        self.size = size_seconds

    def assign(self, events: List[Event]) -> Dict[int, List[Event]]:
        windows = defaultdict(list)
        base = min(e.timestamp for e in events) if events else 0
        for e in events:
            bucket = int((e.timestamp - base) / self.size)
            windows[bucket].append(e)
        return dict(windows)


class SlidingWindow:
    """
    滑动窗口（Sliding Window）
    大小和滑动步长独立
    |══W1══|
       |══W2══|
          |══W3══|
    特点：事件可属于多个窗口
    用途：最近 5 分钟每 1 分钟的统计（滑动去重）
    """

    def __init__(self, size_seconds: float, slide_seconds: float):
        self.size = size_seconds
        self.slide = slide_seconds

    def assign(self, events: List[Event]) -> Dict[int, List[Event]]:
        windows = defaultdict(list)
        base = min(e.timestamp for e in events) if events else 0
        for e in events:
            # 计算该事件所属的所有窗口
            start_bucket = int((e.timestamp - base - self.size + self.slide) / self.slide)
            end_bucket = int((e.timestamp - base) / self.slide)
            for b in range(max(0, start_bucket), end_bucket + 1):
                windows[b].append(e)
        return dict(windows)


# ============================================================
# Phase 3: Watermark（水位线）
# ============================================================
class WatermarkGenerator:
    """
    水位线（Watermark）
    问题：分布式环境下事件到达顺序乱序
      事件时间:  t1  t2  t3
      到达顺序:  t3  t1  t2  ← 乱序！
    
    水位线策略：允许延迟 N 秒
      当前水位线 = max(已到达事件时间) - allowed_lateness
      窗口在水位线超过窗口结束时触发计算
    """

    def __init__(self, allowed_lateness=2.0):
        self.allowed_lateness = allowed_lateness
        self.max_timestamp = 0

    def update(self, event_time: float) -> float:
        """更新水位线"""
        self.max_timestamp = max(self.max_timestamp, event_time)
        return self.max_timestamp - self.allowed_lateness

    def should_fire_window(self, window_end: float, watermark: float) -> bool:
        """水位线超过窗口结束时间 → 触发窗口计算"""
        return watermark >= window_end


# ============================================================
# Phase 4: Checkpoint & Exactly-Once
# ============================================================
class StateBackend:
    """
    状态后端 & Checkpoint
    Flink 的 Exactly-Once 依赖：
      1. Checkpoint（状态快照）
      2. 可重放 Source（Kafka offset）
      3. 事务性 Sink（两阶段提交）
    """

    def __init__(self):
        self.state: Dict[str, float] = defaultdict(float)  # key → value
        self.checkpoints: List[Dict] = []

    def update(self, key: str, value: float):
        self.state[key] += value

    def checkpoint(self) -> int:
        """保存快照，返回 checkpoint ID"""
        snapshot = dict(self.state)
        checkpoint_id = len(self.checkpoints)
        self.checkpoints.append(snapshot)
        return checkpoint_id

    def restore(self, checkpoint_id: int):
        """从快照恢复"""
        if checkpoint_id < len(self.checkpoints):
            self.state = defaultdict(float, self.checkpoints[checkpoint_id])


# ============================================================
# 演示
# ============================================================
def demo():
    # ─── 模拟事件流 ──────────────────────
    print("=" * 60)
    print("D1: Flink 流计算 核心概念")
    print("=" * 60)

    base = time.time()
    events = [
        Event("u1", "click", 0, base + 0.0),
        Event("u2", "click", 0, base + 0.3),
        Event("u1", "purchase", 99.9, base + 0.5),
        Event("u3", "click", 0, base + 0.7),
        Event("u1", "click", 0, base + 1.0),
        Event("u2", "purchase", 199.0, base + 1.2),
        Event("u3", "purchase", 49.9, base + 1.5),
        Event("u1", "purchase", 29.9, base + 2.0),
    ]

    # Phase 1: DataStream 操作
    print("\n📊 Phase 1: DataStream 操作")
    print("   原始事件:", len(events), "条")

    ds = DataStream(events)
    purchases = ds.filter(lambda e: e.action == "purchase")
    print(f"   filter(action='purchase'): {len(purchases.events)} 条")

    # 按用户分组统计
    groups = ds.key_by(lambda e: e.user_id)
    print("   keyBy(user_id):")
    for user, evts in groups.items():
        total = sum(e.amount for e in evts if e.action == "purchase")
        print(f"     {user}: {len(evts)} 事件, 购买金额 ¥{total}")

    # Phase 2: 滚动窗口
    print("\n📊 Phase 2: Tumbling Window（滚动窗口 1s）")
    tw = TumblingWindow(size_seconds=1.0)
    tumbling = tw.assign(events)
    for bucket, evts in sorted(tumbling.items()):
        total = sum(e.amount for e in evts)
        print(f"   Window {bucket}: {len(evts)} 事件, 金额 ¥{total}")

    # 滑动窗口
    print("\n📊 Phase 2b: Sliding Window（滑动 2s, 步长 1s）")
    sw = SlidingWindow(size_seconds=2.0, slide_seconds=1.0)
    sliding = sw.assign(events)
    for bucket, evts in sorted(sliding.items()):
        users = {e.user_id for e in evts}
        print(f"   Window {bucket}: {len(evts)} 事件, {len(users)} 独立用户")

    # Phase 3: Watermark
    print("\n📊 Phase 3: Watermark（水位线，允许 0.5s 延迟）")
    wm = WatermarkGenerator(allowed_lateness=0.5)

    # 模拟乱序到达
    out_of_order = [
        (base + 0.5, "event A"),  # 先到
        (base + 0.1, "event B"),  # 晚到（乱序！）
        (base + 0.8, "event C"),
        (base + 0.3, "event D"),  # 乱序
    ]

    for ts, name in out_of_order:
        watermark = wm.update(ts)
        print(f"   到达: {name}(t={ts-base:.1f}s) → 水位线={watermark-base:.1f}s")

    # Phase 4: Checkpoint & Exactly-Once
    print("\n📊 Phase 4: Checkpoint & Exactly-Once")
    state = StateBackend()

    # 处理事件
    for e in events[:4]:
        state.update(e.user_id, e.amount)
    print(f"   处理后状态: {dict(state.state)}")

    # 故障前保存 Checkpoint
    ck_id = state.checkpoint()
    print(f"   ✅ Checkpoint {ck_id} 保存: {state.checkpoints[ck_id]}")

    # 继续处理
    for e in events[4:6]:
        state.update(e.user_id, e.amount)
    print(f"   继续处理后: {dict(state.state)}")

    # 💥 模拟故障，恢复！
    state.restore(ck_id)
    print(f"   🔄 从 Checkpoint {ck_id} 恢复: {dict(state.state)}")
    print(f"   （丢失了 events[4:6] 的处理结果，但不会重复计算！）")

    # Phase 5: 面试架构速记
    print("\n" + "=" * 60)
    print("Flink 面试速记卡")
    print("=" * 60)
    print("""
  Flink Job = Source → Transform → Sink
              ↑ Kafka     ↑ map       ↑ MySQL
                           ↑ filter    ↑ Redis
                           ↑ keyBy     ↑ Kafka
                           ↑ window
                           ↑ aggregate

  Watermark = max(event_time) - allowed_lateness
           → 解决乱序：水位线不到不关窗

  Checkpoint = 分布式快照（Chandy-Lamport 算法）
            → 故障恢复 Exactly-Once

  Savepoint  = 手动触发 Checkpoint
            → 版本升级 / 暂停恢复

  Window 三种:
    Tumbling  |──|──|──|     固定大小，不重叠
    Sliding   |══|══|══|     固定大小，可重叠  
    Session   |─|  |──|     按活动间隔动态分
""")


if __name__ == "__main__":
    demo()
