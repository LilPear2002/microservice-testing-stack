"""
src/external_services.py — Phase 3 被测代码
===========================================
包含四类需要 Mock 的外部依赖：
1. HTTP API（天气、用户信息）
2. 数据库（用户仓储）
3. 时间（营业时间检查、Token 过期）
4. 文件系统（配置加载）
"""
import requests
import sqlite3
import json
import os
from datetime import datetime, timedelta
from typing import Optional


# ═══════════════════════════════════════════════════════
# 场景 1：HTTP API 调用（需要 responses 来 Mock）
# ═══════════════════════════════════════════════════════

class WeatherService:
    """天气服务 —— 调用外部天气 API"""

    BASE_URL = "https://api.weather.com/v1"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def get_current_temp(self, city: str) -> dict:
        """获取城市当前温度"""
        resp = requests.get(
            f"{self.BASE_URL}/current",
            params={"city": city, "apikey": self.api_key},
            timeout=10
        )
        resp.raise_for_status()
        data = resp.json()
        return {"city": city, "temp": data["temperature"], "unit": "celsius"}

    def get_forecast(self, city: str, days: int = 3) -> list:
        """获取天气预报"""
        resp = requests.get(
            f"{self.BASE_URL}/forecast",
            params={"city": city, "days": days, "apikey": self.api_key},
            timeout=10
        )
        resp.raise_for_status()
        return resp.json()["forecast"]


