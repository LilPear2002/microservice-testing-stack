# 🃏 Mock 测试

> **Mock：让测试只测「自己」的代码，不被别人拖累**

---

## 📋 学习路线

| 阶段 | 主题 | 状态 |
|:---:|------|:---:|
| **P1** | 概念：Mock 是什么、为什么、测试替身分类 | ✅ 完成 |
| P2 | 基础实操：unittest.mock | ✅ 完成 |
| P3 | 进阶：Mock HTTP/DB/外部服务 | ✅ 完成 |
| P4 | 实战：全链路 Mock 测试案例 | ✅ 完成 |

---

# Phase 1：Mock 概念

---

## 1.1 为什么需要 Mock？

### 🧊 一个真实的困境

假设你要测试「下单服务」：

```python
def create_order(user_id, product_id):
    #  查库存——调用库存服务
    stock = inventory_service.check(product_id)
    #  扣钱——调用支付网关（银行接口）
    payment = payment_gateway.charge(user_id, amount)
    #  发通知——发短信/邮件
    notify_service.send(user_id, "订单已创建")
    #  写数据库
    db.insert_order(order)
```

**如果直接测试会怎样？**

| 问题 | 后果 |
|------|------|
| 支付网关每次扣真钱 | 💸 测试一次费一次 |
| 库存服务挂了 | ❌ 测试失败，但不是你代码的锅 |
| 短信服务限流 | ⏳ 测试跑得巨慢 |
| 数据库没搭好 | 🚫 根本跑不起来 |
| 依赖返回不可控的数据 | 🎲 测试结果随机（flaky test） |

---

### 💡 Mock 的思路：造一个「替身」

```
真实依赖（不可控）              Mock 替身（可控）
┌─────────────┐              ┌─────────────┐
│  支付网关    │              │  MockPayGate│
│  · 真扣钱    │      ➜       │  · 永远返回  │
│  · 网络波动  │              │   "支付成功"  │
│  · 接口限流  │              │  · 0ms 返回  │
└─────────────┘              └─────────────┘
```

**核心思想**：单元测试只测「自己的逻辑」，外部依赖用替身替代。

---

## 1.2 Mock 在测试金字塔中的位置

```
         ╱  E2E 测试  ╲        ← 全部真实，慢、贵、脆
        ╱───────────────╲
       ╱  集成测试       ╲      ← 部分 Mock，部分真实
      ╱───────────────────╲
     ╱     单元测试  ★     ╲    ← 大量 Mock，快、稳、廉价
    ╱  (Mock 的主战场)      ╲
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

| 测试层级 | Mock 程度 | 速度 | 典型场景 |
|----------|:---:|------|---------|
| 单元测试 | **大量 Mock** | 毫秒 | 测一个函数/类的纯逻辑 |
| 集成测试 | 部分 Mock | 秒 | 测多个真实组件间的协作 |
| E2E 测试 | 几乎不用 | 分钟 | 测完整用户链路 |

---

## 1.3 测试替身家族（Test Doubles）

> Martin Fowler 的经典分类。Mock 只是其中一种。

```
测试替身 Test Doubles
├── Dummy    —— 占位符，传进去但从来不用
├── Stub     —— 返回固定值，不问「被调用了吗」
├── Spy      —— 记录调用信息，事后检查
├── Mock     —— 预设期望，不符就报错
└── Fake     —— 有真实逻辑的轻量实现
```

### 用生活中的例子理解 👇

**场景**：你在线买机票，要测试「出票逻辑」

| 替身 | 生活中的类比 | 代码中的体现 |
|------|-------------|-------------|
| **Dummy** | 填表时随便写的「收件人姓名」——系统不验证 | `user = User(id=999)` # 只传进去，不调用任何方法 |
| **Stub** | 查询航班时，系统总是返回「CA1234 有空位」 | `flight_check.return_value = True` # 固定返回 |
| **Spy** | 你让朋友帮你订票，事后问他「你打电话了吗？打了几次？」 | `mock.call_count` / `mock.assert_called_once()` |
| **Mock** | 你告诉朋友「必须打 4S 店电话，否则我不付钱」——不照做就闹 | `mock.assert_called_with("4S店")` → 不满足就 AssertionError |
| **Fake** | 飞模拟器——看起来像真飞机，但不是真的 | 内存数据库（SQLite 替代 PostgreSQL） |

---

### 代码对比

```python
#  ───── 要测试的函数 ─────
def send_notification(user, message):
    if user.is_vip():
        email_service.send(user.email, message)
        return "VIP发送成功"
    return "普通用户不发送"

