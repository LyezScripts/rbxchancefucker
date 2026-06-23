import requests
import os
import time
import threading
import random
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
import json

WEBHOOK_URL = os.getenv("WEBHOOK_URL")
RECIPIENT_ID = os.getenv("RECIPIENT_ID")
TOKENS_PATH = os.getenv("TOKENS_PATH", "tokens.txt")
BASE = "https://api.rbxchance.com"
LOOP_INTERVAL = int(os.getenv("LOOP_INTERVAL", "120"))
TIP_CURRENCY = "mm2"
TIP_CRYPTO_THRESHOLD = 0.5
TIP_CRYPTO_LARGE = 0.15
TARGET_CADENCES = {"hourly", "daily", "weekly"}

COLOR_GREEN = 0x57F287
COLOR_RED = 0xED4245
COLOR_YELLOW = 0xFEE75C
COLOR_BLUE = 0x5865F2

PROXY_URL = "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=protocolipport&format=text&protocol=http&timeout=5000&anonymity=all"
proxies_list = []

def test_single_proxy(proxy):
    try:
        r = requests.get("https://httpbin.org/ip", proxies={"http": proxy, "https": proxy}, timeout=5)
        return proxy if r.status_code == 200 else None
    except:
        return None

def fetch_proxies():
    global proxies_list
    proxies_list = []
    print("[~] Fetching proxies...")
    try:
        r = requests.get(PROXY_URL, timeout=15)
        raw = [line.strip() for line in r.text.splitlines() if line.strip() and not line.startswith('#')]
        working = []
        with ThreadPoolExecutor(max_workers=40) as executor:
            futures = [executor.submit(test_single_proxy, p) for p in raw[:200]]
            for future in as_completed(futures):
                if result := future.result():
                    working.append(result)
                    print(f"[+] Good: {result} ({len(working)})")
                if len(working) >= 50:
                    break
        proxies_list = working
        print(f"[+] Loaded {len(proxies_list)} working proxies")
    except Exception as e:
        print(f"[!] Proxy error: {e}")

def get_random_proxy():
    if not proxies_list:
        fetch_proxies()
    return random.choice(proxies_list) if proxies_list else None

def make_headers(access_token):
    return {
        "Authorization": access_token,
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.rbxchance.com",
        "Referer": "https://www.rbxchance.com/",
        "Cookie": f"access_token={access_token}"
    }

def make_request(method, url, headers, json_data=None, timeout=10, account_index=None):
    for attempt in range(3):
        proxy = get_random_proxy()
        proxies = {"http": proxy, "https": proxy} if proxy else None
        try:
            if method.upper() == "GET":
                r = requests.get(url, headers=headers, proxies=proxies, timeout=timeout)
            else:
                r = requests.post(url, headers=headers, json=json_data, proxies=proxies, timeout=timeout)
            print(f"[acc#{account_index}] {method} → {r.status_code}")
            return r
        except:
            if proxy and proxy in proxies_list:
                proxies_list.remove(proxy)
    return None

def load_accounts(path=TOKENS_PATH):
    if not os.path.exists(path):
        print(f"[!] {path} not found!")
        return []
    with open(path, "r") as f:
        tokens = [l.strip() for l in f.readlines() if l.strip()]
    print(f"[+] Loaded {len(tokens)} accounts")
    return tokens

def _print_embed_to_stdout(embed):
    # friendly stdout fallback for testing when WEBHOOK_URL is not set
    print("\n--- EMBED (stdout fallback) ---")
    print(f"Title: {embed.get('title')}")
    print(f"Description: {embed.get('description')}")
    if embed.get("fields"):
        print("Fields:")
        for f in embed["fields"]:
            name = f.get("name")
            value = f.get("value")
            inline = f.get("inline", False)
            print(f"  - {name}: {value} (inline={inline})")
    if thumb := embed.get("thumbnail"):
        print(f"Thumbnail: {thumb.get('url')}")
    print(f"Color: {embed.get('color')}")
    print(f"Timestamp: {embed.get('timestamp')}")
    print(f"Footer: {embed.get('footer', {}).get('text')}")
    print("--- END EMBED ---\n")

