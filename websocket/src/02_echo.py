"""
阶段2: WebSocket Echo 服务 — 收发什么就回什么
"""
import asyncio
import websockets
import json
import time

HOST = "localhost"
PORT = 8765


# ====== 服务端 ======
async def echo_handler(websocket):
    """每连接回调：收到消息原样返回"""
    client = f"{websocket.remote_address}"
    print(f"  ✅ [{client}] 已连接")
    try:
        async for message in websocket:
            print(f"  ← [{client}]: {message[:50]}")
            await websocket.send(f"Echo: {message}")
            print(f"  → [{client}]: Echo: {message[:50]}")
    except websockets.exceptions.ConnectionClosed:
        print(f"  ❌ [{client}] 已断开")


async def start_server():
    server = await websockets.serve(echo_handler, HOST, PORT)
    print(f"🚀 WebSocket Echo 服务启动在 ws://{HOST}:{PORT}")
    return server


# ====== 客户端测试 ======
async def test_echo():
    """测试基础收发"""
    print("\n=== 测试1: 基础 Echo ===")
    uri = f"ws://{HOST}:{PORT}"
    async with websockets.connect(uri) as ws:
        await ws.send("Hello WebSocket!")
        reply = await ws.recv()
        print(f"  发送: Hello WebSocket!")
        print(f"  收到: {reply}")
        assert reply == "Echo: Hello WebSocket!"
        print("  ✅ 通过")

    print("\n=== 测试2: JSON 消息 ===")
    async with websockets.connect(uri) as ws:
        msg = json.dumps({"type": "order", "id": 123, "product": "iPhone"})
        await ws.send(msg)
        reply = await ws.recv()
        print(f"  发送: {msg}")
        print(f"  收到: {reply}")
        assert "order" in reply and "iPhone" in reply
        print("  ✅ 通过")

    print("\n=== 测试3: 中文消息 ===")
    async with websockets.connect(uri) as ws:
        await ws.send("你好世界 🌍")
        reply = await ws.recv()
        print(f"  发送: 你好世界 🌍")
        print(f"  收到: {reply}")
        assert "你好世界" in reply
        print("  ✅ 通过")


async def main():
    server = await start_server()
    try:
        await test_echo()
        print("\n🎉 Echo 服务全部测试通过！")
    finally:
        server.close()
        await server.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