# ───────── Stub ─────────
# "不管你怎么问，我就返回 True"
user_stub = Mock()
user_stub.is_vip.return_value = True
assert send_notification(user_stub, "hi") == "VIP发送成功"

# ───────── Spy ─────────
# "事后来看看，email_service.send 被调用了没？调了几次？"
email_spy = Mock()
send_notification(user_stub, "hi")
print(email_spy.send.call_count)  # 事后检查

# ───────── Mock ─────────
# "我预设你一定会被调用一次，参数是 xxx，不满足就报错！"
email_mock = Mock()
send_notification(vip_user, "hello")
email_mock.send.assert_called_once_with("vip@example.com", "hello")
# ↑ 如果没调用或参数不对→直接 AssertionError
```

---

## 1.4 什么时候该 Mock？什么时候不该？

### ✅ 该 Mock 的

| 依赖类型 | 原因 |
|---------|------|
| 外部 API（支付、短信、地图） | 收费、限流、不可控 |
| 数据库 | 状态污染、环境依赖 |
| 文件系统 | 权限问题、清理麻烦 |
| 时间/随机数 | 结果不确定 |
| 还没开发完的模块 | 并行开发 |

### ❌ 不该 Mock 的

| 对象 | 原因 |
|------|------|
| 值对象（DTO、Entity） | 直接 new 就行 |
| 被测试函数本身 | 那你还测什么… |
| 标准库基础类型 | `Mock(str)` 毫无意义 |
| 你拥有的简单工具函数 | 过度 Mock 增加维护成本 |

### 📏 黄金法则

> **Mock 你「不拥有」的，不 Mock 你「拥有」的。**
>
> ——只 Mock 外部依赖，不 Mock 自己的业务逻辑。

---

## 1.5 Python Mock 生态

| 工具 | 用途 |
|------|------|
| `unittest.mock` | 标准库，Python 3.3+ 内置，Mock/MagicMock/patch |
| `pytest-mock` | pytest 插件，提供 `mocker` fixture，语法更简洁 |
| `responses` | Mock HTTP 请求（拦截 `requests` 库） |
| `httpretty` | 更底层的 HTTP Mock |
| `freezegun` | Mock 时间（`datetime.now()`） |
| `mongomock` | 内存 MongoDB |

**我们主要学前三个**：`unittest.mock` + `pytest-mock` + `responses`。

---

## 1.6 Phase 1 小结

```
┌─────────────────────────────────────────────┐
│            Mock 核心思想三句话               │
├─────────────────────────────────────────────┤
│                                             │
│    "只测自己的代码，别人的用替身"             │
│                                             │
│    "Mock 你依赖的，不 Mock 你拥有的"          │
│                                             │
│    "Stub 问返回、Spy 问过程、Mock 问契约"     │
│                                             │
└─────────────────────────────────────────────┘
```

### 🏁 检查清单

- [ ] 理解了「为什么需要 Mock」
- [ ] 能说出测试金字塔中 Mock 的位置
- [ ] 能区分 Dummy / Stub / Spy / Mock / Fake
- [ ] 知道什么时候该 Mock、什么时候不该
- [ ] 知道 Python 的 Mock 工具栈

---

### 📝 面试话术

> **面试官**：「你们项目中怎么做 Mock 测试？」
>
> **答**：「我们遵循『只 Mock 外部依赖，不 Mock 业务逻辑』的原则。对于第三方 API 比如支付、短信，我们用 `unittest.mock` 的 `patch` 替换掉网络调用；对于数据库，测试环境用 SQLite 这种轻量 Fake 替代；时间相关的用 `freezegun` 冻结。Mock 之后验证两个东西：一是自己函数的返回值正确，二是外部依赖的调用方式符合预期——调了几次、传了什么参数。」

---

> 下一阶段：Phase 2 基础实操，用 `unittest.mock` 写真实的 Mock 测试代码 🚀

---

# Phase 2：unittest.mock 基础实操

> **测试覆盖：36 passed | 8 个知识单元 | 代码在 `tests/test_services.py`**

---

## 2.1 项目结构

```
mock_testing/
├── src/
│   ├── __init__.py
│   └── services.py          ← 被测代码（支付/库存/通知/订单服务）
├── tests/
│   ├── __init__.py
│   └── test_services.py     ← 36 条 Mock 测试，按难度递进
├── .venv/
└── README.md
```

## 2.2 八个知识单元速查表

| # | 知识点 | 一句话 | 测试数 |
|:---:|--------|--------|:---:|
| 1 | **Mock 对象基础** | `Mock()` 创建万能替身，访问任何属性都不报错 | 4 |
| 2 | **return_value** | 让 Mock 方法返回固定值 | 包含在上 |
| 3 | **side_effect** | 抛异常 / 返回序列 / 执行自定义函数 | 4 |
| 4 | **assert_called** | 事后检查：调没调、调几次、传了什么参数 | 7 |
| 5 | **MagicMock** | Mock 的子类，自动支持 `len()`、`iter`、`[]` | 4 |
| 6 | **@patch 装饰器** | 临时替换模块里的类/函数，测试自动恢复 | 3 |
| 7 | **with patch 上下文** | 只在 `with` 块内替换，更灵活 | 2 |
| 8 | **autospec** | 让 Mock 遵守真实接口，拼错方法名立即报错 | 4 |

---

## 2.3 核心 API 速查

### Mock 创建与行为控制

```python
from unittest.mock import Mock, MagicMock, patch, call, create_autospec

