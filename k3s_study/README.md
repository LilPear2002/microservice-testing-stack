# K3s 学习笔记

> 机器配置：Ubuntu 24.04 / 2C2G / 40G 磁盘  
> k3s 版本：v1.35.4+k3s1（CNCF 认证，API 100% 兼容标准 k8s）

---

## 阶段1：概念入门 + 安装 k3s

> 📅 2026-05-13 | ⏱ ~25 分钟（含镜像加速调试）

---

### 1.1 核心概念

#### K8s 解决什么问题？

传统部署 vs K8s 部署：

```
传统：                        K8s：
应用崩了 → 手动重启           声明"我要 3 个副本"→ 自动维持
流量大了 → 手动加机器          声明"每个副本用 100M 内存"→ 自动调度
配置改了 → 逐个服务器改        改 ConfigMap → 所有 Pod 自动更新
机器宕了 → 半夜被叫醒          Node 挂了 → 自动迁移到健康节点
```

**核心理念：声明式管理** — 你告诉 K8s "期望状态"，它不断地把"实际状态"调整到"期望状态"。

#### 架构简图

```
┌─────────────────────────────────┐
│        Control Plane（控制面）     │
│  ┌──────────┐  ┌─────────────┐  │
│  │ API Server│  │  Scheduler  │  │
│  └──────────┘  └─────────────┘  │
│  ┌──────────┐  ┌─────────────┐  │
│  │Controller │  │    etcd     │  │
│  └──────────┘  └─────────────┘  │
└─────────────────────────────────┘
              │
    ┌─────────┴─────────┐
    ▼                   ▼
┌─────────┐       ┌─────────┐
│ Node 1  │       │ Node 2  │
│ ┌─────┐ │       │ ┌─────┐ │
│ │ Pod │ │       │ │ Pod │ │
│ │ Pod │ │       │ │ Pod │ │
│ └─────┘ │       │ └─────┘ │
└─────────┘       └─────────┘
```

| 组件 | 作用 | k3s 怎么处理 |
|------|------|-------------|
| **API Server** | 一切操作的总入口，kubectl 就跟他说话 | 有 ✅ |
| **Scheduler** | 决定 Pod 放在哪个 Node | 有 ✅ |
| **Controller Manager** | 各种控制器（副本、节点等）| 有 ✅ |
| **etcd** | 存储所有集群状态 | 默认用 SQLite（更轻量），也可切换 etcd |
| **kubelet** | 每个 Node 上跑，管理 Pod 生命周期 | 有 ✅ |
| **kube-proxy** | 网络代理，Service 负载均衡 | 有 ✅ |

#### ✨ 你的集群是单节点模式

Control Plane 和 Node 在同一台机器上——学习用完全够，生产环境要分开。

---

### 1.2 核心术语速查

| 术语 | 一句话解释 | 类比 |
|------|-----------|------|
| **Pod** | 最小调度单位，1 个或多个容器共享网络/存储 | 一个"逻辑主机" |
| **Node** | 跑 Pod 的机器（物理或虚拟） | 一台服务器 |
| **Deployment** | 声明式管理 Pod 副本数、滚动更新 | 应用管家 |
| **Service** | 给 Pod 提供稳定的虚拟 IP | 内部负载均衡器 |
| **ConfigMap** | 非敏感的键值配置 | 配置文件 |
| **Secret** | 敏感信息（密码、Token） | 加密配置 |
| **Namespace** | 逻辑隔离的"虚拟集群" | 文件夹 |

---

### 1.3 环境检查

```bash
$ free -h
              total    used    free   shared  buff/cache   available
Mem:          1.6Gi    567Mi   314Mi   2.5Mi      932Mi       1.1Gi
Swap:            0B      0B      0B

$ df -h /
Filesystem      Size  Used Avail Use% Mounted on
/dev/vda3        40G  4.6G   33G  13% /

$ nproc
2

$ uname -r
6.8.0-63-generic
```

✅ **结论：** 内存 1.1G 可用，k3s 最低要求 512MB，完全够用。

---

### 1.4 安装 k3s

#### 遇到的问题：GitHub 下载慢（国内网络）

GitHub 直连下载 k3s 二进制（75MB）超时。

**解决方案：** 使用 GitHub 加速代理 `ghfast.top` 下载二进制，再手动安装。

