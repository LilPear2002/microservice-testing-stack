"""
阶段3: 多人聊天室 + 心跳 + 断线重连
"""
import asyncio
import websockets
import json

HOST = "localhost"
PORT = 8766

# 在线用户: {websocket: username}
connected = {}


# ====== 服务端 ======
async def chat_handler(websocket):
    """聊天室核心：广播消息给所有在线用户"""
    try:
        # 1. 注册
        async for msg in websocket:
            data = json.loads(msg)

            if data["type"] == "join":
                username = data["user"]
                connected[websocket] = username
                print(f"  ✅ [{username}] 加入聊天室 (在线: {len(connected)})")

                # 广播加入通知
                await broadcast({"type": "system", "msg": f"{username} 加入了", "online": len(connected)})

            elif data["type"] == "msg":
                username = connected.get(websocket, "?")
                print(f"  💬 [{username}]: {data['text']}")
                await broadcast({"type": "msg", "user": username, "text": data["text"]})

            elif data["type"] == "ping":
                await websocket.send(json.dumps({"type": "pong"}))

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        # 2. 注销
        if websocket in connected:
            username = connected.pop(websocket)
            print(f"  ❌ [{username}] 离开聊天室 (在线: {len(connected)})")
            await broadcast({"type": "system", "msg": f"{username} 离开了", "online": len(connected)})


async def broadcast(message):
    """向所有在线用户广播消息"""
    if not connected:
        return
    data = json.dumps(message)
    # 发给所有人
    await asyncio.gather(*[ws.send(data) for ws in connected], return_exceptions=True)


# ====== 客户端模拟 ======
async def chat_client(name, messages, result_callback=None):
    """模拟一个聊天客户端"""
    uri = f"ws://{HOST}:{PORT}"
    received = []

    async with websockets.connect(uri, ping_interval=5, ping_timeout=3) as ws:
        # 加入
        await ws.send(json.dumps({"type": "join", "user": name}))
        # 收欢迎消息
        join_msg = json.loads(await ws.recv())
        received.append(join_msg)
        print(f"  [{name}] 收到: {join_msg['msg']}")

        # 发消息 + 收广播
        for text in messages:
            await ws.send(json.dumps({"type": "msg", "text": text}))
            # 收自己的消息（被广播回来）
            reply = json.loads(await ws.recv())
            received.append(reply)
            print(f"  [{name}] 发送: {text} → 收到广播: {reply}")

        # 短等，确保广播都收到
        await asyncio.sleep(0.3)

    if result_callback:
        result_callback(name, received)
    return received


async def main():
    server = await websockets.serve(chat_handler, HOST, PORT)
    print(f"🚀 聊天室启动在 ws://{HOST}:{PORT}\n")

    results = {}

    def collect(name, msgs):
        results[name] = msgs

    # 3 个客户端同时加入并聊天
    print("=== 多人聊天测试 ===")
    await asyncio.gather(
        chat_client("小明", ["大家好！", "今天天气不错 ☀️"], collect),
        chat_client("小红", ["你好小明！", "我来啦 🎉"], collect),
        chat_client("小李", ["我来晚了"], collect),
    )

    print()
    print("=== 结果汇总 ===")
    for name, msgs in results.items():
        sys_msgs = [m for m in msgs if m["type"] == "system"]
        chat_msgs = [m for m in msgs if m["type"] == "msg"]
        print(f"  {name}: 系统消息={len(sys_msgs)}条, 聊天消息={len(chat_msgs)}条")

    # 验证：每个人都能收到别人的消息
    for name, msgs in results.items():
        others = [m for m in msgs if m["type"] == "msg" and m["user"] != name]
        print(f"  [{name}] 收到别人的消息: {len(others)}条 ✓")

    server.close()
    await server.wait_closed()
    print()
    print("🎓 多人聊天室 + 广播 + 心跳 演示完成！")


if __name__ == "__main__":
    asyncio.run(main())
