# gRPC 学习笔记

> 📅 2026-05-15 开始 | 预计 4 阶段  
> 目录结构：protos/（.proto 定义）、server/（服务端）、client/（客户端）
> python: 3.11 | venv: ~/hermes

---

## 阶段1：概念入门

> 📅 2026-05-15 | ⏱ ~5 分钟

### 1.1 gRPC 是什么

gRPC = Google Remote Procedure Call，Google 开源的 RPC 框架。

```
你的代码         gRPC 框架          对方服务
  │                │
  │ call SayHello()│
  ├───────────────►│ ──序列化──►  Protobuf 二进制  ──► 收到请求
  │                │                                    │
  │    返回结果    │ ◄──反序列化── Protobuf 二进制 ◄─── 返回
  │◄───────────────│
```

### 1.2 核心概念表

| 概念 | 一句话 |
|------|--------|
| **gRPC** | HTTP/2 + Protobuf 的高性能 RPC 框架 |
| **Protobuf** | 二进制序列化格式，比 JSON 小 3-10 倍，快 20-100 倍 |
| **.proto 文件** | 接口契约：定义有哪些方法、入参/返回值长什么样 |
| **HTTP/2** | gRPC 底层协议，支持多路复用、双向流 |
| **stub** | 生成的客户端代理，调用它就像调本地函数 |

### 1.3 gRPC vs REST

| | REST | gRPC |
|---|------|------|
| 协议 | HTTP/1.1 | HTTP/2 |
| 格式 | JSON（文本） | Protobuf（二进制） |
| 接口定义 | 口头约定 / Swagger | .proto 强契约 |
| 性能 | 一般 | 小 3-10 倍，快 20-100 倍 |
| 流式 | ❌ 不支持 | ✅ 原生四种模式 |
| 浏览器支持 | ✅ 原生 | ❌ 需 grpc-web |
| 适用 | 前后端 | 微服务间通信 |

### 1.4 四种 RPC 模式

```
1. Unary（一元调用）
   客户端 → 一个请求 → 服务端 → 一个响应
   等同于普通 HTTP 请求

2. Server Streaming（服务端流）
   客户端 → 一个请求 → 服务端 → 多个响应（流）
   场景：查数据库返回大量行，分批推送

3. Client Streaming（客户端流）
   客户端 → 多个请求（流）→ 服务端 → 一个响应
   场景：上传大文件分块

4. Bidi Streaming（双向流）
   客户端 ⇄ 互相发送流 ⇄ 服务端
   场景：聊天、实时协作
```

### 1.5 Protobuf 基本语法速查

```protobuf
syntax = "proto3";          // 版本声明（必须第一行）

package hello;              // 包名（防命名冲突）

message HelloRequest {      // 定义一个消息类型
  string name = 1;          // 字段类型 字段名 = 字段编号
  int32 age = 2;
}

message HelloResponse {
  string message = 1;
}

service Greeter {           // 定义一个服务
  rpc SayHello (HelloRequest) returns (HelloResponse);  // 方法
}
```

**字段编号：** 1-15 用 1 字节编码，16-2047 用 2 字节。常用字段用 1-15！

---

## 阶段2：第一个 gRPC 服务

> 📅 2026-05-15 | ⏱ ~20 分钟（含环境安装）

### 2.1 安装工具链

```bash
# 用 uv 创建项目级虚拟环境（比标准 venv 快 10-100 倍）
uv venv
source .venv/bin/activate

# 用阿里云镜像装依赖（国内网速飞起）
uv pip install --index-url https://mirrors.aliyun.com/pypi/simple/ grpcio grpcio-tools
# → grpcio 1.80.0, grpcio-tools 1.80.0, protobuf 6.33.6, uv 0.11.14
```

### 2.2 项目结构

```
/workspace/grpc/
├── .venv/                  ← uv 创建的项目虚拟环境（Python 3.11）
├── README.md               ← 就是本文件
├── protos/
│   └── hello.proto         ← 接口契约（Protobuf 定义）
├── hello_pb2.py            ← 生成：消息类（HelloRequest, HelloResponse）
├── hello_pb2_grpc.py       ← 生成：服务类（GreeterStub, GreeterServicer）
├── server/
│   └── server.py           ← 服务端实现
└── client/
    └── client.py           ← 客户端调用
```

