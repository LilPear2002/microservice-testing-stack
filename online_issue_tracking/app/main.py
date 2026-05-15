"""
线上问题追踪演示应用 — 内置 3 类 Bug 的 FastAPI 服务

Bug 类型：
  1. 间歇性 500：/api/process 接受负数或零值时崩溃
  2. 慢接口：    /api/report 随机延迟，偶尔 >3s
  3. 内存泄漏：  /api/cache 每次调用往全局列表追加数据，不清理
"""

import random
import time
import uuid
import logging
import json
from datetime import datetime

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import Counter, Histogram, Gauge, generate_latest, REGISTRY
import structlog

# =====================================================
# Prometheus 指标定义
# =====================================================
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total request count",
    ["method", "endpoint", "status"]
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "Request latency in seconds",
    ["method", "endpoint"]
)
ERROR_COUNT = Counter(
    "http_errors_total",
    "Total error count",
    ["method", "endpoint", "error_type"]
)
# 内存泄漏监控指标
CACHE_SIZE = Gauge(
    "app_cache_size_bytes",
    "Approximate size of the in-memory cache"
)
ACTIVE_REQUESTS = Gauge(
    "app_active_requests",
    "Number of requests currently being processed"
)
# Bug 触发的专项指标
BUG_PROCESS_ZERO_VALUE = Counter(
    "bug_process_zero_or_negative_total",
    "Count of /api/process calls with value <= 0"
)
BUG_SLOW_REPORT = Counter(
    "bug_slow_report_total",
    "Count of /api/report calls that took >3s"
)

# =====================================================
# 结构化日志配置
# =====================================================
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)
logger = structlog.get_logger()

# =====================================================
# Bug 3：内存泄漏 — 全局缓存，只增不删
# =====================================================
_global_cache: list = []

app = FastAPI(title="Buggy Demo API", version="1.0.0")


# =====================================================
# 中间件：requestId 注入 + 指标采集 + 结构化日志
# =====================================================
@app.middleware("http")
async def metrics_and_logging_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()

    # 注入 requestId 到日志上下文
    structlog.contextvars.bind_contextvars(request_id=request_id)

    ACTIVE_REQUESTS.inc()
    logger.info("request_started",
                method=request.method,
                path=request.url.path,
                client=request.client.host if request.client else "unknown")

    try:
        response = await call_next(request)
        status = response.status_code
    except Exception as e:
        status = 500
        logger.error("request_failed",
                     method=request.method,
                     path=request.url.path,
                     error=str(e),
                     error_type=type(e).__name__)
        ERROR_COUNT.labels(method=request.method,
                          endpoint=request.url.path,
                          error_type=type(e).__name__).inc()
        response = JSONResponse(
            status_code=500,
            content={"error": "Internal Server Error", "request_id": request_id}
        )
    finally:
        ACTIVE_REQUESTS.dec()
        duration = time.time() - start_time
        REQUEST_COUNT.labels(method=request.method,
                            endpoint=request.url.path,
                            status=str(status)).inc()
        REQUEST_LATENCY.labels(method=request.method,
                              endpoint=request.url.path).observe(duration)

        logger.info("request_completed",
                    method=request.method,
                    path=request.url.path,
                    status=status,
                    duration_seconds=round(duration, 4))

        structlog.contextvars.clear_contextvars()

    return response


# =====================================================
# 端点 1：健康检查（正常）
# =====================================================
@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


# =====================================================
# 端点 2：用户查询（正常）
# =====================================================
@app.get("/api/users/{user_id}")
async def get_user(user_id: int):
    """正常接口：根据 ID 返回用户信息"""
    users = {
        1: {"name": "Alice", "role": "admin"},
        2: {"name": "Bob", "role": "developer"},
        3: {"name": "Charlie", "role": "viewer"},
    }
    if user_id in users:
        return {"user_id": user_id, **users[user_id]}
    raise HTTPException(status_code=404, detail="User not found")


# =====================================================
# 端点 3：数据处理（Bug 1 — 间歇性 500）
# =====================================================
@app.get("/api/process")
async def process_data(value: float = 1.0):
    """
    Bug 1：对传入的 value 做除法运算。
    当 value 为 0 或负数时触发异常。
    模拟：未校验用户输入导致的线上 500。
    """
    if value <= 0:
        BUG_PROCESS_ZERO_VALUE.inc()
        logger.warning("bug_triggered_zero_or_negative",
                       value=value,
                       bug_type="intermittent_500")
        # 模拟"意外崩溃"——真实场景可能是除零、空指针等
        result = 100 / value  # value=0 时 ZeroDivisionError
        return {"result": result}

    # 正常逻辑
    result = 100 / value if value != 1 else value * 42
    return {"input": value, "result": round(result, 4)}


# =====================================================
# 端点 4：报表生成（Bug 2 — 慢接口）
# =====================================================
@app.get("/api/report")
async def generate_report(date: str = "today"):
    """
    Bug 2：模拟报表生成，有 30% 概率耗时 >3s。
    模拟：数据库慢查询 / 外部 API 调用超时。
    """
    # 30% 概率触发慢响应（2~8 秒）
    if random.random() < 0.3:
        delay = random.uniform(2.0, 8.0)
        logger.warning("bug_triggered_slow_response",
                       delay_seconds=round(delay, 2),
                       date=date)
        time.sleep(delay)

        if delay > 3.0:
            BUG_SLOW_REPORT.inc()

        return {
            "date": date,
            "report": f"Report generated in {delay:.1f}s",
            "warning": "This took unusually long!"
        }

    # 正常速度（0.01~0.1s）
    time.sleep(random.uniform(0.01, 0.1))
    return {
        "date": date,
        "report": "Report generated successfully",
        "items": random.randint(10, 100)
    }


# =====================================================
# 端点 5：数据缓存（Bug 3 — 内存泄漏）
# =====================================================
@app.post("/api/cache")
async def add_to_cache(data: dict):
    """
    Bug 3：每次调用把数据追加到全局列表，永不清理。
    模拟：全局对象累积导致的内存泄漏。
    """
    # 模拟"业务需要"把数据缓存起来
    _global_cache.append(data)

    # 生成一些额外的"缓存数据"来加速泄漏
    # 模拟缓存中存了较大的对象
    cache_record = {
        "data": data,
        "cached_at": datetime.now().isoformat(),
        "cache_id": str(uuid.uuid4()),
        "padding": "x" * random.randint(100, 500)  # 每次追加少量数据
    }
    _global_cache.append(cache_record)

    CACHE_SIZE.set(len(str(_global_cache)))  # 用字符串长度模拟内存占用

    logger.info("cache_added",
                cache_size_items=len(_global_cache),
                cache_size_approx=len(str(_global_cache)))

    return {
        "status": "cached",
        "total_items": len(_global_cache),
        "cache_size_approx": len(str(_global_cache))
    }


@app.get("/api/cache/stats")
async def cache_stats():
    """查看缓存状态（方便观察泄漏）"""
    return {
        "total_items": len(_global_cache),
        "cache_size_approx": len(str(_global_cache)),
        "memory_leak_warning": len(_global_cache) > 1000
    }


# =====================================================
# Prometheus 指标暴露端点
# =====================================================
@app.get("/metrics")
async def metrics():
    """暴露 Prometheus 原生格式的指标"""
    return PlainTextResponse(generate_latest(REGISTRY))


# =====================================================
# 启动入口
# =====================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