```bash
# 通过加速下载
curl -L -o /tmp/k3s \
  "https://ghfast.top/https://github.com/k3s-io/k3s/releases/download/v1.35.4%2Bk3s1/k3s"

# 安装二进制
install -m 755 /tmp/k3s /usr/local/bin/k3s

$ k3s --version
k3s version v1.35.4+k3s1 (5dc8fe68)
go version go1.25.9
```

#### 创建 systemd 服务

```ini
# /etc/systemd/system/k3s.service
[Unit]
Description=Lightweight Kubernetes
After=network-online.target

[Service]
Type=notify
ExecStart=/usr/local/bin/k3s server --write-kubeconfig-mode 644
Restart=always
RestartSec=5s

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable k3s
systemctl start k3s
```

#### 遇到的第二个问题：Docker Hub 镜像拉取超时

k3s 系统 Pod 需要从 Docker Hub 拉镜像（coredns, traefik, metrics-server 等），国内也超时。

**解决方案：** 配置 registry 镜像加速。

```yaml
# /etc/rancher/k3s/registries.yaml
mirrors:
  docker.io:
    endpoint:
      - "https://docker.m.daocloud.io"        # DaoCloud 镜像
      - "https://dockerhub.timeweb.cloud"      # Timeweb 镜像
```

重启 k3s 后生效：

```bash
systemctl restart k3s
```

---

### 1.5 配置 kubectl

kubectl 是操作 K8s 的命令行工具。k3s 自带，通过 `k3s kubectl` 调用。

```bash
# 复制 kubeconfig（认证配置文件）
mkdir -p ~/.kube
cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
chmod 600 ~/.kube/config

# 设置别名（追加到 ~/.bashrc）
alias k="k3s kubectl"
alias kubectl="k3s kubectl"
source <(kubectl completion bash)
complete -F __start_kubectl k

# 立即生效
source ~/.bashrc
```

之后用 `k` 代替 `k3s kubectl`：

```bash
k get nodes     # 等同于 k3s kubectl get nodes
k get pods -A   # 等同于 k3s kubectl get pods --all-namespaces
```

---

### 1.6 验证集群

```bash
k get nodes
```
```
NAME                      STATUS   ROLES           AGE   VERSION
izbp199t5safbjd9nyb5sgz   Ready    control-plane   25s   v1.35.4+k3s1
```

| 字段 | 含义 |
|------|------|
| STATUS = Ready | 节点健康 |
| ROLES = control-plane | 这是控制面节点（也是工作节点） |
| VERSION | k3s 版本 |

```bash
k get namespaces
```
```
NAME              STATUS   AGE
default           Active   58s     # 默认命名空间（不指定就放这）
kube-node-lease   Active   58s     # 节点心跳
kube-public       Active   58s     # 公共资源（如 cluster-info）
kube-system       Active   58s     # 系统组件
```

```bash
k get pods -A
```
```
NAMESPACE     NAME                                      READY   STATUS      RESTARTS   AGE
kube-system   coredns-c4dbffb5f-5z8rr                   1/1     Running     0          3m30s
kube-system   helm-install-traefik-2qb8x                0/1     Completed   2          3m24s
kube-system   helm-install-traefik-crd-xj5nn            0/1     Completed   0          3m24s
kube-system   local-path-provisioner-5c4dc5d66d-bzhtn   1/1     Running     0          3m30s
kube-system   metrics-server-786d997795-664kr           1/1     Running     0          3m29s
kube-system   svclb-traefik-b0131cf0-cfm7j              2/2     Running     0          23s
kube-system   traefik-9bcdbbd9-zq7wg                    1/1     Running     0          23s
```

#### 系统组件详解

| 组件 | 作用 | 类型 |
|------|------|------|
| **coredns** | DNS 服务 — Pod 之间通过名字互相找到 | 常驻 Pod |
| **traefik** | Ingress 控制器 — 外部 HTTP 流量入口 | 常驻 Pod |
| **helm-install-traefik** | Helm 安装任务（一次性，完成后 Completed） | Job |
| **metrics-server** | 收集各 Pod 的 CPU/内存用量 | 常驻 Pod |
| **local-path-provisioner** | 动态存储卷分配（Pod 需要磁盘时） | 常驻 Pod |
| **svclb-traefik** | 把 NodePort 流量负载均衡给 traefik | DaemonSet Pod |

