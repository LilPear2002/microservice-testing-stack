# WebSocket 学习笔记

> 📅 2026-05-15 | websockets: 16.0 | pytest-asyncio: 1.3.0

---

## 阶段1：概念入门

> ⏱ ~5 分钟

### 1.1 WebSocket 解决什么问题

```                     
         HTTP（你熟悉的）                     WebSocket
         ──────────────                     ─────────
连接      请求→响应→断开                      一次握手→持久连接
方向      客户端主动，服务端被动              全双工，双方随时发
开销      每次带完整 header                   帧头只有2-6字节
实时性    轮询（延迟高）                      推送（毫秒级）

类比:    HTTP = 寄信（每次写信封）           WebSocket = 打电话（拨通后随便说）
```

### 1.2 握手过程

```
客户端                                     服务端
  │                                          │
  │ GET /chat HTTP/1.1                       │
  │ Upgrade: websocket                       │
  │ Connection: Upgrade                      │
  │ Sec-WebSocket-Key: xxx                   │
  │─────────────────────────────────────────→│
  │                                          │
  │                     HTTP/1.1 101 Switching Protocols
  │                     Upgrade: websocket
  │                     Sec-WebSocket-Accept: yyy
  │←─────────────────────────────────────────│
  │                                          │
  │ ═══════ WebSocket 连接建立 ═══════        │
  │                                          │
  │  text: "你好"  ───────────────────────→   │
  │  ←────────────  text: "欢迎!"             │
  │  binary: <data> ──────────────────────→   │
  │               ...随时收发...              │
```

### 1.3 WebSocket vs 长轮询 vs SSE

| | 短轮询 | 长轮询 | SSE | WebSocket |
|---|--------|--------|-----|-----------|
| 方向 | 客户端→服务端 | 客户端→服务端 | 服务端→客户端 | 双向 |
| 连接 | 每次新建 | 挂起等响应 | 一条长连接 | 一条长连接 |
| 协议 | HTTP | HTTP | HTTP | ws:// |
| 开销 | 极高 | 高 | 低 | 极低 |
| 场景 | 简单查询 | 通知 | 股票推送 | 聊天/游戏 |

### 1.4 测开关注点

```
1. 连接建立     → 握手是否成功？101状态码？
2. 消息收发     → 发什么收什么？乱序？丢帧？
3. 断线重连     → 网络闪断后能否自动恢复？
4. 并发连接     → 1000个连接同时在线，服务端撑得住吗？
5. 心跳机制     → ping/pong 是否正常？超时是否自动断开？
```

---

## 阶段2：Echo 服务 — 第一个 WebSocket 应用

> ⏱ ~10 分钟 | 脚本: `src/02_echo.py`

### 2.1 服务端

```python
import websockets

async def handler(websocket):
    async for message in websocket:       # 持续接收
        await websocket.send(f"Echo: {message}")  # 原样返回

async def main():
    server = await websockets.serve(handler, "localhost", 8765)
    await server.wait_closed()
```

### 2.2 客户端

```python
async with websockets.connect("ws://localhost:8765") as ws:
    await ws.send("Hello WebSocket!")
    reply = await ws.recv()              # 等待回复
    print(reply)                          # → "Echo: Hello WebSocket!"
```

### 2.3 运行结果

```
发送: Hello WebSocket!  → 收到: Echo: Hello WebSocket!
发送: {"id": 123, ...}  → 收到: Echo: {"id": 123, ...}
发送: 你好世界 🌍        → 收到: Echo: 你好世界 🌍
```

---

## 阶段3：多人聊天室 + 心跳

> ⏱ ~15 分钟 | 脚本: `src/03_chat.py`

### 3.1 核心机制

```
聊天室服务端:
  - 维护 connected = {websocket: username}
  - 收到消息 → broadcast() 发给所有人
  - 断开 → 移出 connected + 广播离开通知

客户端:
  - 连接 ws:// → 发送 {"type": "join", "user": "小明"}
  - 发送 {"type": "msg", "text": "大家好"}
  - 收到所有人的广播消息
  - 心跳: ping_interval=5, ping_timeout=3
```

