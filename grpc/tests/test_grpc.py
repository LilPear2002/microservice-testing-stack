"""
阶段4: gRPC 服务 pytest 测试
覆盖全部 4 种 RPC 模式 + 边界场景
"""
import pytest
import grpc
import time
import subprocess
import hello_pb2
import hello_pb2_grpc


# ====== Fixture: 启动/停止服务端 ======
@pytest.fixture(scope="module")
def grpc_channel():
    """在所有测试前启动服务端，测试完后关闭"""
    import sys, os
    sys.path.insert(0, "/workspace/grpc")
    # 启动服务端
    proc = subprocess.Popen(
        ["/workspace/grpc/.venv/bin/python", "server/server.py"],
        cwd="/workspace/grpc",
        env={**os.environ, "PYTHONPATH": "/workspace/grpc"},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    time.sleep(1.5)  # 等待启动

    channel = grpc.insecure_channel("localhost:50051")
    try:
        grpc.channel_ready_future(channel).result(timeout=3)
    except grpc.FutureTimeoutError:
        proc.kill()
        pytest.fail("服务端启动超时")

    yield channel

    channel.close()
    proc.terminate()
    proc.wait(timeout=5)


@pytest.fixture
def stub(grpc_channel):
    """创建客户端 stub"""
    return hello_pb2_grpc.GreeterStub(grpc_channel)


# ====== 1. Unary 测试 ======
class TestUnary:
    def test_say_hello_normal(self, stub):
        """正常调用"""
        resp = stub.SayHello(hello_pb2.HelloRequest(name="小明", age=25))
        assert "小明" in resp.message
        assert "25" in resp.message
        assert resp.timestamp > 0

    def test_say_hello_empty_name(self, stub):
        """空名字"""
        resp = stub.SayHello(hello_pb2.HelloRequest(name="", age=0))
        assert resp.message != ""  # 不应崩溃
        assert resp.timestamp > 0

    def test_say_hello_chinese(self, stub):
        """中文名"""
        resp = stub.SayHello(hello_pb2.HelloRequest(name="张三", age=30))
        assert "张三" in resp.message


# ====== 2. Server Streaming 测试 ======
class TestServerStream:
    def test_tell_story_chunks(self, stub):
        """接收多段故事"""
        chunks = list(stub.TellStory(hello_pb2.StoryRequest(topic="测试")))
        assert len(chunks) == 6
        assert chunks[0].chunk_number == 1
        assert chunks[-1].chunk_number == 6
        # 每段都不为空
        for chunk in chunks:
            assert chunk.content != ""
            assert 1 <= chunk.chunk_number <= 6

    def test_tell_story_topic_included(self, stub):
        """主题包含在故事中"""
        chunks = list(stub.TellStory(hello_pb2.StoryRequest(topic="Redis")))
        # 某一段应该包含主题
        all_text = "".join(c.content for c in chunks)
        assert "Redis" in all_text

    def test_tell_story_order(self, stub):
        """段号严格递增"""
        chunks = list(stub.TellStory(hello_pb2.StoryRequest(topic="测试")))
        numbers = [c.chunk_number for c in chunks]
        assert numbers == sorted(numbers)
        assert numbers == list(range(1, 7))


# ====== 3. Client Streaming 测试 ======
class TestClientStream:
    def _make_logs(self, log_list):
        for level, msg in log_list:
            yield hello_pb2.LogLine(level=level, message=msg, timestamp=0)

    def test_upload_logs_count(self, stub):
        """统计正确性"""
        logs = [
            ("INFO", "a"), ("INFO", "b"),
            ("WARN", "c"),
            ("ERROR", "d"), ("ERROR", "e"),
        ]
        summary = stub.UploadLogs(self._make_logs(logs))
        assert summary.total_lines == 5
        assert summary.info_count == 2
        assert summary.warn_count == 1
        assert summary.error_count == 2

    def test_upload_logs_empty(self, stub):
        """空日志流"""
        summary = stub.UploadLogs(self._make_logs([]))
        assert summary.total_lines == 0
        assert summary.info_count == 0

    def test_upload_logs_all_info(self, stub):
        """全部 INFO"""
        logs = [("INFO", f"msg{i}") for i in range(10)]
        summary = stub.UploadLogs(self._make_logs(logs))
        assert summary.total_lines == 10
        assert summary.info_count == 10
        assert summary.warn_count == 0
        assert summary.error_count == 0


# ====== 4. Bidi Streaming 测试 ======
class TestBidiStream:
    def _make_messages(self, msgs):
        for user, text in msgs:
            yield hello_pb2.ChatMessage(user=user, text=text)

    def test_chat_hello(self, stub):
        """你好 → 收到欢迎回复"""
        msgs = [("小明", "你好！")]
        replies = list(stub.Chat(self._make_messages(msgs)))
        assert len(replies) == 1
        assert "小明" in replies[0].text
        assert "欢迎" in replies[0].text or "你好" in replies[0].text

    def test_chat_question(self, stub):
        """带问号 → 服务端识别为问题"""
        msgs = [("小明", "这个怎么用?")]
        replies = list(stub.Chat(self._make_messages(msgs)))
        assert len(replies) >= 1

    def test_chat_bye(self, stub):
        """/bye 后服务端不再回复"""
        msgs = [("小明", "你好"), ("小明", "/bye"), ("小明", "这句不会被处理")]
        replies = list(stub.Chat(self._make_messages(msgs)))
        # /bye 是第二条，服务端处理到它就 return，不会处理第三条
        # 所以回复数 ≤ 2（收到 /bye 时回复"再见"然后停止）
        assert len(replies) <= 2
        assert any("再见" in r.text for r in replies)

    def test_chat_multi_user(self, stub):
        """多人聊天"""
        msgs = [
            ("小明", "你好"),
            ("小红", "你好"),  # 小红不是"你好 小明"模式
        ]
        replies = list(stub.Chat(self._make_messages(msgs)))
        assert len(replies) == 2


# ====== 5. 边界 & 异常测试 ======
class TestEdgeCases:
    def test_timeout(self, grpc_channel):
        """连接不存在的端口应立即失败"""
        bad_channel = grpc.insecure_channel("localhost:19999")
        bad_stub = hello_pb2_grpc.GreeterStub(bad_channel)
        with pytest.raises(grpc.RpcError):
            bad_stub.SayHello(
                hello_pb2.HelloRequest(name="test", age=0),
                timeout=1,
            )
        bad_channel.close()
