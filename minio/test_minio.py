"""
MinIO 对象存储 pytest 测试
覆盖：Bucket CRUD / Object CRUD / 预签名URL / 元数据 / 策略
"""
import io
import json
import time
from datetime import timedelta

import pytest
import requests
from minio import Minio
from minio.error import S3Error

TEST_BUCKET = "test-minio-bucket"
ENDPOINT = "localhost:9000"
ACCESS_KEY = "minioadmin"
SECRET_KEY = "minioadmin"


@pytest.fixture(scope="module")
def client():
    """模块级 fixture：创建连接 + 清理测试桶"""
    c = Minio(ENDPOINT, ACCESS_KEY, SECRET_KEY, secure=False)

    # 清理旧桶
    try:
        objs = list(c.list_objects(TEST_BUCKET, recursive=True))
        for obj in objs:
            c.remove_object(TEST_BUCKET, obj.object_name)
        c.remove_bucket(TEST_BUCKET)
    except S3Error:
        pass

    c.make_bucket(TEST_BUCKET)
    yield c

    # 清理
    try:
        objs = list(c.list_objects(TEST_BUCKET, recursive=True))
        for obj in objs:
            c.remove_object(TEST_BUCKET, obj.object_name)
        c.remove_bucket(TEST_BUCKET)
    except S3Error:
        pass


# ============================================================
# 1. Bucket 操作
# ============================================================
class TestBucket:
    """桶的创建、存在性检查、列表、删除"""

    def test_bucket_exists(self, client):
        """测试桶存在检查"""
        assert client.bucket_exists(TEST_BUCKET) is True
        assert client.bucket_exists("nonexistent-bucket-xyz") is False

    def test_list_buckets(self, client):
        """测试列出所有桶"""
        buckets = client.list_buckets()
        bucket_names = [b.name for b in buckets]
        assert TEST_BUCKET in bucket_names

    def test_make_and_remove_bucket(self, client):
        """测试创建和删除桶"""
        tmp = "tmp-bucket-delete-me"
        client.make_bucket(tmp)
        assert client.bucket_exists(tmp) is True
        client.remove_bucket(tmp)
        assert client.bucket_exists(tmp) is False


# ============================================================
# 2. Object CRUD
# ============================================================
class TestObjectCRUD:
    """对象的上传、下载、列表、删除"""

    def test_put_and_get_object(self, client):
        """上传字符串并下载验证"""
        content = "Hello, pytest test!"
        data = io.BytesIO(content.encode())
        client.put_object(TEST_BUCKET, "test1.txt", data, length=len(content.encode()))

        resp = client.get_object(TEST_BUCKET, "test1.txt")
        result = resp.read().decode()
        resp.close()
        resp.release_conn()
        assert result == content

    def test_put_binary_object(self, client):
        """上传二进制数据"""
        binary = b"\x00\x01\x02\x03" * 25  # 100 bytes
        client.put_object(
            TEST_BUCKET, "binary.bin",
            io.BytesIO(binary), length=len(binary)
        )
        stat = client.stat_object(TEST_BUCKET, "binary.bin")
        assert stat.size == 100

    def test_list_objects(self, client):
        """列出对象（应该有之前上传的 test1.txt 和 binary.bin）"""
        objs = list(client.list_objects(TEST_BUCKET, recursive=True))
        names = [o.object_name for o in objs]
        assert "test1.txt" in names
        assert "binary.bin" in names

    def test_object_with_path(self, client):
        """带路径前缀的对象"""
        client.put_object(
            TEST_BUCKET, "folder/subfolder/deep.txt",
            io.BytesIO(b"deep"), length=4
        )
        # 按前缀列出
        objs = list(client.list_objects(TEST_BUCKET, prefix="folder/", recursive=True))
        assert len(objs) == 1
        assert objs[0].object_name == "folder/subfolder/deep.txt"

    def test_stat_object(self, client):
        """stat 获取对象元信息"""
        stat = client.stat_object(TEST_BUCKET, "test1.txt")
        assert stat.size > 0
        assert stat.content_type in ["text/plain", "application/octet-stream"]

    def test_remove_object(self, client):
        """删除对象"""
        client.put_object(TEST_BUCKET, "delete-me.txt", io.BytesIO(b"x"), length=1)
        client.remove_object(TEST_BUCKET, "delete-me.txt")
        with pytest.raises(S3Error):
            client.stat_object(TEST_BUCKET, "delete-me.txt")