# ── 创建 Mock ──
m = Mock()                         # 普通替身
m = MagicMock()                    # 支持魔术方法的替身
m = create_autospec(RealClass)     # 绑定真实接口的替身（推荐）

# ── 控制返回值 ──
m.method.return_value = 42         # 固定返回
m.method.side_effect = [1, 2, 3]   # 每次调用返回不同值
m.method.side_effect = Exception() # 抛异常
m.method.side_effect = lambda x: x*2  # 自定义函数

# ── 验证调用 ──
m.method.assert_called()           # 调过就行
m.method.assert_called_once()      # 恰好调了一次
m.method.assert_called_with(a, b)  # 最后一次调用的参数
m.method.assert_not_called()       # 从没被调用
m.method.call_count                # 被调了几次
m.method.call_args_list            # 所有调用的参数历史
```

### patch 三种用法

```python
# 方式1：装饰器（推荐，批量 Mock）
@patch('module.ClassName')
def test_something(MockClass):
    MockClass.return_value.method.return_value = 42
    ...

# 方式2：上下文管理器（临时 Mock）
with patch('module.ClassName') as MockClass:
    MockClass.return_value.method.return_value = 42
    ...

# 方式3：patch.object（替换已有实例的属性）
with patch.object(existing_obj, 'method') as mock_method:
    mock_method.return_value = 42
    ...
```

**关键点**：`patch` 的路径是 **「在哪里被使用」** 的模块路径，不是定义的路径！

---

## 2.4 典型测试模式

### 模式1：正常流程测试

```python
@patch('src.services.PaymentGateway')
@patch('src.services.InventoryService')
@patch('src.services.NotificationService')
def test_happy_path(self, MockNotify, MockInventory, MockPayment):
    # 1. 预设 Mock 行为
    MockInventory.return_value.check_stock.return_value = 10
    MockPayment.return_value.charge.return_value = {"status": "success", "transaction_id": "TXN-001"}

    # 2. 执行被测代码
    service = OrderService(MockPayment(), MockInventory(), MockNotify())
    result = service.create_order("user1", "P1", 99)

    # 3. 验证返回值
    assert result["status"] == "success"

    # 4. 验证依赖调用（你的代码有没有正确调用外部服务）
    MockInventory.return_value.check_stock.assert_called_once_with("P1")
    MockPayment.return_value.charge.assert_called_once_with("user1", 99)
```

### 模式2：异常/边界测试

```python
def test_payment_fails_rollback(self):
    MockPayment.return_value.charge.side_effect = ConnectionError("超时")
    result = service.create_order(...)
    assert result["status"] == "failed"

    # 关键验证：支付失败后必须释放库存！
    MockInventory.return_value.release.assert_called_once()