### 2.3 hello.proto（接口契约）

```protobuf
syntax = "proto3";
package hello;

message HelloRequest {
  string name = 1;
  int32 age = 2;
}

message HelloResponse {
  string message = 1;
  int64 timestamp = 2;
}

service Greeter {
  rpc SayHello (HelloRequest) returns (HelloResponse);
}
```

### 2.4 生成 Python 代码

```bash
cd /workspace/grpc
python3 -m grpc_tools.protoc \
  -I protos \
  --python_out=. \
  --grpc_python_out=. \
  protos/hello.proto

# 生成:
#   hello_pb2.py      → HelloRequest 类、HelloResponse 类的 Python 定义
#   hello_pb2_grpc.py  → GreeterStub（客户端代理）、GreeterServicer（父类）
```

### 2.5 服务端代码

```python
class GreeterServicer(hello_pb2_grpc.GreeterServicer):
    def SayHello(self, request, context):
        # request.name, request.age 是 Protobuf 自动给的对象属性
        return hello_pb2.HelloResponse(
            message=f"你好 {request.name}! 你今年 {request.age} 岁 🎉",
            timestamp=int(time.time()),
        )

# 启动 gRPC server
server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
hello_pb2_grpc.add_GreeterServicer_to_server(GreeterServicer(), server)
server.add_insecure_port("[::]:50051")
server.start()
```

### 2.6 客户端代码

```python
channel = grpc.insecure_channel("localhost:50051")   # 1. 建立连接
stub = hello_pb2_grpc.GreeterStub(channel)           # 2. 创建 stub
request = hello_pb2.HelloRequest(name="小明", age=25) # 3. 构造请求
response = stub.SayHello(request)                    # 4. 调用！

# response.message → "你好 小明! 服务端收到了你的请求，你今年 25 岁 🎉"
# response.timestamp → 1778811965
```

### 2.7 运行结果

```
启动服务端:
🚀 gRPC 服务端启动在 [::]:50051

运行客户端:
📩 收到响应:
   message:   你好 小明! 服务端收到了你的请求，你今年 25 岁 🎉
   timestamp: 1778811965
```

### 2.8 关键概念

| 概念 | 说明 |
|------|------|
| **stub** | 客户端代理对象，调用 `stub.SayHello()` 就像调本地函数 |
| **channel** | HTTP/2 连接通道，可复用 |
| **insecure_port** | 不加密的端口（生产用 SSL/TLS） |
| **ThreadPoolExecutor** | gRPC 服务器用线程池处理并发请求 |
| **grpc_tools.protoc** | 把 .proto 编译成 Python 代码的工具 |

### 2.9 遇到的坑

1. **模块导入路径**：server.py 和 client.py 在子目录，生成的 pb2 文件在父目录，需加 `PYTHONPATH=/workspace/grpc` 运行
2. **端口 50051**：gRPC 社区约定俗成的默认端口（类比 HTTP 的 80）

### 2.10 调用链路图

```
client.py                        server.py
  │                                │
  │ stub.SayHello(request)         │
  ├─► HelloRequest ─序列化─► Protobuf 二进制 ──► 反序列化 → request 对象
  │                                              │
  │                                           SayHello(request, context)
  │                                              │
  │                                           return HelloResponse(...)
  │                                              │
  │◄─ HelloResponse ◄反序列化◄ Protobuf 二进制 ◄── 序列化
  │
  └─► response.message, response.timestamp
```

---

## 阶段3：4种 RPC 模式

> 📅 2026-05-15 | ⏱ ~30 分钟

### 3.1 四种模式总览

```
模式                  客户端                 服务端              典型场景
────────────────────────────────────────────────────────────────────
Unary         一请求 →              ← 一响应          普通 API 调用
Server Stream 一请求 →              ← 流(多个响应)    查数据库大结果集
Client Stream 流(多个请求) →         ← 一响应          上传文件/日志
Bidi Stream   流 ←→                 ←→ 流             聊天/实时协作
```

**关键语法——.proto 中的区别：**

```protobuf
// Unary: 什么都没有
rpc SayHello (HelloRequest) returns (HelloResponse);

// Server Streaming: returns 前有 stream
rpc TellStory (StoryRequest) returns (stream StoryChunk);

// Client Streaming: 参数前有 stream
rpc UploadLogs (stream LogLine) returns (LogSummary);

// Bidi Streaming: 两边都有 stream
rpc Chat (stream ChatMessage) returns (stream ChatReply);
```

