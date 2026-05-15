"""
MeiliSearch 搜索引擎基础 —— 从索引创建到高级搜索

核心概念：
  索引(Index)  ~= 数据库表
  文档(Document) ~= 表中的一行 JSON
  搜索(Search)  ~= 全文检索 + 模糊匹配
  过滤器(Filter) ~= SQL WHERE
  排序(Sort)    ~= SQL ORDER BY
  聚合(Facet)   ~= SQL GROUP BY
"""

import json
import meilisearch

# 连接（MeiliSearch 默认端口 7700）
client = meilisearch.Client("http://localhost:7700", "learn123")

INDEX_NAME = "products"

# ============================================================
# Phase 1: 创建索引 & 批量导入文档
# ============================================================
print("=" * 60)
print("Phase 1: 创建索引 & 批量导入")
print("=" * 60)

# 创建索引（如果已存在则先删）
try:
    client.delete_index(INDEX_NAME)
except:
    pass

# 创建索引并设置主键
task = client.create_index(INDEX_NAME, {"primaryKey": "id"})
print(f"✅ 索引 '{INDEX_NAME}' 创建成功")

# 示例文档：电商商品数据
products = [
    {"id": 1, "title": "iPhone 15 Pro Max 256GB", "brand": "Apple", "category": "手机", "price": 9999, "stock": 50, "tags": ["5G", "旗舰", "拍照"]},
    {"id": 2, "title": "iPhone 15 128GB", "brand": "Apple", "category": "手机", "price": 5999, "stock": 120, "tags": ["5G", "入门"]},
    {"id": 3, "title": "MacBook Pro 14寸 M3芯片", "brand": "Apple", "category": "笔记本", "price": 14999, "stock": 30, "tags": ["办公", "高性能"]},
    {"id": 4, "title": "MacBook Air 13寸 M2芯片", "brand": "Apple", "category": "笔记本", "price": 8999, "stock": 80, "tags": ["轻薄", "办公"]},
    {"id": 5, "title": "小米14 Pro 512GB", "brand": "小米", "category": "手机", "price": 4999, "stock": 200, "tags": ["5G", "旗舰", "拍照"]},
    {"id": 6, "title": "小米笔记本Pro 16寸", "brand": "小米", "category": "笔记本", "price": 6999, "stock": 45, "tags": ["办公", "大屏"]},
    {"id": 7, "title": "华为Mate 60 Pro 256GB", "brand": "华为", "category": "手机", "price": 6999, "stock": 15, "tags": ["5G", "旗舰", "卫星通信"]},
    {"id": 8, "title": "华为MateBook X Pro", "brand": "华为", "category": "笔记本", "price": 11999, "stock": 25, "tags": ["轻薄", "触屏"]},
    {"id": 9, "title": "Sony WH-1000XM5 降噪耳机", "brand": "Sony", "category": "耳机", "price": 2499, "stock": 300, "tags": ["降噪", "无线"]},
    {"id": 10, "title": "AirPods Pro 2 USB-C", "brand": "Apple", "category": "耳机", "price": 1899, "stock": 500, "tags": ["降噪", "无线", "苹果生态"]},
    {"id": 11, "title": "小米降噪耳机Pro", "brand": "小米", "category": "耳机", "price": 799, "stock": 150, "tags": ["降噪", "无线"]},
    {"id": 12, "title": "iPad Pro 12.9寸 M2芯片", "brand": "Apple", "category": "平板", "price": 9299, "stock": 40, "tags": ["办公", "绘画"]},
]

# 批量添加文档
task = client.index(INDEX_NAME).add_documents(products)
print(f"✅ 批量导入 {len(products)} 条商品文档")
print(f"   任务ID: {task.task_uid}")

# 等待任务完成（MeiliSearch 异步处理）
import time
time.sleep(1)

# ============================================================
# Phase 2: 基础搜索 —— 全文检索 + 模糊匹配
# ============================================================
print("\n" + "=" * 60)
print("Phase 2: 基础搜索")
print("=" * 60)

# 2.1 简单搜索
result = client.index(INDEX_NAME).search("iPhone")
print(f"\n🔍 搜索 'iPhone' → {result['estimatedTotalHits']} 条:")
for hit in result["hits"]:
    print(f"   {hit['title']} — ¥{hit['price']}")

