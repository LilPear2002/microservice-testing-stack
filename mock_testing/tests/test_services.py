"""
tests/test_services.py — Phase 2：unittest.mock 基础实操
========================================================
从零开始学 Mock，每个测试函数讲一个知识点。
运行：cd /workspace/mock_testing && source .venv/bin/activate && pytest tests/test_services.py -v
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call

# 导入被测代码
import sys
sys.path.insert(0, '/workspace/mock_testing/src')
from services import OrderService, get_discount, calculate_final_price


# ═══════════════════════════════════════════════════════════
# 第 1 节：Mock 对象基础 —— 创建和基本用法
# ═══════════════════════════════════════════════════════════

class TestMockBasics:
    """Mock 是什么？一个可以「假装成任何对象」的替身"""

    def test_mock_is_a_blank_slate(self):
        """Mock 可以接收任何属性访问和任何方法调用，不会报错"""
        m = Mock()

        # 访问不存在的属性 → 返回一个 Mock（不是 AttributeError！）
        result = m.anything.you.want  # 不会报错
        assert isinstance(result, Mock)

        # 调用不存在的方法 → 也返回 Mock
        result = m.fly_to_the_moon(rocket="Apollo")
        assert isinstance(result, Mock)

    def test_return_value__fixed_response(self):
        """return_value：让 Mock 的方法返回固定值"""
        payment = Mock()
        payment.charge.return_value = {"status": "success", "transaction_id": "TXN-888"}

        result = payment.charge("user123", 99.0)

        assert result == {"status": "success", "transaction_id": "TXN-888"}
        #  每次调用都返回同样的值，不依赖外部

    def test_return_value__different_for_different_methods(self):
        """每个 Mock 方法的 return_value 独立设置"""
        service = Mock()
        service.check_stock.return_value = 42       # 库存有 42 件
        service.send_email.return_value = True       # 邮件发送成功

        assert service.check_stock("P001") == 42
        assert service.send_email("a@b.com", "hi") is True

    def test_return_value__default_is_new_mock(self):
        """不设 return_value 时，返回一个新的 Mock 对象"""
        m = Mock()
        result = m.some_method()
        assert isinstance(result, Mock)  # 默认返回 Mock 实例


# ═══════════════════════════════════════════════════════════
# 第 2 节：side_effect —— Mock 的动态行为
# ═══════════════════════════════════════════════════════════

class TestSideEffect:
    """side_effect 比 return_value 更灵活：可抛异常、可变返回值、可执行函数"""

    def test_side_effect__raise_exception(self):
        """模拟外部服务挂了 → 抛异常"""
        payment = Mock()
        payment.charge.side_effect = ConnectionError("支付网关超时")

        with pytest.raises(ConnectionError, match="支付网关超时"):
            payment.charge("user123", 99.0)

    def test_side_effect__return_sequence(self):
        """每次调用返回不同的值（列表/元组）"""
        mock_db = Mock()
        # 第 1 次查库存→100, 第 2 次→0(缺货), 第 3 次→50
        mock_db.check_stock.side_effect = [100, 0, 50]

        assert mock_db.check_stock("P001") == 100
        assert mock_db.check_stock("P001") == 0
        assert mock_db.check_stock("P001") == 50

    def test_side_effect__custom_function(self):
        """side_effect 可以是一个函数，根据参数动态返回"""
        def my_logic(product_id):
            if product_id == "VIP-ITEM":
                return 999
            return 10

        inventory = Mock()
        inventory.check_stock.side_effect = my_logic

        assert inventory.check_stock("VIP-ITEM") == 999
        assert inventory.check_stock("普通商品") == 10

    def test_side_effect__exception_then_success(self):
        """前两次抛异常，第三次成功 —— 模拟「重试」场景"""
        api = Mock()
        api.call.side_effect = [
            ConnectionError("第1次失败"),
            ConnectionError("第2次失败"),
            {"status": "ok"}  # 第3次成功
        ]

        # 第1、2次失败
        for _ in range(2):
            with pytest.raises(ConnectionError):
                api.call()

        # 第3次成功
        assert api.call() == {"status": "ok"}


# ═══════════════════════════════════════════════════════════
# 第 3 节：assert_called —— 验证 Mock 被怎么调用了
# ═══════════════════════════════════════════════════════════

class TestAssertCalled:
    """Mock 会记录所有调用历史，事后检查调用是否符合预期"""

    def test_assert_called(self):
        """最简单的：被调用过就行"""
        m = Mock()
        m.do_something()
        m.do_something.assert_called()  # ✅ 调过了

    def test_assert_called_once(self):
        """确认只被调用了一次"""
        m = Mock()
        m.do_something()
        m.do_something.assert_called_once()  # ✅

        # 如果调了两次 → AssertionError
        m.do_something()
        with pytest.raises(AssertionError):
            m.do_something.assert_called_once()

    def test_assert_called_with__exact_args(self):
        """确认被调用时传了正确的参数"""
        notifier = Mock()
        notifier.send_email("user@test.com", "标题", "正文")

        notifier.send_email.assert_called_with("user@test.com", "标题", "正文")  # ✅

    def test_assert_called_with__wrong_args_fails(self):
        """参数不对 → 报错"""
        notifier = Mock()
        notifier.send_email("wrong@test.com", "标题", "正文")

        with pytest.raises(AssertionError):
            notifier.send_email.assert_called_with("right@test.com", "标题", "正文")

    def test_assert_not_called(self):
        """确认某个方法从没被调用"""
        m = Mock()
        m.method_a()
        m.method_b.assert_not_called()  # ✅ 确实没调过

    def test_call_count(self):
        """查看被调了几次"""
        m = Mock()
        m.hello()
        m.hello()
        m.hello()

        assert m.hello.call_count == 3

    def test_call_args_list(self):
        """查看每次调用的参数历史"""
        api = Mock()
        api.search("python")
        api.search("golang")
        api.search("rust")

        assert api.search.call_args_list == [
            call("python"),
            call("golang"),
            call("rust"),
        ]


# ═══════════════════════════════════════════════════════════
# 第 4 节：MagicMock —— 自动 Mock 魔术方法
# ═══════════════════════════════════════════════════════════

class TestMagicMock:
    """MagicMock 是 Mock 的子类，自动 mock 了 __len__、__iter__、__getitem__ 等"""

    def test_mock_vs_magicmock__len(self):
        """普通 Mock 没有 __len__ → len() 报错"""
        plain_mock = Mock()
        with pytest.raises(TypeError):
            len(plain_mock)

    def test_magicmock_has_magic_methods(self):
        """MagicMock 自动支持魔术方法"""
        magic = MagicMock()
        magic.__len__.return_value = 5

        assert len(magic) == 5  # ✅

    def test_magicmock__iter(self):
        """MagicMock 默认支持迭代"""
        magic = MagicMock()
        magic.__iter__.return_value = iter([1, 2, 3])

        result = list(magic)
        assert result == [1, 2, 3]

    def test_magicmock__getitem(self):
        """MagicMock 支持 [] 操作"""
        magic = MagicMock()
        magic.__getitem__.return_value = "hello"

        assert magic["any_key"] == "hello"  # ✅


# ═══════════════════════════════════════════════════════════
# 第 5 节：patch —— 替换真实依赖的核心武器 ⭐
# ═══════════════════════════════════════════════════════════

class TestPatchDecorator:
    """@patch 装饰器：临时把模块里的真实类/函数替换成 Mock"""

    @patch('src.services.PaymentGateway')  # 替换 PaymentGateway 类
    @patch('src.services.InventoryService')  # 替换 InventoryService 类
    @patch('src.services.NotificationService')  # 替换 NotificationService 类
    def test_create_order_success(
        self, MockNotify, MockInventory, MockPayment
    ):
        """
         用 @patch 装饰器，三个外部依赖全部替换成 Mock。
         Mock 对象按「从下到上」的顺序传入参数。
        """
        # ── 预设 Mock 行为 ──
        mock_payment = MockPayment.return_value   # 因为 service 里是 PaymentGateway() 实例
        mock_inventory = MockInventory.return_value
        mock_notifier = MockNotify.return_value

        mock_inventory.check_stock.return_value = 10        # 库存充足
        mock_inventory.reserve.return_value = True           # 预留成功
        mock_payment.charge.return_value = {
            "status": "success",
            "transaction_id": "TXN-12345"
        }

        # ── 执行被测代码 ──
        service = OrderService(
            MockPayment(), MockInventory(), MockNotify()
        )
        result = service.create_order("user123", "PROD-001", 99.0)

        # ── 验证返回值 ──
        assert result["status"] == "success"
        assert result["transaction_id"] == "TXN-12345"
        assert result["amount"] == 99.0

        # ── 验证依赖调用 ──
        mock_inventory.check_stock.assert_called_once_with("PROD-001")
        mock_inventory.reserve.assert_called_once_with("PROD-001", 1)
        mock_payment.charge.assert_called_once_with("user123", 99.0)
        mock_notifier.send_email.assert_called_once()

    @patch('src.services.PaymentGateway')
    @patch('src.services.InventoryService')
    @patch('src.services.NotificationService')
    def test_create_order_insufficient_stock(
        self, MockNotify, MockInventory, MockPayment
    ):
        """库存不足 → 订单失败，不扣款、不发通知"""
        mock_inventory = MockInventory.return_value
        mock_inventory.check_stock.return_value = 0  # 库存为 0！

        service = OrderService(
            MockPayment(), MockInventory(), MockNotify()
        )
        result = service.create_order("user123", "PROD-001", 99.0)

        assert result["status"] == "failed"
        assert "库存不足" in result["reason"]

        # 关键验证：库存不足时，不应该扣款
        MockPayment.return_value.charge.assert_not_called()

    @patch('src.services.PaymentGateway')
    @patch('src.services.InventoryService')
    @patch('src.services.NotificationService')
    def test_create_order_payment_fails_rollback(
        self, MockNotify, MockInventory, MockPayment
    ):
        """支付失败 → 释放库存，回滚操作"""
        mock_inventory = MockInventory.return_value
        mock_payment = MockPayment.return_value

        mock_inventory.check_stock.return_value = 10
        mock_inventory.reserve.return_value = True
        mock_payment.charge.side_effect = ConnectionError("支付网络故障")

        service = OrderService(
            MockPayment(), MockInventory(), MockNotify()
        )
        result = service.create_order("user123", "PROD-001", 99.0)

        assert result["status"] == "failed"
        assert "支付失败" in result["reason"]

        #  关键：支付失败后，库存必须释放！
        mock_inventory.release.assert_called_once_with("PROD-001", 1)


class TestPatchContextManager:
    """用 with patch(...) 上下文管理器，更灵活"""

    def test_with_patch_context(self):
        """with patch 只在该代码块内生效，退出后自动恢复"""
        from src import services  # 从 src 目录导入
        original_gateway = services.PaymentGateway

        with patch('src.services.PaymentGateway') as MockPayment:
            mock_instance = MockPayment.return_value
            mock_instance.charge.return_value = {"status": "ok"}

            gateway = services.PaymentGateway()
            assert gateway.charge("u1", 10) == {"status": "ok"}

        #  退出 with 后，自动恢复！
        gateway = services.PaymentGateway()
        assert isinstance(gateway, original_gateway)

    def test_with_patch__partial_mock(self):
        """只 Mock 支付，其他两个用真实（虽然慢，但可以这样）"""
        with patch('src.services.PaymentGateway') as MockPayment:
            mock_payment = MockPayment.return_value
            mock_payment.charge.return_value = {
                "status": "success",
                "transaction_id": "TXN-999"
            }

            from src.services import PaymentGateway, InventoryService, NotificationService
            service = OrderService(
                MockPayment(), InventoryService(), NotificationService()
            )
            result = service.create_order("u1", "P1", 10)

            # 只关心支付是否被正确调用
            mock_payment.charge.assert_called_once_with("u1", 10)


class TestPatchObject:
    """patch.object：替换已存在对象的属性/方法"""

    def test_patch_object__existing_instance(self):
        """已经有了一个实例，想换掉它的某个方法"""
        from services import PaymentGateway

        gateway = PaymentGateway()

        with patch.object(gateway, 'charge') as mock_charge:
            mock_charge.return_value = {"status": "mocked"}

            result = gateway.charge("u1", 10)
            assert result == {"status": "mocked"}

        # 退出 patch.object 后恢复
        # （但 PaymentGateway.charge 原来是真方法，恢复了）


# ═══════════════════════════════════════════════════════════
# 第 6 节：Mock 纯函数依赖 —— get_discount 案例
# ═══════════════════════════════════════════════════════════

class TestGetDiscount:
    """Mock 数据库连接，测试 get_discount 的业务逻辑"""

    def test_get_discount__normal(self):
        """正常折扣计算"""
        mock_db = Mock()
        mock_db.execute.return_value = {"discount": 0.2}  # 打 8 折

        result = get_discount("user123", mock_db)

        assert result == 0.2
        mock_db.execute.assert_called_once_with(
            "SELECT discount FROM users WHERE id=?", "user123"
        )

    def test_get_discount__new_user_no_discount(self):
        """新用户无折扣 → 返回 0"""
        mock_db = Mock()
        mock_db.execute.return_value = None

        result = get_discount("new_user", mock_db)

        assert result == 0.0

    def test_get_discount__cap_at_90_percent(self):
        """折扣上限 90%（VIP 再高也只打 1 折）"""
        mock_db = Mock()
        mock_db.execute.return_value = {"discount": 0.95}  # 95% 折扣

        result = get_discount("vip_user", mock_db)

        assert result == 0.9  # 被上限截断

    def test_calculate_final_price(self):
        """纯函数，不需要 Mock"""
        assert calculate_final_price(100, 0.2) == 80.0  # 8折
        assert calculate_final_price(99.9, 0.15) == 84.92  # 85折


# ═══════════════════════════════════════════════════════════
# 第 7 节：autospec —— 让 Mock 守规矩
# ═══════════════════════════════════════════════════════════

class TestAutospec:
    """
    autospec=True：Mock 会根据原对象的接口来约束自己。
    如果你 Mock 了一个不存在的方法，调用时会报错 —— 帮你发现拼写错误。
    """

    def test_without_autospec__typo_silently_passes(self):
        """不设 autospec：拼错方法名也不报错 → 危险的 false positive"""
        from services import PaymentGateway

        # 拼错了！pay → 应该是 charge
        mock = Mock(spec=None)  # 不加 autospec
        mock.pay("user", 100)  #  不会报错！Mock 接受任何方法

        # 你的测试不会发现这个 bug......
        mock.pay.assert_called()  # ✅ 通过，但测的是错误的方法名

    def test_with_autospec__typo_raises_error(self):
        """autospec=True：拼错方法名 → 立即报错"""
        from services import PaymentGateway

        mock = Mock(spec=PaymentGateway)  #  绑定真实接口

        # 真实 PaymentGateway 只有 charge 和 refund，没有 pay
        with pytest.raises(AttributeError, match="pay"):
            mock.pay("user", 100)  #  报错！帮你发现拼写错误

    def test_autospec__only_valid_methods_work(self):
        """autospec 让 Mock 只接受真实类中存在的方法"""
        from services import PaymentGateway

        mock = Mock(spec=PaymentGateway)
        mock.charge.return_value = {"status": "ok"}

        # ✅ charge 是真实方法
        assert mock.charge("u1", 10) == {"status": "ok"}

        # ✅ refund 也是真实方法
        mock.refund.return_value = {"status": "refunded"}
        assert mock.refund("TXN-1") == {"status": "refunded"}

    def test_create_autospec__convenience_function(self):
        """create_autospec 是更便捷的写法"""
        from unittest.mock import create_autospec
        from services import PaymentGateway

        mock = create_autospec(PaymentGateway)
        mock.charge.return_value = {"status": "ok"}

        assert mock.charge("u1", 100) == {"status": "ok"}

        # 不存在的方法 → 报错
        with pytest.raises(AttributeError):
            mock.fly_to_moon()


# ═══════════════════════════════════════════════════════════
# 第 8 节：综合练习 —— 取消订单
# ═══════════════════════════════════════════════════════════

class TestCancelOrder:
    """综合运用所学，测试 cancel_order 方法"""

    @patch('src.services.PaymentGateway')
    @patch('src.services.InventoryService')
    @patch('src.services.NotificationService')
    def test_cancel_order_full_flow(
        self, MockNotify, MockInventory, MockPayment
    ):
        """取消订单 → 退款 + 释放库存 + 发通知"""
        mock_payment = MockPayment.return_value
        mock_inventory = MockInventory.return_value
        mock_notifier = MockNotify.return_value

        mock_payment.refund.return_value = {"status": "refunded"}

        service = OrderService(
            MockPayment(), MockInventory(), MockNotify()
        )
        result = service.cancel_order("TXN-ABC", "PROD-X")

        assert result["status"] == "cancelled"

        #  验证三个操作都执行了
        mock_payment.refund.assert_called_once_with("TXN-ABC")
        mock_inventory.release.assert_called_once_with("PROD-X", 1)
        mock_notifier.send_email.assert_called_once()


# ═══════════════════════════════════════════════════════════
# 附：pytest-mock 插件用法（mocker fixture）
# pip install pytest-mock 后可用，语法更简洁
# ═══════════════════════════════════════════════════════════

class TestPytestMock:
    """pytest-mock 的 mocker fixture 替代 patch"""

    def test_mocker_patch(self, mocker):
        """mocker.patch 比 @patch 更直观"""
        mock_charge = mocker.patch('src.services.PaymentGateway.charge')
        mock_charge.return_value = {"status": "patched"}

        from src.services import PaymentGateway
        gw = PaymentGateway()
        result = gw.charge("u1", 10)

        assert result == {"status": "patched"}
        mock_charge.assert_called_once_with("u1", 10)

    def test_mocker_mock(self, mocker):
        """mocker.Mock() 创建 Mock 对象"""
        mock_db = mocker.Mock()
        mock_db.execute.return_value = {"discount": 0.3}

        result = get_discount("user1", mock_db)
        assert result == 0.3