---

### 1.7 常用命令速查

```bash
k get nodes                     # 查看节点
k get pods -A                   # 查看所有 Pod
k get namespaces                # 查看命名空间
k get all -A                    # 查看所有资源
k describe node <名字>           # 查看节点详情
k describe pod -n kube-system <名字>  # 查看 Pod 详情
k get events -A | tail -20      # 查看最近事件
```

---

### 1.8 k3s vs k8s 对比

| 方面 | k8s (kubeadm) | k3s | 说明 |
|------|---------------|-----|------|
| 二进制大小 | ~600MB | ~75MB | k3s 把 API Server、Controller 等打包成一个二进制 |
| 最低内存 | 2GB | 512MB | k3s 用 SQLite 代替 etcd，更省内存 |
| 容器引擎 | 需另装 | 内置 containerd | 不需要单独装 Docker |
| 网络插件 | 需另装 Flannel | 内置 Flannel | 开箱即用 |
| API 兼容性 | 标准 | **100% 兼容** | kubectl 命令、YAML 格式完全一样 |
| 适用场景 | 生产集群 | 边缘/IoT/开发/学习 | **学完的知识无缝迁移！** |

---

<div style="page-break-after: always;"></div>

---

---

## 阶段2：Pod 入门

> 📅 2026-05-13 | ⏱ ~20 分钟

### 2.1 Pod 是什么

Pod 是 K8s 里最小的调度单位。一个 Pod 可以包含 1 个或多个容器：

```
Pod = 1 个"逻辑主机"
├── 容器 A（端口 8080）
├── 容器 B（端口 9090）
├── 共享网络（同一个 IP）
└── 共享存储卷
```

**最简单也最常见的用法：** 1 Pod = 1 容器。

### 2.2 YAML 四要素

每个 K8s 资源 YAML 都有这四个必填字段：

```yaml
apiVersion: v1          # API 版本
kind: Pod               # 资源类型
metadata:               # 元数据（名字、标签、命名空间）
  name: hello-k3s
  labels:
    app: demo
spec:                   # 期望状态（这就是"声明式"）
  containers:
  - name: nginx
    image: nginx:alpine
    ports:
    - containerPort: 80
```

### 2.3 创建 Pod

```bash
k apply -f pod-demo.yaml
k get pods
k get pods -o wide        # 加 -o wide 看更多列（IP、Node）
```

```
NAME        READY   STATUS    RESTARTS   AGE   IP           NODE
hello-k3s   1/1     Running   0          18s   10.42.0.23   izbp199t...
```

| 字段 | 含义 |
|------|------|
| READY 1/1 | 1 个容器就绪 / 共 1 个容器 |
| STATUS Running | 容器在运行 |
| RESTARTS 0 | 从未崩溃重启 |
| IP 10.42.0.23 | Pod 在 Flannel 虚拟网络中的 IP |

### 2.4 describe — 查看详情

```bash
k describe pod hello-k3s
```

关键字段：
```
Container ID: containerd://...  ← k3s 用 containerd（不是 Docker）
State: Running, Ready: True    ← 容器状态
Restart Count: 0               ← 重启次数
Mounts: /var/run/secrets/...   ← 自动挂载的认证 token
```

### 2.5 查看日志（测试核心技能）

```bash
k logs hello-k3s               # 全部日志
k logs -f hello-k3s            # 实时跟踪（Ctrl+C 退出）
k logs --tail=20 hello-k3s     # 最后 20 行
k logs --since=1m hello-k3s    # 最近 1 分钟
```

```
/docker-entrypoint.sh: Configuration complete; ready for start up
nginx/1.29.8 starting...
start worker processes
```

### 2.6 进入容器调试

```bash
k exec hello-k3s -- sh         # 交互式进入
k exec hello-k3s -- ps aux     # 执行单条命令
```

容器内进程：
```
PID 1: nginx master    ← PID 1 是主进程，它挂 = 容器挂
PID 29: nginx worker
PID 30: nginx worker
```

> 💡 **测试技巧：** `k exec` 可以执行任何命令，是排查问题最直接的方式。

### 2.7 端口转发

