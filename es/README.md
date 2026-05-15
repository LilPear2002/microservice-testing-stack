# 🔍 Elasticsearch / MeiliSearch 搜索引擎

## 学习时间
2026-05-15

## 为什么用 MeiliSearch 而不是 Elasticsearch？

| 对比 | Elasticsearch | MeiliSearch |
|------|:---:|:---:|
| 内存占用 | ≥ 1GB | ~5MB 空闲 |
| 启动时间 | 30s+（2C2G 跑不动） | <1s |
| 搜索功能 | 完整但复杂 | 核心功能齐全 |
| API 风格 | RESTful | RESTful（几乎一致） |
| 容错搜索 | 需要配置 fuzziness | **内置开箱即用** |
| 学习成本 | 高（mapping/analyzer/tokenizer） | 低（零配置搜索） |

> **结论**：学习搜索引擎核心概念（索引→文档→搜索→过滤→排序→聚合），MeiliSearch 完全够用。ES 就是在这些基础上加了分布式、复杂分词器、聚合分析等，面试理解概念后看看 ES 文档就能对答。

## 核心概念

```
搜索引擎 = 倒排索引 + 全文检索 + 聚合分析

倒排索引（Inverted Index）：
  文档1: "iPhone 15 Pro"     →  iPhone→[1], 15→[1], Pro→[1]
  文档2: "小米14 Pro"        →  小米→[2], 14→[2], Pro→[1,2]
  搜索 "Pro" → 直接定位 [1, 2]  ← O(1) vs 数据库 LIKE %Pro% 的 O(n)
```

### 核心概念对照表

| 概念 | 等价物 | 说明 |
|------|--------|------|
| Index（索引） | 数据库表 | 存放一类文档 |
| Document（文档） | 一行 JSON | 被搜索的最小单元 |
| Field（字段） | 列 | 文档中的属性 |
| Search（搜索） | SELECT + LIKE | 全文检索 |
| Filter（过滤） | WHERE | 条件筛选 |
| Sort（排序） | ORDER BY | 排序 |
| Facet（聚合） | GROUP BY | 分类统计 |

## 环境配置

```bash
# 启动 MeiliSearch（200MB 限制）
docker run -d --name meili-learn \
  -p 7700:7700 \
  -e MEILI_MASTER_KEY=learn123 \
  -e MEILI_NO_ANALYTICS=true \
  --memory=200m \
  getmeili/meilisearch:v1.12

# Python 客户端
uv venv --python 3.11
source .venv/bin/activate
uv pip install meilisearch pytest -i https://mirrors.aliyun.com/pypi/simple/
```

## 5 大阶段实操

### Phase 1: 创建索引 & 导入文档

```python
client = meilisearch.Client("http://localhost:7700", "learn123")
client.create_index("products", {"primaryKey": "id"})

products = [
    {"id": 1, "title": "iPhone 15 Pro", "brand": "Apple", "price": 9999, ...},
    {"id": 2, "title": "小米14 Pro", "brand": "小米", "price": 4999, ...},
    ...
]
client.index("products").add_documents(products)
```

### Phase 2: 基础搜索

```python
# 精确搜索
client.index("products").search("iPhone")     # → 2 条

# 容错搜索（内置！ES 需要配置 fuzziness）
client.index("products").search("ipone")      # → 仍返回 iPhone！

# 中文搜索
client.index("products").search("小米 耳机")   # → 3 条
```

### Phase 3: 过滤器

```python
# 需要先声明可过滤字段
client.index("products").update_filterable_attributes(["brand", "price", ...])

# 等值过滤: brand = Apple
# 范围过滤: price >= 5000 AND price <= 10000
# IN 操作:  brand IN [小米, 华为]
# 组合过滤: category = 手机 AND price < 7000 AND stock > 20
```

### Phase 4: 排序

```python
client.index("products").update_sortable_attributes(["price", "stock"])

# 升序: sort=["price:asc"]  → 最便宜
# 降序: sort=["price:desc"] → 最贵
```

### Phase 5: 聚合（Facets）

```python
result = client.index("products").search("", {
    "facets": ["category", "brand"],
    "limit": 0  # 不返回文档，只要统计
})
# facetDistribution:
#   category: {手机: 4, 笔记本: 4, 耳机: 3, 平板: 1}
#   brand:    {Apple: 6, 小米: 3, 华为: 2, Sony: 1}
```

## 测试结果

```bash
$ pytest test_search.py -v
============================= 23 passed in 2.30s ==============================

测试覆盖:
  ✅ 索引操作 (3):     获取索引 / 列出索引 / 文档统计
  ✅ 文档 CRUD (4):    获取 / 新增 / 更新 / 删除
  ✅ 搜索功能 (4):     精确 / 容错(ipone→iPhone) / 中文 / 部分匹配
  ✅ 过滤器 (4):       品牌 / 价格区间 / IN操作 / 组合条件
  ✅ 排序 (2):         价格升序 / 价格降序
  ✅ 聚合 (2):         分类统计 / 品牌统计
  ✅ 边界 (4):         无结果 / 空搜索 / limit限制 / 不存在的索引
```

## 面试话术

> **Q**: 用过 Elasticsearch 吗？说说原理。
> **A**: 核心是**倒排索引**。传统数据库查 "iPhone" 是扫描全表 `LIKE %iPhone%`，O(n)。ES/MeiliSearch 会把文档先分词建立倒排索引：词→文档ID列表，查 "iPhone" 直接 O(1) 定位到文档。加上**容错匹配**（fuzzy search）、**过滤器**（精确筛选）、**聚合**（GROUP BY），就构成了搜索引擎的四大核心能力。

> **Q**: MeiliSearch 和 Elasticsearch 的区别？
> **A**: MS 是轻量搜索引擎，零配置开箱即用，内置中文分词和容错搜索，适合中小项目和学习。ES 是分布式搜索引擎，支持 PB 级数据、复杂聚合管道、自定义分词器和分析器，适合企业级场景。核心概念完全相通，学会一个另一个看文档就能上手。

## 关键踩坑

1. **MeiliSearch 是异步的**：`add_documents()`、`update_filterable_attributes()` 等操作是异步任务，要用 `client.wait_for_task(task_uid)` 等待完成才能搜到。
2. **字段要先声明才能过滤/排序**：`filterableAttributes` 和 `sortableAttributes` 需要显式设置。
3. **`get_document()` 返回 Document 对象**不是 dict，`dict()` 转换后才能用 `[]` 访问。
4. **`get_indexes()` 返回 `{"results": [...], "total": N}`** 结构，取 `["results"]` 遍历。

## 下一步
- B4: MinIO 对象存储
- C0: ZooKeeper 分布式协调
- C1: Nacos 注册配置中心
