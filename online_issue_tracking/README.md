# 线上问题追踪与改进 — 学习笔记

> 📅 2026-05-14 | 阶段①：构建带 Bug 的演示应用

---

## 阶段①：构建带 Bug 的 FastAPI 演示应用

### 1. 做了什么事

搭建了一个 **刻意包含 3 类线上常见 Bug** 的 FastAPI 服务，为后续的「故障发现 → 定位 → 改进」闭环做准备。

### 2. 项目结构

```
/workspace/online_issue_tracking/
├── PLAN.md              # 5阶段实操计划
├── .venv/               # uv 虚拟环境（Python 3.11）
├── app/
│   ├── main.py          # FastAPI 应用（5个端点 + Prometheus + 结构化日志）
│   ├── requirements.txt # Python 依赖
│   └── Dockerfile       # Docker 镜像构建文件
└── README.md            # 本笔记
```

### 3. 5 个 API 端点

| 端点 | 方法 | 说明 | 是否有 Bug |
|------|------|------|-----------|
| `/health` | GET | 健康检查 | ❌ 正常 |
| `/api/users/{id}` | GET | 用户查询（1=Alice, 2=Bob, 3=Charlie） | ❌ 正常 |
| `/api/process?value=N` | GET | **Bug 1**：当 value≤0 时抛异常 | 🐛 间歇性 500 |
| `/api/report?date=...` | GET | **Bug 2**：30% 概率耗时 2~8s | 🐛 慢接口 |
| `/api/cache` | POST | **Bug 3**：每次追加到全局列表不清理 | 🐛 内存泄漏 |
| `/metrics` | GET | Prometheus 指标暴露 | ❌ 正常（监控用） |

### 4. 3 类 Bug 详解

#### Bug 1：间歇性 500 — 参数校验缺失

```python
# 当用户传入 value=0 或负数时：
# - value=0 → 100/0 = ZeroDivisionError 💥
# - value<0 → 负数除法虽然不报错，但代码逻辑判断 value<=0 就走异常分支

# 根因：没有对用户输入做参数校验
# 线上等价场景：未处理的边界条件、空指针、除零错误
```

**验证命令**：
```bash
curl http://localhost:8080/api/process?value=0    # → 500
curl http://localhost:8080/api/process?value=5    # → 正常
```

**Prometheus 指标**：`bug_process_zero_or_negative_total` 计数器

---

#### Bug 2：慢接口 — 随机超时

```python
# 30% 概率触发 time.sleep(2~8秒)
# 模拟场景：
#   - 数据库慢查询（没建索引 / 全表扫描）
#   - 外部 API 调用超时
#   - 大文件处理
```

**验证命令**：
```bash
# 多跑几次，有时候会卡住 2~8 秒
time curl http://localhost:8080/api/report
```

**Prometheus 指标**：
- `bug_slow_report_total` — 慢请求计数（>3s 才 +1）
- `http_request_duration_seconds` — 所有请求延迟直方图

---

#### Bug 3：内存泄漏 — 只增不减的缓存

```python
_global_cache: list = []  # 全局变量

# 每次 POST /api/cache 往里面追加数据，从不删除
# 持续调用 → 内存占用持续增长 → 最终 OOM
```

**验证命令**：
```bash
# 连续调用观察缓存增长
for i in {1..10}; do
  curl -s -X POST http://localhost:8080/api/cache \
    -H "Content-Type: application/json" \
    -d "{\"key\":\"item$i\"}"
  echo
done
curl http://localhost:8080/api/cache/stats   # 查看缓存大小
```

**Prometheus 指标**：`app_cache_size_bytes` — 缓存近似大小

---

### 5. 可观测性三件套

#### 5.1 Prometheus 指标（Metrics）

应用暴露 6 类指标：

| 指标名 | 类型 | 用途 |
|--------|------|------|
| `http_requests_total` | Counter | 请求计数（按方法/端点/状态码分） |
| `http_request_duration_seconds` | Histogram | 请求延迟分布（P50/P90/P99） |
| `http_errors_total` | Counter | 错误计数（按端点/错误类型分） |
| `app_cache_size_bytes` | Gauge | 缓存大小（观测内存泄漏） |
| `app_active_requests` | Gauge | 当前正在处理的请求数 |
| `bug_*_total` | Counter | 专项 Bug 触发计数 |