**关键语法——Python 实现中的区别：**

| 模式 | 服务端方法签名 | 返回值 |
|------|---------------|--------|
| Unary | `(request, context)` | `return response` |
| Server Stream | `(request, context)` | `yield response`（生成器） |
| Client Stream | `(request_iterator, context)` | `return response` |
| Bidi Stream | `(request_iterator, context)` | `yield response`（生成器） |

> 💡 **核心理解：** `stream` 关键字在 .proto 中的位置 = Python 中用 `yield` 还是 `return`！
> - `returns (stream X)` → 服务端用 `yield`（生成器）
> - `rpc X (stream Y)` → 服务端参数是 `request_iterator`（迭代器）
> - 两边都有 stream → 服务端 `yield` + `request_iterator`

---

### 3.2 Server Streaming（服务端流）

**场景：** 客户端请求一个故事，服务端分 6 段推送。

**proto：**
```protobuf
rpc TellStory (StoryRequest) returns (stream StoryChunk);
```

**服务端核心代码：**
```python
def TellStory(self, request, context):
    for chunk in chapters:
        time.sleep(0.3)          # 模拟耗时
        yield StoryChunk(content=chunk, chunk_number=i)  # yield = 推送
```

**客户端核心代码：**
```python
story_stream = stub.TellStory(StoryRequest(topic="gRPC"))  # 返回迭代器
for chunk in story_stream:                                  # 逐段接收
    print(f"[{chunk.chunk_number}] {chunk.content}")
```

**运行结果：**
```
📥 服务端开始推送故事片段:
   [1] 有一天，小明走进了 gRPC 的世界...
   [2] 他发现这里的消息都是二进制 Protobuf，比 JSON 小多了！
   [3] 他问服务端：'给我讲一个关于gRPC的故事吧'
   [4] 服务端说：'好的，我一段一段发给你...'
   [5] 小明发现，原来 streaming 就是 Python 的 yield！
   [6] 故事讲完了。小明学会了 Server Streaming 🎉
```

---

### 3.3 Client Streaming（客户端流）

**场景：** 客户端逐条发送 8 行日志，服务端汇总统计。

**proto：**
```protobuf
rpc UploadLogs (stream LogLine) returns (LogSummary);
```

**服务端核心代码：**
```python
def UploadLogs(self, request_iterator, context):
    # request_iterator 是迭代器，每 .next() 取一条
    for log_line in request_iterator:
        counts[log_line.level] += 1
    return LogSummary(total_lines=total, info_count=..., ...)
```

**客户端核心代码：**
```python
def log_generator():
    for level, msg in logs:
        yield LogLine(level=level, message=msg)   # yield 逐条发送

summary = stub.UploadLogs(log_generator())         # 传入生成器
```

**运行结果：**
```
📤 开始流式上传日志（Client Streaming）...
📊 服务端返回汇总:
   总计:     8 条
   INFO:     4 条
   WARN:     2 条
   ERROR:    2 条
```

---

### 3.4 Bidi Streaming（双向流）

**场景：** 聊天室——客户端发消息，服务端实时回复，双方独立收发。

**proto：**
```protobuf
rpc Chat (stream ChatMessage) returns (stream ChatReply);
```

**服务端核心代码：**
```python
def Chat(self, request_iterator, context):
    for msg in request_iterator:    # 边收边回
        if msg.text == "/bye":
            yield ChatReply(user="Server", text=f"再见 {msg.user}!")
            return
        yield ChatReply(user="Server", text=f"收到！'{msg.text}'")
```

**客户端核心代码：**
```python
chat_stream = stub.Chat(message_generator())  # 传入发送生成器
for reply in chat_stream:                     # 同时接收回复
    print(f"[{reply.user}]: {reply.text}")
```

**运行结果：**
```
📥 服务端回复:
   [Server]: 你好 小明! 欢迎来到双向流聊天室 🎉
   [Server]: 好问题 小明，让我想想...
   [Server]: 收到！你说的是: '双向流真的可以同时收发吗？'
   [Server]: 收到！你说的是: '我也来试试双向流！'
   [Server]: 再见 小明! 👋
```

---

### 3.5 四种模式总结表

