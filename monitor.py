import json
import os
from pathlib import Path
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

PRODUCTS = [
    ("五大唱片商品 439", "https://www.5music.com.tw/CDList-C.asp?cdno=439"),
    ("五大唱片商品 438475678968", "https://www.5music.com.tw/CDList-C.asp?cdno=438475678968"),
    ("五大唱片商品 438475678969", "https://www.5music.com.tw/CDList-C.asp?cdno=438475678969"),
    ("博客来商品 0020204179", "https://www.books.com.tw/products/0020204179?sloc=main"),
]

STATE_FILE = Path("state.json")
TIMEOUT = 20


def get_page(url):
    r = requests.get(
        url,
        timeout=TIMEOUT,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 Chrome/140 Safari/537.36"
            )
        },
    )
    r.raise_for_status()
    r.encoding = r.apparent_encoding or r.encoding
    return r.text


def parse_status(html, url):
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)

    # 五大唱片：明确显示无现货
    if "5music.com.tw" in url:
        if "目前無現貨" in text or "目前无现货" in text:
            return "out_of_stock"
        return "possibly_in_stock"

    # 博客来：目前商品显示「已售完，補貨中」
    if "books.com.tw" in url:
        if "已售完" in text or "補貨中" in text or "补货中" in text:
            return "out_of_stock"

        # 页面出现购买按钮/加入购物车相关文字时，
        # 视为可能有库存
        buy_words = [
            "加入購物車",
            "加入购物车",
            "立即購買",
            "立即购买",
            "直接購買",
            "直接购买",
        ]

        if any(word in text for word in buy_words):
            return "possibly_in_stock"

        return "possibly_in_stock"

    return "possibly_in_stock"


def get_title(html, fallback):
    soup = BeautifulSoup(html, "html.parser")

    h2 = soup.find("h2")
    if h2:
        title = h2.get_text(" ", strip=True)
        if title:
            return title

    title_tag = soup.find("title")
    if title_tag:
        title = title_tag.get_text(" ", strip=True)
        if title:
            return title

    return fallback


def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass

    return {}


def save_state(state):
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def bark_push(title, body, url):
    key = os.environ.get("BARK_KEY", "").strip()

    if not key:
        raise RuntimeError("BARK_KEY secret is not configured.")

    endpoint = (
        f"https://api.day.app/{quote(key, safe='')}/"
        f"{quote(title, safe='')}/"
        f"{quote(body, safe='')}"
    )

    r = requests.get(
        endpoint,
        params={
            "url": url,
            "group": "五大唱片/博客来",
        },
        timeout=TIMEOUT,
    )

    r.raise_for_status()

    print(f"[BARK] HTTP {r.status_code}")


def main():

    # 手动 Bark 测试
    test_bark = os.environ.get("TEST_BARK", "").lower() == "true"

    if test_bark:
        print("[TEST] Sending Bark test notification...")

        bark_push(
            "🔔 五大唱片/博客来监控测试",
            "GitHub Actions → Bark 测试成功！监控连接正常。",
            "https://www.5music.com.tw/",
        )

        return

    old = load_state()
    new = {}
    notifications = []

    for label, url in PRODUCTS:

        try:
            html = get_page(url)
            status = parse_status(html, url)
            title = get_title(html, label)

        except Exception as e:

            print(f"[ERROR] {label}: {e}")

            if label in old:
                new[label] = old[label]

            continue

        previous = old.get(label, {}).get("status")

        new[label] = {
            "status": status,
            "url": url,
            "title": title,
        }

        print(f"[CHECK] {title}: {previous} -> {status}")

        # 第一次检测只建立基准
        if previous is None:
            continue

        # 无货 → 可能有货
        if previous == "out_of_stock" and status == "possibly_in_stock":
            notifications.append((title, url))

    save_state(new)

    for title, url in notifications:

        bark_push(
            "🔔 补货提醒",
            f"{title}\n检测到商品从「无货」变为「可能有货」，请立即打开查看。",
            url,
        )

    if notifications:
        print(
            f"[ALERT] Sent {len(notifications)} Bark notification(s)."
        )


if __name__ == "__main__":
    main()