### 3.2 广播函数

```python
async def broadcast(message):
    data = json.dumps(message)
    await asyncio.gather(
        *[ws.send(data) for ws in connected],
        return_exceptions=True  # 不怕单个客户端断线
    )
```

### 3.3 运行结果

```
3个用户同时在线:
  小明: 系统消息=3条 (join通知)
  小红: 系统消息=2条, 聊天消息=1条
  小李: 系统消息=1条, 聊天消息=1条

✅ 所有人都收到了别人的消息
✅ 离开时广播通知
✅ ping/pong 心跳维持连接
```

---

## 阶段4：pytest 测试

> ⏱ ~10 分钟 | 测试: `tests/test_websocket.py`

### 4.1 测试结构

```
tests/test_websocket.py  (pytest.ini: asyncio_mode=auto)
├── fixture: 每个测试独立启停 Echo 服务端
├── TestBasic (3)     — 文本/JSON/连续5条
├── TestConcurrency (2) — 10并发/交错收发
├── TestConnection (2)  — 正常关闭/连接失败
├── TestHeartbeat (1)   — ping/pong
└── TestLargeData (1)   — 50KB大消息
```

### 4.2 测试成绩

```
9 passed in 0.08s
├── TestBasic         ×3   echo文本 / echoJSON / 连续5条
├── TestConcurrency   ×2   10并发 / 交错收发
├── TestConnection    ×2   正常关闭 / 连接失败
├── TestHeartbeat     ×1   ping/pong
└── TestLargeData     ×1   50KB不丢失
```

### 4.3 关键 fixture

```python
@pytest.fixture
async def server():
    async def handler(ws):
        async for msg in ws:
            await ws.send(f"Echo: {msg}")
    srv = await websockets.serve(handler, "localhost", 8767)
    yield srv
    srv.close()
    await srv.wait_closed()
```

### 4.4 面试话术

**"WebSocket 和 HTTP 长轮询有什么区别？"**

> WebSocket 是 TCP 层的全双工协议，一次握手后双方随时发送，帧头仅 2-6 字节。
> 长轮询本质还是 HTTP —— 客户端发起请求，服务端挂起到有数据才返回，但每次都要重新建 HTTP 连接。
> WebSocket 的额外开销极小，适合高频实时场景（聊天、游戏、行情推送）。

**"怎么测试 WebSocket 连接？"**

> 用 pytest + pytest-asyncio，fixture 里启动服务端，每个测试建立 ws:// 连接。
> 基础测试验证发什么收什么；并发测试用 asyncio.gather 起多个客户端。
> 心跳测试通过 ping/pong 帧验证；断线测试模拟 connect_fail。
> 压力测试可以用 locust 或自定义脚本建立 N 个长连接测量内存/延迟。

---

## 🎓 WebSocket 学习完成！

### 项目结构

```
/workspace/websocket/
├── .venv/
├── pytest.ini               ← asyncio_mode=auto
├── README.md
├── src/
│   ├── 02_echo.py           ← Echo 服务端+客户端
│   └── 03_chat.py           ← 多人聊天室+广播
└── tests/
    └── test_websocket.py    ← 9 个测试用例
```

### WebSocket 面试核心考点

| 问题 | 要点 |
|------|------|
| WebSocket vs HTTP | 全双工 vs 请求响应、帧头2-6字节 vs 完整header |
| 握手过程 | HTTP Upgrade 101 → Sec-WebSocket-Key/Accept |
| vs 长轮询 vs SSE | 双向 vs 服务端推 vs 单向推送 |
| 心跳机制 | ping/pong 帧，超时断开，防止假连接 |
| 怎么测并发 | asyncio.gather N个客户端，测消息正确性 |

---

**下一个模块：B3. Elasticsearch（搜索引擎）** 🔍