Pod 的 IP（10.42.x.x）只在集群内可访问。用 port-forward 暴露到本地：

```bash
k port-forward pod/hello-k3s 8080:80 --address 0.0.0.0
```

```
本地 8080 → Pod 80
浏览器打开 localhost:8080 → 看到 Welcome to nginx!
```

### 2.8 清理

```bash
k delete pod hello-k3s
```

### 2.9 阶段2 常用命令总结

| 命令 | 作用 |
|------|------|
| `k apply -f file.yaml` | 创建/更新资源 |
| `k get pods` | 查看 Pod 列表 |
| `k get pods -o wide` | 显示 IP、Node 等额外列 |
| `k describe pod <名称>` | 查看 Pod 详细信息 |
| `k logs <名称>` | 查看日志 |
| `k logs -f <名称>` | 实时跟踪日志 |
| `k exec <名称> -- <命令>` | 在容器内执行命令 |
| `k port-forward pod/<名称> LP:RP` | 端口转发到本地 |
| `k delete pod <名称>` | 删除 Pod |

---

<div style="page-break-after: always;"></div>

---

---

## 阶段3：Deployment + Service

> 📅 2026-05-13 | ⏱ ~25 分钟

### 3.1 为什么需要 Deployment 和 Service

```
直接创建 Pod（阶段2）:
  ❌ Pod 挂了 → 没人管
  ❌ 流量大了 → 手动加 Pod
  ❌ IP 变了 → 要改配置

Deployment + Service:
  ✅ Pod 挂 → Deployment 自动重建
  ✅ IP 变 → Service 自动发现
  ✅ 流量大 → 改 replicas 数字
```

### 3.2 Deployment 三层结构

```
Deployment (web-app)         ← 你操作这一层
    │
    └── ReplicaSet (6bbcc66bc)   ← Deployment 自动管理
            │
            ├── Pod 1 (10.42.0.24)
            └── Pod 2 (10.42.0.25)
```

ReplicaSet 负责维持副本数。**滚动更新时 Deployment 创建新的 RS，旧的缩到 0（但不删除）——这就是回滚能秒级完成的原因。**

### 3.3 创建 Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-app
spec:
  replicas: 2
  selector:
    matchLabels:
      app: web
  template:              # Pod 模板 — 跟 Pod YAML 几乎一样
    metadata:
      labels:
        app: web
    spec:
      containers:
      - name: nginx
        image: nginx:alpine
```

```bash
k apply -f deploy-demo.yaml
k get deploy
k get pods -l app=web
k get rs
```

### 3.4 自愈实验 🔥

删除一个 Pod，Deployment 秒级重建：

```bash
k delete pod web-app-6bbcc66bc-tzphd

# 立即再查：
k get pods -l app=web
```

**结果：**
```
删除前: tzphd + w6pxw
删除后: 9kd5t + w6pxw   ← 新 Pod 2 秒内创建！
```

**事件时间线：**
```
14s ago: Kill old pod
14s ago: Create new pod    ← 同时触发！
13s ago: Pull image (已缓存)
13s ago: Container started
```

> 💡 这就是 K8s 的控制循环（Control Loop）：不断对比 "实际状态" 和 "期望状态"，有差异就修正。

### 3.5 Service — 稳定的访问入口

Pod IP 会变（10.42.0.24 → 10.42.0.30），Service 提供固定 IP：

```yaml
apiVersion: v1
kind: Service
metadata:
  name: web-svc
spec:
  selector:
    app: web
  ports:
  - port: 80
    targetPort: 80
  type: ClusterIP
```

```bash
k apply -f svc-demo.yaml
k get svc
# 输出: web-svc  ClusterIP  10.43.212.117  ← 固定 IP，永远不变
```

**测试 Service 负载均衡：**

```bash
# 创建临时 Pod 访问 Service
k run test --rm -it --image=busybox -- wget -qO- web-svc

# 查看 Service 绑定的 Pod
k get endpoints web-svc
# 输出: 10.42.0.25:80,10.42.0.26:80  ← 自动发现了两个 Pod
```

```
请求 → web-svc (10.43.212.117)
              ├→ Pod A (10.42.0.25)  50%
              └→ Pod B (10.42.0.26)  50%