| | Unary | Server Stream | Client Stream | Bidi Stream |
|---|-------|---------------|---------------|-------------|
| 客户端发送 | 1 个 | 1 个 | N 个（生成器） | N 个（生成器） |
| 服务端返回 | 1 个 | N 个（yield） | 1 个 | N 个（yield） |
| 服务端参数 | `request` | `request` | `request_iterator` | `request_iterator` |
| 服务端 return | `return` | `yield` | `return` | `yield` |
| 客户端调用返回 | 值 | 迭代器 | 值 | 迭代器 |
| 典型场景 | REST 风格 API | 大结果集分页 | 文件上传 | 聊天/协作 |

### 3.6 新增文件清单

```
/workspace/grpc/
├── protos/hello.proto          ← 更新：4 个 rpc 全部定义
├── server/server.py            ← 更新：4 个方法全部实现
└── client/
    ├── client.py               ← Unary（阶段2）
    ├── server_stream.py        ← Server Streaming 客户端
    ├── client_stream.py        ← Client Streaming 客户端
    └── bidi_stream.py          ← Bidi Streaming 客户端
```

---

## 阶段4：测试 + 调试

> 📅 2026-05-15 | ⏱ ~25 分钟

### 4.1 测试方案

```
测试 gRPC 接口的两种方式：

1. grpcurl（命令行）  → 手工调试、快速验证
2. pytest（自动化）   → 回归测试、CI 集成
```

---

### 4.2 grpcurl 命令行测试

#### 安装

```bash
# grpcurl 是 Go 写的单二进制工具
curl -L -o /tmp/grpcurl.tar.gz \
  "https://ghfast.top/https://github.com/fullstorydev/grpcurl/releases/download/v1.9.3/grpcurl_1.9.3_linux_x86_64.tar.gz"
tar -xzf /tmp/grpcurl.tar.gz -C /tmp
install -m 755 /tmp/grpcurl /usr/local/bin/grpcurl

# 版本: v1.9.3
```

#### 前提：服务端开启 reflection

grpcurl 通过 reflection 自动发现服务方法，否则每次要手动传 .proto 文件：

```python
from grpc_reflection.v1alpha import reflection

SERVICE_NAMES = (
    hello_pb2.DESCRIPTOR.services_by_name['Greeter'].full_name,
    reflection.SERVICE_NAME,
)
reflection.enable_server_reflection(SERVICE_NAMES, server)
```

#### 常用命令

```bash
# 列出所有服务
grpcurl -plaintext localhost:50051 list
# → hello.Greeter

# 列出某服务的所有方法
grpcurl -plaintext localhost:50051 list hello.Greeter
# → SayHello, TellStory, UploadLogs, Chat

# 调用 Unary
grpcurl -plaintext -d '{"name":"测试员","age":28}' \
  localhost:50051 hello.Greeter/SayHello

# 调用 Server Stream（结果逐行返回）
grpcurl -plaintext -d '{"topic":"测试"}' \
  localhost:50051 hello.Greeter/TellStory

# 调用 Client Stream（stdin 逐行读）
cat logs.json | grpcurl -plaintext -d @ \
  localhost:50051 hello.Greeter/UploadLogs
```

#### 实际输出

```
SayHello → {"message":"你好 测试员! 你今年 28 岁 🎉","timestamp":"1778813515"}
TellStory → 6 段 chunk 逐行输出
UploadLogs → {"total_lines":3,"info_count":1,"warn_count":1,"error_count":1}
```

> 💡 `-plaintext` 是因为我们没用 TLS 加密。生产环境用 `-insecure` 跳证书验证。

---

### 4.3 pytest 自动化测试

#### 测试结构

```
tests/
└── test_grpc.py
    ├── fixture: 自动启动/停止服务端
    ├── TestUnary (3 个)        — 正常/空名/中文
    ├── TestServerStream (3 个) — 段数/主题/顺序
    ├── TestClientStream (3 个) — 统计/空流/全INFO
    ├── TestBidiStream (4 个)   — 问候/问题/再见/多人
    └── TestEdgeCases (1 个)    — 连接失败超时
```

#### 关键 fixture

