"""
阶段4: WebSocket pytest 测试
覆盖: 基础收发 / 并发连接 / 连接管理 / 心跳 / 大数据
"""
import asyncio
import json
import pytest
import websockets

HOST = "localhost"
PORT = 8767


# ====== Fixture: Echo 服务端（每个测试独立启停） ======
@pytest.fixture
async def server():
    """每个测试独立启动 Echo 服务端"""
    async def handler(ws):
        async for msg in ws:
            await ws.send(f"Echo: {msg}")

    srv = await websockets.serve(handler, HOST, PORT)
    yield srv
    srv.close()
    await srv.wait_closed()


def ws_url():
    return f"ws://{HOST}:{PORT}"


# ====== 基础收发测试 ======
class TestBasic:
    async def test_echo_text(self, server):
        async with websockets.connect(ws_url()) as ws:
            await ws.send("hello")
            reply = await ws.recv()
        assert reply == "Echo: hello"

    async def test_echo_json(self, server):
        msg = json.dumps({"id": 1, "data": "test"})
        async with websockets.connect(ws_url()) as ws:
            await ws.send(msg)
            reply = await ws.recv()
        assert "id" in reply and "test" in reply

    async def test_multiple_messages(self, server):
        async with websockets.connect(ws_url()) as ws:
            for i in range(5):
                await ws.send(str(i))
            for i in range(5):
                reply = await ws.recv()
                assert reply == f"Echo: {i}"


# ====== 并发连接测试 ======
@pytest.mark.asyncio
class TestConcurrency:
    async def test_10_concurrent(self, server):
        async def client(i):
            async with websockets.connect(ws_url()) as ws:
                await ws.send(f"msg-{i}")
                reply = await ws.recv()
                return reply

        results = await asyncio.gather(*[client(i) for i in range(10)])
        assert len(results) == 10
        for i, r in enumerate(results):
            assert r == f"Echo: msg-{i}"

    async def test_interleaved(self, server):
        async with websockets.connect(ws_url()) as ws1, \
                   websockets.connect(ws_url()) as ws2:
            await ws1.send("A1"); await ws2.send("B1")
            await ws1.send("A2"); await ws2.send("B2")

            r1a = await ws1.recv(); r2a = await ws2.recv()
            r1b = await ws1.recv(); r2b = await ws2.recv()

        assert r1a == "Echo: A1"; assert r2a == "Echo: B1"
        assert r1b == "Echo: A2"; assert r2b == "Echo: B2"


# ====== 连接管理测试 ======
@pytest.mark.asyncio
class TestConnection:
    async def test_close_clean(self, server):
        ws = await websockets.connect(ws_url())
        await ws.send("test")
        await ws.recv()
        await ws.close()
        assert ws.state.name == "CLOSED"

    async def test_connect_fail(self, server):
        with pytest.raises((OSError, ConnectionRefusedError,
                            websockets.InvalidURI)):
            async with websockets.connect("ws://localhost:19999",
                                          open_timeout=2):
                pass


# ====== 心跳测试 ======
@pytest.mark.asyncio
class TestHeartbeat:
    async def test_ping_pong(self, server):
        async with websockets.connect(ws_url(), ping_interval=2) as ws:
            pong_waiter = await ws.ping()
            await asyncio.wait_for(pong_waiter, timeout=3)
            await ws.send("alive")
            reply = await ws.recv()
            assert reply == "Echo: alive"


# ====== 大数据测试 ======
@pytest.mark.asyncio
class TestLargeData:
    async def test_large_payload(self, server):
        big_msg = "X" * 50_000
        async with websockets.connect(ws_url(), max_size=2**20) as ws:
            await ws.send(big_msg)
            reply = await ws.recv()
        assert reply == f"Echo: {big_msg}"
