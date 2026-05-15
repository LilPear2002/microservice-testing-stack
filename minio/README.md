# 🪣 MinIO 对象存储

## 学习时间
2026-05-15

## 什么是对象存储？

```
传统文件系统: /home/user/photos/2024/vacation.jpg
              路径即地址，目录层级

对象存储:     bucket="photos"  key="2024/vacation.jpg"
              「桶 + Key」二维寻址，无层级（key 可含 / 但只是视觉分隔）
```

### 核心概念

| 概念 | 说明 | 类比 |
|------|------|------|
| **Bucket（桶）** | 顶级命名空间，存放对象 | 文件夹/项目 |
| **Object（对象）** | 数据 + 元数据 + 唯一 Key | 文件 + 标签 |
| **Key（键）** | 对象在桶内的唯一标识 | 文件名（可含路径） |
| **Presigned URL** | 带签名的临时访问链接 | 一次性分享链接 |
| **Policy（策略）** | JSON 格式的访问控制 | IAM 权限规则 |
| **Metadata** | 对象的自定义标签 | 文件属性 |

### MinIO vs AWS S3

```
MinIO = 自建 S3，同一套 API
  - AWS S3 SDK 直接连 MinIO
  - 阿里云 OSS 也是 S3 兼容
  - 学会 MinIO = 学会 所有 S3 生态

API 流派统一：
  S3 API → MinIO / AWS S3 / 阿里云 OSS / GCS / 七牛
```

## 环境配置

```bash
# 启动 MinIO（256MB 限制，154MB 实际占用）
docker run -d --name minio-learn \
  -p 9000:9000 -p 9001:9001 \
  -e MINIO_ROOT_USER=minioadmin \
  -e MINIO_ROOT_PASSWORD=minioadmin \
  --memory=256m \
  minio/minio:latest server /data --console-address ":9001"

# Python 客户端
uv venv --python 3.11
source .venv/bin/activate
uv pip install minio requests pytest -i https://mirrors.aliyun.com/pypi/simple/
```

## 5 大阶段实操

### Phase 1: Bucket CRUD

```python
from minio import Minio
client = Minio("localhost:9000", "minioadmin", "minioadmin", secure=False)

client.make_bucket("my-bucket")          # 创建
client.bucket_exists("my-bucket")        # True/False
client.list_buckets()                    # 列出所有桶
client.remove_bucket("my-bucket")        # 删除（需先清空）
```

### Phase 2: Object CRUD

```python
# 上传
client.put_object("my-bucket", "hello.txt",
    io.BytesIO(b"content"), length=7)

# 下载
resp = client.get_object("my-bucket", "hello.txt")
data = resp.read()

# 列表（支持 prefix 前缀过滤）
for obj in client.list_objects("my-bucket", prefix="folder/", recursive=True):
    print(obj.object_name, obj.size)

# 获取元信息
stat = client.stat_object("my-bucket", "hello.txt")
print(stat.size, stat.content_type, stat.last_modified)

# 删除
client.remove_object("my-bucket", "hello.txt")
```

### Phase 3: 预签名 URL（Presigned URL）

```python
from datetime import timedelta

# 生成临时下载链接（1小时有效）
url = client.presigned_get_object("my-bucket", "secret.pdf",
    expires=timedelta(hours=1))
# → http://localhost:9000/bucket/key?X-Amz-Algorithm=...&X-Amz-Signature=...

# 生成临时上传链接
url = client.presigned_put_object("my-bucket", "upload.txt",
    expires=timedelta(minutes=10))
```

> **用途**：给用户生成临时链接，无需暴露 access_key

### Phase 4: 元数据

```python
# 上传带自定义元数据
client.put_object("my-bucket", "data.txt",
    io.BytesIO(b"data"), length=4,
    metadata={"author": "zhangsan", "version": "2.0"})
# S3 自动加 x-amz-meta- 前缀 → x-amz-meta-author, x-amz-meta-version

stat = client.stat_object("my-bucket", "data.txt")
print(stat.metadata["x-amz-meta-author"])  # "zhangsan"
```

### Phase 5: 策略（Policy）

```python
# 设为公开读
public_policy = {
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Principal": {"AWS": ["*"]},
        "Action": ["s3:GetObject"],
        "Resource": ["arn:aws:s3:::my-bucket/*"]
    }]
}
client.set_bucket_policy("my-bucket", json.dumps(public_policy))

# 现在可以直接 HTTP GET
requests.get("http://localhost:9000/my-bucket/hello.txt")  # 200 OK

# 恢复私有
client.delete_bucket_policy("my-bucket")
```

## 测试结果

```bash
$ pytest test_minio.py -v
============================= 19 passed in 0.25s ==============================

测试覆盖:
  ✅ Bucket (3):    存在性检查 / 列表 / 创建删除
  ✅ Object CRUD (6): 上传下载 / 二进制 / 列表 / 路径前缀 / stat / 删除
  ✅ 预签名URL (2):   下载链接 / 上传链接
  ✅ 元数据 (2):      自定义元数据 / 无元数据
  ✅ 策略 (2):        设置读取 / 删除恢复
  ✅ 边界 (4):        不存在的桶 / 不存在的对象 / 空对象 / 覆盖
```

## 面试话术

> **Q**: 对象存储和文件存储的区别？
> **A**: 文件存储是树形层级（/a/b/c.txt），对象存储是扁平的「桶+Key」二维寻址。对象存储没有真正的"文件夹"——`folder/sub/file.txt` 只是 Key 带了 `/` 而已。好处是无上限扩展、RESTful API 直接 HTTP 访问、自带元数据和版本控制。

> **Q**: MinIO 和 AWS S3 的关系？
> **A**: MinIO 是 S3 兼容的对象存储，同一套 API。AWS S3 SDK 改个 endpoint 就能连 MinIO。阿里云 OSS 也是 S3 兼容。所以学会 MinIO = 学会整个 S3 生态。区别是 MinIO 可以自部署，S3 是云服务。

> **Q**: 预签名 URL 的原理？
> **A**: 服务端用 secret_key 对「操作+对象+过期时间」签名生成 URL，客户端拿着 URL 直接访问对象存储，不需要 access_key。常用于：生成临时下载链接给用户、前端直传文件到对象存储。

## 关键踩坑

1. **put_object 需要预设 length**：`io.BytesIO()` 后要知道字节长度。
2. **get_object 后要 close + release_conn**：否则连接泄漏。
3. **`list_objects` 对不存在的桶行为不一致**：老版本返回空，新版本抛 S3Error，用 try/except 适配。
4. **自定义元数据自动加 `x-amz-meta-` 前缀**：上传时传 `{"author": "me"}`，读取时 key 是 `"x-amz-meta-author"`。

## 下一步
- C0: ZooKeeper 分布式协调
- C1: Nacos 注册配置中心
- C2: Gateway 网关
