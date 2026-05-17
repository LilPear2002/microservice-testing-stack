"""
tests/test_ecommerce.py — Phase 4：电商全链路 Mock 测试
========================================================
覆盖：正常流程 + 6 种失败场景 + 回滚验证 + 审计日志

运行：cd /workspace/mock_testing && source .venv/bin/activate && pytest tests/test_ecommerce.py -v
"""
import pytest
import sys
from unittest.mock import Mock, MagicMock, patch

import responses

sys.path.insert(0, '/workspace/mock_testing/src')
from ecommerce import (
    OrderOrchestrator, UserService, InventoryService,
    PaymentService, LogisticsService, NotificationService, AuditLogger
)


# ═══════════════════════════════════════════════════════
# 测试辅助：创建 Mock 服务和被测对象
# ═══════════════════════════════════════════════════════

class EcommerceTestBase:
    """基类：提供公共的 Mock 服务和测试数据"""

    def setup_method(self):
        """每个测试前创建全新的 Mock 对象"""
        self.user_svc = MagicMock(spec=UserService)
        self.inventory_svc = MagicMock(spec=InventoryService)
        self.payment_svc = MagicMock(spec=PaymentService)
        self.logistics_svc = MagicMock(spec=LogisticsService)
        self.notification_svc = MagicMock(spec=NotificationService)
        self.audit_logger = AuditLogger(":memory:")  # 用真实 SQLite 测审计日志

        self.orchestrator = OrderOrchestrator(
            self.user_svc, self.inventory_svc, self.payment_svc,
            self.logistics_svc, self.notification_svc, self.audit_logger
        )

        # 默认测试数据
        self.valid_items = [
            {"sku": "PHONE-001", "quantity": 1, "price": 4999.0},
            {"sku": "CASE-002", "quantity": 2, "price": 49.0},
        ]
        self.total = 4999.0 + 49.0 * 2  # = 5097.0
        self.address = {
            "name": "张三", "phone": "13800138000",
            "address": "北京市朝阳区 xxx 路 100 号"
        }

    def mock_happy_path(self):
        """预设所有 Mock 为正常返回值"""
        # User
        self.user_svc.get_user.return_value = {
            "id": "U001", "name": "张三", "email": "zhang@test.com"
        }
        self.user_svc.check_balance.return_value = True

        # Inventory
        self.inventory_svc.check_availability.return_value = [
            {"sku": "PHONE-001", "available": True, "stock": 50},
            {"sku": "CASE-002", "available": True, "stock": 200},
        ]
        self.inventory_svc.lock_items.return_value = True

        # Payment
        self.payment_svc.pre_auth.return_value = {
            "auth_id": "AUTH-ABC123", "status": "authorized"
        }
        self.payment_svc.capture.return_value = {
            "transaction_id": "TXN-XYZ789", "status": "captured"
        }

        # Logistics
        self.logistics_svc.create_shipment.return_value = {
            "tracking_number": "SF1234567890", "carrier": "顺丰速运"
        }

        # Notification
        self.notification_svc.send_order_confirmation.return_value = True


# ═══════════════════════════════════════════════════════
# 场景 1：正常流程 —— 全部成功 ✅
# ═══════════════════════════════════════════════════════

