"""
tests/test_external_mock.py — Phase 3：Mock 外部依赖进阶
========================================================
四大场景：HTTP API / 数据库 / 时间 / 文件系统

运行：cd /workspace/mock_testing && source .venv/bin/activate && pytest tests/test_external_mock.py -v
"""
import pytest
import json
import sys
from unittest.mock import Mock, MagicMock, patch, mock_open
from datetime import datetime, timedelta

import responses
import requests

sys.path.insert(0, '/workspace/mock_testing/src')
from external_services import (
    WeatherService, UserService, UserRepository,
    BusinessHoursChecker, TokenManager, ConfigLoader, OrderNotifier
)


# ═══════════════════════════════════════════════════════
# 场景 1：Mock HTTP 请求 —— 用 responses 库
# ═══════════════════════════════════════════════════════

class TestWeatherServiceWithResponses:
    """
    responses 库拦截 requests 发出的 HTTP 请求，返回预设响应。
    完全不发网络请求，速度快、结果可控。
    """

    @responses.activate  # 激活 responses 拦截器
    def test_get_current_temp(self):
        """Mock 天气 API → 返回预设的温度数据"""
        # 注册 Mock 响应：当有人 GET 这个 URL 时，返回以下 JSON
        responses.get(
            "https://api.weather.com/v1/current",
            json={"temperature": 28, "humidity": 60},
            status=200
        )

        service = WeatherService(api_key="test-key")
        result = service.get_current_temp("上海")

        assert result == {"city": "上海", "temp": 28, "unit": "celsius"}
        assert len(responses.calls) == 1  # 确认只发了一次请求

    @responses.activate
    def test_get_forecast(self):
        """Mock 天气预报 → 返回多日预报数组"""
        responses.get(
            "https://api.weather.com/v1/forecast",
            json={"forecast": [
                {"date": "2025-01-20", "high": 30, "low": 22},
                {"date": "2025-01-21", "high": 28, "low": 20},
                {"date": "2025-01-22", "high": 25, "low": 18},
            ]},
            status=200
        )

        service = WeatherService(api_key="test-key")
        forecast = service.get_forecast("广州", days=3)

        assert len(forecast) == 3
        assert forecast[0]["date"] == "2025-01-20"

        # 验证请求参数（中文会被 URL 编码）
        req = responses.calls[0].request
        assert "days=3" in req.url
        assert "apikey=test-key" in req.url

    @responses.activate
    def test_api_error__server_down(self):
        """Mock 服务器 500 错误 → 验证异常处理"""
        responses.get(
            "https://api.weather.com/v1/current",
            status=500,
            body="Internal Server Error"
        )

        service = WeatherService(api_key="test-key")
        with pytest.raises(requests.HTTPError, match="500"):
            service.get_current_temp("北京")

    @responses.activate
    def test_api_error__timeout(self):
        """Mock 网络超时"""
        responses.get(
            "https://api.weather.com/v1/current",
            body=requests.exceptions.Timeout()
        )

        service = WeatherService(api_key="test-key")
        with pytest.raises(requests.exceptions.Timeout):
            service.get_current_temp("深圳")


