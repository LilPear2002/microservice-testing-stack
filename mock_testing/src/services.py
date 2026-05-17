"""
src/services.py — 要测试的「真实」业务代码
这些类都依赖外部服务，直接测不了，需要 Mock
"""
import time
import random


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 三个「外部依赖」（支付、库存、通知）
# 现实中这些都是第三方 API / RPC 调用
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class PaymentGateway:
    """支付网关 — 对接银行/支付宝/微信"""

    def charge(self, user_id: str, amount: float) -> dict:
        """真实调用会扣钱、走网络、可能超时"""
        time.sleep(0.5)  # 模拟网络延迟
        # 模拟偶尔失败
        if random.random() < 0.1:
            raise ConnectionError("支付网关连接超时")
        return {"status": "success", "transaction_id": f"TXN-{random.randint(1000,9999)}"}

    def refund(self, transaction_id: str) -> dict:
        time.sleep(0.3)
        return {"status": "refunded"}


class InventoryService:
    """库存服务 — 查询/扣减库存"""

    def check_stock(self, product_id: str) -> int:
        """查询库存，现实中是 RPC/HTTP 调用"""
        time.sleep(0.2)
        return random.randint(0, 100)

    def reserve(self, product_id: str, quantity: int) -> bool:
        """预留库存"""
        time.sleep(0.2)
        return True

    def release(self, product_id: str, quantity: int) -> bool:
        """释放库存"""
        time.sleep(0.2)
        return True


class NotificationService:
    """通知服务 — 发短信/邮件/推送"""

    def send_email(self, to: str, subject: str, body: str) -> bool:
        """真实调用走邮件网关，收费+限流"""
        time.sleep(0.3)
        return True

    def send_sms(self, phone: str, message: str) -> bool:
        time.sleep(0.3)
        return True


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 被测对象：订单服务
# 这是我们「真正要测」的业务逻辑
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class OrderService:
    """
    订单服务 —— 核心业务逻辑
    依赖三个外部服务：支付、库存、通知
    """

    def __init__(self, payment: PaymentGateway,
                 inventory: InventoryService,
                 notification: NotificationService):
        self.payment = payment
        self.inventory = inventory
        self.notification = notification

    def create_order(self, user_id: str, product_id: str, amount: float) -> dict:
        """
        创建订单的完整流程：
        1. 查库存 → 2. 预留库存 → 3. 扣款 → 4. 发通知 → 5. 返回
        """
        # 1. 检查库存
        stock = self.inventory.check_stock(product_id)
        if stock <= 0:
            return {"status": "failed", "reason": "库存不足"}

        # 2. 预留库存
        reserved = self.inventory.reserve(product_id, 1)
        if not reserved:
            self.inventory.release(product_id, 0)  # 幂等释放
            return {"status": "failed", "reason": "预留库存失败"}

        # 3. 扣款
        try:
            payment_result = self.payment.charge(user_id, amount)
        except Exception as e:
            # 扣款失败 → 释放库存
            self.inventory.release(product_id, 1)
            return {"status": "failed", "reason": f"支付失败: {e}"}

        # 4. 发通知
        self.notification.send_email(
            user_id,
            "订单确认",
            f"您购买 {product_id} 的订单已确认，金额 {amount}"
        )

        # 5. 返回成功
        return {
            "status": "success",
            "transaction_id": payment_result["transaction_id"],
            "product_id": product_id,
            "amount": amount,
        }

    def cancel_order(self, transaction_id: str, product_id: str) -> dict:
        """取消订单：退款 + 释放库存"""
        refund_result = self.payment.refund(transaction_id)
        self.inventory.release(product_id, 1)
        self.notification.send_email(
            "user@example.com",
            "订单取消",
            f"订单 {transaction_id} 已取消"
        )
        return {"status": "cancelled", "refund": refund_result}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 一个简单的工具函数（也拿来练习 Mock）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_discount(user_id: str, db_connection) -> float:
    """
    查询用户折扣。依赖外部数据库连接。
    我们要 Mock db_connection 来测试折扣计算逻辑。
    """
    # 真实情况：db_connection.execute("SELECT discount FROM users WHERE id=?", user_id)
    row = db_connection.execute("SELECT discount FROM users WHERE id=?", user_id)
    if row is None:
        return 0.0
    return min(row['discount'], 0.9)  # 折扣上限 90%


def calculate_final_price(original_price: float, discount: float) -> float:
    """计算折后价格（纯函数，不需要 Mock）"""
    return round(original_price * (1 - discount), 2)


if __name__ == "__main__":
    #  直接跑会非常慢（每次 sleep）且结果随机
    payment = PaymentGateway()
    inventory = InventoryService()
    notification = NotificationService()
    service = OrderService(payment, inventory, notification)

    result = service.create_order("user123", "PROD-001", 99.0)
    print(result)