**名词解释**：
- **Counter**：只增不减的计数器（如请求总数、错误总数）
- **Gauge**：可增可减的瞬时值（如内存使用量、并发数）
- **Histogram**：分布统计（如 P99 延迟 = 99% 的请求在 X 秒内完成）

#### 5.2 结构化日志（Structured Logging）

使用 `structlog` 输出 JSON 格式日志，关键字段：
```json
{
  "request_id": "aae386f5",      // 每次请求唯一 ID，用于串联
  "method": "GET",
  "path": "/api/process",
  "status": 200,
  "duration_seconds": 0.023,
  "event": "request_completed",
  "timestamp": "2026-05-14T12:48:30Z",
  "level": "info"
}
```

**为什么用结构化日志而不是 `print()`？**
- 可以被日志采集系统（如 ELK、Loki）自动解析和索引
- 通过 `request_id` 串联一次请求的所有日志
- 支持按字段过滤（如 `status=500` 的所有日志）

#### 5.3 分布式追踪基础（requestId）

通过中间件给每个请求注入 `request_id`（UUID 前 8 位），埋入日志上下文：
```
用户请求 → 中间件生成 request_id → 注入 structlog 上下文
         → 所有后续日志自动带 request_id
         → 500 错误响应也返回 request_id 给客户端
```

---

### 6. 环境配置

```bash
# 创建虚拟环境
uv venv --python 3.11

# 安装依赖
uv pip install --python .venv/bin/python fastapi uvicorn prometheus-client structlog python-json-logger

# 启动服务
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8080
```

### 7. Docker 化

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py .
EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

```bash
docker build -t buggy-api:v1 .
```

---

### 8. 阶段① 检验清单

- [x] 5 个 API 端点全部可用
- [x] Bug 1 传入 value=0 时返回 500 + request_id
- [x] Bug 2 有一定概率响应 >3s
- [x] Bug 3 连续 POST 缓存持续增长
- [x] `/metrics` 端点正确暴露 Prometheus 指标
- [x] 结构化日志包含 request_id / method / path / status / duration
- [x] Docker 镜像构建成功

---

> **下一阶段**：阶段② — 部署到 k3s + 挂 Prometheus 监控

---

## 阶段②：部署到 k3s + 搭建 Prometheus 监控

> 📅 2026-05-14 | ⏱ ~40 分钟

### 1. 做了什么事

把阶段①的 buggy-api 容器部署到 k3s 集群，并搭建 Prometheus 监控系统，实现「应用运行 → 指标暴露 → 自动采集 → 异常告警」的完整链路。

### 2. 最终架构

```
┌─────────────────────────────────────────────────┐
│                    k3s 集群                       │
│  ┌──────────────────┐  ┌──────────────────┐     │
│  │ buggy-api Pod ×2 │  │ buggy-api Pod ×2 │     │
│  │   :8080/metrics  │  │   :8080/metrics  │     │
│  └──────┬───────────┘  └──────┬───────────┘     │
│         └────── Service ──────┘                  │
│              NodePort :30080                     │
└──────────────────┬──────────────────────────────┘
                   │
          ┌────────▼────────┐
          │   Prometheus    │  宿主机进程
          │   :9090 (UI)    │  每 15s 抓取一次
          │   告警规则 ×4   │
          └─────────────────┘
```

### 3. k3s 部署步骤

#### 3.1 启动 k3s

```bash
systemctl start k3s
# kubectl 通过 k3s 内置命令访问
k3s kubectl get nodes
```

**⚠️ 注意**：k3s 自带 containerd，与 Docker 的 containerd 互不冲突。

#### 3.2 清理旧资源

之前学习留下的 Pod（web-app、whoami、config-demo）占用内存，需要清理：

```bash
k3s kubectl delete deploy web-app whoami --ignore-not-found
k3s kubectl delete pod config-demo --ignore-not-found
```

#### 3.3 导入 Docker 镜像到 k3s

k3s 默认使用 containerd（不是 Docker），需要手动导入：

