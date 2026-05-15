# 🚀 大数据链路（D1-D3）

## 学习时间
2026-05-15

## ⚠️ 全概念学习
Flink / Doris / DataBus 均为分布式系统，2C2G 机器无法运行。本模块用 Python 模拟 + 架构图 + 面试话术学习。

---

## D1: Apache Flink — 流计算引擎

### 一句话
```Flink = 有状态的分布式流处理引擎```

### 核心架构

```
Flink Job = Source → Transform → Sink
              ↑ Kafka         ↑ map/filter    ↑ MySQL
              ↑ MySQL         ↑ keyBy/window  ↑ Redis
                              ↑ aggregate     ↑ Kafka

真正流处理（vs Spark Streaming 微批）
事件来一条处理一条，毫秒级延迟
```

### 三大窗口

| 窗口 | 图示 | 特点 |
|------|------|------|
| **Tumbling**（滚动） | \|---\|---\|---\| | 固定大小，不重叠 |
| **Sliding**（滑动） | \|══\|══\|══\| | 大小+步长，可重叠 |
| **Session**（会话） | \|- \|   \|--\| | 按活动间隔动态 |

### Watermark（水位线）

```
问题：分布式环境事件到达乱序
  事件时间: t1  t2  t3
  到达顺序: t3  t1  t2  ← 乱序！

水位线 = max(已到达事件时间) - allowed_lateness
窗口关闭条件：watermark >= window_end
```

### Exactly-Once 三步

```
1. Checkpoint → 状态快照（Chandy-Lamport 算法）
2. 可重放 Source → Kafka offset 回退
3. 事务性 Sink → 两阶段提交（2PC）
```

---

## D2: Apache Doris — MPP 分析型数据库

### 一句话
```Doris = 列式存储 + MPP 并行 + MySQL 兼容```

### 架构

```
MySQL 协议 ← 直接用 MySQL 客户端连接！
    │
┌───▼──────────────┐
│  FE（Frontend）  │ ← SQL 解析、执行计划、元数据
│  多 FE 主从       │
└──┬──────┬──────┬─┘
   │      │      │
┌──▼──┐ ┌▼───┐ ┌▼───┐
│BE#1 │ │BE#2│ │BE#3│ ← 存储 + 计算在同一个节点
│分片1│ │分片2│ │分片3│   每个 BE 处理本地分片数据
└─────┘ └────┘ └────┘   查询时并行计算 → FE 汇总
```

### 列式存储优势

```
行式存储（MySQL）:
  [u1,杭州,99.9] [u2,北京,199.0] [u1,杭州,49.9]
  查 SUM(amount) → 扫描所有行，读全部字段

列式存储（Doris）:
  user:  [u1, u2, u1]
  city:  [杭州,北京,杭州]
  amount:[99.9, 199.0, 49.9]  ← 只读这列！
  查 SUM(amount) → 只读 amount 列，快 10~100x
```

### 三种数据模型

| 模型 | 特点 | 适用场景 |
|------|------|----------|
| **Duplicate** | 保留所有原始数据 | 日志、事件流水 |
| **Unique** | 主键唯一，新覆盖旧 | 用户画像、订单状态 |
| **Aggregate** | 写入时自动 SUM/MAX/MIN | 报表、指标汇总 |

---

## D3: DataBus — CDC 数据总线

### 一句话
```DataBus = Canal + Kafka + 下游（把你的 MySQL 数据实时同步到任何地方）```

### 核心链路

```
业务 MySQL → Canal → Kafka
  (binlog)    (解析)   (消息队列)
                          ├→ Flink → Doris（实时计算+分析）
                          ├→ ES（全文搜索）
                          ├→ Redis（热数据缓存）
                          └→ HDFS/OSS（归档）
```

### Canal 原理

```
Canal 把自己伪装成 MySQL Slave:
  MySQL Master ──binlog──→ Canal（伪 Slave）
                              │
                              ├ 解析 binlog → JSON
                              └ → Kafka Topic

为什么不用定时 SELECT？
  ❌ 无法感知 DELETE
  ❌ 对业务库有查询压力  
  ❌ 延迟：定时 1 分钟 = 最差 1 分钟
  ✅ Binlog：实时、完整、零业务压力
```