def send_embed(title, description, color, fields=None, thumbnail=None):
    embed = {
        "title": title,
        "description": description,
        "color": color,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "footer": {"text": "RBXChance Auto-Joiner"}
    }
    if fields: embed["fields"] = fields
    if thumbnail: embed["thumbnail"] = {"url": thumbnail}
    if not WEBHOOK_URL:
        _print_embed_to_stdout(embed)
        return
    try:
        requests.post(WEBHOOK_URL, json={"embeds": [embed]}, timeout=10)
    except:
        # on failure, fallback to stdout so you can see what would have been sent
        _print_embed_to_stdout(embed)

def get_giveaways(headers, account_index):
    r = make_request("GET", f"{BASE}/freebies", headers, account_index=account_index)
    if not r or r.status_code != 200:
        return []
    return r.json().get("giveaways", [])

def get_inventory(headers, account_index):
    r = make_request("GET", f"{BASE}/inventory", headers, account_index=account_index)
    if not r or r.status_code != 200:
        return []
    data = r.json()
    return data if isinstance(data, list) else data.get("items", data.get("inventory", []))

def get_balance(headers, account_index):
    r = make_request("GET", f"{BASE}/balance", headers, account_index=account_index)
    if not r or r.status_code != 200:
        return None
    data = r.json()
    return data.get("balance", data)

def tip_inventory(headers, account_index, recipient_id=RECIPIENT_ID):
    if not recipient_id:
        print(f"[acc#{account_index}] No RECIPIENT_ID set; skipping MM2 tip.")
        return
    items = get_inventory(headers, account_index)
    if not items:
        print(f"[acc#{account_index}] No items to tip.")
        return
    item_ids = [item.get("_id") or item.get("id") for item in items if item.get("_id") or item.get("id")]
    if not item_ids:
        return
    payload = {"recipient_id": recipient_id, "currency": TIP_CURRENCY, "item_ids": item_ids}
    r = make_request("POST", f"{BASE}/tip", headers, json_data=payload, account_index=account_index)
    if r and r.status_code in (200, 201):
        send_embed("MM2 Items Tipped", f"Account **#{account_index}** tipped **{len(item_ids)}** items", COLOR_BLUE)

def tip_crypto(headers, account_index, recipient_id, amount):
    if not recipient_id:
        print(f"[acc#{account_index}] No RECIPIENT_ID set; skipping crypto tip.")
        return
    payload = {"recipient_id": recipient_id, "currency": "usd", "amount": amount}
    r = make_request("POST", f"{BASE}/tip", headers, json_data=payload, account_index=account_index)
    if r and r.status_code in (200, 201):
        send_embed(f"Crypto Tip Sent - #{account_index}", "Success", COLOR_GREEN)

def try_join(gw_id, headers, account_index):
    r = make_request("POST", f"{BASE}/freebies/giveaways/{gw_id}/join", headers, account_index=account_index)
    if not r:
        return None, "No response"
    try:
        body = r.json()
    except:
        body = {}
    if r.status_code == 404 or body.get("message") == "Not Found":
        return 404, ""
    return r.status_code, r.text

def check_accounts_online(accounts):
    print("\n[=== ACCOUNT ONLINE CHECK START ===]")
    online = 0
    for idx, token in enumerate(accounts, 1):
        headers = make_headers(token)
        r = make_request("GET", f"{BASE}/freebies", headers, account_index=idx)
        status = "✅ ONLINE" if r and r.status_code == 200 else "❌ FAILED"
        print(f"Account #{idx} → {status}")
        if r and r.status_code == 200:
            online += 1
        time.sleep(0.6)
    print(f"\nSUMMARY: {online}/{len(accounts)} online\n[=== END ===]\n")

def manual_tip_mm2(accounts, recipient_id=None):
    recipient_id = recipient_id or RECIPIENT_ID
    print(f"[~] MM2 tip -> {recipient_id}")
    for idx, token in enumerate(accounts, 1):
        headers = make_headers(token)
        tip_inventory(headers, idx, recipient_id)
        time.sleep(0.5)

def manual_tip_crypto(accounts, recipient_id=None):
    recipient_id = recipient_id or RECIPIENT_ID
    print(f"[~] Crypto tip -> {recipient_id}")
    for idx, token in enumerate(accounts, 1):
        headers = make_headers(token)
        balance = get_balance(headers, idx)
        if not balance: continue
        crypto = balance.get("crypto") if isinstance(balance, dict) else balance
        if crypto and crypto > 0:
            amount = TIP_CRYPTO_LARGE if crypto > TIP_CRYPTO_THRESHOLD else round(crypto, 8)
            tip_crypto(headers, idx, recipient_id, amount)
        time.sleep(0.5)

