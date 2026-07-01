import os
import re
import time
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright

# === Supabase 設定區 ===
RAW_URL = os.environ.get("SUPABASE_URL", "https://azezhxlatzfgltzqguoa.supabase.co/rest/v1/")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "sb_publishable_FPMDx4PO77A99RzoVbs3XQ_P9R5aOFP")
TABLE_NAME = "water_dispensers"

# 🧬 自動化清洗網址：防呆機制，確保最後格式一定是 https://xxx.supabase.co/rest/v1
# 不管你填入的有帶 /rest/v1/ 還是只有純 domain，都會被修正好
clean_match = re.match(r"(https://[^/]+)", RAW_URL.strip())
if clean_match:
    SUPABASE_URL = f"{clean_match.group(1)}/rest/v1"
else:
    SUPABASE_URL = RAW_URL.rstrip('/')


def get_threads_ids_from_supabase():
    """從 Supabase 撈取所有需要爬取的飲水機 threads_id"""
    url = f"{SUPABASE_URL}/{TABLE_NAME}?select=id,threads_id"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        req = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode('utf-8'))
            return [item for item in data if item.get("threads_id")]
            
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f"❌ Supabase API 讀取失敗 (HTTP {e.code}): {error_body}")
        print(f"🔗 當時請求的完整網址為: {url}")
        return []
    except Exception as e:
        print(f"❌ 連線至 Supabase 發生異常: {e}")
        return []


def update_supabase_followers(record_id, followers_str):
    """將抓到的粉絲數與更新時間同步回資料庫"""
    url = f"{SUPABASE_URL}/{TABLE_NAME}?id=eq.{record_id}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }
    
    payload_data = {
        "followers": followers_str,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    payload = json.dumps(payload_data).encode('utf-8')
    
    try:
        req = urllib.request.Request(url, data=payload, headers=headers, method="PATCH")
        with urllib.request.urlopen(req, timeout=15) as response:
            return "OK"
    except Exception as e:
        return f"Error: {e}"


def get_threads_follower(page, username):
    """爬取單一 Threads 帳號的粉絲數"""
    target_url = f"https://www.threads.net/@{username}"
    try:
        page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)

        # 方案 A：從 Meta Description 抓取
        meta_desc = page.locator('meta[name="description"]').get_attribute("content")
        if meta_desc:
            meta_match = re.search(r"([\d\.,\s]+[M|K|萬|億]?)\s*(followers|位粉絲)", meta_desc, re.IGNORECASE)
            if meta_match:
                return meta_match.group(1).strip()

        # 方案 B：網頁原始碼暴力掃描
        page_content = page.content()
        match = re.search(r"([\d\.,\s]+[M|K|萬]?)\s*(followers|位粉絲)", page_content, re.IGNORECASE)
        if match:
            return match.group(1).strip()

        return "未公開/格式變更"
    except Exception as e:
        print(f"❌ 抓取 @{username} 發生異常: {e}")
        return "抓取錯誤"


def main():
    print(f"📡 [偵測環境] 格式化後的 API 進入點: {SUPABASE_URL}")
    print("🚀 正在連線至 Supabase 獲取飲水機清單...")
    account_list = get_threads_ids_from_supabase()
    
    if not account_list:
        print("⚠️ 未能撈取到任何有效的任務，流程結束。")
        return

    print(f"📊 成功載入！本次排程共計抓取 {len(account_list)} 個目標帳號。")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        for idx, account in enumerate(account_list, start=1):
            db_id = account["id"]
            threads_id = account["threads_id"]

            print(f"\n【{idx}/{len(account_list)}】正在分析：@{threads_id}")
            followers_result = get_threads_follower(page, threads_id)
            print(f"   -> 偵測到粉絲數：{followers_result}")

            status = update_supabase_followers(db_id, followers_result)
            print(f"   -> 同步狀態：{status}")

            time.sleep(2)

        browser.close()

    print("\n🎉 所有飲水機 Threads 粉絲數已與 Supabase 同步完成！")


if __name__ == "__main__":
    main()
