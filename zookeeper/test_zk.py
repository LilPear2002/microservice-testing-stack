"""
ZooKeeper pytest 测试
覆盖：连接 / CRUD / 临时节点 / 顺序节点 / 版本控制 / Watch / 分布式锁
"""
import time
import threading

import pytest
from kazoo.client import KazooClient
from kazoo.exceptions import NodeExistsError, NoNodeError, BadVersionError
from kazoo.recipe.lock import Lock

TEST_BASE = "/test-learn"


@pytest.fixture(scope="module")
def zk():
    """模块级 fixture：创建连接 + 清理"""
    client = KazooClient(hosts="localhost:2181")
    client.start()
    client.ensure_path(TEST_BASE)
    yield client
    # 清理
    try:
        client.delete(TEST_BASE, recursive=True)
    except NoNodeError:
        pass
    client.stop()


# ============================================================
# 1. 连接测试
# ============================================================
class TestConnection:
    """连接状态"""

    def test_connected(self, zk):
        """连接后状态应为 CONNECTED"""
        assert zk.state == "CONNECTED"

    def test_server_version(self, zk):
        """能获取服务器信息（envi 命令在 3.9 可能被禁用，退而验证连接）"""
        # ZK 3.9 默认禁用四字命令，改为验证根节点操作
        zk.ensure_path(f"{TEST_BASE}/version-check-tmp")
        assert zk.exists(f"{TEST_BASE}/version-check-tmp") is not None


# ============================================================
# 2. 节点 CRUD
# ============================================================
class TestCRUD:
    """节点的增删改查"""

    def test_create_and_get(self, zk):
        """创建节点并读取"""
        path = f"{TEST_BASE}/crud-test"
        zk.create(path, "hello".encode())
        data, stat = zk.get(path)
        assert data.decode() == "hello"
        zk.delete(path)

    def test_set_and_get(self, zk):
        """更新节点数据"""
        path = f"{TEST_BASE}/set-test"
        zk.create(path, "v1".encode())
        zk.set(path, "v2".encode())
        data, _ = zk.get(path)
        assert data.decode() == "v2"
        zk.delete(path)

    def test_delete(self, zk):
        """删除节点后不存在"""
        path = f"{TEST_BASE}/del-test"
        zk.create(path, "x".encode())
        zk.delete(path)
        assert not zk.exists(path)

    def test_duplicate_create(self, zk):
        """重复创建抛 NodeExistsError"""
        path = f"{TEST_BASE}/dup-test"
        zk.create(path, "x".encode())
        with pytest.raises(NodeExistsError):
            zk.create(path, "y".encode())
        zk.delete(path)

    def test_get_nonexistent(self, zk):
        """读取不存在的节点抛 NoNodeError"""
        with pytest.raises(NoNodeError):
            zk.get(f"{TEST_BASE}/no-such-node")

    def test_exists_false(self, zk):
        """exists 对不存在的节点返回 None"""
        assert zk.exists(f"{TEST_BASE}/no-such-node") is None


# ============================================================
# 3. 临时节点
# ============================================================
class TestEphemeral:
    """临时节点特性"""

    def test_ephemeral_exists(self, zk):
        """临时节点在当前会话中存在"""
        path = f"{TEST_BASE}/ephemeral-test"
        zk.create(path, "ephem".encode(), ephemeral=True)
        assert zk.exists(path) is not None
        zk.delete(path)

    def test_ephemeral_disappears(self, zk):
        """新建会话的临时节点在原会话断开后消失（模拟）"""
        # 用第二个客户端创建临时节点然后断开
        zk2 = KazooClient(hosts="localhost:2181")
        zk2.start()
        path = f"{TEST_BASE}/ephemeral-disappear"
        zk2.create(path, "tmp".encode(), ephemeral=True)
        assert zk.exists(path) is not None  # 主客户端可见
        zk2.stop()
        time.sleep(1)
        # 第二个客户端断开后，临时节点应该消失
        assert zk.exists(path) is None