def manual_promo(accounts, code):
    print(f"[~] Redeeming promo: {code}")
    for idx, token in enumerate(accounts, 1):
        headers = make_headers(token)
        make_request("POST", f"{BASE}/promocodes/redeem", headers, {"code": code}, account_index=idx)
        time.sleep(0.5)

def run_once(accounts):
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Running cycle...")
    gw_map = {}
    per_account_headers = {}
    for idx, token in enumerate(accounts, 1):
        headers = make_headers(token)
        per_account_headers[idx] = headers
        gws = get_giveaways(headers, idx)
        for gw in gws:
            if gw.get("cadence") in TARGET_CADENCES and gw.get("_id") not in gw_map:
                gw_map[gw["_id"]] = gw
    if not gw_map:
        print("[~] No target giveaways found.")
        return
    for gw_id, gw in gw_map.items():
        title = gw.get("title", gw.get("cadence", "Unknown"))
        prize_item = gw.get("prize_item")
        if prize_item:
            prize_str = f"{prize_item.get('display_name')} ({prize_item.get('rarity')}) — **{prize_item.get('value')}**"
            thumbnail = prize_item.get("thumbnail")
        else:
            prize_str = f"**{gw.get('prize_amount', '?')}** balance"
            thumbnail = None
        joined, already, failed, not_found = [], [], [], []
        for idx, token in enumerate(accounts, 1):
            headers = per_account_headers[idx]
            status, _ = try_join(gw_id, headers, idx)
            if status in (200, 201):
                joined.append(f"#{idx}")
            elif status == 409:
                already.append(f"#{idx}")
            elif status == 404:
                not_found.append(f"#{idx}")
            else:
                failed.append(f"#{idx}")
            time.sleep(0.4)
        lines = []
        if joined: lines.append(f"Joined: {', '.join(joined)}")
        if already: lines.append(f"Already in: {', '.join(already)}")
        if not_found: lines.append(f"Not found: {', '.join(not_found)}")
        if failed: lines.append(f"Failed: {', '.join(failed)}")
        color = COLOR_GREEN if joined else (COLOR_YELLOW if already else COLOR_RED)
        fields = [
            {"name": "Cadence", "value": gw.get("cadence", "").capitalize(), "inline": True},
            {"name": "Prize", "value": prize_str, "inline": False},
            {"name": "Entrants", "value": str(gw.get("entrants", "?")), "inline": True},
            {"name": "ID", "value": f"`{gw_id}`", "inline": False},
        ]
        send_embed(title, "\n".join(lines), color, fields, thumbnail)

def input_listener(accounts):
    while True:
        try:
            cmd = input().strip()
            if not cmd: continue
            parts = cmd.split()
            keyword = parts[0].lower()
            if keyword == "tip" and len(parts) == 3:
                mode, uid = parts[1].lower(), parts[2]
                if mode == "crypto":
                    threading.Thread(target=manual_tip_crypto, args=(accounts, uid), daemon=True).start()
                elif mode == "mm2":
                    threading.Thread(target=manual_tip_mm2, args=(accounts, uid), daemon=True).start()
            elif keyword == "promo" and len(parts) == 2:
                threading.Thread(target=manual_promo, args=(accounts, parts[1]), daemon=True).start()
            elif keyword == "onliner":
                threading.Thread(target=check_accounts_online, args=(accounts,), daemon=True).start()
        except:
            break

def main():
    print("RBXChance Auto-Joiner ")
    print("=" * 55)
    fetch_proxies()
    accounts = load_accounts()
    if not accounts:
        print(f"[!] No accounts in {TOKENS_PATH}")
        return
    print(f"Ready! Commands: onliner | tip crypto <uid> | tip mm2 <uid> | promo <code>")
    threading.Thread(target=input_listener, args=(accounts,), daemon=True).start()
    while True:
        run_once(accounts)
        print(f"[~] Sleeping {LOOP_INTERVAL}s...")
        send_embed("Going to Sleep", f"Next run in **{LOOP_INTERVAL} seconds**.", COLOR_YELLOW)
        time.sleep(LOOP_INTERVAL)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
    except Exception as e:
        print(f"Error: {e}")