```

### 3.6 滚动更新

```bash
# 更新镜像
k set image deploy/web-app nginx=nginx:1.25-alpine

# 观察过程
k rollout status deploy/web-app
```

**过程：** 逐步替换，始终有 Pod 可用，用户无感知。

```
旧 RS: Pod 数量 2 → 1 → 0
新 RS: Pod 数量 0 → 1 → 2
```

滚动更新后 Service 端点自动更新：
```
旧: 10.42.0.25, 10.42.0.26  →  新: 10.42.0.28, 10.42.0.29
```

### 3.7 回滚

旧 ReplicaSet 从未删除，只是缩到 0。回滚就是把它扩回来：

```bash
k rollout history deploy/web-app    # 查看版本历史
k rollout undo deploy/web-app       # 回滚到上一版本
```

```
回滚前:  RS-旧=0副本, RS-新=2副本
回滚后:  RS-旧=2副本, RS-新=0副本   ← 秒切！
```

### 3.8 阶段3 常用命令总结

| 命令 | 作用 |
|------|------|
| `k apply -f deploy.yaml` | 创建/更新 Deployment |
| `k get deploy` | 查看 Deployment |
| `k get rs` | 查看 ReplicaSet |
| `k get pods -l app=web` | 按标签筛选 Pod |
| `k delete pod <名称>` | 删除 Pod（观察自愈） |
| `k apply -f svc.yaml` | 创建 Service |
| `k get svc` | 查看 Service |
| `k get endpoints <名称>` | 查看 Service 后端 Pod |
| `k set image deploy/<名> <容器>=<镜像>` | 更新镜像 |
| `k rollout status deploy/<名>` | 观察滚动更新 |
| `k rollout history deploy/<名>` | 查看版本历史 |
| `k rollout undo deploy/<名>` | 回滚 |
| `k run <名> --rm -it --image=...` | 创建临时 Pod 测试 |

---

<div style="page-break-after: always;"></div>

---

---

## 阶段4：ConfigMap + Secret — 配置与安全

> 📅 2026-05-13 | ⏱ ~20 分钟

### 4.1 为什么要配置外置

```
坏做法：配置写死在镜像
  镜像: myapp:v1-staging
  切生产？→ 改代码 → 重建镜像 → 重新部署

好做法：配置外置
  镜像: myapp:v1（通用）
  切生产？→ 只改 ConfigMap → 重启 Pod 即可
```

**测试的黄金场景：** 同一套代码，不同 ConfigMap = 不同环境。

### 4.2 ConfigMap — 非敏感配置

ConfigMap 是键值对存储，两种使用方式：

| 方式 | 适用场景 |
|------|---------|
| **环境变量** (`envFrom`) | 简单值：`APP_ENV`, `LOG_LEVEL` |
| **文件挂载** (`volumeMount`) | 完整配置文件：`nginx.conf`, `app.yaml` |

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
data:
  APP_ENV: "staging"
  LOG_LEVEL: "debug"
  APP_PORT: "8080"
  nginx.conf: |
    server {
      listen 80;
      location / {
        return 200 "Hello from K3s ConfigMap!";
      }
    }
```

```bash
k apply -f configmap-demo.yaml
k get configmap app-config -o yaml
```

### 4.3 Pod 使用 ConfigMap

```yaml
spec:
  containers:
  - name: nginx
    image: nginx:alpine
    envFrom:                          # 方式1: 环境变量
    - configMapRef:
        name: app-config
    volumeMounts:                     # 方式2: 文件挂载
    - name: nginx-config
      mountPath: /etc/nginx/conf.d
  volumes:
  - name: nginx-config
    configMap:
      name: app-config
      items:
      - key: nginx.conf
        path: default.conf
```

```bash
# 验证环境变量
k exec config-demo -- env | grep APP_

# 验证文件挂载（nginx 返回了 ConfigMap 里的自定义页面！）
k port-forward pod/config-demo 8081:80
curl localhost:8081    # → "Hello from K3s ConfigMap!"
```

### 4.4 Secret — 敏感信息

| | ConfigMap | Secret |
|---|-----------|--------|
| 存储 | 明文 | Base64（不是加密！）|
| `k describe` | 显示值 | 仅显示字节数 |
| 用途 | 应用配置 | 密码、Token、证书 |

