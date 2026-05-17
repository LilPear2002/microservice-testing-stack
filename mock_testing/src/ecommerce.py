"""
src/ecommerce.py — Phase 4：电商微服务全链路 Mock 实战
=====================================================
场景：电商下单全流程，涉及 6 个外部依赖

调用链：
  下单请求 → 用户校验 → 库存检查 → 锁定库存 → 预授权 → 
  确认扣款 → 创建运单 → 发通知 → 写审计日志 → 返回结果

所有外部依赖全部 Mock，只测业务编排逻辑本身。
"""
import requests
import sqlite3
import json
import uuid
from datetime import datetime
from typing import Optional, List


# ═══════════════════════════════════════════════════════
# 六种外部依赖定义（真实场景中都是 RPC/HTTP/DB 调用）
# ═══════════════════════════════════════════════════════

class UserService:
    """用户服务 —— 查用户信息、校验余额"""

    BASE_URL = "https://user-service.internal/api"

    def get_user(self, user_id: str) -> Optional[dict]:
        """获取用户信息"""
        resp = requests.get(f"{self.BASE_URL}/users/{user_id}", timeout=5)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    def check_balance(self, user_id: str, amount: float) -> bool:
        """检查余额是否足够"""
        resp = requests.post(
            f"{self.BASE_URL}/users/{user_id}/check-balance",
            json={"amount": amount},
            timeout=5
        )
        resp.raise_for_status()
        return resp.json()["sufficient"]


class InventoryService:
    """库存服务 —— 查库存、锁定、释放"""

    BASE_URL = "https://inventory-service.internal/api"

    def check_availability(self, items: List[dict]) -> List[dict]:
        """
        批量检查库存
        items: [{"sku": "ITEM-001", "quantity": 2}, ...]
        返回每个 SKU 的库存状态
        """
        resp = requests.post(
            f"{self.BASE_URL}/check",
            json={"items": items},
            timeout=5
        )
        resp.raise_for_status()
        return resp.json()["results"]

    def lock_items(self, items: List[dict], order_id: str) -> bool:
        """
        锁定库存（防止超卖）
        返回 True 如果全部锁定成功
        """
        resp = requests.post(
            f"{self.BASE_URL}/lock",
            json={"items": items, "order_id": order_id},
            timeout=5
        )
        resp.raise_for_status()
        return resp.json()["locked"]

    def release_items(self, order_id: str) -> bool:
        """释放库存（取消订单/支付失败时回滚）"""
        resp = requests.post(
            f"{self.BASE_URL}/release",
            json={"order_id": order_id},
            timeout=5
        )
        resp.raise_for_status()
        return resp.json()["released"]


class PaymentService:
    """支付服务 —— 预授权、确认、退款"""

    BASE_URL = "https://payment-gateway.internal/api"

    def pre_auth(self, user_id: str, amount: float, order_id: str) -> dict:
        """
        预授权（冻结资金，不实际扣款）
        返回 {"auth_id": "AUTH-xxx", "status": "authorized"}
        """
        resp = requests.post(
            f"{self.BASE_URL}/pre-auth",
            json={"user_id": user_id, "amount": amount, "order_id": order_id},
            timeout=10
        )
        resp.raise_for_status()
        return resp.json()

    def capture(self, auth_id: str) -> dict:
        """
        确认扣款（实际从账户扣钱）
        返回 {"transaction_id": "TXN-xxx", "status": "captured"}
        """
        resp = requests.post(
            f"{self.BASE_URL}/capture",
            json={"auth_id": auth_id},
            timeout=10
        )
        resp.raise_for_status()
        return resp.json()

    def refund(self, transaction_id: str, amount: float) -> dict:
        """退款"""
        resp = requests.post(
            f"{self.BASE_URL}/refund",
            json={"transaction_id": transaction_id, "amount": amount},
            timeout=10
        )
        resp.raise_for_status()
        return resp.json()