```python
@pytest.fixture(scope="module")
def grpc_channel():
    proc = subprocess.Popen(
        [".venv/bin/python", "server/server.py"],
        cwd="/workspace/grpc",
        env={**os.environ, "PYTHONPATH": "/workspace/grpc"},
    )
    time.sleep(1.5)
    channel = grpc.insecure_channel("localhost:50051")
    grpc.channel_ready_future(channel).result(timeout=3)

    yield channel  # 测试用 channel

    channel.close()
    proc.terminate()
```

#### 测试结果

```
$ pytest tests/test_grpc.py -v

TestUnary::test_say_hello_normal        PASSED
TestUnary::test_say_hello_empty_name    PASSED
TestUnary::test_say_hello_chinese       PASSED
TestServerStream::test_tell_story_chunks       PASSED
TestServerStream::test_tell_story_topic_included PASSED
TestServerStream::test_tell_story_order        PASSED
TestClientStream::test_upload_logs_count       PASSED
TestClientStream::test_upload_logs_empty       PASSED
TestClientStream::test_upload_logs_all_info    PASSED
TestBidiStream::test_chat_hello               PASSED
TestBidiStream::test_chat_question            PASSED
TestBidiStream::test_chat_bye                 PASSED
TestBidiStream::test_chat_multi_user          PASSED
TestEdgeCases::test_timeout                   PASSED

========================= 14 passed in 7.01s =========================
```

---

### 4.4 面试话术

**"你怎么测试 gRPC 接口？"**

> 分两个层次：
>
> **手工调试阶段**，用 grpcurl。前提是服务端开启了 reflection，grpcurl 就能自动发现所有方法。
> `grpcurl -plaintext localhost:50051 list` 看有哪些服务，`-d` 传 JSON 参数调方法，流式接口直接看逐行输出。
>
> **自动化测试阶段**，用 pytest。把服务端启动写在 fixture 里（module 级别，所有测试共享一个进程），
> 通过 `grpc.insecure_channel` 创建连接，protobuf 生成的 stub 就是客户端。
> Unary 调 `stub.Method(request)` 拿返回值断言；
> 流式的把返回的迭代器转成 list，验证数量和内容；
> 边界场景包括空值、空流、连接失败超时等。

---

### 4.5 所需依赖

```bash
# 服务端新增
uv pip install --index-url https://mirrors.aliyun.com/pypi/simple/ grpcio-reflection

# 测试
uv pip install --index-url https://mirrors.aliyun.com/pypi/simple/ pytest

# 命令行工具
# grpcurl v1.9.3（Go 二进制，直接下载安装）
```

---

## 🎓 gRPC 学习完成！

```
✅ 阶段1: 概念入门          — gRPC/Protobuf/HTTP/2，对比 REST
✅ 阶段2: 第一个 gRPC       — .proto 编写 → 生成代码 → 跑通
✅ 阶段3: 4种 RPC 模式     — Unary / Server Stream / Client Stream / Bidi
✅ 阶段4: 测试 + 调试      — grpcurl + pytest 14 测试全绿
```

### 最终项目结构

```
/workspace/grpc/
├── .venv/                      ← uv 管理
├── README.md                   ← 完整学习笔记
├── requirements.txt            （待生成）
├── protos/
│   └── hello.proto             ← 接口契约（4 rpc）
├── hello_pb2.py                ← 生成：消息类
├── hello_pb2_grpc.py           ← 生成：stub + servicer
├── server/
│   └── server.py               ← 完整服务端（含 reflection）
├── client/
│   ├── client.py               ← Unary 客户端
│   ├── server_stream.py        ← Server Stream 客户端
│   ├── client_stream.py        ← Client Stream 客户端
│   └── bidi_stream.py          ← Bidi Stream 客户端
└── tests/
    └── test_grpc.py            ← pytest 14 个测试用例
```

### gRPC 核心面试考点

| 问题 | 要点 |
|------|------|
| gRPC vs REST | HTTP/2 vs 1.1、Protobuf vs JSON、.proto 强契约、4 种流式 |
| Protobuf 优势 | 二进制序列化、小 3-10 倍、快 20-100 倍、跨语言 |
| 4 种 RPC 模式 | Unary（一问一答）、Server Stream（yield 推送）、Client Stream（客户端流）、Bidi（双向） |
| 怎么测 gRPC | grpcurl 手工调试 + pytest fixture 自动化测试 |
| stub 是什么 | 客户端代理，调远程方法像调本地函数 |

---

**下一个模块：B1. Redis（内存缓存）** 🔴
