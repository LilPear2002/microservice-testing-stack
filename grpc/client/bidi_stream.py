"""
阶段3: Bidi Streaming 客户端
双向流 — 客户端可以随时发，服务端可以随时回
"""
import grpc
import hello_pb2
import hello_pb2_grpc
import time
import threading


def run():
    channel = grpc.insecure_channel("localhost:50051")
    stub = hello_pb2_grpc.GreeterStub(channel)

    def message_generator():
        """在另一个线程中逐条发送消息"""
        messages = [
            ("小明", "你好！"),
            ("小明", "我想问个问题?"),
            ("小明", "双向流真的可以同时收发吗？"),
            ("小红", "我也来试试双向流！"),
            ("小明", "/bye"),
        ]
        for user, text in messages:
            time.sleep(0.5)
            yield hello_pb2.ChatMessage(user=user, text=text)

    print("💬 进入双向流聊天室（Bidi Streaming）...")
    print("   客户端和服务端可以同时收发消息")
    print()

    # 返回的也是迭代器
    chat_stream = stub.Chat(message_generator())

    print("📥 服务端回复:")
    for reply in chat_stream:
        print(f"   [{reply.user}]: {reply.text}")

    print()
    print("✅ 双向流通话结束！")


if __name__ == "__main__":
    run()