```bash
docker save buggy-api:v1 -o /tmp/buggy-api.tar
k3s ctr images import /tmp/buggy-api.tar
```

**名词解释**：
- `containerd`：k3s 内置的容器运行时，管理容器生命周期
- `ctr`：containerd 的命令行工具
- 为什么要导入？Docker 和 containerd 的镜像存储是隔离的

#### 3.4 Deployment YAML 关键字段

```yaml
# replicas: 2 → 两个副本，高可用
# resources.requests: 64Mi/50m → 调度时的最低保证
# resources.limits: 128Mi/200m → 硬上限，超了会被 OOMKill
# livenessProbe → 探活，挂了自动重启
# readinessProbe → 就绪探针，健康才分配流量
# prometheus.io/* annotations → 告诉 Prometheus 来抓这个 Pod
```

**关键知识点**：
- **requests vs limits**：requests 是调度时的「预定」；limits 是运行时的「天花板」
- **探针类型**：livenessProbe（活没活）→ 不健康就重启；readinessProbe（能不能接流量）→ 不健康就摘除
- **NodePort**：在每个 Node 上开一个端口（30000-32767），把流量转发到 Service，方便外部访问

#### 3.5 部署验证

```bash
k3s kubectl apply -f k8s/buggy-api.yaml

# 查看 Pod 状态
k3s kubectl get pods -n buggy-demo

# 验证 API 可用
curl http://localhost:30080/health
curl http://localhost:30080/api/users/1
```

### 4. Prometheus 监控搭建

#### 4.1 为什么 Prometheus 跑在宿主机而非 k3s 内？

机器只有 2C2G（可用 400MB），k3s 已经占了大半内存。Prometheus 跑在 Pod 里会多一层容器开销和 k3s 系统 Pod 的内存压力。**跑在宿主机上，功能完全一样，资源更省。**

#### 4.2 配置说明（prometheus.yml）

```yaml
scrape_interval: 15s      # 每 15 秒抓一次指标
static_configs:
  - targets: ["localhost:30080"]  # 指向 k3s NodePort
```

**为什么用 static_configs 而不用 Kubernetes SD？**
- 静态配置更简单，学习重点在 Prometheus 本身
- Kubernetes 服务发现需要 RBAC 授权，增加复杂度

#### 4.3 启动命令

```bash
prometheus \
  --config.file=prometheus.yml \
  --storage.tsdb.retention.time=2h \    # 只保留 2h（省磁盘）
  --storage.tsdb.max-block-duration=30m \
  --web.listen-address=0.0.0.0:9090
```

#### 4.4 验证指标采集

```bash
# 健康检查
curl http://localhost:9090/-/healthy

# 查看抓取目标
curl http://localhost:9090/api/v1/targets

# 查询指标
curl "http://localhost:9090/api/v1/query?query=http_requests_total"
```

### 5. 告警规则（4 条）

| 告警名 | 触发条件 | 严重级别 |
|--------|---------|---------|
| `HighErrorRate` | 5 分钟内错误率 > 0.1/s | 🔴 critical |
| `HighLatency` | P99 延迟 > 2s | 🟡 warning |
| `MemoryLeakWarning` | 缓存 > 10KB | 🟡 warning |
| `BugProcessZeroValueFrequent` | Bug1 触发 > 0.05/s | 🟡 warning |

**PromQL 语法速查**：
- `rate(metric[5m])` — 5 分钟内的每秒平均增长率
- `histogram_quantile(0.99, rate(...))` — P99 分位数
- `> 0.1` — 阈值比较
- `for: 1m` — 持续 1 分钟才触发告警（防止抖动误报）

### 6. 资源现状

| 组件 | 状态 |
|------|------|
| k3s 集群 | ✅ 运行中（1 node） |
| buggy-api Pod ×2 | ✅ Running（128Mi each） |
| Prometheus | ✅ 健康（宿主机 :9090） |
| 内存 | ⚠️ 1.2G/1.6G（408M 可用） |

### 7. 踩坑记录

