"""
压测脚本：向 buggy-api 发送混合流量，触发 3 类 Bug。
配合 Prometheus 监控观察指标变化和告警触发。

用法：
  python load_test.py
  python load_test.py --duration 180  # 跑 3 分钟
"""

import time
import random
import threading
import urllib.request
import urllib.error
import json
import sys
from concurrent.futures import ThreadPoolExecutor

BASE_URL = "http://localhost:30080"
STATS = {
    "total": 0,
    "success": 0,
    "error_500": 0,
    "slow": 0,
    "cache_ops": 0,
}
lock = threading.Lock()


def request(method, path, data=None):
    """发送 HTTP 请求并统计结果"""
    url = f"{BASE_URL}{path}"
    start = time.time()

    try:
        if data:
            req = urllib.request.Request(
                url,
                data=json.dumps(data).encode(),
                headers={"Content-Type": "application/json"},
                method=method
            )
        else:
            req = urllib.request.Request(url, method=method)

        with urllib.request.urlopen(req, timeout=10) as resp:
            duration = time.time() - start
            status = resp.status

    except urllib.error.HTTPError as e:
        duration = time.time() - start
        status = e.code
    except Exception as e:
        duration = time.time() - start
        status = 0

    with lock:
        STATS["total"] += 1
        if status == 200:
            STATS["success"] += 1
        elif status == 500:
            STATS["error_500"] += 1
        if duration > 2:
            STATS["slow"] += 1

    return status, duration


def normal_traffic():
    """正常流量：80% 概率"""
    r = random.random()
    if r < 0.3:
        request("GET", "/health")
    elif r < 0.6:
        uid = random.randint(1, 3)
        request("GET", f"/api/users/{uid}")
    else:
        request("GET", "/api/process?value=5")


def bug_traffic():
    """Bug 触发流量：20% 概率"""
    r = random.random()
    if r < 0.4:
        # Bug 1：传零值或负数触发 500
        bad_value = random.choice([0, -1, -5, -0.5])
        request("GET", f"/api/process?value={bad_value}")
    elif r < 0.7:
        # Bug 2：触发慢接口（本身有 30% 概率慢）
        request("GET", "/api/report?date=2026-05-14")
    else:
        # Bug 3：内存泄漏
        request("POST", "/api/cache", data={"key": f"item_{random.randint(1, 1000)}"})
        with lock:
            STATS["cache_ops"] += 1


def worker():
    """单个 worker 循环发送请求"""
    while True:
        if random.random() < 0.2:
            bug_traffic()
        else:
            normal_traffic()
        time.sleep(random.uniform(0.05, 0.3))  # 每秒 3~20 个请求


def print_stats():
    """每秒打印统计"""
    last_total = 0
    while True:
        time.sleep(5)
        with lock:
            total = STATS["total"]
            rate = (total - last_total) / 5
            print(f"[{time.strftime('%H:%M:%S')}] "
                  f"总请求:{total:>5} "
                  f"速率:{rate:.1f}/s "
                  f"500错误:{STATS['error_500']:>3} "
                  f"慢请求:{STATS['slow']:>3} "
                  f"缓存写入:{STATS['cache_ops']:>3} "
                  f"成功率:{STATS['success']/max(total,1)*100:.1f}%")
            last_total = total


def main(duration=120):
    print(f"🔥 开始压测，持续 {duration} 秒...")
    print(f"   目标: {BASE_URL}")
    print(f"   策略: 80% 正常流量 + 20% Bug 触发流量")
    print(f"   Bug 类型: 间歇500 / 慢接口 / 内存泄漏")
    print()

    # 启动统计线程
    stats_thread = threading.Thread(target=print_stats, daemon=True)
    stats_thread.start()

    # 用 5 个并发 worker 发请求
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(worker) for _ in range(5)]

        time.sleep(duration)
        # 暴力退出（worker 是无限循环）
        executor._threads.clear()
        for f in futures:
            f.cancel()

    # 最终统计
    print()
    print("=" * 50)
    with lock:
        print(f"📊 压测结束 总请求: {STATS['total']}")
        print(f"   ✅ 成功: {STATS['success']}")
        print(f"   ❌ 500错误: {STATS['error_500']}")
        print(f"   🐌 慢请求(>2s): {STATS['slow']}")
        print(f"   💾 缓存写入: {STATS['cache_ops']}")
        if STATS['total'] > 0:
            err_rate = STATS['error_500'] / STATS['total'] * 100
            print(f"   📈 错误率: {err_rate:.1f}%")
            print(f"   🎯 成功率: {STATS['success']/STATS['total']*100:.1f}%")


if __name__ == "__main__":
    duration = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[1] == "--duration" else 120
    main(duration)
