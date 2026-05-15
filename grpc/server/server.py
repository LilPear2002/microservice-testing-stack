"""
阶段3+4: gRPC 4 种 RPC 模式 — 完整服务端（含 reflection）
"""
import grpc
import time
from concurrent import futures
from grpc_reflection.v1alpha import reflection
import hello_pb2
import hello_pb2_grpc


class GreeterServicer(hello_pb2_grpc.GreeterServicer):

    # ====== 1. Unary：普通一问一答 ======
    def SayHello(self, request, context):
        print(f"[Unary] 收到: name={request.name}, age={request.age}")
        return hello_pb2.HelloResponse(
            message=f"你好 {request.name}! 你今年 {request.age} 岁 🎉",
            timestamp=int(time.time()),
        )

    # ====== 2. Server Streaming：服务端持续推送 ======
    def TellStory(self, request, context):
        """
        客户端发一个请求，服务端 yield 多次
        生成器函数 = 流式响应
        """
        print(f"[ServerStream] 收到: topic={request.topic}")
        chapters = [
            "有一天，小明走进了 gRPC 的世界...",
            "他发现这里的消息都是二进制 Protobuf，比 JSON 小多了！",
            f"他问服务端：'给我讲一个关于{request.topic}的故事吧'",
            "服务端说：'好的，我一段一段发给你...'",
            "小明发现，原来 streaming 就是 Python 的 yield！",
            "故事讲完了。小明学会了 Server Streaming 🎉",
        ]
        for i, chunk_text in enumerate(chapters, 1):
            time.sleep(0.3)  # 模拟耗时（让客户端能看到逐段到达）
            yield hello_pb2.StoryChunk(content=chunk_text, chunk_number=i)
            print(f"  → 第{i}段已发送")

    # ====== 3. Client Streaming：客户端持续发送 ======
    def UploadLogs(self, request_iterator, context):
        """
        客户端流式发送，服务端全部收完后返回一个响应
        request_iterator 是一个迭代器，每次 .next() 拿一个 LogLine
        """
        print(f"[ClientStream] 开始接收日志流...")
        total = 0
        counts = {"INFO": 0, "WARN": 0, "ERROR": 0}

        for log_line in request_iterator:
            total += 1
            level = log_line.level if log_line.level in counts else "INFO"
            counts[level] = counts.get(level, 0) + 1
            print(f"  ← 收到: [{level}] {log_line.message}")

        print(f"[ClientStream] 流结束，共 {total} 条")
        return hello_pb2.LogSummary(
            total_lines=total,
            info_count=counts.get("INFO", 0),
            warn_count=counts.get("WARN", 0),
            error_count=counts.get("ERROR", 0),
        )

    # ====== 4. Bidi Streaming：双向自由收发 ======
    def Chat(self, request_iterator, context):
        """
        双向流：接收 request_iterator，同时 yield 响应
        收发顺序完全自由——可以收一条回一条，也可以收多条回一条
        """
        print(f"[Bidi] 聊天室开启...")
        for msg in request_iterator:
            print(f"  ← [{msg.user}]: {msg.text}")

            if msg.text == "/bye":
                yield hello_pb2.ChatReply(
                    user="Server", text=f"再见 {msg.user}! 👋"
                )
                print(f"[Bidi] 聊天结束")
                return

            # 根据消息内容回复
            if "你好" in msg.text or "hello" in msg.text.lower():
                reply_text = f"你好 {msg.user}! 欢迎来到双向流聊天室 🎉"
            elif "?" in msg.text:
                reply_text = f"好问题 {msg.user}，让我想想..."
            else:
                reply_text = f"收到！你说的是: '{msg.text}'（双向流模式下发的）"

            yield hello_pb2.ChatReply(user="Server", text=reply_text)
            print(f"  → [Server]: {reply_text}")


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    hello_pb2_grpc.add_GreeterServicer_to_server(GreeterServicer(), server)
    server.add_insecure_port("[::]:50051")
    # 开启 reflection — grpcurl 等工具可以自动发现所有方法
    SERVICE_NAMES = (
        hello_pb2.DESCRIPTOR.services_by_name['Greeter'].full_name,
        reflection.SERVICE_NAME,
    )
    reflection.enable_server_reflection(SERVICE_NAMES, server)
    server.start()
    print("🚀 gRPC 服务端启动在 [::]:50051（支持 4 种 RPC 模式）")
    print("   Unary / ServerStream / ClientStream / Bidi 全部就绪")
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