# ============================================================
# 3. 预签名 URL
# ============================================================
class TestPresignedURL:
    """预签名 URL 的生成和验证"""

    def test_presigned_get_url(self, client):
        """生成下载预签名 URL 并验证"""
        client.put_object(TEST_BUCKET, "presigned.txt", io.BytesIO(b"secret"), length=6)

        url = client.presigned_get_object(TEST_BUCKET, "presigned.txt", expires=timedelta(hours=1))
        assert "X-Amz-Algorithm" in url
        assert "X-Amz-Signature" in url

        # 用 URL 下载
        resp = requests.get(url, timeout=5)
        assert resp.status_code == 200
        assert resp.text == "secret"

    def test_presigned_put_url(self, client):
        """生成上传预签名 URL"""
        url = client.presigned_put_object(TEST_BUCKET, "presigned-upload.txt", expires=timedelta(minutes=10))
        assert "X-Amz-Algorithm" in url
        assert "uploaded" not in url  # 还没上传


# ============================================================
# 4. 元数据
# ============================================================
class TestMetadata:
    """自定义元数据上传与读取"""

    def test_custom_metadata(self, client):
        """上传带自定义元数据的对象"""
        metadata = {"author": "tester", "x-amz-meta-version": "2.0"}
        client.put_object(
            TEST_BUCKET, "meta.txt",
            io.BytesIO(b"data"), length=4,
            metadata=metadata
        )
        stat = client.stat_object(TEST_BUCKET, "meta.txt")
        assert stat.metadata["x-amz-meta-author"] == "tester"
        assert stat.metadata["x-amz-meta-version"] == "2.0"

    def test_no_metadata(self, client):
        """无自定义元数据的对象"""
        client.put_object(TEST_BUCKET, "no-meta.txt", io.BytesIO(b"x"), length=1)
        stat = client.stat_object(TEST_BUCKET, "no-meta.txt")
        # 标准 HTTP 头存在，自定义 amz-meta-* 不存在
        assert "Content-Type" in stat.metadata or "content-type" in str(stat.metadata).lower()


# ============================================================
# 5. 策略（Policy）
# ============================================================
class TestPolicy:
    """桶策略的设置和删除"""

    def test_set_and_get_policy(self, client):
        """设置公开读策略并验证"""
        policy = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"AWS": ["*"]},
                "Action": ["s3:GetObject"],
                "Resource": [f"arn:aws:s3:::{TEST_BUCKET}/*"]
            }]
        }
        client.set_bucket_policy(TEST_BUCKET, json.dumps(policy))
        retrieved = json.loads(client.get_bucket_policy(TEST_BUCKET))
        assert retrieved["Statement"][0]["Effect"] == "Allow"

    def test_delete_policy(self, client):
        """删除策略后恢复私有"""
        # 先设置一个策略
        policy = {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Principal": {"AWS": ["*"]}, "Action": ["s3:GetObject"], "Resource": [f"arn:aws:s3:::{TEST_BUCKET}/*"]}]}
        client.set_bucket_policy(TEST_BUCKET, json.dumps(policy))
        # 删除
        client.delete_bucket_policy(TEST_BUCKET)
        # 再次获取应该抛异常
        with pytest.raises(S3Error):
            client.get_bucket_policy(TEST_BUCKET)


# ============================================================
# 6. 边界条件
# ============================================================
class TestEdgeCases:
    """边界情况"""

    def test_nonexistent_bucket(self, client):
        """操作不存在的桶"""
        # 不同版本行为不同：可能抛 S3Error 或返回空
        try:
            objs = list(client.list_objects("bucket-does-not-exist"))
            assert len(objs) == 0
        except S3Error as e:
            assert "NoSuchBucket" in str(e)
        assert client.bucket_exists("bucket-does-not-exist") is False

    def test_nonexistent_object(self, client):
        """获取不存在的对象"""
        with pytest.raises(S3Error):
            client.get_object(TEST_BUCKET, "does-not-exist.txt")

    def test_empty_object(self, client):
        """上传空对象"""
        client.put_object(TEST_BUCKET, "empty.txt", io.BytesIO(b""), length=0)
        stat = client.stat_object(TEST_BUCKET, "empty.txt")
        assert stat.size == 0

    def test_overwrite_object(self, client):
        """覆盖已有对象"""
        client.put_object(TEST_BUCKET, "overwrite.txt", io.BytesIO(b"v1"), length=2)
        client.put_object(TEST_BUCKET, "overwrite.txt", io.BytesIO(b"v2-new"), length=6)
        resp = client.get_object(TEST_BUCKET, "overwrite.txt")
        assert resp.read() == b"v2-new"
        resp.close()
        resp.release_conn()
