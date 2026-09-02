"""
Ban Detection Test Script
=========================
Sends rapid requests to TEFAS (bypassing anti-ban) to trigger 429s,
then monitors the worker's ban state via /api/status.
"""

import requests
import time
import json
from datetime import datetime

TEFAS_BASE = "https://www.tefas.gov.tr"
WORKER_URL = "http://localhost:8001"

def get_worker_status():
    try:
        r = requests.get(f"{WORKER_URL}/api/status", timeout=3)
        return r.json()
    except:
        return None

def print_ban_state(status, label=""):
    if not status:
        print("  ❌ Worker not responding")
        return
    ban = status.get("ban_detected", False)
    level = status.get("ban_level", 0)
    msg = status.get("ban_message", "")
    total429 = status.get("total_429s", 0)
    cons429 = status.get("consecutive_429s", 0)
    errors = status.get("total_errors", 0)
    slowdown = status.get("slowdown_factor", 1.0)
    cooldown = status.get("ban_cooldown_until")
    reqs = status.get("request_count", 0)

    level_icon = "🟢" if level == 0 else "🟡" if level == 1 else "🔴"
    ban_text = "BAN!" if ban else "OK"

    print(f"  {level_icon} [{ban_text}] Level={level} | 429s: {total429} (cons: {cons429}) | "
          f"Errors: {errors} | Speed: {slowdown:.1f}x | Reqs: {reqs}")
    if msg:
        print(f"     Message: {msg}")
    if cooldown:
        print(f"     Cooldown until: {cooldown}")

def send_rapid_requests(count=15):
    """Send rapid requests to TEFAS to trigger 429s."""
    from fake_useragent import UserAgent
    ua = UserAgent()
    
    print(f"\n{'='*60}")
    print(f"🚀 Sending {count} RAPID requests to TEFAS (no delay!)")
    print(f"{'='*60}\n")
    
    success = 0
    fail_429 = 0
    fail_other = 0
    
    for i in range(count):
        headers = {
            "User-Agent": ua.random,
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Referer": "https://www.tefas.gov.tr/",
            "Origin": "https://www.tefas.gov.tr",
        }
        try:
            r = requests.post(
                f"{TEFAS_BASE}/api/funds/fonUnvanAra",
                json={"fonKodu": "", "dil": "TR"},
                headers=headers,
                timeout=10,
            )
            if r.status_code == 200:
                success += 1
                print(f"  [{i+1}/{count}] ✅ 200 OK")
            elif r.status_code == 429:
                fail_429 += 1
                print(f"  [{i+1}/{count}] 🚫 429 TOO MANY REQUESTS!")
            else:
                fail_other += 1
                print(f"  [{i+1}/{count}] ⚠️  {r.status_code}")
        except Exception as e:
            fail_other += 1
            print(f"  [{i+1}/{count}] ❌ Error: {e}")
        
        # Check worker state after each request
        if (i + 1) % 5 == 0:
            print()
            print_ban_state(get_worker_status(), f"After {i+1} requests")
            print()
    
    print(f"\n{'='*60}")
    print(f"Results: {success} OK | {fail_429} x 429 | {fail_other} other errors")
    print(f"{'='*60}")

def main():
    print("🔬 BAN DETECTION TEST")
    print("=" * 60)
    
    # 1. Show initial state
    print("\n📊 Step 1: Initial ban state")
    print_ban_state(get_worker_status())
    
    # 2. Send rapid requests
    print("\n⚡ Step 2: Sending rapid requests to TEFAS...")
    send_rapid_requests(count=20)
    
    # 3. Wait 5 seconds for worker to process
    print("\n⏳ Step 3: Waiting 5s for worker to process...")
    time.sleep(5)
    
    # 4. Check final state
    print("\n📊 Step 4: Final ban state (after rapid fire)")
    status = get_worker_status()
    print_ban_state(status)
    
    if status and status.get("ban_detected"):
        print("\n🚨 BAN DETECTION WORKING! Worker detected the ban.")
        cooldown = status.get("ban_cooldown_until")
        if cooldown:
            print(f"   Cooldown until: {cooldown}")
            until = datetime.fromisoformat(cooldown)
            remaining = (until - datetime.now()).total_seconds()
            if remaining > 0:
                print(f"   Remaining: {int(remaining)} seconds")
                print("   Waiting for cooldown to end...")
                while datetime.now() < until:
                    time.sleep(10)
                    remaining = (until - datetime.now()).total_seconds()
                    if remaining > 0:
                        print(f"   ... {int(remaining)}s left")
                
                # 5. Check recovery
                print("\n📊 Step 5: After cooldown — checking recovery")
                time.sleep(3)
                status2 = get_worker_status()
                print_ban_state(status2)
    else:
        print("\n✅ No ban detected (TEFAS may not be rate-limiting right now)")
    
    # 6. Get TEFAS worker logs
    print("\n📋 Step 6: Worker logs (last 30 lines)")
    try:
        r = requests.get(f"{WORKER_URL}/api/logs", timeout=3)
        logs = r.json().get("logs", [])
        for line in logs[-30:]:
            print(f"  {line}")
    except Exception as e:
        print(f"  Could not fetch logs: {e}")

if __name__ == "__main__":
    main()
