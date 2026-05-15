"""
MinIO 对象存储基础 —— S3 兼容协议

核心概念：
  Bucket（桶）     ~= 文件夹/命名空间
  Object（对象）   ~= 文件 + 元数据
  Presigned URL    ~= 临时下载链接（带签名+过期时间）
  Policy（策略）   ~= 访问权限控制

MinIO = 自建 S3，一套 API 同时适配 AWS S3 / 阿里云 OSS / MinIO
"""

import io
import json
import time
from datetime import timedelta
import requests
from minio import Minio
from minio.error import S3Error

# 连接
client = Minio(
    "localhost:9000",
    access_key="minioadmin",
    secret_key="minioadmin",
    secure=False  # 本地测试不用 HTTPS
)

BUCKET = "my-bucket"

# ============================================================
# Phase 1: Bucket 操作
# ============================================================
print("=" * 60)
print("Phase 1: Bucket（桶）CRUD")
print("=" * 60)

# 清理旧桶
try:
    # 先清空再删除
    objs = client.list_objects(BUCKET, recursive=True)
    for obj in objs:
        client.remove_object(BUCKET, obj.object_name)
    client.remove_bucket(BUCKET)
    print(f"🗑️  旧桶 '{BUCKET}' 已清理")
except S3Error:
    pass

# 1.1 创建桶
client.make_bucket(BUCKET)
print(f"✅ 桶 '{BUCKET}' 创建成功")

# 1.2 桶是否存在
exists = client.bucket_exists(BUCKET)
print(f"✅ 桶 '{BUCKET}' 存在: {exists}")

# 1.3 列出所有桶
buckets = client.list_buckets()
print(f"✅ 共有 {len(buckets)} 个桶: {[b.name for b in buckets]}")

# ============================================================
# Phase 2: Object 对象上传/下载/列表
# ============================================================
print("\n" + "=" * 60)
print("Phase 2: Object（对象）CRUD")
print("=" * 60)

# 2.1 上传字符串（put_object）
content = "Hello, MinIO! 这是对象存储的第一条数据。\n第二行内容。"
data = io.BytesIO(content.encode("utf-8"))
client.put_object(
    BUCKET, "hello.txt",
    data, length=len(content.encode("utf-8")),
    content_type="text/plain"
)
print(f"✅ 上传对象 'hello.txt' ({len(content.encode('utf-8'))} bytes)")

# 2.2 上传二进制（图片/文件）
binary_data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100  # 模拟二进制
client.put_object(
    BUCKET, "data/fake.png",
    io.BytesIO(binary_data), length=len(binary_data),
    content_type="image/png"
)
print(f"✅ 上传对象 'data/fake.png' ({len(binary_data)} bytes)")

# 2.3 列出对象
objects = client.list_objects(BUCKET, recursive=True)
print(f"\n📂 桶 '{BUCKET}' 中的对象:")
for obj in objects:
    print(f"   {obj.object_name:20s} | {obj.size:>6} bytes | {obj.last_modified}")

# 2.4 获取对象（下载到内存）
response = client.get_object(BUCKET, "hello.txt")
downloaded = response.read().decode("utf-8")
response.close()
response.release_conn()
print(f"\n📥 下载 'hello.txt' 内容: '{downloaded[:50]}...'")

# 2.5 检查对象是否存在
try:
    stat = client.stat_object(BUCKET, "hello.txt")
    print(f"✅ stat 'hello.txt': size={stat.size}, type={stat.content_type}")
except S3Error as e:
    print(f"❌ 对象不存在: {e}")

# ============================================================
# Phase 3: 预签名 URL（Presigned URL）
# ============================================================
print("\n" + "=" * 60)
print("Phase 3: 预签名 URL — 临时下载链接")
print("=" * 60)

# 生成一个 1 小时有效的下载链接
url = client.presigned_get_object(BUCKET, "hello.txt", expires=timedelta(hours=1))
print(f"🔗 预签名下载 URL (1小时有效):")
print(f"   {url[:80]}...")

# 也可以生成上传链接
upload_url = client.presigned_put_object(BUCKET, "uploaded-via-url.txt", expires=timedelta(minutes=10))
print(f"\n🔗 预签名上传 URL (10分钟有效):")
print(f"   {upload_url[:80]}...")

# ============================================================
# Phase 4: 对象元数据 & 标签
# ============================================================
print("\n" + "=" * 60)
print("Phase 4: 元数据 & 标签")
print("=" * 60)

# 4.1 上传带自定义元数据
client.put_object(
    BUCKET, "meta-demo.txt",
    io.BytesIO(b"content with metadata"), length=20,
    metadata={
        "author": "learner",
        "version": "1.0",
        "x-amz-meta-custom": "hello-world"
    }
)
print("✅ 上传带元数据的对象")

# 4.2 读取元数据
stat = client.stat_object(BUCKET, "meta-demo.txt")
print(f"   标准属性: size={stat.size}, content_type={stat.content_type}")
print(f"   自定义元数据: {stat.metadata}")

# ============================================================
# Phase 5: 权限策略 & 公开访问
# ============================================================
print("\n" + "=" * 60)
print("Phase 5: 桶策略 — 公开/私有")
print("=" * 60)

# 5.1 查看当前桶策略
try:
    policy = client.get_bucket_policy(BUCKET)
    print(f"   当前策略: {policy}")
except S3Error:
    print("   当前无策略（默认私有）")

# 5.2 设为公开读（JSON 格式的 IAM 策略）
public_policy = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {"AWS": ["*"]},
            "Action": ["s3:GetObject"],
            "Resource": [f"arn:aws:s3:::{BUCKET}/*"]
        }
    ]
}
client.set_bucket_policy(BUCKET, json.dumps(public_policy))
print(f"✅ 桶 '{BUCKET}' 已设为公开读")

# 5.3 验证公开访问
public_url = f"http://localhost:9000/{BUCKET}/hello.txt"
resp = requests.get(public_url)
print(f"🔓 公开访问验证: HTTP {resp.status_code}")
print(f"   内容: '{resp.text[:50]}'")

# 5.4 恢复私有
client.delete_bucket_policy(BUCKET)
print(f"🔒 恢复为私有")

print("\n✅ MinIO 5 阶段全部通关！")
