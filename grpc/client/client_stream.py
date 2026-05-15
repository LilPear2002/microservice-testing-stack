"""
阶段3: Client Streaming 客户端
客户端流式发送多条数据，服务端汇总后返回一个响应
"""
import grpc
import hello_pb2
import hello_pb2_grpc
import time


def log_generator():
    """生成器函数 — 逐条 yield 日志，模拟流式上传"""
    logs = [
        ("INFO", "应用启动完成"),
        ("INFO", "监听端口 8080"),
        ("WARN", "内存使用率 85%，请关注"),
        ("INFO", "处理请求 /api/users"),
        ("ERROR", "数据库连接超时，正在重试..."),
        ("WARN", "重试第 2 次..."),
        ("INFO", "数据库重连成功"),
        ("ERROR", "磁盘空间不足 10%"),
    ]
    for level, msg in logs:
        time.sleep(0.15)  # 模拟逐条产生
        yield hello_pb2.LogLine(level=level, message=msg, timestamp=int(time.time()))


def run():
    channel = grpc.insecure_channel("localhost:50051")
    stub = hello_pb2_grpc.GreeterStub(channel)

    print("📤 开始流式上传日志（Client Streaming）...")
    print("   客户端逐条发送，服务端全部收完后汇总")
    print()

    # 把生成器传给 UploadLogs
    summary = stub.UploadLogs(log_generator())

    print("📊 服务端返回汇总:")
    print(f"   总计:     {summary.total_lines} 条")
    print(f"   INFO:     {summary.info_count} 条")
    print(f"   WARN:     {summary.warn_count} 条")
    print(f"   ERROR:    {summary.error_count} 条")
    print()
    print("✅ 客户端流上传完成！")


if __name__ == "__main__":
    run()