class UserService:
    """用户服务 —— 调用用户中心 API 查用户信息"""

    API_URL = "https://user-center.internal/api"

    def get_user_info(self, user_id: str, token: str) -> dict:
        """获取用户详情"""
        resp = requests.get(
            f"{self.API_URL}/users/{user_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    def update_user_profile(self, user_id: str, data: dict, token: str) -> dict:
        """更新用户信息"""
        resp = requests.put(
            f"{self.API_URL}/users/{user_id}",
            json=data,
            headers={"Authorization": f"Bearer {token}"},
            timeout=5
        )
        resp.raise_for_status()
        return resp.json()

    def deactivate_user(self, user_id: str, token: str) -> bool:
        """注销用户"""
        resp = requests.delete(
            f"{self.API_URL}/users/{user_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5
        )
        return resp.status_code == 204


# ═══════════════════════════════════════════════════════
# 场景 2：数据库操作（Mock 数据库连接）
# ═══════════════════════════════════════════════════════

class UserRepository:
    """用户仓储 —— 封装数据库操作"""

    def __init__(self, db_path: str = ":memory:"):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row  # 让查询结果可用 dict 方式访问
        self._init_table()

    def _init_table(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT UNIQUE,
                vip_level INTEGER DEFAULT 0,
                created_at TEXT
            )
        """)
        self.conn.commit()

    def create_user(self, user_id: str, name: str, email: str) -> dict:
        """创建用户"""
        now = datetime.now().isoformat()
        self.conn.execute(
            "INSERT INTO users (id, name, email, created_at) VALUES (?, ?, ?, ?)",
            (user_id, name, email, now)
        )
        self.conn.commit()
        return {"id": user_id, "name": name, "email": email, "created_at": now}

    def find_by_id(self, user_id: str) -> Optional[dict]:
        """按 ID 查找"""
        cursor = self.conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def find_by_email(self, email: str) -> Optional[dict]:
        """按邮箱查找（用于判重）"""
        cursor = self.conn.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def update_vip_level(self, user_id: str, level: int) -> bool:
        """升级 VIP"""
        cursor = self.conn.execute(
            "UPDATE users SET vip_level = ? WHERE id = ?",
            (level, user_id)
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def delete_user(self, user_id: str) -> bool:
        """删除用户"""
        cursor = self.conn.execute(
            "DELETE FROM users WHERE id = ?", (user_id,)
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def get_vip_users(self) -> list:
        """获取所有 VIP 用户"""
        cursor = self.conn.execute(
            "SELECT * FROM users WHERE vip_level > 0 ORDER BY vip_level DESC"
        )
        return [dict(row) for row in cursor.fetchall()]


# ═══════════════════════════════════════════════════════
# 场景 3：时间依赖（Mock datetime）
# ═══════════════════════════════════════════════════════

class BusinessHoursChecker:
    """检查是否在营业时间内"""

    def is_business_hours(self) -> bool:
        """周一至周五 9:00-18:00"""
        now = datetime.now()
        if now.weekday() >= 5:  # 周六日
            return False
        return 9 <= now.hour < 18

    def is_holiday(self, holiday_list: list) -> bool:
        """检查今天是否是节假日"""
        today = datetime.now().strftime("%Y-%m-%d")
        return today in holiday_list

    def minutes_until_close(self) -> int:
        """距离下班还有多少分钟"""
        now = datetime.now()
        close_time = now.replace(hour=18, minute=0, second=0, microsecond=0)
        delta = close_time - now
        return max(0, int(delta.total_seconds() / 60))


class TokenManager:
    """Token 管理 —— 检查过期"""

    def __init__(self, token: str, expires_at: datetime):
        self.token = token
        self.expires_at = expires_at

    def is_valid(self) -> bool:
        """检查 Token 是否过期"""
        return datetime.now() < self.expires_at

    def refresh_if_needed(self, refresh_fn) -> str:
        """如果过期则刷新 Token"""
        if not self.is_valid():
            self.token = refresh_fn()
            self.expires_at = datetime.now() + timedelta(hours=1)
        return self.token

    def minutes_until_expiry(self) -> int:
        """距离过期还有多少分钟"""
        delta = self.expires_at - datetime.now()
        return max(0, int(delta.total_seconds() / 60))


# ═══════════════════════════════════════════════════════
# 场景 4：文件系统（Mock 文件读写）
# ═══════════════════════════════════════════════════════

class ConfigLoader:
    """配置加载器 —— 从文件读 JSON 配置"""

    def load_config(self, filepath: str) -> dict:
        """读取 JSON 配置文件"""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"配置文件不存在: {filepath}")

        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)

    def save_config(self, filepath: str, config: dict) -> None:
        """保存配置到文件"""
        os.makedirs(os.path.dirname(filepath) or '.', exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

    def get_nested_value(self, filepath: str, *keys) -> any:
        """读取嵌套配置：config["db"]["host"]"""
        config = self.load_config(filepath)
        result = config
        for key in keys:
            result = result.get(key, {})
        return result if result != {} else None


# ═══════════════════════════════════════════════════════
# 综合服务：组合多个依赖
# ═══════════════════════════════════════════════════════

class OrderNotifier:
    """订单通知服务 —— 综合多个外部依赖"""

    def __init__(self, user_service: UserService,
                 weather_service: WeatherService,
                 repo: UserRepository):
        self.user_service = user_service
        self.weather = weather_service
        self.repo = repo

    def send_welcome_message(self, user_id: str, token: str) -> str:
        """新用户注册欢迎消息 —— 查用户信息 + 查天气 + 查数据库"""
        # 1. 从 API 获取用户信息
        user = self.user_service.get_user_info(user_id, token)
        if not user:
            return "用户不存在"

        # 2. 从数据库查 VIP 等级
        db_user = self.repo.find_by_id(user_id)
        vip_badge = "⭐VIP" if db_user and db_user.get("vip_level", 0) > 0 else ""

        # 3. 查天气加一句关怀
        weather_info = self.weather.get_current_temp(user.get("city", "北京"))
        weather_tip = (
            "天气炎热，注意防暑☀️" if weather_info["temp"] > 35
            else "天气寒冷，注意保暖❄️" if weather_info["temp"] < 5
            else "天气不错，适合出去走走🌤️"
        )

        return f"欢迎 {user['name']} {vip_badge}！{weather_tip}"