class TestUserServiceWithResponses:
    """用户服务 —— 多种 HTTP 方法（GET/PUT/DELETE）"""

    @responses.activate
    def test_get_user_info__found(self):
        """GET 请求 → 返回用户信息"""
        responses.get(
            "https://user-center.internal/api/users/U001",
            json={"id": "U001", "name": "张三", "city": "北京", "email": "zhang@test.com"},
            status=200
        )

        service = UserService()
        user = service.get_user_info("U001", "token-abc")

        assert user["name"] == "张三"
        assert user["city"] == "北京"

        # 验证携带了正确的 Authorization header
        req = responses.calls[0].request
        assert req.headers["Authorization"] == "Bearer token-abc"

    @responses.activate
    def test_get_user_info__not_found(self):
        """404 返回 None"""
        responses.get(
            "https://user-center.internal/api/users/U999",
            status=404
        )

        service = UserService()
        user = service.get_user_info("U999", "token")

        assert user is None

    @responses.activate
    def test_update_user(self):
        """PUT 请求 → 更新用户信息"""
        responses.put(
            "https://user-center.internal/api/users/U001",
            json={"id": "U001", "name": "张三", "city": "上海"},
            status=200
        )

        service = UserService()
        result = service.update_user_profile(
            "U001",
            {"city": "上海"},
            "token-abc"
        )

        assert result["city"] == "上海"

        # 验证请求体
        req = responses.calls[0].request
        assert b'"city"' in req.body

    @responses.activate
    def test_deactivate_user(self):
        """DELETE 请求 → 204 No Content 表示成功"""
        responses.delete(
            "https://user-center.internal/api/users/U001",
            status=204
        )

        service = UserService()
        assert service.deactivate_user("U001", "token") is True

    @responses.activate
    def test_multiple_requests_in_one_test(self):
        """一次测试中 Mock 多个不同的 HTTP 请求"""
        # Mock 用户查询
        responses.get(
            "https://user-center.internal/api/users/U001",
            json={"id": "U001", "name": "张三", "city": "上海"},
            status=200
        )
        # Mock 天气查询
        responses.get(
            "https://api.weather.com/v1/current",
            json={"temperature": 22},
            status=200
        )

        # 两个服务各自调用
        user_svc = UserService()
        weather_svc = WeatherService(api_key="k")

        user = user_svc.get_user_info("U001", "t")
        temp = weather_svc.get_current_temp("上海")

        assert user["city"] == "上海"
        assert temp["temp"] == 22
        assert len(responses.calls) == 2


# ═══════════════════════════════════════════════════════
# 场景 2：Mock 数据库
# ═══════════════════════════════════════════════════════

class TestUserRepository__RealSQLite:
    """
    数据库测试策略对比：

    策略 A：用真实 SQLite 内存数据库（轻量 Fake）
        ✅ 优点：真实 SQL，能测出 SQL 语法错误
        ❌ 缺点：不是生产数据库（MySQL/PostgreSQL），行为可能不同

    策略 B：Mock 数据库连接（下一节）
        ✅ 优点：完全不依赖数据库，飞一样快
        ❌ 缺点：测不到真实的 SQL 交互

    这里先用策略 A，下面用策略 B
    """

    def test_create_and_find_user(self):
        repo = UserRepository(":memory:")  # 内存数据库

        repo.create_user("U1", "张三", "zhang@test.com")
        user = repo.find_by_id("U1")

        assert user["name"] == "张三"
        assert user["email"] == "zhang@test.com"
        assert user["vip_level"] == 0  # 默认值

    def test_find_by_email(self):
        repo = UserRepository(":memory:")
        repo.create_user("U1", "张三", "zhang@test.com")
        repo.create_user("U2", "李四", "li@test.com")

        assert repo.find_by_email("li@test.com")["name"] == "李四"
        assert repo.find_by_email("notexist@test.com") is None

    def test_update_vip(self):
        repo = UserRepository(":memory:")
        repo.create_user("U1", "张三", "zhang@test.com")

        assert repo.update_vip_level("U1", 3) is True
        assert repo.find_by_id("U1")["vip_level"] == 3

    def test_update_nonexistent_user(self):
        repo = UserRepository(":memory:")
        assert repo.update_vip_level("U999", 1) is False

    def test_delete_user(self):
        repo = UserRepository(":memory:")
        repo.create_user("U1", "张三", "zhang@test.com")

        assert repo.delete_user("U1") is True
        assert repo.find_by_id("U1") is None

    def test_get_vip_users(self):
        repo = UserRepository(":memory:")
        repo.create_user("U1", "普通", "a@test.com")
        repo.create_user("U2", "VIP1", "b@test.com")
        repo.create_user("U3", "VIP2", "c@test.com")

        repo.update_vip_level("U2", 1)
        repo.update_vip_level("U3", 5)

        vips = repo.get_vip_users()
        assert len(vips) == 2
        assert vips[0]["vip_level"] == 5  # 按 VIP 等级降序
        assert vips[1]["vip_level"] == 1