class LogisticsService:
    """物流服务 —— 创建运单"""

    BASE_URL = "https://logistics-service.internal/api"

    def create_shipment(self, order_id: str, address: dict,
                        items: List[dict]) -> dict:
        """
        创建运单
        返回 {"tracking_number": "SF1234567890", "carrier": "顺丰"}
        """
        resp = requests.post(
            f"{self.BASE_URL}/shipments",
            json={
                "order_id": order_id,
                "address": address,
                "items": items
            },
            timeout=5
        )
        resp.raise_for_status()
        return resp.json()


class NotificationService:
    """通知服务 —— 发邮件/短信"""

    def send_order_confirmation(self, user_id: str, order_id: str,
                                tracking: str) -> bool:
        """发送订单确认通知（含运单号）"""
        try:
            resp = requests.post(
                f"https://notification.internal/api/send",
                json={
                    "user_id": user_id,
                    "type": "order_confirmation",
                    "data": {"order_id": order_id, "tracking": tracking}
                },
                timeout=5
            )
            return resp.status_code == 200
        except Exception:
            return False  # 通知失败不影响主流程

    def send_payment_failed(self, user_id: str, order_id: str, reason: str) -> bool:
        """发送支付失败通知"""
        try:
            resp = requests.post(
                f"https://notification.internal/api/send",
                json={
                    "user_id": user_id,
                    "type": "payment_failed",
                    "data": {"order_id": order_id, "reason": reason}
                },
                timeout=5
            )
            return resp.status_code == 200
        except Exception:
            return False


