# 🦍 ZooKeeper 分布式协调

## 学习时间
2026-05-15

## 什么是 ZooKeeper？

```
ZooKeeper = 分布式系统的"协调员"

四大经典场景：
  1. 配置管理    → 所有服务 Watch /config，改一处全部生效
  2. 服务发现    → /services/ 注册临时节点，上下线自动感知
  3. 分布式锁    → 临时顺序节点排队，公平锁
  4. 领导选举    → 同分布式锁，序号最小 = Leader
```

### 数据模型

```
类 Unix 文件系统：
  /                          ← 根节点
  ├── /config                ← 持久节点（存配置 JSON）
  │   ├── /config/app        ← 具体配置
  │   └── /config/db
  ├── /services              ← 服务发现
  │   ├── /services/order-1  ← 临时节点（断连自动删除）
  │   └── /services/order-2
  └── /locks                 ← 分布式锁
      ├── /locks/lock-0001   ← 临时顺序节点
      └── /locks/lock-0002

每个 Znode 可以：
  - 存储数据（默认上限 1MB）
  - 拥有子节点
  - 触发 Watch 通知
```

### 四种节点类型

| 类型 | 创建方式 | 生命周期 | 用途 |
|------|----------|----------|------|
| **PERSISTENT** | 默认 | 手动删除才消失 | 配置存储 |
| **EPHEMERAL** | `ephemeral=True` | 客户端断开自动删除 | 服务注册、心跳 |
| **PERSISTENT_SEQUENTIAL** | `sequence=True` | 手动删除才消失 | 唯一 ID 生成 |
| **EPHEMERAL_SEQUENTIAL** | 两个都 True | 断连删除，序号递增 | **分布式锁**、**领导选举** |

## 环境配置

```bash
# 启动 ZooKeeper（256MB 限制，93MB 实际占用）
docker run -d --name zk-learn \
  -p 2181:2181 \
  -e ZOO_MY_ID=1 \
  -e ZOO_SERVERS="server.1=0.0.0.0:2888:3888;2181" \
  --memory=256m \
  zookeeper:3.9

# Python 客户端
uv venv --python 3.11
source .venv/bin/activate
uv pip install kazoo pytest -i https://mirrors.aliyun.com/pypi/simple/
```

## 5 大阶段实操

### Phase 1: 四种 Znode

```python
from kazoo.client import KazooClient
zk = KazooClient(hosts="localhost:2181")
zk.start()

# PERSISTENT — 持久节点
zk.create("/app/config", b'{"port":8080}')

# EPHEMERAL — 临时节点（断连自动删除）
zk.create("/services/order-1", b"192.168.1.10:8080", ephemeral=True)

# PERSISTENT_SEQUENTIAL — 持久顺序
zk.create("/ids/user-", b"", sequence=True)   # → /ids/user-0000000001
zk.create("/ids/user-", b"", sequence=True)   # → /ids/user-0000000002

# EPHEMERAL_SEQUENTIAL — 临时顺序（分布式锁核心）
zk.create("/locks/lock-", b"", ephemeral=True, sequence=True)
# → /locks/lock-0000000003
```

### Phase 2: CRUD + 乐观锁

```python
# 创建
zk.create("/data", b"v0")
val, stat = zk.get("/data")     # stat.version = 0

# 更新（需要当前版本号）
stat2 = zk.set("/data", b"v1", version=0)   # ✅ stat2.version = 1

# 版本冲突检测
zk.set("/data", b"v2", version=0)           # ❌ BadVersionError
zk.set("/data", b"v2", version=-1)          # ✅ -1 = 强制覆盖
```

### Phase 3: DataWatch 数据监听

```python
@zk.DataWatch("/config")
def on_config_change(data, stat, event=None):
    print(f"配置变更: {data.decode()}")

zk.set("/config", b'{"port":9090}')  # → 自动触发 on_config_change
```

> **特点**：Watch 是一次性的！触发后需重新注册。但 kazoo 的 `DataWatch` 封装了自动重注册。

### Phase 4: ChildrenWatch 服务发现

```python
@zk.ChildrenWatch("/services")
def on_service_change(children):
    print(f"服务列表: {children}")

# 服务上下线自动感知
zk.create("/services/svr-1", b"...", ephemeral=True)  # → on_service_change
zk.create("/services/svr-2", b"...", ephemeral=True)  # → on_service_change
zk.delete("/services/svr-1")                           # → on_service_change
```

### Phase 5: 分布式锁

```python
from kazoo.recipe.lock import Lock

lock = Lock(zk, "/locks/counter")
with lock:
    # 临界区：同一时刻只有1个客户端执行
    counter.value += 1
```

**原理**：所有竞争者创建 `EPHEMERAL_SEQUENTIAL` 节点，序号最小的获得锁，后面的 Watch 前一个。锁释放 → 序号次小的自动获得。这就是公平的排队锁！

## 测试结果

```bash
$ pytest test_zk.py -v
============================= 17 passed in 3.24s ==============================

测试覆盖:
  ✅ 连接 (2):      状态 / 操作验证
  ✅ CRUD (6):      创建读取 / 更新 / 删除 / 重复创建 / 不存在节点 / exists
  ✅ 临时节点 (2):   存在 / 断连消失
  ✅ 顺序节点 (1):   自动递增
  ✅ 版本控制 (1):   冲突拦截（乐观锁）
  ✅ Watch (2):     数据变更 / 子节点变更（服务发现）
  ✅ 分布式锁 (1):   3线程×10次=30，无竞态
  ✅ 边界 (2):      空数据 / 10KB 大数据
```

## 面试话术

> **Q**: ZooKeeper 怎么实现分布式锁？
> **A**: 所有竞争者在同一路径下创建**临时顺序节点**（EPHEMERAL_SEQUENTIAL），ZK 自动分配递增序号。序号最小的获得锁，后面的 Watch 前一个节点。锁持有者断开 → 临时节点自动删除 → ZK 通知下一个节点获得锁。这是一个**公平锁**，先来先得。

> **Q**: 为什么用临时节点？
> **A**: 临时节点与客户端会话绑定。客户端崩溃/断连后，ZK 检测到 session 超时，自动删除临时节点。这样不会出现死锁——即使用了分布式锁的客户端挂了，锁也会自动释放。

> **Q**: ZooKeeper vs etcd？
> **A**: 都是 CP 分布式协调系统（一致性 > 可用性）。ZK 更老牌（Hadoop 生态）、Java 编写、API 更底层。etcd（K8s 用）更现代、Go 编写、gRPC API、更好用。概念相通：etcd 的 key-value 对应 ZK 的 znode，etcd 的 lease + Watch 对应 ZK 的 ephemeral + Watch。

> **Q**: ZK 的 Watch 机制特点？
> **A**: 一次性触发，触发后需重新注册。但客户端库（如 kazoo）通常封装了自动重注册。Watch 保证在变更和通知之间不会丢失中间状态——要么看到旧状态，要么看到新状态。

## 关键踩坑

1. **ZK 3.9 默认禁用四字命令**：`ruok`、`envi` 等需要配置白名单，学习用客户端 API 代替。
2. **DataWatch 回调签名**：新 kazoo 版本先尝试 3 参数 `(data, stat, event)`，失败回退 2 参数。
3. **版本号从 0 开始**：`stat.version` 初始为 0，每次 set 成功 +1。
4. **`version=-1` 强制覆盖**：跳过乐观锁检查。

## 下一步
- C1: Nacos 注册配置中心
- C2: Gateway 网关
- D1~D3: 大数据链路