```bash
# 从字面量创建
k create secret generic db-secret \
  --from-literal=username=admin \
  --from-literal=password=SuperSecret123

# describe 不暴露值
k describe secret db-secret
# Data:
#   password:  14 bytes    ← 只显示大小

# 授权用户可解码
k get secret db-secret -o jsonpath='{.data.password}' | base64 -d
# → SuperSecret123
```

### 4.5 测试场景：切换环境

ConfigMap 更新后，**已有 Pod 不会自动重启** —— 这是关键概念！

```bash
# 初始: APP_ENV=staging
k exec config-demo -- printenv APP_ENV    # → staging

# 修改 ConfigMap
k patch configmap app-config -p '{"data":{"APP_ENV":"production"}}'

# 旧 Pod 仍是旧值！
k exec config-demo -- printenv APP_ENV    # → staging（没变！）

# 重建 Pod 后生效
k delete pod config-demo
k apply -f pod-with-config.yaml
k exec config-demo -- printenv APP_ENV    # → production ✅
```

> 💡 生产环境中用 **Reloader** 或 `k rollout restart deploy` 自动触发重启。

### 4.6 阶段4 常用命令总结

| 命令 | 作用 |
|------|------|
| `k apply -f cm.yaml` | 创建 ConfigMap |
| `k get configmap` | 查看 ConfigMap 列表 |
| `k get configmap <名> -o yaml` | 查看完整内容 |
| `k patch configmap <名> -p '{...}'` | 修改配置 |
| `k create secret generic <名> --from-literal=k=v` | 创建 Secret |
| `k get secret <名> -o jsonpath='{.data.xxx}' \| base64 -d` | 解码 Secret |
| `k exec <pod> -- env \| grep APP_` | 验证环境变量 |
| `k exec <pod> -- cat /path/to/file` | 验证文件挂载 |

---

<div style="page-break-after: always;"></div>

---

---

## 阶段5：综合实战 — whoami 应用

> 📅 2026-05-13 | ⏱ ~30 分钟

### 5.1 部署架构

```
                  ┌──────────────────────────────┐
                  │     whoami-svc (ClusterIP)    │
                  │      10.43.163.230:80         │
                  └──────────┬───────────────────┘
                             │ 负载均衡
              ┌──────────────┴──────────────┐
              ▼                              ▼
  ┌────────────────────┐    ┌────────────────────┐
  │   Pod 1 (gzwhz)    │    │   Pod 2 (wkm7r)    │
  │  traefik/whoami    │    │  traefik/whoami    │
  │  CPU: 50m~200m     │    │  CPU: 50m~200m     │
  │  MEM: 32Mi~128Mi   │    │  MEM: 32Mi~128Mi   │
  │  Liveness: :80/    │    │  Liveness: :80/    │
  │  Readiness: :80/   │    │  Readiness: :80/   │
  └────────────────────┘    └────────────────────┘
         ▲      ▲                  ▲      ▲
         │      │                  │      │
    ConfigMap  Secret         ConfigMap  Secret
  (whoami-config)(whoami-secret)
```

### 5.2 完整 YAML

```yaml
# 一个文件包含 4 个资源（用 --- 分隔）
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: whoami-config
data:
  APP_ENV: "production"
  WELCOME_MSG: "🎉 Hello from K3s!"
---
apiVersion: v1
kind: Secret
metadata:
  name: whoami-secret
stringData:                      # 自动 Base64 编码
  DB_USER: "admin"
  DB_PASS: "K3sLearning2026"
---
apiVersion: v1
kind: Service
metadata:
  name: whoami-svc
spec:
  selector:
    app: whoami
  ports:
  - port: 80
    targetPort: 80
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: whoami
spec:
  replicas: 2
  selector:
    matchLabels: { app: whoami }
  template:
    metadata:
      labels: { app: whoami }
    spec:
      containers:
      - name: app
        image: traefik/whoami     # 端口 80, 返回 HTTP 请求信息
        ports:
        - containerPort: 80
        envFrom:                  # ConfigMap → 环境变量
        - configMapRef:
            name: whoami-config
        env:                      # Secret → 环境变量
        - name: DB_USER
          valueFrom:
            secretKeyRef:
              name: whoami-secret
              key: DB_USER
        - name: DB_PASS
          valueFrom:
            secretKeyRef:
              name: whoami-secret
              key: DB_PASS
        resources:                # 资源限制
          requests:
            memory: "32Mi"
            cpu: "50m"
          limits:
            memory: "128Mi"
            cpu: "200m"
        livenessProbe:            # 存活探针
          httpGet:
            path: /
            port: 80
          initialDelaySeconds: 5
          periodSeconds: 10
          failureThreshold: 3     # 连续 3 次失败 → 重启
        readinessProbe:           # 就绪探针
          httpGet:
            path: /
            port: 80
          initialDelaySeconds: 3
          periodSeconds: 5
          failureThreshold: 2     # 连续 2 次失败 → 停止接流量
```