```

---

## 2.5 踩坑记录

###  坑1：patch 路径不匹配

```python
#  错：patched 的是定义模块，但代码里 import 的是另一个模块
# 如果 services.py 里写了 `from payment import PaymentGateway`，
# 那应该 patch `services.PaymentGateway`，不是 `payment.PaymentGateway`

# ✅ 规则：patch "在哪里被使用"，不是 "在哪里被定义"
```

###  坑2：Mock 忘记 `.return_value`

```python
#  错
MockPayment.charge.return_value = {...}  # MockPayment 是类，不是实例
#  代码里是 PaymentGateway() → 实例化，所以 Mock 也返回了实例

# ✅ 对
MockPayment.return_value.charge.return_value = {...}
```

###  坑3：autospec 的重要性

```python
# 不用 autospec：拼错方法名 → 测试静默通过，线上爆炸
mock = Mock()
mock.chage("user", 100)    # typo！应该是 charge
mock.chage.assert_called() # ✅ 通过！但测了个不存在的方法

# 用 autospec：立即报错
mock = create_autospec(PaymentGateway)
mock.chage("user", 100)    # ❌ AttributeError: Mock object has no attribute 'chage'
```

---

## 2.6 🏁 Phase 2 检查清单

- [ ] 能用 `Mock()` 创建替身对象
- [ ] 能用 `return_value` 控制返回值
- [ ] 能用 `side_effect` 模拟异常和序列返回
- [ ] 能用 `assert_called_with` 验证调用参数
- [ ] 能用 `call_count` 和 `call_args_list` 查调用历史
- [ ] 能区分 `Mock` 和 `MagicMock`
- [ ] 能用 `@patch` 替换外部依赖
- [ ] 能用 `with patch` 做临时替换
- [ ] 理解 autospec 的意义和用法
- [ ] 36 条测试全部通过

---

### 📝 面试话术 — unittest.mock

> **面试官**：「用过 Python 的 unittest.mock 吗？patch 的路径怎么写？」
>
> **答**：「用过。`patch` 的核心原则是『patch 在哪里被使用，不是在哪里被定义』。比如 `services.py` 里 `from payment import PaymentGateway`，那你应该 `@patch('services.PaymentGateway')`。我一般用 `@patch` 装饰器做批量 Mock，配上 `return_value` 预设行为，`side_effect` 模拟异常。测试完用 `assert_called_once_with` 验证外部依赖被正确调用了。生产代码推荐用 `create_autospec` 绑定真实接口，避免方法名拼写错误导致假阳性。」

---

> 下一阶段：Phase 3 进阶，用 `responses` Mock HTTP、用 Mock 替代数据库，处理更复杂的依赖场景 🚀

---

# Phase 3：Mock 外部依赖进阶

> **测试覆盖：36 passed | 5 大场景 | 代码在 `tests/test_external_mock.py`**

---

## 3.1 场景总览

| # | Mock 对象 | 工具 | 核心技巧 |
|:---:|----------|------|---------|
| 1 | **HTTP API** | `responses` 库 | `@responses.activate` + `responses.get/post/put/delete` |
| 2 | **数据库 SQLite** | `unittest.mock` | 两种策略：真实内存DB vs 完全Mock连接 |
| 3 | **时间 datetime** | `patch('module.datetime')` | `mock_dt.now.return_value = fixed_time` |
| 4 | **文件系统** | `mock_open` + `patch` | `mock_open(read_data=json_str)` + Mock `os.path.exists` |
| 5 | **综合 Mock** | 以上组合 | 一个方法依赖 HTTP+DB+天气，全都 Mock |

---

## 3.2 Mock HTTP 请求 —— responses 库

### 核心用法

```python
import responses

@responses.activate  # ← 激活拦截器，必须加！
def test_api_call():
    # 1. 注册 Mock 响应
    responses.get(
        "https://api.example.com/data",
        json={"key": "value"},  # 返回 JSON
        status=200
    )

    # 2. 正常发请求（被 responses 拦截，不发网络）
    resp = requests.get("https://api.example.com/data")

    # 3. 验证
    assert resp.json() == {"key": "value"}
    assert len(responses.calls) == 1  # 确认只发了一次请求