class TestHappyPath(EcommerceTestBase):

    def test_place_order_full_flow(self):
        """下单全流程：用户→余额→库存→锁定→预授权→扣款→运单→通知→完成"""
        self.mock_happy_path()

        result = self.orchestrator.place_order("U001", self.valid_items, self.address)

        # ── 验证返回值 ──
        assert result["status"] == "success"
        assert result["order_id"].startswith("ORD-")
        assert result["transaction_id"] == "TXN-XYZ789"
        assert result["tracking_number"] == "SF1234567890"
        assert result["total_amount"] == self.total
        assert result["items"] == 2

        # ── 验证每一步都被调用了 ──
        self.user_svc.get_user.assert_called_once_with("U001")
        self.user_svc.check_balance.assert_called_once_with("U001", self.total)
        self.inventory_svc.check_availability.assert_called_once()
        self.inventory_svc.lock_items.assert_called_once()
        self.payment_svc.pre_auth.assert_called_once()
        self.payment_svc.capture.assert_called_once_with("AUTH-ABC123")
        self.logistics_svc.create_shipment.assert_called_once()
        self.notification_svc.send_order_confirmation.assert_called_once()

        # ── 验证审计日志 ──
        events = self.audit_logger.get_events(result["order_id"])
        event_names = [e["event"] for e in events]
        assert "ORDER_CREATED" in event_names
        assert "USER_VERIFIED" in event_names
        assert "BALANCE_SUFFICIENT" in event_names
        assert "STOCK_VERIFIED" in event_names
        assert "ITEMS_LOCKED" in event_names
        assert "PRE_AUTH_SUCCESS" in event_names
        assert "PAYMENT_CAPTURED" in event_names
        assert "SHIPMENT_CREATED" in event_names
        assert "NOTIFICATION_SENT" in event_names
        assert "ORDER_COMPLETED" in event_names
        assert len(events) == 10  # 共 10 个事件节点

    def test_single_item_order(self):
        """单商品下单 —— 边界条件"""
        self.mock_happy_path()
        single_item = [{"sku": "BOOK-001", "quantity": 1, "price": 59.0}]

        result = self.orchestrator.place_order("U001", single_item, self.address)

        assert result["status"] == "success"
        assert result["total_amount"] == 59.0
        assert result["items"] == 1


# ═══════════════════════════════════════════════════════
# 场景 2：用户相关失败
# ═══════════════════════════════════════════════════════

class TestUserFailures(EcommerceTestBase):

    def test_user_not_found(self):
        """用户不存在 → 直接返回失败，不执行后续步骤"""
        self.user_svc.get_user.return_value = None

        result = self.orchestrator.place_order("U999", self.valid_items, self.address)

        assert result["status"] == "failed"
        assert result["step"] == "user_check"
        assert "用户不存在" in result["reason"]

        # 关键：后续步骤不应该被调用
        self.user_svc.check_balance.assert_not_called()
        self.inventory_svc.check_availability.assert_not_called()

        # 但审计日志应该记录了
        events = self.audit_logger.get_events(result.get("order_id", ""))
        if events:
            assert events[0]["event"] == "ORDER_CREATED"

    def test_insufficient_balance(self):
        """余额不足 → 失败，不查库存"""
        self.user_svc.get_user.return_value = {"id": "U001", "name": "张三"}
        self.user_svc.check_balance.return_value = False  # 余额不够

        result = self.orchestrator.place_order("U001", self.valid_items, self.address)

        assert result["status"] == "failed"
        assert result["step"] == "balance_check"
        assert "余额不足" in result["reason"]

        self.inventory_svc.check_availability.assert_not_called()
        self.payment_svc.pre_auth.assert_not_called()


# ═══════════════════════════════════════════════════════
# 场景 3：库存相关失败
# ═══════════════════════════════════════════════════════

class TestInventoryFailures(EcommerceTestBase):

    def test_stock_insufficient__one_item(self):
        """单个商品缺货"""
        self.user_svc.get_user.return_value = {"id": "U001", "name": "张三"}
        self.user_svc.check_balance.return_value = True
        self.inventory_svc.check_availability.return_value = [
            {"sku": "PHONE-001", "available": False, "stock": 0},
            {"sku": "CASE-002", "available": True, "stock": 200},
        ]

        result = self.orchestrator.place_order("U001", self.valid_items, self.address)

        assert result["status"] == "failed"
        assert result["step"] == "stock_check"
        assert "PHONE-001" in result["reason"]

        # 没锁定、没扣款
        self.inventory_svc.lock_items.assert_not_called()
        self.payment_svc.pre_auth.assert_not_called()

    def test_stock_insufficient__multiple_items(self):
        """多个商品缺货 —— 全部列出"""
        self.user_svc.get_user.return_value = {"id": "U001", "name": "张三"}
        self.user_svc.check_balance.return_value = True
        self.inventory_svc.check_availability.return_value = [
            {"sku": "PHONE-001", "available": False, "stock": 0},
            {"sku": "CASE-002", "available": False, "stock": 0},
        ]

        result = self.orchestrator.place_order("U001", self.valid_items, self.address)

        assert "PHONE-001" in result["reason"]
        assert "CASE-002" in result["reason"]

    def test_lock_items_fails(self):
        """库存有货但锁定失败（并发导致）"""
        self.user_svc.get_user.return_value = {"id": "U001", "name": "张三"}
        self.user_svc.check_balance.return_value = True
        self.inventory_svc.check_availability.return_value = [
            {"sku": "PHONE-001", "available": True, "stock": 10},
            {"sku": "CASE-002", "available": True, "stock": 100},
        ]
        self.inventory_svc.lock_items.return_value = False  # 锁定失败

        result = self.orchestrator.place_order("U001", self.valid_items, self.address)

        assert result["status"] == "failed"
        assert result["step"] == "lock_items"
        assert "锁定库存失败" in result["reason"]


