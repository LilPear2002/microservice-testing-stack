"""
阶段3: Server Streaming 客户端
发送一个请求，接收服务端流式推送的多段响应
"""
import grpc
import hello_pb2
import hello_pb2_grpc


def run():
    channel = grpc.insecure_channel("localhost:50051")
    stub = hello_pb2_grpc.GreeterStub(channel)

    print("📖 请求 TellStory（服务端流）...")
    print("   客户端: '给我讲一个关于 <gRPC> 的故事'")
    print()

    # 调用返回的不是一个值，而是一个迭代器！
    story_stream = stub.TellStory(hello_pb2.StoryRequest(topic="gRPC"))

    print("📥 服务端开始推送故事片段:")
    for chunk in story_stream:
        print(f"   [{chunk.chunk_number}] {chunk.content}")

    print()
    print("✅ 故事接收完毕！所有 chunk 都是服务端主动推送的")


if __name__ == "__main__":
    run()