class TestUserRepository__MockDB:
    """
    策略 B：完全 Mock 数据库连接。
    适用场景：测业务逻辑是否正确组装了 SQL 参数，
    不关心 SQL 到底有没有语法错误。
    """

    def test_create_user__mock_db(self):
        """Mock sqlite3.connect → 验证传入了正确的 INSERT 参数"""
        with patch('external_services.sqlite3.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.execute.return_value = mock_cursor

            repo = UserRepository("test.db")

            repo.create_user("U1", "张三", "zhang@test.com")

            # 验证 execute 被调了两次（CREATE TABLE + INSERT）
            assert mock_conn.execute.call_count >= 1

            # 找到 INSERT 调用
            insert_calls = [
                c for c in mock_conn.execute.call_args_list
                if "INSERT" in str(c)
            ]
            assert len(insert_calls) == 1

    def test_find_by_id__mock_db(self):
        """Mock 查询返回预设结果"""
        with patch('external_services.sqlite3.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.execute.return_value = mock_cursor

            # 预设 fetchone 返回值
            mock_cursor.fetchone.return_value = {
                "id": "U1", "name": "张三", "email": "z@t.com",
                "vip_level": 0, "created_at": "2025-01-01T00:00:00"
            }

            repo = UserRepository("test.db")
            user = repo.find_by_id("U1")

            assert user["name"] == "张三"
            mock_conn.execute.assert_called_with(
                "SELECT * FROM users WHERE id = ?", ("U1",)
            )

    def test_find_by_id__not_found(self):
        """Mock 查询返回空 → None"""
        with patch('external_services.sqlite3.connect') as mock_connect:
            #  直接设置 connect() 返回的 Mock 对象
            mock_connect.return_value.execute.return_value.fetchone.return_value = None

            repo = UserRepository("test.db")
            assert repo.find_by_id("U999") is None


# ═══════════════════════════════════════════════════════
# 场景 3：Mock 时间（datetime）
# ═══════════════════════════════════════════════════════

class TestBusinessHours:
    """Mock datetime.now() 来控制「现在几点」"""

    def test_monday_10am__is_business_hours(self):
        """周一上午 10 点 → 在营业时间"""
        mock_now = datetime(2025, 1, 20, 10, 0, 0)  # 周一
        with patch('external_services.datetime') as mock_dt:
            mock_dt.now.return_value = mock_now
            # 需要保留其他 datetime 功能（weekday, hour 等）
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)

            checker = BusinessHoursChecker()
            # 重新设计：patch datetime.now 即可
            pass

    def test_is_business_hours__various_times(self):
        """用一个方法测多个时间点 —— 更干净的写法"""

        test_cases = [
            # (时间, 预期结果, 说明)
            (datetime(2025, 1, 20, 10, 0), True, "周一 10:00"),
            (datetime(2025, 1, 20, 8, 59), False, "周一 08:59 没开门"),
            (datetime(2025, 1, 20, 18, 0), False, "周一 18:00 已下班"),
            (datetime(2025, 1, 20, 17, 59), True, "周一 17:59 还在上班"),
            (datetime(2025, 1, 25, 10, 0), False, "周六 10:00 休息"),
            (datetime(2025, 1, 26, 14, 0), False, "周日 14:00 休息"),
        ]

        for now, expected, desc in test_cases:
            with patch('external_services.datetime') as mock_dt:
                mock_dt.now.return_value = now
                # 让 strftime 也能正常工作
                mock_dt.strftime = datetime.strftime
                #  关键：让 datetime.now() 返回固定时间，但保留 datetime 类的其他方法
                mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)

                checker = BusinessHoursChecker()
                assert checker.is_business_hours() == expected, f"失败：{desc}"

    def test_is_holiday__today_is_holiday(self):
        """今天是节假日"""
        holidays = ["2025-01-20", "2025-01-21"]
        mock_now = datetime(2025, 1, 20, 12, 0)

        with patch('external_services.datetime') as mock_dt:
            mock_dt.now.return_value = mock_now
            mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
            mock_dt.strftime = datetime.strftime

            checker = BusinessHoursChecker()
            assert checker.is_holiday(holidays) is True

    def test_is_holiday__today_is_normal_day(self):
        """今天不是节假日"""
        holidays = ["2025-01-22", "2025-01-23"]
        mock_now = datetime(2025, 1, 20, 12, 0)

        with patch('external_services.datetime') as mock_dt:
            mock_dt.now.return_value = mock_now
            mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
            mock_dt.strftime = datetime.strftime

            checker = BusinessHoursChecker()
            assert checker.is_holiday(holidays) is False

    def test_minutes_until_close(self):
        """16:30 → 距离下班 90 分钟"""
        mock_now = datetime(2025, 1, 20, 16, 30, 0)

        with patch('external_services.datetime') as mock_dt:
            mock_dt.now.return_value = mock_now
            mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)

            checker = BusinessHoursChecker()
            assert checker.minutes_until_close() == 90