# ═══════════════════════════════════════════════════════
# 场景 4：支付相关失败 + 回滚验证  ⭐ 核心
# ═══════════════════════════════════════════════════════

class TestPaymentRollback(EcommerceTestBase):

    def setup_method(self):
        super().setup_method()
        # 预设用户和库存都正常
        self.user_svc.get_user.return_value = {"id": "U001", "name": "张三"}
        self.user_svc.check_balance.return_value = True
        self.inventory_svc.check_availability.return_value = [
            {"sku": "PHONE-001", "available": True, "stock": 50},
            {"sku": "CASE-002", "available": True, "stock": 200},
        ]
        self.inventory_svc.lock_items.return_value = True

    def test_pre_auth_fails__release_inventory(self):
        """预授权失败 → 必须释放库存"""
        self.payment_svc.pre_auth.side_effect = ConnectionError("支付网关超时")

        result = self.orchestrator.place_order("U001", self.valid_items, self.address)

        assert result["status"] == "failed"
        assert result["step"] == "pre_auth"

        #  关键：库存必须释放！
        order_id = list(result.values())[0] if False else None
        self.inventory_svc.release_items.assert_called_once()

        # 后续步骤不能执行
        self.payment_svc.capture.assert_not_called()
        self.logistics_svc.create_shipment.assert_not_called()

    def test_capture_fails__release_inventory_and_notify(self):
        """确认扣款失败 → 释放库存 + 发失败通知"""
        self.payment_svc.pre_auth.return_value = {
            "auth_id": "AUTH-ABC", "status": "authorized"
        }
        self.payment_svc.capture.side_effect = Exception("银行拒绝交易")

        result = self.orchestrator.place_order("U001", self.valid_items, self.address)

        assert result["status"] == "failed"
        assert result["step"] == "capture"

        #  关键：库存必须释放
        self.inventory_svc.release_items.assert_called_once()
        #  关键：用户必须收到失败通知
        self.notification_svc.send_payment_failed.assert_called_once()

        self.logistics_svc.create_shipment.assert_not_called()

    def test_capture_fails__pre_auth_not_captured(self):
        """
        重要边界：预授权成功但扣款失败时，
        预授权会在一段时间后自动过期（银行机制），
        不需要代码里显式取消预授权，但必须释放库存。
        """
        self.payment_svc.pre_auth.return_value = {"auth_id": "AUTH-ABC"}
        self.payment_svc.capture.side_effect = Exception("网络中断")

        self.orchestrator.place_order("U001", self.valid_items, self.address)

        # 预授权成功过
        self.payment_svc.pre_auth.assert_called_once()
        # 尝试过扣款
        self.payment_svc.capture.assert_called_once()
        # 没有退款（因为没真正扣款成功）
        self.payment_svc.refund.assert_not_called()
        # 库存释放了
        self.inventory_svc.release_items.assert_called_once()


# ═══════════════════════════════════════════════════════
# 场景 5：运单创建失败 → 退款 + 释放库存
# ═══════════════════════════════════════════════════════

