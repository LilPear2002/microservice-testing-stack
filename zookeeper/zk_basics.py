"""
ZooKeeper 分布式协调基础

核心概念：
  Znode（节点）      ~= 文件系统中的文件/目录（可存数据 + 可有子节点）
  Ephemeral（临时）  ~= 客户端断开自动删除
  Sequential（顺序） ~= 自动追加递增序号
  Watch（监听）      ~= 一次性订阅节点变化通知
  Distributed Lock    ~= 用临时顺序节点实现的分布式锁

ZooKeeper 的数据模型：类 Unix 文件系统的树形结构
  /                          ← 根节点
  ├── /config                ← 持久节点（存配置）
  ├── /services              ← 服务发现
  │   ├── /services/order    ← 订单服务地址
  │   └── /services/payment  ← 支付服务地址
  ├── /locks                 ← 分布式锁目录
  └── /election              ← 领导选举
"""

import time
import threading
from kazoo.client import KazooClient
from kazoo.exceptions import NodeExistsError, NoNodeError
from kazoo.recipe.lock import Lock

# 连接
zk = KazooClient(hosts="localhost:2181")
zk.start()
print("✅ 连接 ZooKeeper")

BASE = "/learn"

# 清理旧数据
def cleanup():
    try:
        zk.delete(BASE, recursive=True)
    except NoNodeError:
        pass

cleanup()
zk.ensure_path(BASE)  # 确保路径存在

# ============================================================
# Phase 1: Znode 四种类型
# ============================================================
print("\n" + "=" * 60)
print("Phase 1: Znode 四种节点类型")
print("=" * 60)

# 1.1 PERSISTENT（持久节点）—— 客户端断开后还在
path = zk.create(f"{BASE}/persistent", "持久节点数据".encode())
print(f"✅ PERSISTENT:     {path}")
val, stat = zk.get(f"{BASE}/persistent")
print(f"   数据: {val.decode()} | 版本: v{stat.version}")

# 1.2 EPHEMERAL（临时节点）—— 客户端断开自动删除
path = zk.create(f"{BASE}/ephemeral", "临时节点数据".encode(), ephemeral=True)
print(f"✅ EPHEMERAL:      {path}")
print(f"   （断开连接后自动消失）")

# 1.3 PERSISTENT_SEQUENTIAL（持久顺序节点）
path = zk.create(f"{BASE}/seq-", "1".encode(), sequence=True)
print(f"✅ PERSISTENT_SEQ: {path}  ← 自动加了序号")
path = zk.create(f"{BASE}/seq-", "2".encode(), sequence=True)
print(f"✅ PERSISTENT_SEQ: {path}  ← 序号递增")

# 1.4 EPHEMERAL_SEQUENTIAL（临时顺序节点）
path = zk.create(f"{BASE}/lock-", "".encode(), ephemeral=True, sequence=True)
print(f"✅ EPHEMERAL_SEQ:  {path}  ← 分布式锁的核心！")

# 列出所有子节点
children = zk.get_children(BASE)
print(f"\n📂 {BASE} 的子节点: {children}")

# ============================================================
# Phase 2: CRUD + 版本控制
# ============================================================
print("\n" + "=" * 60)
print("Phase 2: 数据操作 & 版本控制")
print("=" * 60)

# 2.1 创建 + 获取
zk.create(f"{BASE}/config", b'{"port":8080}')
val, stat = zk.get(f"{BASE}/config")
print(f"✅ 读取: {val.decode()}")

# 2.2 更新（需传入当前版本号，乐观锁）
stat2 = zk.set(f"{BASE}/config", b'{"port":9090}', version=stat.version)
print(f"✅ 更新: 版本 v{stat.version} → v{stat2.version}")

val, _ = zk.get(f"{BASE}/config")
print(f"   新值: {val.decode()}")

# 2.3 版本冲突检测（模拟 CAS）
try:
    zk.set(f"{BASE}/config", b'{"port":8081}', version=-1)  # 强制覆盖
    val, stat = zk.get(f"{BASE}/config")
    print(f"✅ 强制覆盖(version=-1): {val.decode()} (v{stat.version})")
except Exception as e:
    print(f"❌ 覆盖失败: {e}")