class AuditLogger:
    """审计日志 —— 写数据库"""

    def __init__(self, db_path: str = ":memory:"):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_table()

    def _init_table(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id TEXT PRIMARY KEY,
                order_id TEXT NOT NULL,
                event TEXT NOT NULL,
                detail TEXT,
                created_at TEXT NOT NULL
            )
        """)
        self.conn.commit()

    def log(self, order_id: str, event: str, detail: dict = None) -> str:
        """记录一条审计日志"""
        log_id = str(uuid.uuid4())[:8]
        now = datetime.now().isoformat()
        self.conn.execute(
            "INSERT INTO audit_log (id, order_id, event, detail, created_at) VALUES (?, ?, ?, ?, ?)",
            (log_id, order_id, event, json.dumps(detail or {}), now)
        )
        self.conn.commit()
        return log_id

    def get_events(self, order_id: str) -> List[dict]:
        """查询某个订单的所有事件"""
        cursor = self.conn.execute(
            "SELECT * FROM audit_log WHERE order_id = ? ORDER BY created_at",
            (order_id,)
        )
        return [dict(row) for row in cursor.fetchall()]


# ═══════════════════════════════════════════════════════
# 被测对象：订单编排器（核心业务逻辑）
# ═══════════════════════════════════════════════════════

class OrderOrchestrator:
    """
    订单编排器 —— 协调 6 个外部服务完成下单流程
    
    这是我们要测试的核心对象！
    所有外部依赖都在构造函数注入 → 方便 Mock
    """

    def __init__(self,
                 user_svc: UserService,
                 inventory_svc: InventoryService,
                 payment_svc: PaymentService,
                 logistics_svc: LogisticsService,
                 notification_svc: NotificationService,
                 audit_logger: AuditLogger):
        self.user = user_svc
        self.inventory = inventory_svc
        self.payment = payment_svc
        self.logistics = logistics_svc
        self.notification = notification_svc
        self.audit = audit_logger

    def place_order(self, user_id: str, items: List[dict],
                    shipping_address: dict) -> dict:
        """
        下单全流程（SAGA 模式：每一步失败都回滚）
        
        参数:
            user_id: 用户 ID
            items: [{"sku": "ITEM-001", "quantity": 2, "price": 99.0}, ...]
            shipping_address: {"name": "张三", "phone": "138...", "address": "..."}
        
        返回:
            {"status": "success", "order_id": "...", "tracking": "...", ...}
            或 {"status": "failed", "reason": "...", "step": "..."}
        """
        order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"
        total_amount = sum(item["quantity"] * item["price"] for item in items)

        self.audit.log(order_id, "ORDER_CREATED", {"user": user_id, "items": len(items)})

        # ── Step 1: 校验用户 ──
        user = self.user.get_user(user_id)
        if not user:
            self.audit.log(order_id, "USER_NOT_FOUND")
            return {"status": "failed", "order_id": order_id, "reason": "用户不存在", "step": "user_check"}

        self.audit.log(order_id, "USER_VERIFIED", {"name": user.get("name")})

        # ── Step 2: 校验余额 ──
        has_balance = self.user.check_balance(user_id, total_amount)
        if not has_balance:
            self.audit.log(order_id, "BALANCE_INSUFFICIENT", {"amount": total_amount})
            return {"status": "failed", "order_id": order_id, "reason": "余额不足", "step": "balance_check"}

        self.audit.log(order_id, "BALANCE_SUFFICIENT", {"amount": total_amount})

        # ── Step 3: 检查库存 ──
        stock_check = self.inventory.check_availability(items)
        unavailable = [r for r in stock_check if not r.get("available")]
        if unavailable:
            skus = [r["sku"] for r in unavailable]
            self.audit.log(order_id, "STOCK_INSUFFICIENT", {"skus": skus})
            return {"status": "failed", "order_id": order_id, "reason": f"以下商品库存不足: {', '.join(skus)}", "step": "stock_check"}

        self.audit.log(order_id, "STOCK_VERIFIED")

        # ── Step 4: 锁定库存 ──
        locked = self.inventory.lock_items(items, order_id)
        if not locked:
            self.audit.log(order_id, "LOCK_FAILED")
            return {"status": "failed", "order_id": order_id, "reason": "锁定库存失败", "step": "lock_items"}

        self.audit.log(order_id, "ITEMS_LOCKED")

        # ── Step 5: 预授权 ──
        try:
            auth_result = self.payment.pre_auth(user_id, total_amount, order_id)
        except Exception as e:
            # 预授权失败 → 释放库存
            self.inventory.release_items(order_id)
            self.audit.log(order_id, "PRE_AUTH_FAILED", {"error": str(e)})
            return {"status": "failed", "order_id": order_id, "reason": f"预授权失败: {e}", "step": "pre_auth"}

        auth_id = auth_result["auth_id"]
        self.audit.log(order_id, "PRE_AUTH_SUCCESS", {"auth_id": auth_id})

        # ── Step 6: 确认扣款 ──
        try:
            capture_result = self.payment.capture(auth_id)
        except Exception as e:
            # 扣款失败 → 释放库存（预授权会自动过期，不需要单独取消）
            self.inventory.release_items(order_id)
            self.audit.log(order_id, "CAPTURE_FAILED", {"error": str(e)})
            self.notification.send_payment_failed(user_id, order_id, str(e))
            return {"status": "failed", "order_id": order_id, "reason": f"扣款失败: {e}", "step": "capture"}

        transaction_id = capture_result["transaction_id"]
        self.audit.log(order_id, "PAYMENT_CAPTURED", {"txn_id": transaction_id})

        # ── Step 7: 创建运单 ──
        try:
            shipment = self.logistics.create_shipment(order_id, shipping_address, items)
            tracking = shipment["tracking_number"]
        except Exception as e:
            # 运单创建失败 → 退款 + 释放库存
            self.payment.refund(transaction_id, total_amount)
            self.inventory.release_items(order_id)
            self.audit.log(order_id, "SHIPMENT_FAILED", {"error": str(e)})
            return {"status": "failed", "order_id": order_id, "reason": f"创建运单失败: {e}", "step": "shipment"}

        self.audit.log(order_id, "SHIPMENT_CREATED", {"tracking": tracking})

        # ── Step 8: 发通知（失败不影响主流程） ──
        try:
            self.notification.send_order_confirmation(user_id, order_id, tracking)
        except Exception:
            pass  # 通知挂了不影响订单
        self.audit.log(order_id, "NOTIFICATION_SENT")

        # ── Step 9: 返回成功 ──
        self.audit.log(order_id, "ORDER_COMPLETED")
        return {
            "status": "success",
            "order_id": order_id,
            "transaction_id": transaction_id,
            "tracking_number": tracking,
            "total_amount": total_amount,
            "items": len(items),
        }