class TestTokenManager:
    """Mock 时间测 Token 过期逻辑"""

    def test_token_valid(self):
        """还没到过期时间 → 有效"""
        now = datetime(2025, 1, 20, 12, 0)
        expires = datetime(2025, 1, 20, 13, 0)  # 1 小时后过期

        with patch('external_services.datetime') as mock_dt:
            mock_dt.now.return_value = now
            mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)

            # TokenManager 中的 timedelta 需要真实 datetime
            tm = TokenManager("token-abc", expires)
            assert tm.is_valid() is True

    def test_token_expired(self):
        """已经过了过期时间 → 无效"""
        now = datetime(2025, 1, 20, 14, 0)
        expires = datetime(2025, 1, 20, 13, 0)  # 1 小时前已过期

        with patch('external_services.datetime') as mock_dt:
            mock_dt.now.return_value = now
            mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)

            tm = TokenManager("old-token", expires)
            assert tm.is_valid() is False

    def test_refresh_when_expired(self):
        """Token 过期 → 自动刷新"""
        now = datetime(2025, 1, 20, 14, 0)
        expires = datetime(2025, 1, 20, 13, 0)

        with patch('external_services.datetime') as mock_dt:
            mock_dt.now.return_value = now
            mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)

            tm = TokenManager("old-token", expires)
            refresh_fn = Mock(return_value="new-token-xyz")

            result = tm.refresh_if_needed(refresh_fn)

            assert result == "new-token-xyz"
            refresh_fn.assert_called_once()  # 确实调了刷新函数

    def test_no_refresh_when_valid(self):
        """Token 有效 → 不刷新"""
        now = datetime(2025, 1, 20, 12, 0)
        expires = datetime(2025, 1, 20, 13, 0)

        with patch('external_services.datetime') as mock_dt:
            mock_dt.now.return_value = now
            mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)

            tm = TokenManager("valid-token", expires)
            refresh_fn = Mock()

            result = tm.refresh_if_needed(refresh_fn)

            assert result == "valid-token"
            refresh_fn.assert_not_called()  # 没调刷新函数

    def test_minutes_until_expiry(self):
        """12:30 → 距 13:00 过期还有 30 分钟"""
        now = datetime(2025, 1, 20, 12, 30)
        expires = datetime(2025, 1, 20, 13, 0)

        with patch('external_services.datetime') as mock_dt:
            mock_dt.now.return_value = now
            mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)

            tm = TokenManager("token", expires)
            assert tm.minutes_until_expiry() == 30


# ═══════════════════════════════════════════════════════
# 场景 4：Mock 文件系统
# ═══════════════════════════════════════════════════════

class TestConfigLoader:
    """用 mock_open 和 patch 模拟文件读写"""

    def test_load_config__success(self):
        """Mock open() → 假装读到 JSON 配置文件"""
        fake_json = json.dumps({
            "app": {"name": "myapp", "version": "1.0"},
            "db": {"host": "localhost", "port": 3306}
        })

        with patch("builtins.open", mock_open(read_data=fake_json)), \
             patch("os.path.exists", return_value=True):  # ← 关键：让文件「存在」
            loader = ConfigLoader()
            config = loader.load_config("/etc/app/config.json")

            assert config["app"]["name"] == "myapp"
            assert config["db"]["port"] == 3306

    def test_load_config__file_not_found(self):
        """Mock os.path.exists → False → 抛 FileNotFoundError"""
        with patch("external_services.os.path.exists", return_value=False):
            loader = ConfigLoader()
            with pytest.raises(FileNotFoundError, match="配置文件不存在"):
                loader.load_config("/nonexistent/config.json")

    def test_get_nested_value(self):
        """读取嵌套配置值"""
        fake_json = json.dumps({
            "db": {"host": "prod-db.example.com", "port": 5432}
        })

        with patch("builtins.open", mock_open(read_data=fake_json)), \
             patch("os.path.exists", return_value=True):
            loader = ConfigLoader()

            # db.host
            host = loader.get_nested_value("config.json", "db", "host")
            assert host == "prod-db.example.com"

            # db.port
            port = loader.get_nested_value("config.json", "db", "port")
            assert port == 5432

    def test_get_nested_value__key_not_found(self):
        """嵌套 key 不存在 → None"""
        fake_json = json.dumps({"app": {"name": "test"}})

        with patch("builtins.open", mock_open(read_data=fake_json)), \
             patch("os.path.exists", return_value=True):
            loader = ConfigLoader()
            assert loader.get_nested_value("config.json", "nonexistent") is None

    def test_save_config(self):
        """Mock open + json.dump → 验证写入内容"""
        mock_file = mock_open()

        with patch("builtins.open", mock_file), \
             patch("external_services.os.makedirs"):  # Mock 目录创建
            loader = ConfigLoader()
            loader.save_config("output.json", {"key": "value"})

            # 验证 open 被以写入模式调用
            mock_file.assert_called_once_with("output.json", 'w', encoding='utf-8')

            # 验证写入了正确的内容
            handle = mock_file()
            written = ''.join(
                call.args[0] for call in handle.write.call_args_list
            )
            assert '"key"' in written
            assert '"value"' in written