# 2.4 版本冲突
try:
    zk.set(f"{BASE}/config", "conflict".encode(), version=0)  # 用旧版本号
except Exception as e:
    print(f"✅ 版本冲突拦截: version mismatch（乐观锁机制）")

# ============================================================
# Phase 3: Watch（监听机制）
# ============================================================
print("\n" + "=" * 60)
print("Phase 3: Watch — 一次性监听")
print("=" * 60)

# 创建被监听的节点
zk.create(f"{BASE}/watched", "初始值".encode())
print(f"✅ 创建节点 /learn/watched")

# 监听事件队列
events = []

@zk.DataWatch(f"{BASE}/watched")
def watch_data(data, stat, event=None):
    v = stat.version if stat else "?"
    d = data.decode() if data else "N/A"
    events.append(f"数据变更: {d}, v{v}")

# 触发变更
time.sleep(0.3)
zk.set(f"{BASE}/watched", "第一次更新".encode())
time.sleep(0.3)
zk.set(f"{BASE}/watched", "第二次更新".encode())
time.sleep(0.3)

print(f"📡 Watch 捕获的事件:")
for evt in events:
    print(f"   {evt}")
print(f"   共 {len(events)} 次变更被监听到")

# ============================================================
# Phase 4: 子节点监听 — 服务发现基础
# ============================================================
print("\n" + "=" * 60)
print("Phase 4: 子节点监听 — 服务发现")
print("=" * 60)

zk.ensure_path(f"{BASE}/services")

child_events = []

@zk.ChildrenWatch(f"{BASE}/services")
def watch_children(children):
    child_events.append(f"服务列表: {children}")

# 模拟服务上下线
time.sleep(0.3)
zk.create(f"{BASE}/services/order-svr-1", "192.168.1.10:8080".encode(), ephemeral=True)
time.sleep(0.3)
zk.create(f"{BASE}/services/order-svr-2", "192.168.1.11:8080".encode(), ephemeral=True)
time.sleep(0.3)
zk.delete(f"{BASE}/services/order-svr-1")
time.sleep(0.3)

print(f"📡 服务发现事件:")
for evt in child_events:
    print(f"   {evt}")

# ============================================================
# Phase 5: 分布式锁（Distributed Lock）
# ============================================================
print("\n" + "=" * 60)
print("Phase 5: 分布式锁")
print("=" * 60)

"""
原理：
1. 所有竞争者创建 EPHEMERAL_SEQUENTIAL 节点（如 /lock/lock-0001, /lock/lock-0002）
2. 序号最小的获得锁
3. 后面的 watch 前面一个节点
4. 锁释放（删节点）→ 下一个自动获得

这就是"排队等锁"的公平锁实现！
"""

shared_counter = {"value": 0}

def worker(name, lock_path):
    lock = Lock(zk, lock_path)
    for _ in range(5):
        with lock:  # 获取分布式锁
            current = shared_counter["value"]
            time.sleep(0.01)  # 模拟处理
            shared_counter["value"] = current + 1
            print(f"   [{name}] counter: {current} → {shared_counter['value']}")

print("🔒 两个线程竞争分布式锁（各加5次）:")
threads = []
for i in range(2):
    t = threading.Thread(target=worker, args=(f"Worker-{i+1}", f"{BASE}/counter-lock"))
    threads.append(t)
    t.start()

for t in threads:
    t.join()

print(f"✅ 最终计数: {shared_counter['value']} (期望 10, 实际 {shared_counter['value']})")

# ============================================================
# 总结
# ============================================================
print("\n" + "=" * 60)
print("ZK 四大经典应用场景:")
print("=" * 60)
print("""
  1. 配置管理    → /config/app 存储配置，所有服务 Watch 自动更新
  2. 服务发现    → /services/ 下注册临时节点，ChildrenWatch 感知上下线
  3. 分布式锁    → EPHEMERAL_SEQUENTIAL 排队，公平锁
  4. 领导选举    → 同分布式锁，序号最小的当 Leader
""")

# 清理 + 断开
cleanup()
zk.stop()
print("✅ ZooKeeper 5 阶段通关，连接已关闭")