# ============================================================
# 4. 顺序节点
# ============================================================
class TestSequential:
    """顺序节点自动递增"""

    def test_sequential_auto_increment(self, zk):
        """顺序节点序号自动递增"""
        p1 = zk.create(f"{TEST_BASE}/seq-", "a".encode(), sequence=True)
        p2 = zk.create(f"{TEST_BASE}/seq-", "b".encode(), sequence=True)
        p3 = zk.create(f"{TEST_BASE}/seq-", "c".encode(), sequence=True)

        # 提取序号
        def extract_seq(path):
            return int(path.split("-")[-1])

        s1, s2, s3 = extract_seq(p1), extract_seq(p2), extract_seq(p3)
        assert s1 < s2 < s3, f"序号应递增: {s1} < {s2} < {s3}"

        zk.delete(p1)
        zk.delete(p2)
        zk.delete(p3)


# ============================================================
# 5. 版本控制（乐观锁）
# ============================================================
class TestVersionControl:
    """CAS 乐观锁"""

    def test_version_mismatch(self, zk):
        """用旧版本号更新抛 BadVersionError"""
        path = f"{TEST_BASE}/version-test"
        zk.create(path, "v0".encode())
        data, stat = zk.get(path)
        # 用正确版本更新
        zk.set(path, "v1".encode(), version=stat.version)
        # 用旧版本号再更新 → 失败
        with pytest.raises(BadVersionError):
            zk.set(path, "v2".encode(), version=0)
        zk.delete(path)


# ============================================================
# 6. Watch 监听
# ============================================================
class TestWatch:
    """数据变更监听"""

    def test_data_watch(self, zk):
        """DataWatch 能捕获数据变更"""
        path = f"{TEST_BASE}/watch-test"
        zk.create(path, "init".encode())

        events = []

        @zk.DataWatch(path)
        def watcher(data, stat, event=None):
            d = data.decode() if data else "N/A"
            events.append(d)

        time.sleep(0.2)
        zk.set(path, "change1".encode())
        time.sleep(0.3)
        zk.set(path, "change2".encode())
        time.sleep(0.3)

        assert len(events) >= 3, f"应至少3次事件（init+2次变更），实际: {events}"
        assert "init" in events
        assert "change1" in events
        assert "change2" in events

        zk.delete(path)

    def test_children_watch(self, zk):
        """ChildrenWatch 能捕获子节点变更"""
        path = f"{TEST_BASE}/children-watch"
        zk.ensure_path(path)

        events = []

        @zk.ChildrenWatch(path)
        def watcher(children):
            events.append(sorted(children))

        time.sleep(0.2)
        zk.create(f"{path}/svc-a", "a".encode(), ephemeral=True)
        time.sleep(0.3)
        zk.create(f"{path}/svc-b", "b".encode(), ephemeral=True)
        time.sleep(0.3)
        zk.delete(f"{path}/svc-a")
        time.sleep(0.3)

        assert len(events) >= 3
        assert events[0] == []  # 初始空
        assert events[1] == ["svc-a"]
        assert "svc-a" in str(events[2]) and "svc-b" in str(events[2])

        try:
            zk.delete(path, recursive=True)
        except:
            pass


# ============================================================
# 7. 分布式锁
# ============================================================
class TestDistributedLock:
    """分布式锁并发安全"""

    def test_lock_prevents_race_condition(self, zk):
        """分布式锁保证计数器并发安全"""
        lock_path = f"{TEST_BASE}/lock-test"
        counter = {"value": 0}
        errors = []

        def increment(name):
            lock = Lock(zk, lock_path)
            for _ in range(10):
                try:
                    with lock:
                        current = counter["value"]
                        time.sleep(0.005)  # 放大竞态窗口
                        counter["value"] = current + 1
                except Exception as e:
                    errors.append(str(e))

        threads = []
        for i in range(3):
            t = threading.Thread(target=increment, args=(f"t{i}",))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0, f"锁操作异常: {errors}"
        assert counter["value"] == 30, f"3线程×10次=30, 实际: {counter['value']}"


# ============================================================
# 8. 边界条件
# ============================================================
class TestEdgeCases:
    """边界情况"""

    def test_empty_data(self, zk):
        """空数据节点"""
        path = f"{TEST_BASE}/empty"
        zk.create(path, "".encode())
        data, _ = zk.get(path)
        assert data == b""
        zk.delete(path)

    def test_large_data(self, zk):
        """较大数据（接近 1MB 但 ZK 限制约 1MB，这里测 10KB）"""
        path = f"{TEST_BASE}/large"
        big = "x" * 10240  # 10KB
        zk.create(path, big.encode())
        data, _ = zk.get(path)
        assert len(data) == 10240
        zk.delete(path)
