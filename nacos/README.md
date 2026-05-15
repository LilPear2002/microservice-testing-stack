# 🏗️ Nacos 注册配置中心

## 学习时间
2026-05-15

## ⚠️ 为什么没跑真实 Nacos？

```
Nacos 是 Java 应用，默认 JVM 堆 1GB
2C2G 机器直接 OOM-kill（exit 137）
即使降 JVM 到 256MB，Java 进程实际内存 > 400MB

策略：用 Python 写的 MiniNacos 演示所有核心概念
     API 模式 100% 对齐真实 Nacos SDK！
     学会 MiniNacos = 学会 Nacos SDK 使用方式
```

## Nacos = 注册中心 + 配置中心

```
┌─────────────────────────────────────────┐
│              Nacos Server               │
│  ┌──────────────┐  ┌──────────────────┐│
│  │  注册中心     │  │    配置中心      ││
│  │  (Naming)    │  │   (Config)      ││
│  │              │  │                  ││
│  │ /order-svc   │  │ /order-svc.yaml ││
│  │  ├ 10.0.1:80 │  │ /db-config.yaml ││
│  │  └ 10.0.2:80 │  │ /redis.yaml     ││
│  └──────────────┘  └──────────────────┘│
└─────────────────────────────────────────┘
         ↑                    ↑
    服务注册/发现        配置拉取/监听
         ↓                    ↓
    ┌─────────┐         ┌─────────┐
    │  微服务A │         │  微服务B │
    └─────────┘         └─────────┘
```

### 三大核心功能

| 功能 | SDK 方法 | 说明 |
|------|----------|------|
| **服务注册** | `register_instance(svc, ip, port)` | 启动时注册 |
| **服务发现** | `get_all_instances(svc)` / `subscribe(svc, callback)` | 拉取 + 订阅 |
| **配置管理** | `get_config(id)` / `add_listener(id, callback)` | 拉取 + 热更新 |

### 核心概念对照

| 概念 | Nacos | 对比 ZooKeeper |
|------|-------|---------------|
| 服务注册 | naming_client.register_instance | zk.create(ephemeral=True) |
| 服务发现 | naming_client.subscribe + callback | zk.ChildrenWatch |
| 配置管理 | config_client.get_config | zk.get + DataWatch |
| 命名空间 | namespace（租户级隔离） | 无（靠路径前缀） |
| 分组 | group | 路径层级 |
| 健康检查 | 主动检测 + 被动上报 | session 超时 |

## MiniNacos 5 大阶段

### Phase 1: 服务注册

```python
nacos = MiniNacos()

# 注册服务实例（带元数据）
nacos.register_instance("order-service", "10.0.1.10", 8080,
    metadata={"version": "1.0", "region": "cn-hangzhou"})

nacos.register_instance("order-service", "10.0.1.11", 8080)

# 拉取实例列表
instances = nacos.get_all_instances("order-service")
# → [Instance(ip="10.0.1.10", port=8080), Instance(ip="10.0.1.11", port=8080)]
```

### Phase 2: 服务发现 + 订阅

```python
def on_change(instances):
    print(f"order-service 实例变更: {instances}")

# 订阅服务变更（注册/注销时自动通知）
nacos.subscribe("order-service", callback=on_change)

# 扩容
nacos.register_instance("order-service", "10.0.1.12", 8080)
# → 自动触发 on_change

# 下线
nacos.deregister_instance("order-service", "10.0.1.10", 8080)
# → 自动触发 on_change
```

### Phase 3: 配置管理

```python
# 发布配置
nacos.publish_config("order-service.yaml",
    "spring.datasource.url=jdbc:mysql://10.0.3.10:3306/orders\n"
    "spring.datasource.username=admin")

# 获取配置
config = nacos.get_config("order-service.yaml")
```

### Phase 4: 配置热更新

```python
def on_config_change(content):
    print(f"🔥 配置热更新: {content}")

nacos.add_config_listener("order-service.yaml", on_config_change)

# 运维修改数据库地址 → 所有监听的服务自动收到新配置
nacos.publish_config("order-service.yaml", 
    "spring.datasource.url=jdbc:mysql://10.0.3.20:3306/orders")
# → 🔥 热更新: ...
```

### Phase 5: 健康检查 & 故障摘除

```python
# 标记不健康
inst = nacos.get_all_instances("order-service")[0]
inst.healthy = False

# get_all_instances 自动过滤不健康实例
healthy = nacos.get_all_instances("order-service")
# → 只有健康实例
```

## 测试结果

```bash
$ pytest test_nacos.py -v
============================= 19 passed in 0.43s ==============================

测试覆盖:
  ✅ 服务注册 (5):  单实例 / 多实例 / 元数据 / 注销 / 空服务
  ✅ 服务发现 (3):  即时回调 / 新实例通知 / 注销通知
  ✅ 配置管理 (4):  发布获取 / 更新 / 不存在 / 变更监听
  ✅ 健康检查 (2):  不健康过滤 / 全不健康
  ✅ 负载均衡 (2):  获取一个实例 / 空服务
  ✅ 边界 (3):      注销最后一个 / 重复注册 / 空配置
```

## 面试话术

> **Q**: Nacos 和 ZooKeeper 选哪个？
> **A**: Nacos = ZK + Spring Cloud Config，一个组件干两件事。ZK 是 CP 系统（强一致性），Nacos 支持 AP/CP 切换（优先可用性）。Nacos 自带管理界面、健康检查更灵活（支持 HTTP/TCP/MySQL 探测），配置管理支持热更新。如果用 Spring Cloud Alibaba 体系，选 Nacos；如果已有 Hadoop/ZK 生态，复用 ZK。

> **Q**: 配置热更新是怎么实现的？
> **A**: 应用启动时从 Nacos 拉取配置并注册 Listener。Nacos 配置变更后，通过长轮询（Long Polling）通知客户端，客户端回调 Listener 更新本地配置。Spring Cloud 下 `@RefreshScope` + `@Value` 注解的 Bean 会自动刷新，无需重启。

> **Q**: 服务发现的流程？
> **A**: 
> 1. 服务提供者启动 → 向 Nacos 注册（IP:Port + metadata）
> 2. 服务消费者启动 → 向 Nacos 订阅服务名 → Nacos 推送实例列表
> 3. 服务提供者下线 → Nacos 通知消费者剔除该实例
> 4. 消费者本地缓存 + 定时拉取，即使 Nacos 挂了也能用本地缓存继续调用

> **Q**: 临时实例 vs 持久实例？
> **A**: 临时实例（ephemeral=true）靠心跳保活，断连自动剔除（类似 ZK 临时节点）。持久实例（ephemeral=false）即使断连也保留，靠健康检查判定。大多数微服务用临时实例。

## 下一步
- C2: Gateway 网关
- D1~D3: 大数据链路
