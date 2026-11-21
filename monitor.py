import json
import os
from pathlib import Path
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright


PRODUCTS = [
    # =========================
    # 五大唱片
    # =========================
    (
        "五大唱片商品 439405678604",
        "https://www.5music.com.tw/CDList-C.asp?cdno=439405678604",
    ),
    (
        "五大唱片商品 438475678968",
        "https://www.5music.com.tw/CDList-C.asp?cdno=438475678968",
    ),
    (
        "五大唱片商品 438475678969",
        "https://www.5music.com.tw/CDList-C.asp?cdno=438475678969",
    ),

    # =========================
    # 博客来
    # 暂时保留，不调整 Cloudflare
    # =========================
    (
        "博客来商品 0020204179",
        "https://www.books.com.tw/products/0020204179",
    ),

    # =========================
    # 滚石購物網 Rockmall
    # =========================
    (
        "滚石｜張惠妹 / 偏執面〔神經白膠唱片〕",
        "https://shop.rockmall.com.tw/product_view.php?id=100083",
    ),
    (
        "滚石｜張惠妹 / 偷故事的人〔黑膠〕",
        "https://shop.rockmall.com.tw/product_view.php?id=100084",
    ),
    (
        "滚石｜張惠妹 / 阿密特2〔視覺黑膠唱片〕",
        "https://shop.rockmall.com.tw/product_view.php?id=100082",
    ),
]


STATE_FILE = Path("state.json")
TIMEOUT = 30


def get_page_requests(url):
    r = requests.get(
        url,
        timeout=TIMEOUT,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/140.0.0.0 Safari/537.36"
            )
        },
    )
    r.raise_for_status()
    r.encoding = r.apparent_encoding or r.encoding
    return r.text


def get_books_page(url):
    print("[BOOKS] Starting Chromium...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            locale="zh-TW",
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/140.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        try:
            response = page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=TIMEOUT * 1000,
            )
            if response:
                print(f"[BOOKS] HTTP {response.status}")
            page.wait_for_timeout(3000)
            text = page.locator("body").inner_text()
            title = page.title()
            print(f"[BOOKS] Page title: {title}")
            print(f"[BOOKS] Text length: {len(text)}")
            return text, title
        finally:
            browser.close()


def get_rockmall_page(url):
    print("[ROCKMALL] Starting Chromium...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            locale="zh-TW",
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/140.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        try:
            response = page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=TIMEOUT * 1000,
            )
            if response:
                print(f"[ROCKMALL] HTTP {response.status}")
            page.wait_for_timeout(2000)
            text = page.locator("body").inner_text()
            title = page.title()
            print(f"[ROCKMALL] Page title: {title}")
            return text, title
        finally:
            browser.close()


def parse_5music_status(html):
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    if "目前無現貨" in text or "目前无现货" in text:
        return "out_of_stock"
    return "possibly_in_stock"


def parse_books_status(text):
    out_words = ["已售完", "補貨中", "补货中"]
    if any(word in text for word in out_words):
        return "out_of_stock"

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
    return "unknown"


def parse_rockmall_status(text):
    # 缺貨/售完優先判斷，避免頁面同時殘留購物車字樣時誤判
    out_words = ["售完", "缺貨", "缺货", "暫無庫存", "暂无库存"]
    if any(word in text for word in out_words):
        return "out_of_stock"

    # 滾石頁面出現「加入購物車」即視為可下單
    cart_words = ["加入購物車", "加入购物车"]
    if any(word in text for word in cart_words):
        return "in_stock"

    return "unknown"


