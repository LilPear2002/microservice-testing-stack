"""Order API Handler"""
import logging
from datetime import datetime

logger = logging.getLogger("api.order")

class OrderHandler:
    VALID_STATUSES = ["pending", "confirmed", "shipped", "delivered", "cancelled"]

    def create_order(self, user_id, items):
        if not items:
            raise ValueError("items cannot be empty")
        order_id = f"ORD-{datetime.now().strftime('%Y%m%d')}-{hash(str(items)) % 10000:04d}"
        logger.info(f"Order created: {order_id} for user {user_id}")
        return {"order_id": order_id, "status": "pending", "items": items}

    def update_status(self, order_id, status):
        if status not in self.VALID_STATUSES:
            raise ValueError(f"Invalid status: {status}")
        logger.info(f"Order {order_id} status -> {status}")
        return {"order_id": order_id, "new_status": status}

    def get_order(self, order_id):
        logger.debug(f"Fetching order {order_id}")
        return {"order_id": order_id, "user_id": 42, "status": "shipped"}
