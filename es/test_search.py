"""
搜索引擎模块 pytest 测试
覆盖：索引操作 / 文档CRUD / 搜索 / 过滤 / 排序 / 聚合 / 边界
"""
import pytest
import meilisearch
import time

TEST_INDEX = "test_products"
MASTER_KEY = "learn123"
BASE_URL = "http://localhost:7700"


@pytest.fixture(scope="module")
def client():
    """模块级 fixture：创建连接 + 测试索引"""
    c = meilisearch.Client(BASE_URL, MASTER_KEY)
    # 清理旧索引
    try:
        c.delete_index(TEST_INDEX)
    except:
        pass
    time.sleep(0.3)  # 确保删除任务完成

    idx = c.create_index(TEST_INDEX, {"primaryKey": "id"})
    time.sleep(0.3)

    # 设置可过滤/可排序字段
    task = c.index(TEST_INDEX).update_filterable_attributes(
        ["brand", "category", "price", "stock", "tags"]
    )
    c.wait_for_task(task.task_uid)
    task = c.index(TEST_INDEX).update_sortable_attributes(["price", "stock"])
    c.wait_for_task(task.task_uid)

    # 导入测试数据
    docs = [
        {"id": 1, "title": "iPhone 15 Pro", "brand": "Apple", "category": "手机", "price": 9999, "stock": 50},
        {"id": 2, "title": "iPhone 15", "brand": "Apple", "category": "手机", "price": 5999, "stock": 100},
        {"id": 3, "title": "小米14 Pro", "brand": "小米", "category": "手机", "price": 4999, "stock": 200},
        {"id": 4, "title": "MacBook Pro", "brand": "Apple", "category": "笔记本", "price": 14999, "stock": 30},
        {"id": 5, "title": "小米笔记本", "brand": "小米", "category": "笔记本", "price": 6999, "stock": 50},
    ]
    task = c.index(TEST_INDEX).add_documents(docs)
    time.sleep(0.5)

    return c


# ============================================================
# 1. 索引操作测试
# ============================================================
class TestIndexOperations:
    """索引的创建、获取、列表、删除"""

    def test_get_index(self, client):
        """获取索引信息"""
        idx = client.get_index(TEST_INDEX)
        assert idx.uid == TEST_INDEX
        assert idx.primary_key == "id"

    def test_list_indexes(self, client):
        """索引列表包含测试索引"""
        indexes = client.get_indexes()
        uids = [i.uid for i in indexes["results"]]
        assert TEST_INDEX in uids

    def test_index_stats(self, client):
        """索引统计：文档数"""
        stats = client.index(TEST_INDEX).get_stats()
        assert stats.number_of_documents == 5


# ============================================================
# 2. 文档 CRUD 测试
# ============================================================
class TestDocumentCRUD:
    """文档的增删改查"""

    def test_get_document(self, client):
        """获取单个文档"""
        doc = dict(client.index(TEST_INDEX).get_document(1))
        assert doc["title"] == "iPhone 15 Pro"
        assert doc["price"] == 9999

    def test_add_single_document(self, client):
        """添加单个新文档"""
        doc = {"id": 6, "title": "AirPods Pro", "brand": "Apple", "category": "耳机", "price": 1899, "stock": 500}
        task = client.index(TEST_INDEX).add_documents([doc])
        time.sleep(0.3)
        result = dict(client.index(TEST_INDEX).get_document(6))
        assert result["title"] == "AirPods Pro"
        assert result["category"] == "耳机"

    def test_update_document(self, client):
        """更新文档（全量替换）"""
        doc = {"id": 1, "title": "iPhone 15 Pro Max", "brand": "Apple", "category": "手机", "price": 10999, "stock": 30}
        task = client.index(TEST_INDEX).add_documents([doc])
        time.sleep(0.3)
        result = dict(client.index(TEST_INDEX).get_document(1))
        assert result["title"] == "iPhone 15 Pro Max"
        assert result["price"] == 10999

    def test_delete_document(self, client):
        """删除文档"""
        task = client.index(TEST_INDEX).delete_document(6)
        time.sleep(0.3)
        with pytest.raises(Exception):
            client.index(TEST_INDEX).get_document(6)