def get_title_from_html(html, fallback):
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

    if "5music.com.tw" in url:
        bark_title = "🎵 五大唱片｜补货提醒"
        bark_group = "五大唱片"
    elif "rockmall.com.tw" in url:
        bark_title = "🎸 滚石購物網｜补货提醒"
        bark_group = "滚石"
    elif "books.com.tw" in url:
        bark_title = "📚 博客来｜补货提醒"
        bark_group = "博客来"
    else:
        bark_title = title
        bark_group = "音乐商品监控"

    endpoint = (
        f"https://api.day.app/"
        f"{quote(key, safe='')}/"
        f"{quote(bark_title, safe='')}/"
        f"{quote(body, safe='')}"
    )
    r = requests.get(
        endpoint,
        params={"url": url, "group": bark_group},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    print(f"[BARK] {bark_group} HTTP {r.status_code}")


def main():
    test_bark = (
        os.environ.get("TEST_BARK", "").lower() == "true"
    )

    # Bark 测试模式
    if test_bark:
        print("[TEST] Sending Bark test notifications...")

        five_music_test = [
            (
                "五大唱片测试 439405678604",
                "https://www.5music.com.tw/CDList-C.asp?cdno=439405678604",
            ),
            (
                "五大唱片测试 438475678968",
                "https://www.5music.com.tw/CDList-C.asp?cdno=438475678968",
            ),
            (
                "五大唱片测试 438475678969",
                "https://www.5music.com.tw/CDList-C.asp?cdno=438475678969",
            ),
        ]
        for test_name, test_url in five_music_test:
            bark_push(
                "",
                (
                    f"{test_name}\n"
                    "GitHub Actions → 五大唱片 Bark 测试成功！\n"
                    "点击通知可直接打开对应专辑页面。"
                ),
                test_url,
            )

        rockmall_test = [
            ("滚石测试｜張惠妹 / 偏執面〔神經白膠唱片〕", "https://shop.rockmall.com.tw/product_view.php?id=100083"),
            ("滚石测试｜張惠妹 / 偷故事的人〔黑膠〕", "https://shop.rockmall.com.tw/product_view.php?id=100084"),
            ("滚石测试｜張惠妹 / 阿密特2〔視覺黑膠唱片〕", "https://shop.rockmall.com.tw/product_view.php?id=100082"),
        ]
        for test_name, test_url in rockmall_test:
            bark_push(
                "",
                f"{test_name}\nGitHub Actions → 滚石購物網 Bark 测试成功！\n点击通知可直接打开对应商品页面。",
                test_url,
            )

        print("[TEST] Bark test notifications sent.")
        return

    old = load_state()
    new = {}
    notifications = []

    for label, url in PRODUCTS:
        try:
            if "5music.com.tw" in url:
                html = get_page_requests(url)
                status = parse_5music_status(html)
                title = get_title_from_html(html, label)

            elif "books.com.tw" in url:
                text, page_title = get_books_page(url)
                status = parse_books_status(text)
                title = label
                if page_title:
                    print(f"[BOOKS] {page_title}")

            elif "rockmall.com.tw" in url:
                text, page_title = get_rockmall_page(url)
                status = parse_rockmall_status(text)
                title = label
                if page_title:
                    print(f"[ROCKMALL] {page_title}")

            else:
                status = "unknown"
                title = label

        except Exception as e:
            print(f"[ERROR] {label}: {e}")
            if label in old:
                new[label] = old[label]
            continue

        previous = old.get(label, {}).get("status")
        print(f"[CHECK] {title}: {previous} -> {status}")

        if status == "unknown":
            if label in old:
                new[label] = old[label]
            continue

        new[label] = {
            "status": status,
            "url": url,
            "title": title,
        }

        # 第一次建立狀態不發通知
        if previous is None:
            continue

        # 缺貨 -> 有貨：五大/博客來使用原有 possibly_in_stock；
        # 滾石加入購物車後回傳 in_stock。
        if (
            previous == "out_of_stock"
            and status in ("possibly_in_stock", "in_stock")
        ):
            notifications.append((title, url, status))

    save_state(new)

    for title, url, status in notifications:
        if status == "in_stock":
            status_text = "已出现「加入购物车」，现在可以下单！"
        else:
            status_text = "检测到商品从「无货」变为「可能有货」。"

        bark_push(
            "",
            f"{title}\n{status_text}\n请立即打开商品页面查看。",
            url,
        )

    if notifications:
        print(f"[ALERT] Sent {len(notifications)} Bark notification(s).")
    else:
        print("[INFO] No stock change detected.")


if __name__ == "__main__":
    main()