| 坑 | 原因 | 解决 |
|----|------|------|
| Docker 构建超时 | GitHub 直连不通 | 重启 Docker 加载 mirror 加速 |
| kubectl 命令找不到 | k3s 的 kubectl 不在普通 PATH 中 | 用 `k3s kubectl` 代替 |
| Pod 导入后不识别 | Docker 镜像和 containerd 不共享 | 用 `k3s ctr images import` 导入 |
| 内存爆炸，kubectl 超时 | Docker + k3s 同时跑 | 停掉 Docker（镜像已导入 containerd） |

### 8. 阶段② 检验清单

- [x] k3s 集群正常，1 node Ready
- [x] buggy-api 2 个副本全部 Running
- [x] NodePort :30080 可访问所有 API
- [x] `/health` 探活正常
- [x] Prometheus 健康 + 正在抓取 buggy-api
- [x] 指标可查询（http_requests_total 有数据）
- [x] 4 条告警规则全部加载（state: inactive）
- [x] Prometheus UI 可访问（:9090）

---

> **下一阶段**：阶段③ — 注入故障 + 通过监控发现（脚本压测 + 触发告警）

---

## 阶段③：注入故障 + 通过监控发现

> 📅 2026-05-14 | ⏱ ~30 分钟

### 1. 做了什么事

主动向 buggy-api 注入故障请求，通过应用的 `/metrics` 端点实时观察 Bug 计数器变化，最后启动 Prometheus 验证告警规则从 `inactive` 变为 `firing`。

### 2. 注入前后对比（/metrics 直接观察）

| 指标 | 注入前 | 注入后 |
|------|--------|--------|
| `bug_process_zero_or_negative_total` | 0 | **27** |
| `bug_slow_report_total` | 0 | **~3** |
| `app_cache_size_bytes` | 0 | **16661** |
| `http_errors_total` (ZeroDivisionError) | 0 | **~15** |

### 3. 注入方法

#### Bug 1：间歇性 500
```bash
for v in 0 0 -1 -5 0 0 -1 -5 0 0 -1 0; do
  curl "http://localhost:8080/api/process?value=$v"
done
# → bug_process_zero_or_negative_total +12
# → http_errors_total{error_type="ZeroDivisionError"} +7
```

#### Bug 2：慢接口
```bash
for i in $(seq 1 8); do
  curl "http://localhost:8080/api/report"
done
# → bug_slow_report_total 记录 >3s 的请求数
```

#### Bug 3：内存泄漏
```bash
for i in $(seq 1 20); do
  curl -X POST http://localhost:8080/api/cache \
    -H "Content-Type: application/json" \
    -d "{\"key\":\"leak_$i\"}"
done
# → app_cache_size_bytes 持续增长
```

### 4. 告警触发结果

| 告警 | 状态 | 说明 |
|------|------|------|
| 🔴 `HighLatency` | **firing** | P99 延迟 > 2s，已触发！ |
| 🔴 `BugProcessZeroValueFrequent` | **firing** | Bug1 触发速率 > 0.05/s，已触发！ |
| 🟡 `MemoryLeakWarning` | **pending** | 缓存 > 10KB，等待 5min 持续 → firing |
| ⚪ `HighErrorRate` | inactive | 错误不够密集（需 >0.1/s 持续 1min） |

### 5. 告警状态机

```
inactive（正常）
   │  触发条件满足
   ▼
pending（等待 for 持续时间）
   │  持续满 for 时间（如 1m、5m）
   ▼
firing（🔥 告警中！）
   │  触发条件消失
   ▼
inactive
```

**pending vs firing 的区别**：
- `pending`：条件满足了，但在等 `for` 时间（防止瞬时抖动误报）
- `firing`：持续超过 `for` 时间，正式触发告警

### 6. 核心观察

从 `/metrics` 端点直接看指标就够了——Prometheus 的价值在于：
1. **时间序列存储**：能看到历史趋势（如缓存"持续增长"）
2. **PromQL 查询**：计算错误率、P99 延迟等派生指标
3. **告警规则**：自动评估 + 状态管理

但对排查问题来说，最关键是 **① Bug 专项指标** + **② 错误日志中的 requestId**。

### 7. 踩坑记录