# 2.2 模糊搜索（typo tolerance 内置！）
result = client.index(INDEX_NAME).search("ipone")  # 故意拼错
print(f"\n🔍 搜索 'ipone'(拼错) → {result['estimatedTotalHits']} 条:")
for hit in result["hits"]:
    print(f"   {hit['title']} — ¥{hit['price']}")

# 2.3 多关键词搜索
result = client.index(INDEX_NAME).search("小米 耳机")
print(f"\n🔍 搜索 '小米 耳机' → {result['estimatedTotalHits']} 条:")
for hit in result["hits"]:
    print(f"   {hit['title']} — ¥{hit['price']}")

# ============================================================
# Phase 3: 过滤器（Filter）—— 精准筛选
# ============================================================
print("\n" + "=" * 60)
print("Phase 3: 过滤器（Filter）")
print("=" * 60)

# 先设置可过滤字段（等待异步任务完成）
task = client.index(INDEX_NAME).update_filterable_attributes(["brand", "category", "price", "stock", "tags"])
client.wait_for_task(task.task_uid)
print(f"✅ 过滤器属性已设置")

# 3.1 按品牌过滤
result = client.index(INDEX_NAME).search("", {"filter": "brand = Apple"})
print(f"\n🔍 过滤 'brand = Apple' → {result['estimatedTotalHits']} 条:")
for hit in result["hits"]:
    print(f"   [{hit['category']}] {hit['title']} — ¥{hit['price']}")

# 3.2 价格区间过滤
result = client.index(INDEX_NAME).search("", {"filter": "price >= 5000 AND price <= 10000"})
print(f"\n🔍 过滤 'price 5K~10K' → {result['estimatedTotalHits']} 条:")
for hit in result["hits"]:
    print(f"   {hit['title']} — ¥{hit['price']}")

# 3.3 多条件组合
result = client.index(INDEX_NAME).search("", {
    "filter": "category = 手机 AND price < 7000 AND stock > 20"
})
print(f"\n🔍 过滤 '手机 + <7000 + 有货' → {result['estimatedTotalHits']} 条:")
for hit in result["hits"]:
    print(f"   {hit['title']} — ¥{hit['price']} (库存: {hit['stock']})")

# 3.4 IN 操作符
result = client.index(INDEX_NAME).search("", {
    "filter": "brand IN [小米, 华为]"
})
print(f"\n🔍 过滤 'brand IN 小米/华为' → {result['estimatedTotalHits']} 条:")
for hit in result["hits"]:
    print(f"   [{hit['brand']}] {hit['title']} — ¥{hit['price']}")

# ============================================================
# Phase 4: 排序 & 分页
# ============================================================
print("\n" + "=" * 60)
print("Phase 4: 排序 & 分页")
print("=" * 60)

task = client.index(INDEX_NAME).update_sortable_attributes(["price", "stock"])
client.wait_for_task(task.task_uid)
print(f"\n✅ 排序属性已设置")

# 4.1 按价格升序
result = client.index(INDEX_NAME).search("", {
    "sort": ["price:asc"],
    "limit": 5
})
print(f"\n🔍 最便宜的 5 件商品:")
for hit in result["hits"]:
    print(f"   {hit['title']} — ¥{hit['price']}")

# 4.2 按价格降序
result = client.index(INDEX_NAME).search("", {
    "sort": ["price:desc"],
    "limit": 5
})
print(f"\n🔍 最贵的 5 件商品:")
for hit in result["hits"]:
    print(f"   {hit['title']} — ¥{hit['price']}")

# ============================================================
# Phase 5: 聚合（Facets）—— 分类统计
# ============================================================
print("\n" + "=" * 60)
print("Phase 5: 聚合（Facets）")
print("=" * 60)

# 聚合：MeiliSearch 的 facet 直接基于已设置的 filterableAttributes
# 无需额外配置（v1.12+ 自动生效）
print(f"✅ 聚合已就绪（基于 filterableAttributes）")

# 5.1 按分类统计
result = client.index(INDEX_NAME).search("", {
    "facets": ["category"],
    "limit": 0
})
print(f"\n📊 按分类统计:")
for cat, count in result["facetDistribution"]["category"].items():
    print(f"   {cat}: {count} 件")

# 5.2 按品牌统计
result = client.index(INDEX_NAME).search("", {
    "facets": ["brand"],
    "limit": 0
})
print(f"\n📊 按品牌统计:")
for brand, count in result["facetDistribution"]["brand"].items():
    print(f"   {brand}: {count} 件")

print("\n✅ 全部操作完成！")
