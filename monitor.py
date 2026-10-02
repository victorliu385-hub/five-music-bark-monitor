import json
import os
import re
from pathlib import Path
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

PRODUCTS = [
    ("五大唱片商品 439", "https://www.5music.com.tw/CDList-C.asp?cdno=439"),
    ("五大唱片商品 438475678968", "https://www.5music.com.tw/CDList-C.asp?cdno=438475678968"),
    ("五大唱片商品 438475678969", "https://www.5music.com.tw/CDList-C.asp?cdno=438475678969"),
]

STATE_FILE = Path("state.json")
TIMEOUT = 20

def get_page(url):
    r = requests.get(
        url,
        timeout=TIMEOUT,
        headers={"User-Agent": "Mozilla/5.0 (compatible; FiveMusicStockMonitor/1.0)"},
    )
    r.raise_for_status()
    r.encoding = r.apparent_encoding or r.encoding
    return r.text

def parse_status(html):
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    # Five Music currently displays this exact phrase when the item is out of stock.
    if "目前無現貨" in text or "目前无现货" in text:
        return "out_of_stock"
    # If an explicit out-of-stock phrase is absent, treat it as potentially available.
    # This is intentionally conservative: a site redesign should not silently mark
    # a product as unavailable.
    return "possibly_in_stock"

def get_title(html, fallback):
    soup = BeautifulSoup(html, "html.parser")
    h2 = soup.find("h2")
    if h2:
        title = h2.get_text(" ", strip=True)
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
    endpoint = f"https://api.day.app/{quote(key, safe='')}/{quote(title, safe='')}/{quote(body, safe='')}"
    r = requests.get(endpoint, params={"url": url, "group": "五大唱片"}, timeout=TIMEOUT)
    r.raise_for_status()

def main():
    old = load_state()
    new = {}
    notifications = []

    for label, url in PRODUCTS:
        try:
            html = get_page(url)
            status = parse_status(html)
            title = get_title(html, label)
        except Exception as e:
            print(f"[ERROR] {label}: {e}")
            # Keep the previous state on a temporary fetch failure.
            if label in old:
                new[label] = old[label]
            continue

        previous = old.get(label, {}).get("status")
        new[label] = {"status": status, "url": url, "title": title}

        print(f"[CHECK] {title}: {previous} -> {status}")

        # First successful observation initializes the baseline without alerting.
        if previous is None:
            continue

        # Only alert on an actual transition from the known out-of-stock state.
        if previous == "out_of_stock" and status == "possibly_in_stock":
            notifications.append((title, url))

    save_state(new)

    for title, url in notifications:
        bark_push(
            "🔔 五大唱片补货",
            f"{title}\n检测到商品状态从「无现货」变为「可能有现货」，请立即打开查看。",
            url,
        )

    if notifications:
        print(f"[ALERT] Sent {len(notifications)} Bark notification(s).")

if __name__ == "__main__":
    main()