| 坑 | 原因 | 解决 |
|----|------|------|
| 5 并发压测炸了机器 | 2C2G + 慢磁盘 I/O 打满 | 降低并发、串行注入 |
| Prometheus + k3s 同跑 I/O 爆 | 两者都要写磁盘（TSDB + containerd） | 停 k3s，uvicorn 直跑 |
| Prometheus lifecycle API 不可用 | 启动时没加 `--web.enable-lifecycle` | 重启时加上 |
| 抓取目标未切换 | reload 前改了配置但 reload API 不可用 | 重启 Prometheus |

### 8. 压测脚本

`/workspace/online_issue_tracking/load_test.py` — 可调并发数、Bug 比例、持续时间。

### 9. 阶段③ 检验清单

- [x] Bug1 注入后 `bug_process_zero_or_negative_total` 增长
- [x] Bug2 注入后 `bug_slow_report_total` 增长
- [x] Bug3 注入后 `app_cache_size_bytes` 持续增长
- [x] Prometheus 采集到所有指标
- [x] 至少 1 条告警从 inactive → firing
- [x] pending 状态机制得到验证（for 持续时间）
- [x] 理解了告警 3 态：inactive → pending → firing

---

> **下一阶段**：阶段④ — 根因定位 RCA（从告警回溯日志+代码，定位具体行）

---

## 阶段④：根因定位 RCA

> 📅 2026-05-14 | ⏱ ~15 分钟

### 1. 做了什么事

从 Prometheus 告警出发，按照「告警 → 指标 → 日志 → 代码」的路径，逐一追溯到每个 Bug 的具体代码行，总结出通用的线上问题排查方法论。

### 2. 当前告警状态

| 告警 | 状态 | 接口 | 数据 |
|------|------|------|------|
| 🔴 HighLatency | **firing** | /api/report | P99 = **7.35s** |
| 🔴 BugProcessZeroValueFrequent | **firing** | /api/process | 速率 0.052/s |
| 🟡 MemoryLeakWarning | **pending** | /api/cache | 缓存 **16661 bytes** |
| ⚪ HighErrorRate | inactive | — | 速率不足 |

### 3. Bug1 RCA：HighLatency → /api/report → 第 163-180 行

```
告警: HighLatency 💥 P99 延迟 > 2s
   → 查 Prometheus: endpoint=/api/report, P99=7.35s
   → 查代码: main.py L163-180
        if random.random() < 0.3:
            delay = random.uniform(2.0, 8.0)  ← 2~8秒 sleep！
            time.sleep(delay)
   → 根因: 30% 概率触发 2~8s 的 sleep，模拟数据库慢查询
   → 修复: 加超时控制 / 异步化 / 加缓存层
```

### 4. Bug2 RCA：BugProcessZeroValue → /api/process → 第 125-136 行

```
告警: BugProcessZeroValueFrequent 💥 频繁非法参数
   → 查 Prometheus: counter=27, 速率 0.052/s
   → 触发一次观察: value=0 → 500 + request_id:"8cff95b6"
   → 查日志 (用 requestId):
        { "event":"bug_triggered_zero_or_negative", "value":0 }
   → 查代码: main.py L125-136
        if value <= 0:          ← 缺少参数校验
            result = 100 / value  ← value=0 → ZeroDivisionError
   → 根因: 未校验用户输入，除零导致 500
   → 修复: if value <= 0: raise HTTPException(400, "value must be positive")
```

### 5. Bug3 RCA：MemoryLeakWarning → /api/cache → 第 228-250 行

```
告警: MemoryLeakWarning 🟡 缓存 16661 bytes > 10000 阈值
   → 查 Prometheus: app_cache_size_bytes = 16661, 持续增长
   → 查代码: main.py L228-250
        _global_cache: list = []     ← 全局变量
        _global_cache.append(data)   ← 只增不删
        _global_cache.append(cache_record)
   → 根因: 全局列表只追加不清理，内存只增不减
   → 修复: LRU 淘汰 / TTL 过期 / 定期清理
```

### 6. RCA 方法论总结

**通用线上问题排查 6 步法**：

