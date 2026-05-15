"""
阶段3: Redis Pub/Sub — 发布订阅
演示：精准订阅 + 通配符模式订阅
"""
import redis
import time
import threading

r = redis.Redis(host="localhost", port=6379, decode_responses=True)

received = {}  # {订阅者名: [消息列表]}


def subscriber(name, channels, use_pattern=False):
    """订阅指定频道，超时5秒后自动退出"""
    sub = redis.Redis(host="localhost", port=6379, decode_responses=True)
    pubsub = sub.pubsub()
    if use_pattern:
        pubsub.psubscribe(*channels)
    else:
        pubsub.subscribe(*channels)

    print(f"📡 [{name}] 已订阅: {channels}")
    received[name] = []

    deadline = time.time() + 5
    while time.time() < deadline:
        msg = pubsub.get_message(timeout=0.5)
        if msg and msg["type"] in ("message", "pmessage"):
            ch = msg.get("channel", msg.get("pattern", "?"))
            received[name].append(f"[{ch}] {msg['data']}")
            print(f"  📩 [{name}] 收到: [{ch}] {msg['data']}")

    print(f"  🛑 [{name}] 超时退出，共收到 {len(received[name])} 条")


def publisher():
    time.sleep(0.5)
    msgs = [
        ("news:tech", "🚀 gRPC 项目已上线"),
        ("news:sports", "⚽ 中国队赢了"),
        ("news:tech", "🐳 Docker 25.0 发布"),
    ]
    for ch, msg in msgs:
        time.sleep(0.3)
        count = r.publish(ch, msg)
        print(f"📢 [发布者] → {ch}: {msg} ({count}人收到)")


if __name__ == "__main__":
    print("=" * 50)
    print("📻 Redis Pub/Sub 演示")
    print("=" * 50)

    threads = [
        threading.Thread(target=subscriber, args=("订阅者A", ["news:tech"]), daemon=True),
        threading.Thread(target=subscriber, args=("订阅者B", ["news:sports"]), daemon=True),
        threading.Thread(target=subscriber, args=("通配符订阅", ["news:*"], True), daemon=True),
    ]
    for t in threads:
        t.start()

    publisher()

    for t in threads:
        t.join(timeout=8)

    print()
    print("=" * 50)
    print("📊 结果汇总:")
    for name, msgs in received.items():
        print(f"   {name}: {len(msgs)}条 → {msgs}")
    print()
    print("💡 通配符订阅者收到了两个频道 (news:tech + news:sports)")
    print("   精准订阅者只收自己频道的消息")
    print("   发布者完全不知道谁在订阅 — 彻底解耦 ✅")
    print("=" * 50)
