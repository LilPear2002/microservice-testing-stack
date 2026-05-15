# 🚪 API 网关（Gateway）

## 学习时间
2026-05-15

## 什么是 API 网关？

```
客户端 → [API Gateway] → 微服务集群
         统一入口        内部随便改

无网关：客户端要知道所有服务地址
有网关：客户端只认一个地址，网关负责路由

网关 = 所有请求的"大门"
  进门前：鉴权、限流、日志
  进门后：路由、负载均衡
  异常时：熔断、降级
```

### 架构图

```
                    ┌──────────────────────────────┐
   客户端 ─────────→│        API Gateway           │
                    │                              │
                    │  ① 鉴权（API Key / JWT）      │
                    │  ② 限流（Token Bucket）       │
                    │  ③ 路由（/api/orders → order）│
                    │  ④ 负载均衡（轮询 / 权重）     │
                    │  ⑤ 熔断（后端挂了快速失败）    │
                    │  ⑥ 日志（统一记录）           │
                    └──┬────────┬────────┬─────────┘
                       │        │        │
                  ┌────▼───┐ ┌──▼───┐ ┌──▼──────┐
                  │ order  │ │payment│ │  user   │
                  │  svc   │ │  svc  │ │   svc   │
                  └────────┘ └──────┘ └─────────┘
```

## 六大核心功能

### 1. 路由转发（Routing）

```python
gateway.add_route("/api/orders", order_backend)
gateway.add_route("/api/payments", payment_backend)

# /api/orders/123 → order-service
# /api/payments/456 → payment-service
# /api/unknown → 404
```

**匹配策略**：最长前缀匹配（`/api/orders/v2` 优先匹配 `/api/orders/v2` 而不是 `/api/orders`）

### 2. 鉴权（Authentication）

```python
# 统一在网关验证 API Key，后端服务不需要重复写鉴权逻辑
headers = {"X-API-Key": "test-key-123"}
valid_key → 200 OK
invalid_key → 401 Unauthorized
```

### 3. 负载均衡（Load Balancing）

```python
# 轮询算法（Round Robin）
# 请求1 → 10.0.0.1:8080
# 请求2 → 10.0.0.2:8080
# 请求3 → 10.0.0.1:8080
# 请求4 → 10.0.0.2:8080
```

**真实网关还支持**：加权轮询、最少连接、一致性哈希、就近路由

### 4. 限流（Rate Limiting）

```python
# Token Bucket 算法
limiter = RateLimiter(rate=5, capacity=10)
# rate=5：每秒补充 5 个令牌
# capacity=10：最多攒 10 个（允许突发流量）

for 12 requests:
    前几个 → 200 OK（有令牌）
    后面 → 429 Too Many Requests（令牌耗尽）
```

### 5. 熔断器（Circuit Breaker）

```
三种状态转换：
  CLOSED ──连续失败N次──→ OPEN ──超时后──→ HALF_OPEN
    ↑                                        │
    └──────────试探成功───────────────←────────┘

关键参数：
  failure_threshold=3  → 连续3次失败就熔断
  timeout=5            → 5秒后尝试恢复
```

### 6. 访问日志

```python
# 每个请求自动记录
{"method":"GET", "path":"/api/orders/123", "status":200,
 "elapsed_ms":0.01, "user":"user1", "target":"10.0.0.1:8080"}
```

## 真实网关对比

| 网关 | 语言 | 特点 |
|------|------|------|
| **Spring Cloud Gateway** | Java | Spring 生态，WebFlux 异步 |
| **Kong** | Lua/OpenResty | 插件丰富，高性能 |
| **APISIX** | Lua | 国产，云原生 |
| **Nginx** | C | 最基础，反向代理 |
| **Traefik** | Go | K8s 原生，自动发现 |

## 测试结果

```bash
$ pytest test_gateway.py -v
============================= 21 passed in 0.55s ==============================

测试覆盖:
  ✅ 路由 (4):    匹配 / 不匹配404 / 根路径
  ✅ 鉴权 (4):    有效Key / 无效Key / 缺少Key / 管理员
  ✅ 负载均衡 (2): 轮询分发 / 单实例
  ✅ 限流 (3):    突发允许 / 耗尽拒绝 / 令牌补充
  ✅ 熔断 (3):    CLOSED→OPEN / 快速失败 / 恢复
  ✅ 日志 (2):    记录 / 字段完整
  ✅ HTTP方法 (3): POST / PUT / DELETE
```

## 面试话术

> **Q**: API 网关的作用？
> **A**: 六大功能：**路由**（统一入口）、**鉴权**（不用每个服务写一遍）、**限流**（防刷）、**负载均衡**（分发流量）、**熔断**（后端挂了快速失败而不是超时等待）、**日志/监控**（统一埋点）。本质是把横切关注点（cross-cutting concerns）从业务服务中抽到网关层。

> **Q**: 熔断器（Circuit Breaker）三种状态？
> **A**: CLOSED（正常转发，计数失败）→ 连续失败超过阈值 → OPEN（直接拒绝，快速失败）→ 超时后 → HALF_OPEN（试探性放行一个请求）→ 成功则恢复 CLOSED，失败则回到 OPEN。防止故障扩散（级联故障）。

> **Q**: 令牌桶 vs 漏桶？
> **A**: 令牌桶允许**突发流量**（桶里有攒的令牌就可以瞬间消耗），漏桶严格**平滑流量**（固定速率流出）。网关一般用令牌桶，允许正常突发但限制长期平均速率。

> **Q**: 网关会成为瓶颈吗？
> **A**: 会，所以网关要高性能（异步非阻塞、Nginx/Lua/Go）、无状态可水平扩展、前面再挂一层 L4 负载均衡。Kong/APISIX 能跑到数万 QPS。

## 下一步
- D1~D3: 大数据链路（Flink / Doris / DataBus 概念学习）