```
1️⃣ 告警通知
   └→ Prometheus / AlertManager 触发 firing / pending

2️⃣ 确定问题维度
   └→ 哪个接口？什么时间？什么指标异常？
   关键词: endpoint, time_range, metric

3️⃣ 查指标（Prometheus）
   └→ 错误率 / 延迟分布 / 资源使用 → 缩小范围
   工具: PromQL, Grafana Dashboard

4️⃣ 查日志（structlog / ELK）
   └→ 用 requestId / traceId 关联 → 找到具体请求上下文
   关键字段: request_id, method, path, status, duration

5️⃣ 定位代码
   └→ 从日志中的路径 + 参数 → 对应代码行
   → 如果代码层面找不到 → 排查配置 / 依赖 / 环境

6️⃣ 确认根因 + 复现
   └→ 能稳定复现吗？
   ├→ 代码层: 逻辑 bug、边界条件、并发问题
   ├→ 配置层: 超时设置、资源限制
   └→ 环境层: 依赖版本、网络、磁盘
```

**🔑 关键工具链**：
- `Bug 专项指标`（bug_*_total）→ 快速定位是哪个 Bug
- `requestId` → 串联一次请求的所有日志
- `结构化日志` → 可搜索、可过滤、可聚合

### 7. 阶段④ 检验清单

- [x] 3 条告警都追溯到具体代码行
- [x] HighLatency → /api/report → L163-180
- [x] BugProcessZeroValue → /api/process → L125-136
- [x] MemoryLeakWarning → /api/cache → L228-250
- [x] requestId 串联日志验证通过
- [x] RCA 6 步法总结完成

---

> **下一阶段**：阶段⑤ — 改进闭环（RCA 报告 + 补测试 + 加监控 + 总结面试话术）

---

## 阶段⑤：改进闭环

> 📅 2026-05-14 | ⏱ ~20 分钟

### 1. 做了什么事

完成了从「发现问题」到「防止再犯」的完整闭环：RCA 报告 → 补测试 → 加监控 → 方法论文档化。

### 2. RCA 报告

已生成正式报告：`/workspace/online_issue_tracking/rca_report.md`

报告结构：
- 故障概述 + 时间线
- 3 个 Bug 的根因分析（代码位置、直接原因、根本原因）
- 为什么测试没拦住？
- 改进措施（代码修复 + 测试补充 + 监控改进）
- 经验教训

### 3. 自动化测试补充

测试文件：`/workspace/online_issue_tracking/test_bugs.py`

**14 条用例**，分 4 个测试类：

| 测试类 | 用例数 | 覆盖 Bug |
|--------|--------|---------|
| `TestBug1BoundaryValues` | 6 | 间歇 500 — 边界值/等价类 |
| `TestBug2Performance` | 2 | 慢接口 — 延迟断言 |
| `TestBug3MemoryLeak` | 1 | 内存泄漏 — 浸泡测试 |
| `TestSmoke` | 4 | 冒烟 — 回归保护 |

运行：
```bash
cd /workspace/online_issue_tracking
.venv/bin/pytest test_bugs.py -v   # 14 passed in 1.07s
```

**测试金字塔视角**：
```
        /\
       /浸泡\          ← Bug3: 持续调用检测资源泄漏
      /------\
     / 性能测  \        ← Bug2: 延迟断言、超时控制
    /----------\
   / 边界值测试  \      ← Bug1: 等价类 + 边界值(parametrize)
  /--------------\
 /   冒烟测试      \     ← 回归保护：health/users/404/metrics
/──────────────────\
```

### 4. 监控改进

#### 4.1 当前告警规则（4 条，已于阶段②配置）

| 告警 | 状态 | 价值 |
|------|------|------|
| HighLatency | ✅ firing | 能发现慢接口 |
| BugProcessZeroValueFrequent | ✅ firing | 专项指标，直接定位 Bug |
| MemoryLeakWarning | ✅ pending | 能发现内存趋势 |
| HighErrorRate | 未触发 | 通用错误率兜底 |

#### 4.2 改进建议

| 新增告警 | PromQL | 目的 |
|---------|--------|------|
| **接口可用性** | `up == 0` | 应用挂了立刻知道 |
| **错误率按接口分** | `rate(http_errors_total[5m]) by (endpoint)` | 区分哪个接口出错 |
| **进程内存** | `process_resident_memory_bytes > 200e6` | 更直接的内存告警 |
| **慢请求占比** | `rate(bug_slow_report_total[5m]) / rate(http_requests_total[5m]) > 0.1` | 慢请求占比异常 |