```

### 支持的方法

```python
responses.get(url, json={}, status=200)     # GET
responses.post(url, json={}, status=201)    # POST
responses.put(url, json={}, status=200)     # PUT
responses.delete(url, status=204)           # DELETE
responses.patch(url, json={}, status=200)   # PATCH
```

### 常见场景

```python
# 模拟错误
responses.get(url, status=500)                           # 服务器错误
responses.get(url, body=requests.exceptions.Timeout())   # 超时
responses.get(url, status=404)                           # 资源不存在

# 一次 Mock 多个请求（自动按注册顺序匹配）
responses.get("http://api1.com", json={"a": 1})
responses.get("http://api2.com", json={"b": 2})

# 验证请求细节
req = responses.calls[0].request
req.headers["Authorization"]  # 验证 Header
req.body                      # 验证 Body（bytes）
```

### ⚠️ 踩坑：中文 URL 编码

```python
#  requests 会将中文参数编码为 %E5%B9... 
#  所以 assert "广州" in req.url 会失败
# ✅ 改用 assert "apikey=xxx" in req.url 或 parse_qs
```

---

## 3.3 Mock 数据库 —— 两种策略

### 策略 A：真实 SQLite 内存数据库（推荐用于 CRUD 测试）

```python
def test_with_real_sqlite():
    repo = UserRepository(":memory:")  # 内存数据库，不落盘
    repo.create_user("U1", "张三", "z@t.com")
    user = repo.find_by_id("U1")
    assert user["name"] == "张三"

# ✅ 优点：真实 SQL，能测出 SQL 语法错误
# ❌ 缺点：不是生产数据库，SQL 方言可能不同
```

### 策略 B：完全 Mock 数据库连接（推荐用于测业务逻辑）

```python
def test_with_mock_db(self):
    with patch('module.sqlite3.connect') as mock_connect:
        # 设置 Mock 行为
        mock_connect.return_value.execute.return_value.fetchone.return_value = {
            "id": "U1", "name": "张三", "vip_level": 5
        }

        repo = UserRepository("test.db")
        user = repo.find_by_id("U1")

        assert user["vip_level"] == 5
        # 验证 SQL 参数
        mock_connect.return_value.execute.assert_called_with(
            "SELECT * FROM users WHERE id = ?", ("U1",)
        )

# ✅ 优点：飞一样快，完全不依赖数据库
# ❌ 缺点：测不到真实的 SQL 语义
```

### 🎯 选择建议

| 场景 | 用哪个 |
|------|--------|
| 测试复杂 SQL（JOIN/聚合/子查询） | 策略 A（SQLite 内存） |
| 测试业务逻辑（参数组装是否正确） | 策略 B（Mock 连接） |
| 异常处理（连接失败、超时） | 策略 B（side_effect=Exception） |
| CI 中快速验证 | 策略 B |

---

## 3.4 Mock 时间 —— 冻结「现在」

### 核心模式

```python
from datetime import datetime
from unittest.mock import patch

def test_business_hours():
    # 2. 冻结时间为「周一上午 10 点」
    fixed_now = datetime(2025, 1, 20, 10, 0, 0)  # 周一

    with patch('mymodule.datetime') as mock_dt:
        mock_dt.now.return_value = fixed_now
        # 关键：保留 datetime 类的其他功能
        mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)

        checker = BusinessHoursChecker()
        assert checker.is_business_hours() is True
```

### ⚠️ patch datetime 的坑

```python
#  只 mock now() 还不够！
#  代码里可能用 datetime.strftime(), datetime.weekday(), timedelta() 等
#  这些方法来自真实的 datetime 类，需要保留

# ✅ 正确做法：side_effect 是 datetime 构造函数
mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
mock_dt.now.return_value = fixed_now
mock_dt.strftime = datetime.strftime  # 保留 strftime
```

### 多时间点测试

```python
test_cases = [
    (datetime(2025, 1, 20, 10, 0), True,  "周一 10:00 → 营业"),
    (datetime(2025, 1, 20,  8, 0), False, "周一 08:00 → 没开门"),
    (datetime(2025, 1, 25, 10, 0), False, "周六 10:00 → 休息"),
]

for now, expected, desc in test_cases:
    with patch('module.datetime') as mock_dt:
        mock_dt.now.return_value = now
        mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
        assert check() == expected, desc
```

---

## 3.5 Mock 文件系统 —— mock_open

### 读文件

```python
from unittest.mock import mock_open, patch