### CDC 事件类型

```json
{"op":"INSERT", "after":{"id":1, "name":"张三"}}
{"op":"UPDATE", "before":{"id":1, "name":"张三"}, "after":{"id":1, "name":"张三三"}}
{"op":"DELETE", "before":{"id":1, "name":"张三三"}, "after":{}}
```

---

## 测试结果

```bash
$ pytest test_bigdata.py -v
============================= 18 passed in 0.03s ==============================

Flink (10):  filter / map / keyBy / 空filter / 滚动窗 / 滑动窗 / 窗聚合 / 水位线 / 触发判断 / checkpoint恢复 / ID递增
Doris (3):   聚合合并 / 多城市 / 空表
DataBus (5): INSERT捕获 / DELETE捕获 / 扇出 / 表过滤 / 全链路
```

## 面试话术

### Flink

> **Q**: Flink 怎么保证 Exactly-Once？
> **A**: 三步：Checkpoint（定期快照状态）→ 可重放 Source（Kafka offset 回退）→ 事务性 Sink（两阶段提交）。故障时从最近 Checkpoint 恢复，重放 Source，Sink 靠事务保证不重复不丢失。

> **Q**: Watermark 解决什么问题？
> **A**: 分布式环境下事件到达乱序。Watermark = max(已到达事件时间) - allowed_lateness。窗口在水位线超过 window_end 时才触发计算，允许迟到的数据还能被窗口容纳。

### Doris

> **Q**: Doris 为什么比 MySQL 快？
> **A**: 1) 列式存储：聚合查询只读需要的列；2) MPP 并行：多 BE 同时计算各自分片；3) 预聚合：Aggregate 模型写入时自动合并；4) 向量化执行：批量处理代替逐行。简单聚合查询能快 100 倍以上。

> **Q**: FE 和 BE 的职责？
> **A**: FE 是"大脑"：元数据管理、SQL 解析、查询规划（类似 MySQL Server 层）。BE 是"手脚"：存储数据分片（Tablet）、执行计算任务。每个 BE 无状态（数据有副本），扩缩容方便。

### DataBus

> **Q**: 怎么把 MySQL 数据实时同步到 ES？
> **A**: Canal 伪装 MySQL Slave 接收 binlog → 解析成结构化事件 → 发到 Kafka → 消费者写入 ES。毫秒级延迟，包含 INSERT/UPDATE/DELETE 全量变更。

> **Q**: 为什么不用定时任务 SELECT 同步？
> **A**: 1) 无法感知 DELETE；2) 定时查询给业务库带来压力；3) 延迟不可控（1 分钟定时 = 最差 59 秒延迟）；4) 无法保证顺序。Binlog 是数据库原生的变更日志，最可靠。

---

## 全路线总结

```
A 层 - 协议通信
  A1: gRPC ───── 接口协议（Unary + 3 Streaming）
  A2: WebSocket ─ 长连接（Echo/聊天室/心跳）

B 层 - 中间件
  B1: Redis ──── 内存缓存（5 类型/缓存三大问题）
  B2: Kafka ──── 消息队列（分区/消费组/可靠性）
  B3: ES/Meili ─ 搜索引擎（倒排索引/容错/聚合）
  B4: MinIO ──── 对象存储（S3 协议/Presigned URL）

C 层 - 微服务体系
  C0: ZooKeeper ─ 分布式协调（临时节点/Watch/分布式锁）
  C1: Nacos ──── 注册配置中心（服务发现/配置热更新）
  C2: Gateway ── API 网关（路由/鉴权/限流/熔断）

D 层 - 大数据
  D1: Flink ──── 流计算（Window/Watermark/Checkpoint）
  D2: Doris ──── OLAP 分析（列式/MPP/Aggregate 模型）
  D3: DataBus ── CDC 管道（Canal→Kafka→下游扇出）

🏆 总计: 12 模块 / 162 测试 / 全部通过！
```
