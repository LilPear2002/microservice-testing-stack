"""
阶段2: 第一个 gRPC 客户端
用 stub 调用远程方法，像调本地函数一样
"""
import grpc
import hello_pb2
import hello_pb2_grpc


def run():
    # 1. 建立连接（HTTP/2 channel）
    channel = grpc.insecure_channel("localhost:50051")

    # 2. 创建 stub（客户端代理）
    stub = hello_pb2_grpc.GreeterStub(channel)

    # 3. 构造请求
    request = hello_pb2.HelloRequest(name="小明", age=25)

    # 4. 发起调用 — 跟调本地函数一样！
    response = stub.SayHello(request)

    # 5. 打印结果
    print(f"📩 收到响应:")
    print(f"   message:   {response.message}")
    print(f"   timestamp: {response.timestamp}")
    print(f"   (服务端时间: {response.timestamp})")


if __name__ == "__main__":
    run()