fake_json = '{"db": {"host": "localhost"}}'

with patch("builtins.open", mock_open(read_data=fake_json)), \
     patch("os.path.exists", return_value=True):  # ← 关键：必须 Mock exists！
    loader = ConfigLoader()
    config = loader.load_config("config.json")

# ⚠️  常见的坑：只 Mock 了 open，忘记 Mock os.path.exists
# 代码里通常先 `if not os.path.exists(path)` 再 `open()`
# 必须两个都 Mock！
```

### 写文件

```python
mock_file = mock_open()
with patch("builtins.open", mock_file):
    save_config("output.json", {"key": "value"})

    mock_file.assert_called_once_with("output.json", 'w', encoding='utf-8')

    # 验证写入内容
    handle = mock_file()
    written = ''.join(call.args[0] for call in handle.write.call_args_list)
    assert '"key": "value"' in written
```

---

## 3.6 综合 Mock —— 多依赖场景

```python
@responses.activate
def test_complex_service():
    # Mock HTTP 1: 用户信息
    responses.get("http://user-api/users/U1", json={"name": "张三", "city": "北京"})
    # Mock HTTP 2: 天气
    responses.get("http://weather-api/current", json={"temperature": 38})

    # Mock 数据库
    with patch('module.sqlite3.connect') as mock_db:
        mock_db.return_value.execute.return_value.fetchone.return_value = {
            "vip_level": 5
        }

        notifier = OrderNotifier(user_svc, weather_svc, repo)
        msg = notifier.send_welcome_message("U1", "token")

        assert "VIP" in msg
        assert "注意防暑" in msg
        assert len(responses.calls) == 2  # 确认只发了 2 个 HTTP 请求
