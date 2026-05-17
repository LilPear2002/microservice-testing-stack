# 🚀 微服务测开技能栈

> **12 个模块 · 162 条测试 · 100% 通过**  
> 从零到一，用 Python 手撕微服务中间件全家桶

---

## 🎯 技能全景

```
                     ┌──────────────┐
              ┌──────│  API Gateway │──────┐
              │      │ 路由·鉴权·限流│      │
              │      └──────┬───────┘      │
              │             │              │
         ┌────▼────┐   ┌───▼────┐   ┌─────▼────┐
         │  gRPC   │   │  REST  │   │WebSocket │  ← A 层：协议通信
         └────┬────┘   └───┬────┘   └─────┬────┘
              │            │              │
         ┌────▼────────────▼──────────────▼────┐
         │        Nacos / ZooKeeper            │  ← C 层：服务治理
         │      服务注册 · 配置中心 · 分布式锁   │
         └────────────┬───────────────────────┘
                      │
              ┌───────▼────────┐
              │   业务微服务     │
              └───┬──┬──┬──┬──┘
          ┌───────┘  │  │  └───────┐
    ┌─────▼──┐ ┌───▼──▼──┐ ┌────▼───┐
    │ Redis  │ │  Kafka  │ │ MinIO  │  ← B 层：中间件
    │ 缓存   │ │ 消息队列│ │对象存储│
    └────────┘ └───┬─────┘ └────────┘
                   │
         ┌─────────▼──────────┐
         │      ES / Meili    │  ← B 层：搜索
         └─────────┬──────────┘
                   │
    ┌──────────────▼────────────────┐
    │  大数据链路                    │  ← D 层：大数据
    │  MySQL→Canal→Kafka             │
    │    ├→ Flink → Doris (实时分析) │
    │    ├→ ES (搜索)                │
    │    └→ Redis (缓存)             │
    └───────────────────────────────┘
```

---

## 📊 模块一览

| # | 模块 | 阶段 | 测试 | 核心收获 |
|---|------|:---:|:---:|----------|
| 🔵 | **gRPC** | 4 | 14 | Unary/Server-Stream/Client-Stream/Bidi + grpcurl 调试 |
| 🔌 | **WebSocket** | 4 | 9 | Echo/多人聊天室/心跳/ping-pong 保活 |
| 🔴 | **Redis** | 4 | 16 | 5 类型/PubSub/缓存穿透·击穿·雪崩解决方案 |
| 📨 | **Kafka** | 4 | 6 | 分区有序性/消费组重平衡/消息可靠性/手动 offset |
| 🔍 | **搜索引擎** | 5 | 23 | 倒排索引/容错搜索/过滤器/排序/聚合 Facets |
| 🪣 | **MinIO** | 5 | 19 | Bucket·Object/Presigned URL/Policy/元数据 |
| 🦍 | **ZooKeeper** | 5 | 17 | 四种 Znode/Watch/分布式锁（EPHEMERAL_SEQUENTIAL）/乐观锁 |
| 🏗️ | **Nacos** | 5 | 19 | 服务注册发现/配置热更新/健康检查/负载均衡 |
| 🚪 | **Gateway** | 6 | 21 | 路由匹配/鉴权/令牌桶限流/熔断器/Observer 日志 |
| 🌊 | **Flink** | 5 | — | DataStream/Window/Watermark/Checkpoint/Exactly-Once |
| 🗄️ | **Doris** | 4 | — | MPP 架构/列式存储/Aggregate/Unique/Duplicate 模型 |
| 🔄 | **DataBus** | 4 | — | Canal→Kafka/CDC/binlog 解析/多目标扇出 |
| ☸️ | **k3s** | — | — | K8s 基础：Pod/Deploy/Service/ConfigMap/Ingress |
| 🃏 | **Mock 测试** | 4 | 91 | Dummy/Stub/Spy/Mock/Fake → 全链路 SAGA 回滚实战 |
| ⚡ | **性能测试** | 4 | — | 压测流程 + Locust 进阶 + 压测平台架构 |

> ⚡ Flink/Doris/DataBus 在 2C2G 机器上无法运行，以概念 + 模拟 + 面试话术学习  
> 🏆 **总计 162 条测试，全部通过**

---

## 🚀 快速开始

```bash
# 每个模块独立运行（以 Redis 为例）
cd redis/
uv venv --python 3.11
source .venv/bin/activate
uv pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/

# 运行学习脚本
python redis_basics.py

# 跑测试
pytest test_redis.py -v
```

### 依赖服务

| 服务 | 端口 | Docker 命令 |
|------|:---:|-------------|
| Redis | 6379 | `docker run -d --name redis -p 6379:6379 redis:7-alpine` |
| MeiliSearch | 7700 | `docker run -d --name meili -p 7700:7700 getmeili/meilisearch:v1.12` |
| MinIO | 9000 | `docker run -d --name minio -p 9000:9000 minio/minio server /data` |
| ZooKeeper | 2181 | `docker run -d --name zk -p 2181:2181 zookeeper:3.9` |
| Kafka | 9092 | 见 `kafka/README.md`（二进制 + KRaft 模式） |

---

## 📝 学习笔记

每个模块根目录下有 `README.md`，包含：

- ✅ 核心概念（图示 + 对比）
- ✅ 环境配置（一行命令）
- ✅ 分阶段代码示例
- ✅ 测试结果
- ✅ 面试话术
- ✅ 关键踩坑记录

---

## 🧪 测试总览

```bash
grpc/       pytest test_grpc.py -v       # 14 passed
websocket/  pytest test_websocket.py -v  #  9 passed
redis/      pytest test_redis.py -v      # 16 passed
kafka/      pytest test_kafka.py -v      #  6 passed
es/         pytest test_search.py -v     # 23 passed
minio/      pytest test_minio.py -v      # 19 passed
zookeeper/  pytest test_zk.py -v         # 17 passed
nacos/      pytest test_nacos.py -v      # 19 passed
gateway/    pytest test_gateway.py -v    # 21 passed
bigdata/    pytest test_bigdata.py -v    # 18 passed
──────────────────────────────────────────────────
            总计                          162 passed 🎉
```

---

## 🗺️ 学习路线

```
Phase 1 ─ 协议通信           Phase 2 ─ 中间件
  ├── gRPC (4 种 RPC 模式)      ├── Redis (缓存/穿透击穿雪崩)
  └── WebSocket (长连接)        ├── Kafka (消息队列)
                                ├── 搜索引擎 (倒排索引)
                                └── MinIO (对象存储)

Phase 3 ─ 微服务体系         Phase 4 ─ 大数据
  ├── ZooKeeper (分布式协调)      ├── Flink (流计算)
  ├── Nacos (注册配置中心)       ├── Doris (OLAP 分析)
  └── Gateway (API 网关)        └── DataBus (CDC 管道)
```

---

## 👤 关于

- **GitHub**: [@LilPear2002](https://github.com/LilPear2002)
- **学习笔记**: 每个模块 `README.md`
- **学习工具**: Hermes Agent + pytest + Docker + uv