### 5. 面试话术总结

**如果面试官问："你做过线上问题追踪和监控改进吗？"**

> 我通过一个模拟项目完整走了一遍「线上问题 → 监控发现 → 根因定位 → 改进闭环」的流程。我给一个 FastAPI 应用埋了 3 类线上常见 Bug（间歇 500、慢接口、内存泄漏），集成了 Prometheus 指标监控和 alert rules。然后通过压测触发 Bug，在 Prometheus 里观察到 2 条告警从 inactive 变成 firing。接着按照「告警 → PromQL 查指标 → 用 requestId 串日志 → 定位代码行」的路径完成了 RCA，最后补了 14 条 pytest 用例（边界值 + 性能 + 浸泡测试）来防止再犯。整个过程让我理解了测开的核心价值：**每次线上问题都应该反哺测试体系和监控体系**。

**如果追问："TOB 产品怎么做？"**

> TOB 产品部署在客户环境，确实不能像 toC 那样实时监控。但可以做几件事：第一，在客户授权下做健康检查心跳上报；第二，把客户工单当"告警源"做趋势分析，比如某类问题最近增长快说明有共性 bug；第三，在交付前做好充分的边界值测试和浸泡测试，因为客户环境差异大。核心思路是一样的：问题驱动改进。

### 6. 完整项目产出

```
/workspace/online_issue_tracking/
├── PLAN.md              # 5 阶段实操计划
├── README.md            # 📝 完整学习笔记（阶段①-⑤）
├── rca_report.md        # 正式 RCA 报告
├── prometheus.yml        # Prometheus 抓取配置
├── prometheus-alerts.yml # 4 条告警规则
├── load_test.py          # 压测脚本
├── test_bugs.py          # 14 条自动化用例
├── app/
│   ├── main.py           # FastAPI 应用（含 3 Bug + metrics + structlog）
│   ├── requirements.txt
│   └── Dockerfile
├── k8s/
│   └── buggy-api.yaml    # Deployment + Service + Namespace
└── .venv/                # uv Python 3.11 虚拟环境
```

### 7. 5 阶段总检验清单

- [x] 阶段①：构建带 3 类 Bug 的可观测 API + Docker 化
- [x] 阶段②：部署到 k3s + Prometheus 监控 + 4 告警规则
- [x] 阶段③：压测注入故障 + 告警 firing（2 条 🔴）
- [x] 阶段④：RCA 定位到代码行 + 总结 6 步排查法
- [x] 阶段⑤：RCA 报告 + 14 条 pytest + 监控改进 + 面试话术

### 8. 学到的核心能力

| 能力 | 具体体现 |
|------|---------|
| **可观测性设计** | 在代码中埋 metrics（Counter/Histogram/Gauge）+ structlog |
| **Prometheus 运维** | 配置抓取、PromQL 查询、告警规则编写、状态机理解 |
| **k8s 部署** | Deployment/Service/NodePort/探针/资源限制/镜像导入 |
| **RCA 方法论** | 告警→指标→日志→代码 6 步法 |
| **测试体系设计** | 边界值/性能/浸泡/冒烟 多层覆盖 |
| **改进闭环思维** | 每次线上问题 → 反哺测试 + 监控 |

### 9. 踩坑总汇

| 阶段 | 坑 | 解决 |
|------|-----|------|
| ① | GitHub 不通 | ghfast.top 代理下载 |
| ① | Docker 镜像拉超时 | 配置 daocloud/timeweb 镜像加速 |
| ② | kubectl 找不到 | 用 `k3s kubectl` |
| ② | Docker 镜像 containerd 不认 | `k3s ctr images import` |
| ②③ | k3s + Prometheus I/O 爆炸 | 停 k3s，uvicorn 直跑（资源省一半） |
| ③ | 5 并发压测卡死机器 | 降到串行，降低请求速率 |
| ③ | Prometheus lifecycle API 不可用 | 启动加 `--web.enable-lifecycle` |

---

> 🎉 **5 阶段全部完成！** 从零搭建了一个可观测的 buggy 应用，经历了完整的「故障 → 发现 → 定位 → 改进」闭环。