```bash
k apply -f final-app.yaml
# → configmap/whoami-config created
# → secret/whoami-secret created
# → service/whoami-svc created
# → deployment.apps/whoami created
```

### 5.3 测试结果

```bash
# 端口转发测试
k port-forward svc/whoami-svc 8082:80 &
curl localhost:8082

# 输出:
Hostname: whoami-5f89c5589-9gvbq
IP: 10.42.0.38
RemoteAddr: 127.0.0.1:45710
GET / HTTP/1.1
User-Agent: curl/8.5.0
```

### 5.4 验证健康检查

```bash
k describe pod <pod名> | grep -A2 "Liveness\|Readiness"
```

```
Liveness:  http-get http://:80/ delay=5s period=10s failure=3
Readiness: http-get http://:80/ delay=3s period=5s  failure=2
Conditions: Ready=True, ContainersReady=True  ✅
```

### 5.5 故障模拟

```bash
# 删除一个 Pod
k delete pod whoami-5f89c5589-9gvbq

# 秒级重建
k get pods -l app=whoami
# 删除前: 9gvbq (10.42.0.38) + wkm7r (10.42.0.39)
# 删除后: gzwhz (10.42.0.40) + wkm7r (10.42.0.39)

# Service 端点自动更新
k get endpoints whoami-svc
# → 10.42.0.39:80, 10.42.0.40:80
```

### 5.6 资源限制验证

```bash
k top pods -l app=whoami
```

```
NAME                     CPU(cores)   MEMORY(bytes)
whoami-...-gzwhz         1m           1Mi           ← requests: 50m/32Mi
whoami-...-wkm7r         1m           4Mi           ← limits: 200m/128Mi
```

### 5.7 Request vs Limit

| | Requests | Limits |
|---|----------|--------|
| **含义** | 调度保证（"至少给这些"） | 硬上限（"最多用这些"） |
| **CPU 超限** | N/A | 限流（不杀进程） |
| **内存超限** | N/A | **OOMKilled**（直接杀） |
| **影响调度** | ✅ Scheduler 据此选择 Node | ❌ 不影响调度 |

### 5.8 遇到的坑

1. **镜像错误：** `containous/whoami` 已迁移到 `traefik/whoami`，端口也从 8080 变为 80
2. **探针端口不匹配：** 探针指向 8080 但应用监听 80 → 全部失败
3. **精简镜像无 shell：** `traefik/whoami` 是 from scratch 的 Go 应用，没有 `kill`、`sh` 等命令

### 5.9 五个阶段总览

```
✅ 阶段1: 概念 + 安装     — k3s 集群 Ready
✅ 阶段2: Pod 入门        — 创建/日志/exec/port-forward
✅ 阶段3: Deployment+Service — 副本/自愈/滚动更新/回滚
✅ 阶段4: ConfigMap+Secret  — 配置外置/环境切换
✅ 阶段5: 综合实战        — 健康检查/资源限制/故障模拟
```

**集群当前运行资源：**

| 资源 | 名称 | 用途 |
|------|------|------|
| Deployment | web-app | 阶段3 的 nginx（2 副本） |
| Service | web-svc | web-app 的入口 |
| Deployment | whoami | 阶段5 的 whoami（2 副本） |
| Service | whoami-svc | whoami 的入口 |
| ConfigMap | app-config, whoami-config | 配置 |
| Secret | db-secret, whoami-secret | 敏感信息 |

---

<div style="page-break-after: always;"></div>

---

## 🎓 K3s 学习完成！

### 下一步进阶方向