```

**核心思路**：把每个外部依赖的 Mock 一一叠加上去，像搭积木一样。

---

## 3.7 🏁 Phase 3 检查清单

- [ ] 能用 `@responses.activate` + `responses.get/post/put/delete` Mock HTTP
- [ ] 能 Mock 多种 HTTP 状态码（200/404/500/timeout）
- [ ] 能用 `responses.calls` 验证请求细节（URL/Header/Body）
- [ ] 理解数据库 Mock 的两种策略（真实 SQLite vs 完全 Mock）
- [ ] 能用 `patch('module.datetime')` 冻结时间
- [ ] 知道 patch datetime 需要 `side_effect=datetime` 保留其他方法
- [ ] 能用 `mock_open` + `patch('os.path.exists')` Mock 文件读写
- [ ] 能手写综合 Mock 场景（HTTP + DB + 时间都 Mock）

---

### 📝 面试话术 — Mock 外部依赖

> **面试官**：「你们怎么做 HTTP 和数据库的 Mock？」
>
> **答**：「HTTP 我们用 Python 的 `responses` 库，`@responses.activate` 激活后，所有 `requests` 发出的请求都会被拦截返回预设的 JSON，完全不发网络。我们会在测试里模拟各种状态码——200正常、404不存在、500服务器错误、timeout超时——来覆盖异常分支。
>
> 数据库分两种情况：测复杂 SQL 就用 SQLite 内存数据库做轻量 Fake，能真实执行 SQL；测业务逻辑就用 `unittest.mock` 完全 Mock 连接，`fetchone.return_value` 预设返回值，再 `assert_called_with` 验证 SQL 参数是否正确组装。时间相关的用 `patch` 把 `datetime.now()` 冻结到固定时间点。」

---

> 下一阶段：Phase 4 实战 —— 完整全链路 Mock 测试案例，模拟一个真实微服务调用链 🚀

---

# Phase 4：电商全链路 Mock 实战 🏆

> **测试覆盖：19 passed | 9 大场景 | 代码在 `tests/test_ecommerce.py`**
> **总计：91 tests / 91 passed / 4 阶段**

---

## 4.1 实战场景：电商下单全流程

```
┌──────────────────────────────────────────────────────────────┐
│                    OrderOrchestrator（被测）                   │
│                                                              │
│  下单请求 → ① 用户校验 → ② 余额检查 → ③ 库存检查             │
│           → ④ 锁定库存 → ⑤ 预授权 → ⑥ 确认扣款               │
│           → ⑦ 创建运单 → ⑧ 发通知 → ⑨ 审计日志              │
│                                                              │
│  依赖 6 个外部服务：                                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                     │
│  │UserService│ │Inventory │ │ Payment  │  ← 全部 Mock        │
│  │  (HTTP)  │ │  (HTTP)  │ │  (HTTP)  │                     │
│  └──────────┘ └──────────┘ └──────────┘                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                     │
│  │Logistics │ │Notif.    │ │AuditLog  │                     │
│  │ (HTTP)   │ │ (HTTP)   │ │  (DB)    │                     │
│  └──────────┘ └──────────┘ └──────────┘                     │
└──────────────────────────────────────────────────────────────┘
```

---

## 4.2 测试场景矩阵（19 条测试）

| # | 场景 | 分类 | 核心验证点 |
|:---:|------|:---:|-----------|
| 1 | 正常下单全流程 | 😊 正常 | 6 个服务全部调用，返回值完整 |
| 2 | 单商品下单 | 😊 边界 | 单个商品，金额正确 |
| 3 | 用户不存在 | ❌ 用户 | 后续步骤全部不执行 |
| 4 | 余额不足 | ❌ 用户 | 不查库存、不扣款 |
| 5 | 一个商品缺货 | ❌ 库存 | 列出缺货 SKU |
| 6 | 多个商品缺货 | ❌ 库存 | 全部缺货 SKU 列出 |
| 7 | 库存锁定失败 | ❌ 库存 | 并发场景 |
| 8 | 预授权失败 | 🔄 回滚 | **释放库存** |
| 9 | 确认扣款失败 | 🔄 回滚 | **释放库存 + 发失败通知** |
| 10 | 扣款失败不退款 | 🔄 边界 | 预授权成功但未真正扣款 → 不退款 |
| 11 | 运单创建失败 | 🔄 回滚 | **退款 + 释放库存**（钱和货全退） |
| 12 | 通知返回 False | 💪 容错 | 订单仍然成功 |
| 13 | 通知抛异常 | 💪 容错 | 订单仍然成功 |
| 14 | 审计日志完整性 | 📋 审计 | 10 个步骤全部记录，顺序正确 |
| 15 | 失败流程审计 | 📋 审计 | 日志停在失败步骤 |
| 16 | 审计时间戳 | 📋 审计 | 每条日志有 ISO 时间戳 |
| 17 | 动态验证金额 | 🔍 动态Mock | side_effect 函数校验传参 |
| 18 | 验证预授权参数 | 🔍 参数 | call_args 检查完整参数 |
| 19 | 真实 HTTP Mock | 🌐 混合 | responses 库 Mock 真实 UserService 的 HTTP |

---

## 4.3 SAGA 回滚模式

```python
#  回滚矩阵：每一步失败 → 需要回滚什么
"""
Step 1  用户校验失败     → 无需回滚（还没创建任何资源）
Step 2  余额不足          → 无需回滚
Step 3  库存不足          → 无需回滚
Step 4  锁定库存失败      → 无需回滚
Step 5  预授权失败        →  释放库存
Step 6  确认扣款失败      →  释放库存 + 通知用户
Step 7  运单创建失败      →  退款 + 释放库存  ← 最重的回滚
Step 8  通知失败          →  忽略（不是关键路径）
"""
```

### 回滚测试模板

```python
def test_step_X_fails__rollback_Y(self):
    """Step X 失败 → 验证 Y 被回滚"""
    # 1. 预设前面的步骤全部成功
    self.setup_success_up_to_step(X - 1)
    
    # 2. 让 Step X 失败
    self.service_X.method.side_effect = Exception("故障")
    
    # 3. 执行
    result = self.orchestrator.place_order(...)
    
    # 4. 验证失败
    assert result["status"] == "failed"
    assert result["step"] == "capture"
    
    # 5. 验证回滚操作
    self.inventory_svc.release_items.assert_called_once()  # 释放库存
    self.payment_svc.refund.assert_called_once()           # 退款（如果有）
```

---

## 4.4 Mock 审计日志 —— 真实 SQLite

```python
# 审计日志用真实 SQLite 内存数据库（不 Mock）
# 好处：能验证完整的审计链，每条日志都真实写入
self.audit_logger = AuditLogger(":memory:")