# ============================================================
# 3. 搜索测试
# ============================================================
class TestSearch:
    """全文搜索功能"""

    def test_exact_search(self, client):
        """精确搜索"""
        result = client.index(TEST_INDEX).search("iPhone")
        assert result["estimatedTotalHits"] >= 2

    def test_typo_tolerance(self, client):
        """容错搜索：ipone → iPhone"""
        result = client.index(TEST_INDEX).search("ipone")
        assert result["estimatedTotalHits"] >= 2
        # 排序靠前的应该是 iPhone
        assert "iPhone" in result["hits"][0]["title"]

    def test_chinese_search(self, client):
        """中文搜索"""
        result = client.index(TEST_INDEX).search("小米")
        assert result["estimatedTotalHits"] == 2
        titles = [h["title"] for h in result["hits"]]
        assert "小米14 Pro" in titles
        assert "小米笔记本" in titles

    def test_partial_match(self, client):
        """部分匹配：Pro → 匹配所有含 Pro 的"""
        result = client.index(TEST_INDEX).search("Pro")
        assert result["estimatedTotalHits"] >= 3  # iPhone 15 Pro, iPhone 15 Pro Max, 小米14 Pro


# ============================================================
# 4. 过滤器测试
# ============================================================
class TestFilter:
    """过滤器功能"""

    def test_filter_by_brand(self, client):
        """按品牌过滤"""
        result = client.index(TEST_INDEX).search("", {"filter": "brand = Apple"})
        brands = {h["brand"] for h in result["hits"]}
        assert brands == {"Apple"}

    def test_filter_price_range(self, client):
        """价格区间过滤"""
        result = client.index(TEST_INDEX).search("", {
            "filter": "price >= 5000 AND price <= 7000"
        })
        for h in result["hits"]:
            assert 5000 <= h["price"] <= 7000

    def test_filter_in_operator(self, client):
        """IN 操作符多值"""
        result = client.index(TEST_INDEX).search("", {
            "filter": "brand IN [小米]"
        })
        brands = {h["brand"] for h in result["hits"]}
        assert brands == {"小米"}

    def test_filter_combined(self, client):
        """组合过滤：分类+库存"""
        result = client.index(TEST_INDEX).search("", {
            "filter": "category = 手机 AND stock > 60"
        })
        for h in result["hits"]:
            assert h["category"] == "手机"
            assert h["stock"] > 60


# ============================================================
# 5. 排序测试
# ============================================================
class TestSorting:
    """排序功能"""

    def test_sort_price_asc(self, client):
        """价格升序"""
        result = client.index(TEST_INDEX).search("", {
            "sort": ["price:asc"]
        })
        prices = [h["price"] for h in result["hits"]]
        assert prices == sorted(prices)

    def test_sort_price_desc(self, client):
        """价格降序"""
        result = client.index(TEST_INDEX).search("", {
            "sort": ["price:desc"]
        })
        prices = [h["price"] for h in result["hits"]]
        # 降序检查：前一个 >= 后一个
        for i in range(len(prices) - 1):
            assert prices[i] >= prices[i + 1]


# ============================================================
# 6. 聚合（Facets）测试
# ============================================================
class TestFacets:
    """聚合统计功能"""

    def test_facet_by_category(self, client):
        """按分类聚合"""
        result = client.index(TEST_INDEX).search("", {
            "facets": ["category"],
            "limit": 0
        })
        facets = result["facetDistribution"]["category"]
        assert "手机" in facets
        assert "笔记本" in facets
        assert facets["手机"] >= 2

    def test_facet_by_brand(self, client):
        """按品牌聚合"""
        result = client.index(TEST_INDEX).search("", {
            "facets": ["brand"],
            "limit": 0
        })
        facets = result["facetDistribution"]["brand"]
        assert "Apple" in facets
        assert "小米" in facets
        assert facets["Apple"] >= 3


# ============================================================
# 7. 边界条件测试
# ============================================================
class TestEdgeCases:
    """边界情况"""

    def test_search_no_results(self, client):
        """搜索无结果"""
        result = client.index(TEST_INDEX).search("xyz不存在的商品")
        assert result["estimatedTotalHits"] == 0
        assert len(result["hits"]) == 0

    def test_empty_search(self, client):
        """空搜索返回所有文档"""
        result = client.index(TEST_INDEX).search("")
        assert result["estimatedTotalHits"] >= 5

    def test_limit_param(self, client):
        """limit 参数限制返回数"""
        result = client.index(TEST_INDEX).search("", {"limit": 2})
        assert len(result["hits"]) == 2

    def test_nonexistent_index(self, client):
        """访问不存在的索引抛出异常"""
        with pytest.raises(Exception):
            client.get_index("nonexistent_index_xyz")