class TestShipmentRollback(EcommerceTestBase):

    def setup_method(self):
        super().setup_method()
        self.user_svc.get_user.return_value = {"id": "U001", "name": "张三"}
        self.user_svc.check_balance.return_value = True
        self.inventory_svc.check_availability.return_value = [
            {"sku": "PHONE-001", "available": True, "stock": 50},
        ]
        self.inventory_svc.lock_items.return_value = True
        self.payment_svc.pre_auth.return_value = {"auth_id": "AUTH-ABC"}
        self.payment_svc.capture.return_value = {
            "transaction_id": "TXN-XYZ", "status": "captured"
        }

    def test_shipment_fails__refund_and_release(self):
        """运单创建失败 → 退款 + 释放库存（钱和货都回滚）"""
        self.logistics_svc.create_shipment.side_effect = Exception("物流系统故障")

        result = self.orchestrator.place_order(
            "U001",
            [{"sku": "PHONE-001", "quantity": 1, "price": 4999.0}],
            self.address
        )

        assert result["status"] == "failed"
        assert result["step"] == "shipment"

        #  关键：必须退款
        self.payment_svc.refund.assert_called_once_with("TXN-XYZ", 4999.0)
        #  关键：必须释放库存
        self.inventory_svc.release_items.assert_called_once()

        # 确认通知没发（因为失败了）
        self.notification_svc.send_order_confirmation.assert_not_called()


# ═══════════════════════════════════════════════════════
# 场景 6：通知失败不影响主流程
# ═══════════════════════════════════════════════════════

class TestNotificationFailure(EcommerceTestBase):

    def test_notification_fails__order_still_succeeds(self):
        """通知发送失败 → 订单仍然成功（通知不是关键路径）"""
        self.mock_happy_path()
        self.notification_svc.send_order_confirmation.return_value = False

        result = self.orchestrator.place_order("U001", self.valid_items, self.address)

        #  关键：虽然通知失败，但订单仍然成功
        assert result["status"] == "success"
        assert "tracking_number" in result

        # 所有其他步骤都正常执行了
        self.payment_svc.capture.assert_called_once()
        self.logistics_svc.create_shipment.assert_called_once()

    def test_notification_throws_exception__order_still_succeeds(self):
        """通知抛异常 → 订单仍然成功"""
        self.mock_happy_path()
        self.notification_svc.send_order_confirmation.side_effect = Exception("邮件网关爆炸")

        result = self.orchestrator.place_order("U001", self.valid_items, self.address)

        assert result["status"] == "success"  # 仍然成功！


# ═══════════════════════════════════════════════════════
# 场景 7：审计日志完整性验证
# ═══════════════════════════════════════════════════════

class TestAuditTrail(EcommerceTestBase):

    def test_success_flow__has_complete_audit_trail(self):
        """成功流程 → 审计日志记录所有步骤"""
        self.mock_happy_path()

        result = self.orchestrator.place_order("U001", self.valid_items, self.address)

        events = self.audit_logger.get_events(result["order_id"])
        event_names = [e["event"] for e in events]

        # 验证事件顺序
        expected_order = [
            "ORDER_CREATED", "USER_VERIFIED", "BALANCE_SUFFICIENT",
            "STOCK_VERIFIED", "ITEMS_LOCKED", "PRE_AUTH_SUCCESS",
            "PAYMENT_CAPTURED", "SHIPMENT_CREATED",
            "NOTIFICATION_SENT", "ORDER_COMPLETED"
        ]
        assert event_names == expected_order, f"事件顺序不对: {event_names}"

    def test_failed_flow__audit_shows_failure_point(self):
        """失败流程 → 日志记录失败在哪个步骤"""
        self.user_svc.get_user.return_value = {"id": "U001", "name": "张三"}
        self.user_svc.check_balance.return_value = False  # 余额不足

        result = self.orchestrator.place_order("U001", self.valid_items, self.address)

        events = self.audit_logger.get_events(result["order_id"])
        event_names = [e["event"] for e in events]

        assert "ORDER_CREATED" in event_names
        assert "USER_VERIFIED" in event_names
        assert "BALANCE_INSUFFICIENT" in event_names  # 停在余额检查
        assert "STOCK_VERIFIED" not in event_names    # 没走到库存

    def test_each_audit_event_has_timestamp(self):
        """每条审计日志都有时间戳"""
        self.mock_happy_path()

        result = self.orchestrator.place_order("U001", self.valid_items, self.address)
        events = self.audit_logger.get_events(result["order_id"])

        for event in events:
            assert event["created_at"] is not None
            assert "T" in event["created_at"]  # ISO 格式


