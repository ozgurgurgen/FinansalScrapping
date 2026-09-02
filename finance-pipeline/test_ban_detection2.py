"""
Ban Detection Test v2 — Heavy Load
===================================
Sends 50+ rapid requests to multiple TEFAS endpoints to trigger rate limiting.
Tests the ban detection escalation chain.
"""

import requests
import time
import json
import sys
from datetime import datetime

WORKER_URL = "http://localhost:8001"
TEFAS_BASE = "https://www.tefas.gov.tr"

# Test fund codes
TEST_FUNDS = [
    "YAC", "TKF", "TCD", "TCA", "TCH", "TRY", "TSP",
    "GGS", "GAF", "GAR", "GPY", "HIÇ", "HYH", "IKV",
    "IAK", "ISB", "INV", "IYH", "IYE", "IZN", "IZF",
    "IZT", "KAP", "KGL", "KKF", "KSF", "KVT", "MCH",
    "MRF", "NCF", "NTH", "OFS", "OIH", "ONC", "PNZ",
    "QUA", "RLI", "RYH", "TAL", "TCV", "TDC", "TKN",
    "TLP", "TMD", "TNH", "TTE", "TUG", "TVM", "YYL",
]

def get_status():
    try:
        return requests.get(f"{WORKER_URL}/api/status", timeout=3).json()
    except:
        return None

def get_logs(n=15):
    try:
        return requests.get(f"{WORKER_URL}/api/logs", timeout=3).json().get("logs", [])[-n:]
    except:
        return []

def show_state():
    s = get_status()
    if not s:
        print("  [!] Worker not responding")
        return
    ban = s.get("ban_detected", False)
    lvl = s.get("ban_level", 0)
    icon = "\033[92mOK\033[0m" if lvl == 0 else "\033[93mWARN\033[0m" if lvl == 1 else "\033[91mBAN\033[0m"
    print(f"  [{icon}] Level={lvl} | 429s={s.get('total_429s',0)} (cons={s.get('consecutive_429s',0)}) "
          f"| Errors={s.get('total_errors',0)} | Speed={s.get('slowdown_factor',1.0):.1f}x "
          f"| Reqs={s.get('request_count',0)} | Ban={ban}")
    msg = s.get("ban_message", "")
    cd = s.get("ban_cooldown_until")
    if msg:
        print(f"     Msg: {msg}")
    if cd:
        until = datetime.fromisoformat(cd)
        remain = max(0, int((until - datetime.now()).total_seconds()))
        print(f"     Cooldown: {remain}s remaining")
    return s

def hit_tefas(endpoint, payload, label):
    """Single rapid request to TEFAS."""
    from fake_useragent import UserAgent
    ua = UserAgent()
    headers = {
        "User-Agent": ua.random,
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Referer": "https://www.tefas.gov.tr/",
        "Origin": "https://www.tefas.gov.tr",
    }
    try:
        r = requests.post(f"{TEFAS_BASE}{endpoint}", json=payload, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            count = len(data.get("resultList", []))
            print(f"    {label}: 200 OK ({count} results)")
            return 200
        else:
            print(f"    {label}: {r.status_code}")
            return r.status_code
    except Exception as e:
        print(f"    {label}: ERROR {e}")
        return 0

def main():
    print("=" * 60)
    print("BAN DETECTION TEST v2 — HEAVY LOAD")
    print("=" * 60)

    # Step 1: Baseline
    print("\n[1] BASELINE STATE:")
    show_state()

    # Step 2: Burst — 30 rapid requests to fonBilgiGetir (per-fund, more protected)
    print("\n[2] PHASE A — 30 rapid requests to fonBilgiGetir (different funds)...")
    for i, code in enumerate(TEST_FUNDS[:30]):
        hit_tefas("/api/funds/fonBilgiGetir", {"fonKodu": code, "dil": "TR"}, f"  [{i+1}/30] {code}")
        # NO delay — intentionally aggressive

    print("\n  >>> STATE AFTER PHASE A:")
    show_state()

    # Step 3: Check logs
    print("\n[3] RECENT LOGS:")
    for line in get_logs(15):
        print(f"  {line}")

    # Step 4: Burst — 20 more to fonFiyatBilgiGetir (price history, another endpoint)
    print("\n[4] PHASE B — 20 rapid requests to fonFiyatBilgiGetir...")
    for i, code in enumerate(TEST_FUNDS[:20]):
        hit_tefas("/api/funds/fonFiyatBilgiGetir", {"fonKodu": code, "dil": "TR", "periyod": 3}, f"  [{i+1}/20] {code}")

    print("\n  >>> STATE AFTER PHASE B:")
    show_state()

    # Step 5: Final logs
    print("\n[5] FINAL LOGS (last 20):")
    for line in get_logs(20):
        print(f"  {line}")

    # Step 6: Wait for any cooldown
    final_state = show_state()
    if final_state and final_state.get("ban_detected"):
        cd = final_state.get("ban_cooldown_until")
        if cd:
            until = datetime.fromisoformat(cd)
            remain = max(0, int((until - datetime.now()).total_seconds()))
            print(f"\n[6] BAN ACTIVE — waiting {remain}s for cooldown...")
            while datetime.now() < until:
                time.sleep(10)
                r = max(0, int((until - datetime.now()).total_seconds()))
                if r > 0:
                    print(f"  ... {r}s remaining")
            print("\n  >>> STATE AFTER COOLDOWN:")
            time.sleep(3)
            show_state()
            print("\n  >>> FINAL LOGS:")
            for line in get_logs(10):
                print(f"  {line}")

    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    main()
