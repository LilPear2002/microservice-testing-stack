"""
大数据链路 pytest 测试
覆盖：Flink Window/Watermark/Checkpoint, Doris Aggregate, DataBus CDC
"""
import sys
sys.path.insert(0, "/workspace/bigdata")

import pytest
from flink_concepts import (
    Event, DataStream, TumblingWindow, SlidingWindow,
    WatermarkGenerator, StateBackend
)


# ============================================================
# Flink: DataStream
# ============================================================
class TestDataStream:
    """DataStream 操作"""

    def test_filter(self):
        events = [
            Event("u1", "click"),
            Event("u1", "purchase", 99.9),
            Event("u2", "click"),
        ]
        ds = DataStream(events)
        purchases = ds.filter(lambda e: e.action == "purchase")
        assert len(purchases.events) == 1
        assert purchases.events[0].amount == 99.9

    def test_map(self):
        events = [Event("u1", "purchase", 99.9)]
        ds = DataStream(events)
        amounts = ds.map(lambda e: e.amount)
        assert amounts.events == [99.9]

    def test_key_by(self):
        events = [
            Event("u1", "purchase", 10),
            Event("u1", "purchase", 20),
            Event("u2", "purchase", 30),
        ]
        ds = DataStream(events)
        groups = ds.key_by(lambda e: e.user_id)
        assert len(groups["u1"]) == 2
        assert len(groups["u2"]) == 1

    def test_filter_empty(self):
        ds = DataStream([])
        result = ds.filter(lambda e: True)
        assert result.events == []


# ============================================================
# Flink: Window
# ============================================================
class TestWindows:
    """窗口函数"""

    def test_tumbling_window(self):
        events = [
            Event("u1", "purchase", 10, 0.0),
            Event("u2", "purchase", 20, 0.3),
            Event("u1", "purchase", 30, 1.2),  # 第二个窗口
        ]
        tw = TumblingWindow(size_seconds=1.0)
        windows = tw.assign(events)
        assert len(windows) == 2  # 两个窗口
        assert len(windows[0]) == 2  # 第一个窗口 2 条
        assert len(windows[1]) == 1  # 第二个窗口 1 条

    def test_sliding_window(self):
        events = [
            Event("u1", "purchase", 10, 0.0),
            Event("u2", "purchase", 20, 0.5),
            Event("u1", "purchase", 30, 1.5),
        ]
        sw = SlidingWindow(size_seconds=2.0, slide_seconds=1.0)
        windows = sw.assign(events)
        # 事件 0.0 和 0.5 属于多个窗口
        assert len(windows) >= 2  # 至少 2 个窗口

    def test_window_total_amount(self):
        """窗口内金额求和"""
        events = [
            Event("u1", "purchase", 10, 0.0),
            Event("u2", "purchase", 20, 0.3),
            Event("u1", "purchase", 30, 0.6),
        ]
        tw = TumblingWindow(size_seconds=1.0)
        windows = tw.assign(events)
        assert len(windows) == 1  # 所有事件在同一个 1s 窗口
        total = sum(e.amount for e in windows[0])
        assert total == 60


# ============================================================
# Flink: Watermark
# ============================================================
class TestWatermark:
    """水位线"""

    def test_watermark_basic(self):
        wm = WatermarkGenerator(allowed_lateness=2.0)
        wm.update(10.0)
        assert wm.update(12.0) == 10.0  # 12 - 2
        assert wm.update(5.0) == 10.0   # 乱序事件不移动水位线

    def test_should_fire(self):
        wm = WatermarkGenerator(allowed_lateness=1.0)
        watermark = wm.update(10.0)  # watermark = 9.0
        assert wm.should_fire_window(8.0, watermark) is True
        assert wm.should_fire_window(9.5, watermark) is False


# ============================================================
# Flink: Checkpoint
# ============================================================
class TestCheckpoint:
    """Checkpoint 与状态恢复"""

    def test_checkpoint_and_restore(self):
        state = StateBackend()
        state.update("u1", 100)
        state.update("u2", 200)
        ck_id = state.checkpoint()

        # 继续处理
        state.update("u1", 50)
        state.update("u3", 300)

        # 恢复到 checkpoint
        state.restore(ck_id)
        assert state.state["u1"] == 100  # 恢复后的值
        assert state.state["u2"] == 200
        assert state.state["u3"] == 0    # u3 丢失

    def test_checkpoint_id_increment(self):
        state = StateBackend()
        assert state.checkpoint() == 0
        assert state.checkpoint() == 1
        assert state.checkpoint() == 2


# ============================================================
# Doris: Aggregate 模型（从 doris_databus.py）
# ============================================================
class TestDorisAggregate:
    """Doris Aggregate 数据模型"""

    def test_aggregate_merge(self):
        from doris_databus import AggregateTable
        table = AggregateTable()
        table.insert("2026-01-01", "杭州", 100)
        table.insert("2026-01-01", "杭州", 200)
        results = table.query(date="2026-01-01")
        assert len(results) == 1
        assert results[0]["amount"] == 300  # 自动聚合

    def test_aggregate_multi_city(self):
        from doris_databus import AggregateTable
        table = AggregateTable()
        table.insert("2026-01-01", "杭州", 100)
        table.insert("2026-01-01", "北京", 50)
        results = table.query()
        cities = {r["city"] for r in results}
        assert cities == {"杭州", "北京"}

    def test_aggregate_empty(self):
        from doris_databus import AggregateTable
        table = AggregateTable()
        assert table.query() == []


# ============================================================
# DataBus: CDC
# ============================================================
class TestDataBus:
    """CDC 数据同步管道"""

    def test_canal_capture_insert(self):
        from doris_databus import CanalSimulator
        canal = CanalSimulator()
        canal.capture_insert("users", {"id": 1, "name": "张三"})
        assert len(canal.events) == 1
        assert canal.events[0].op == "INSERT"
        assert canal.events[0].after["name"] == "张三"

    def test_canal_capture_delete(self):
        from doris_databus import CanalSimulator
        canal = CanalSimulator()
        canal.capture_delete("users", {"id": 1})
        assert canal.events[0].op == "DELETE"
        assert canal.events[0].after == {}

    def test_pipeline_fanout(self):
        from doris_databus import (
            CanalSimulator, DataBusPipeline,
            sink_doris, sink_es, sink_redis
        )
        import doris_databus as dd

        canal = CanalSimulator()
        pipeline = DataBusPipeline()
        pipeline.add_sink("Doris", "orders", sink_doris)
        pipeline.add_sink("ES", "orders", sink_es)
        pipeline.add_sink("Redis", "orders", sink_redis)

        canal.capture_insert("orders", {"id": 1, "amount": 99.9})
        targets = pipeline.process(canal.events[0])
        assert len(targets) == 3  # 扇出到 3 个目标
        assert "Doris" in targets
        assert "ES" in targets
        assert "Redis" in targets

    def test_pipeline_filter_by_table(self):
        from doris_databus import CanalSimulator, DataBusPipeline
        canal = CanalSimulator()
        pipeline = DataBusPipeline()

        results = []
        pipeline.add_sink("Doris", "orders", lambda e, t: results.append(t))

        canal.capture_insert("orders", {"id": 1})
        canal.capture_insert("users", {"id": 2})  # 不同表

        targets_orders = pipeline.process(canal.events[0])
        targets_users = pipeline.process(canal.events[1])

        assert len(targets_orders) == 1  # 匹配 orders 表
        assert targets_users == []       # 不匹配，不处理