# ═══════════════════════════════════════════════════════
# 场景 8：响应式 Mock —— 根据输入动态返回
# ═══════════════════════════════════════════════════════

class TestDynamicMock(EcommerceTestBase):

    def test_balance_check_uses_correct_amount(self):
        """动态验证：确认传给余额检查的金额是正确的"""
        self.user_svc.get_user.return_value = {"id": "U001", "name": "张三"}

        def verify_balance(user_id, amount):
            # 动态校验金额
            assert user_id == "U001"
            expected = 4999.0 + 49.0 * 2  # 5097.0
            assert amount == expected, f"金额错误: {amount} != {expected}"
            return True

        self.user_svc.check_balance.side_effect = verify_balance
        self.inventory_svc.check_availability.return_value = [
            {"sku": "PHONE-001", "available": True, "stock": 50},
            {"sku": "CASE-002", "available": True, "stock": 200},
        ]
        self.inventory_svc.lock_items.return_value = True
        self.payment_svc.pre_auth.return_value = {"auth_id": "AUTH-ABC"}
        self.payment_svc.capture.return_value = {"transaction_id": "TXN-XYZ"}
        self.logistics_svc.create_shipment.return_value = {"tracking_number": "SF123"}

        result = self.orchestrator.place_order("U001", self.valid_items, self.address)
        assert result["status"] == "success"

    def test_pre_auth_receives_correct_data(self):
        """验证传给预授权的数据完整正确"""
        self.mock_happy_path()

        self.orchestrator.place_order("U001", self.valid_items, self.address)

        # 检查预授权调用参数
        call_args = self.payment_svc.pre_auth.call_args
        assert call_args[0][0] == "U001"  # user_id
        assert call_args[0][1] == self.total  # amount
        assert call_args[0][2].startswith("ORD-")  # order_id


# ═══════════════════════════════════════════════════════
# 场景 9：HTTP 层面验证 —— 用 responses 模拟真实调用
# ═══════════════════════════════════════════════════════

class TestWithRealHTTPMocks:
    """
    演示如果用真实 UserService（非 MagicMock）如何 Mock HTTP。

    Phase 3 学过 responses，这里在实战中复习一下。
    """

    @responses.activate
    def test_real_user_service_with_mocked_http(self):
        """用真实的 UserService 类，但 Mock 它的 HTTP 请求"""
        # Mock 用户查询
        responses.get(
            "https://user-service.internal/api/users/U001",
            json={"id": "U001", "name": "张三", "email": "zhang@test.com"},
            status=200
        )
        # Mock 余额检查
        responses.post(
            "https://user-service.internal/api/users/U001/check-balance",
            json={"sufficient": False},  # 余额不足
            status=200
        )

        # 其他服务仍然用 MagicMock
        inventory = MagicMock(spec=InventoryService)
        payment = MagicMock(spec=PaymentService)

        # 用真实的 UserService（会发 HTTP 请求，但被 responses 拦截）
        real_user_svc = UserService()

        orchestrator = OrderOrchestrator(
            real_user_svc, inventory, payment,
            MagicMock(spec=LogisticsService),
            MagicMock(spec=NotificationService),
            AuditLogger(":memory:")
        )

        result = orchestrator.place_order(
            "U001",
            [{"sku": "ITEM-001", "quantity": 1, "price": 100}],
            {"name": "张三", "phone": "138", "address": "北京"}
        )

        assert result["status"] == "failed"
        assert result["step"] == "balance_check"
        assert len(responses.calls) == 2  # 用户查询 + 余额检查