# 验证完整审计链
events = self.audit_logger.get_events(order_id)
event_names = [e["event"] for e in events]
assert event_names == [
    "ORDER_CREATED", "USER_VERIFIED", "BALANCE_SUFFICIENT",
    "STOCK_VERIFIED", "ITEMS_LOCKED", "PRE_AUTH_SUCCESS",
    "PAYMENT_CAPTURED", "SHIPMENT_CREATED",
    "NOTIFICATION_SENT", "ORDER_COMPLETED"
]
```

---

## 4.5 动态 Mock —— side_effect 函数

```python
# 不只是固定返回值，还能在 Mock 里做断言
def verify_balance(user_id, amount):
    assert user_id == "U001"
    assert amount == 5097.0, f"金额计算错误: {amount}"
    return True

self.user_svc.check_balance.side_effect = verify_balance
```

---

## 4.6 项目最终文件结构

```
mock_testing/
├── src/
│   ├── __init__.py
│   ├── services.py           ← P2: 订单服务（支付/库存/通知）
│   ├── external_services.py  ← P3: HTTP/DB/时间/文件
│   └── ecommerce.py          ← P4: 电商全链路编排器
├── tests/
│   ├── __init__.py
│   ├── test_services.py      ← 36 tests: unittest.mock 基础
│   ├── test_external_mock.py ← 36 tests: HTTP/DB/时间/文件
│   └── test_ecommerce.py     ← 19 tests: 全链路实战
├── .venv/
└── README.md                 ← 完整学习笔记
```

---

## 4.7 🏁 Phase 4 检查清单

- [ ] 能画出电商下单的完整调用链
- [ ] 能识别每一步失败时需要回滚什么（SAGA 回滚矩阵）
- [ ] 能写出完整回滚测试（预授权失败 → 释放库存）
- [ ] 能验证审计日志的完整性和正确顺序
- [ ] 能用 `side_effect` 函数做动态参数校验
- [ ] 能用 `call_args` 检查 Mock 方法收到的完整参数
- [ ] 理解「通知失败不影响主流程」的容错设计
- [ ] 能用 `MagicMock(spec=RealClass)` 创建带接口约束的 Mock
- [ ] 19 条测试全部通过

---

## 4.8 Mock 测试全模块总结

```
┌─────────────────────────────────────────────────────────┐
│                Mock 测试学习完成 ✅                       │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  P1 概念     理解为什么、测试替身 5 种分类                │
│  P2 基础     Mock/MagicMock/patch/autospec 36 tests     │
│  P3 进阶     responses HTTP/DB/时间/文件 Mock 36 tests   │
│  P4 实战     电商全链路 SAGA 回滚 19 tests                │
│                                                         │
│  总计：91 tests / 91 passed / 6 个源文件                  │
│                                                         │
│  掌握技能：                                              │
│  ✅ 用 unittest.mock 替换任何外部依赖                    │
│  ✅ 用 responses 拦截 HTTP 请求                          │
│  ✅ Mock 数据库（真实 SQLite + 完全 Mock）                │
│  ✅ 冻结时间（patch datetime）                            │
│  ✅ Mock 文件读写（mock_open）                            │
│  ✅ 全链路回滚测试（SAGA 模式）                           │
│  ✅ 审计日志验证                                         │
│  ✅ 动态 side_effect 参数校验                            │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

### 📝 终极面试话术 — 全链路 Mock 测试

> **面试官**：「你们怎么测试一个涉及多个微服务的下单流程？」
>
> **答**：「我们用全链路 Mock 测试。把下单流程涉及的用户服务、库存服务、支付网关、物流服务、通知服务全部用 `unittest.mock` 的 `MagicMock(spec=RealClass)` 替换掉，每步预设 `return_value` 和 `side_effect`。测试分三类：
>
> 第一类是**正常流程**，验证 6 个服务被按正确顺序调用，返回值包含完整订单信息。
>
> 第二类是**异常回滚**——这是最有价值的。比如预授权成功但确认扣款失败时，代码必须释放库存；运单创建失败时，必须同时退款和释放库存。我们用 `assert_called_once_with` 验证回滚操作确实执行了。
>
> 第三类是**容错测试**，比如通知服务挂了，订单本身不受影响。
>
> 审计日志我们用真实 SQLite 内存数据库，验证每一步都记录了正确的事件和时间戳。」

---

> 🎉 Mock 测试模块完结！下一站：性能测试流程 🚀