| 主题 | 内容 |
|------|------|
| **Ingress** | 域名访问、TLS 证书、路径路由 |
| **PersistentVolume** | 持久化存储（Pod 重启数据不丢） |
| **Helm** | K8s 的包管理器（一键部署复杂应用） |
| **HPA** | 自动扩缩容（CPU 高了自动加 Pod） |
| **NetworkPolicy** | 网络隔离（Pod 之间谁能访问谁） |
| **监控** | Prometheus + Grafana 看板 |

---

---

## 🖥️ KubeSphere 是什么

> 你之前在公司用的"去上面查日志"的平台，就是它。

### 一句话理解

```
KubeSphere = K8s 的 "网页版操作界面"

kubectl（你刚学的）  →  命令行操作 K8s
KubeSphere           →  浏览器操作 K8s（底层还是调 kubectl / K8s API）
```

它把 `k get pods`、`k logs`、`k describe` 这些命令变成了**可视化的网页**。

### 你之前的操作 vs 对应命令

| 你在 KubeSphere 做的 | 底层等价命令 |
|----------------------|-------------|
| 点进"工作负载" → 看 Pod 列表 | `k get pods` |
| 点进某个 Pod → 看容器日志 | `k logs <pod-name>` |
| 点进某个 Pod → 看详情/事件 | `k describe pod <pod-name>` |
| 点"终端"进容器 | `k exec -it <pod-name> -- sh` |
| 看 Deployment 副本数 | `k get deploy` |
| 修改镜像版本 | `k set image deploy/xxx ...` |
| 看 ConfigMap 内容 | `k get configmap xxx -o yaml` |

**你之前一直在用 K8s，只是通过网页而不是命令行！**

### KubeSphere 架构（它跟 K8s 的关系）

```
┌──────────────────────────────────────────┐
│              你的浏览器                    │
│       https://kubesphere.company.com      │
└──────────────────┬───────────────────────┘
                   │
┌──────────────────▼───────────────────────┐
│            KubeSphere（Web 平台）          │
│  ┌─────────┐ ┌──────────┐ ┌───────────┐ │
│  │ 工作负载 │ │ 配置管理  │ │ 日志查询   │ │
│  │ (你常用的)│ │(ConfigMap)│ │(你常用的)  │ │
│  └────┬─────┘ └────┬─────┘ └─────┬─────┘ │
│       └─────────────┼─────────────┘       │
│                     ▼                     │
│            调用 K8s API Server             │
└──────────────────┬───────────────────────┘
                   │
┌──────────────────▼───────────────────────┐
│            K8s 集群（k3s/kubeadm）         │
│     Pod  Pod  Deployment  Service  ...    │
└──────────────────────────────────────────┘
```

**KubeSphere 不是替代 K8s，是 K8s 上的一层"皮肤"**—— 底层还是一样的 K8s API，你学的 `kubectl` 命令和 KubeSphere 点按钮做的事情完全一样。

### 常见 K8s 管理平台对比

| 平台 | 特点 | 谁在用 |
|------|------|--------|
| **KubeSphere** | 国产开源，功能全，UI 好看 | 国内中大型企业 |
| **Rancher** | 多集群管理强 | 外企、跨国团队 |
| **Lens** | 桌面应用，轻量 | 开发者个人使用 |
| **k9s** | 终端 UI（非网页） | 喜欢命令行的 DevOps |
| **K8s Dashboard** | K8s 官方自带 | 简单场景 |

### 总结：你现在能做什么

```
以前:  打开 KubeSphere → 找到服务 → 点进容器 → 看日志
       BUT: 不知道"Pod"是什么，不知道为什么有 2 个副本

现在:  用 kubectl 完成同样的事 + 理解底层原理
       k get pods -l app=xxx
       k logs <pod-name>
       k describe pod <pod-name>
       
       → 还知道为什么 Pod 挂了会自动重启（Deployment 自愈）
       → 还知道 ConfigMap 怎么切环境
       → 还知道 Liveness/Readiness 探针是干什么的
```

**你之前是"用户"，现在是"明白原理的用户"了。** 🎉

---

*🎉 恭喜！你已经从零搭建了 K3s 集群，掌握了 K8s 的核心概念和操作。学完 k3s 的知识 100% 适用标准 k8s！*