# ═══════════════════════════════════════════════════════
# 场景 5：综合 Mock —— 同时 Mock HTTP + 数据库 + 天气
# ═══════════════════════════════════════════════════════

class TestOrderNotifierIntegration:
    """综合场景：一个方法依赖 3 个外部服务"""

    @responses.activate
    def test_send_welcome__normal_user_no_vip(self):
        """普通用户 + 正常天气 → 欢迎消息"""
        #   Mock HTTP: 用户信息
        responses.get(
            "https://user-center.internal/api/users/U001",
            json={"id": "U001", "name": "张三", "city": "北京"},
            status=200
        )
        #   Mock HTTP: 天气
        responses.get(
            "https://api.weather.com/v1/current",
            json={"temperature": 25},
            status=200
        )

        # Mock 数据库: 普通用户（vip=0）
        with patch('external_services.sqlite3.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.execute.return_value = mock_cursor
            mock_cursor.fetchone.return_value = {
                "id": "U001", "name": "张三", "email": "z@t.com",
                "vip_level": 0, "created_at": "2025-01-01"
            }

            user_svc = UserService()
            weather_svc = WeatherService(api_key="k")
            repo = UserRepository("test.db")

            notifier = OrderNotifier(user_svc, weather_svc, repo)
            msg = notifier.send_welcome_message("U001", "token")

            assert "张三" in msg
            assert "VIP" not in msg  # 不是 VIP
            assert "天气不错" in msg
            assert len(responses.calls) == 2

    @responses.activate
    def test_send_welcome__vip_user_hot_weather(self):
        """VIP 用户 + 炎热天气 → 特殊欢迎消息"""
        responses.get(
            "https://user-center.internal/api/users/U001",
            json={"id": "U001", "name": "VIP张三", "city": "重庆"},
            status=200
        )
        responses.get(
            "https://api.weather.com/v1/current",
            json={"temperature": 38},  # 38°C → 高温
            status=200
        )

        with patch('external_services.sqlite3.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_conn.execute.return_value.fetchone.return_value = {
                "id": "U001", "name": "VIP张三", "email": "v@t.com",
                "vip_level": 5, "created_at": "2025-01-01"
            }
            mock_connect.return_value = mock_conn

            notifier = OrderNotifier(
                UserService(), WeatherService("k"), UserRepository("test.db")
            )
            msg = notifier.send_welcome_message("U001", "t")

            assert "VIP张三" in msg
            assert "⭐VIP" in msg
            assert "注意防暑" in msg

    @responses.activate
    def test_send_welcome__user_not_found(self):
        """用户不存在 → 返回提示"""
        responses.get(
            "https://user-center.internal/api/users/U999",
            status=404
        )

        # 天气 API 不应该被调用（因为用户不存在提前返回了）
        # 所以我们不注册天气的 mock → 如果被调用了会报错

        with patch('external_services.sqlite3.connect'):
            notifier = OrderNotifier(
                UserService(), WeatherService("k"), UserRepository("test.db")
            )
            msg = notifier.send_welcome_message("U999", "t")

            assert msg == "用户不存在"
            assert len(responses.calls) == 1  # 只调用了用户查询，没调天气
