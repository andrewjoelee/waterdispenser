import os
import re
import time
from datetime import datetime
import urllib.request
import urllib.parse
from playwright.sync_api import sync_playwright

# === 終極設定區 ===
# ⚠️ 請確保這行換成你複製的「網頁應用程式 URL」
WEB_APP_URL = "https://script.google.com/macros/s/AKfycbyAw_RaACLaX8cTCcHLl3aqGvZrXcn4g-xPB76xgZZxw8_UeoiyGDCzJyy5mZ1tkL0L/exec"

# ⚠️ 在這裡輸入你要抓取的 Threads 帳號 ID 清單（你可以多加幾個試試看！）
THREADS_ACCOUNTS = [
"waterdispenserylshlinfeng2f2nd",
"ymhs_waterdispenser",
"fhsh_waterdispenser",
"waterdispenser_wlsh_zhuqing1",
"tcfsh.water.nya"] 


def get_threads_follower(page, username):
    """進階版：抓取單一 Threads 帳號的粉絲數"""
    target_url = f"https://www.threads.net/@{username}"
    try:
        # 模擬真人正常滾動載入
        page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000) 

        # 方案 A：直接從網頁的 meta description 撈，這最穩定、最不受網頁改版影響
        meta_desc = page.locator('meta[name="description"]').get_attribute("content")
        if meta_desc:
            # 匹配例如 "9.9M followers"、"450K 位粉絲"、"1,234 followers"
            meta_match = re.search(r"([\d\.,\s]+[M|K|萬|億]?)\s*(followers|位粉絲)", meta_desc, re.IGNORECASE)
            if meta_match:
                return meta_match.group(1).strip()

        # 方案 B：如果 meta 沒撈到，直接暴力搜全網頁原始碼
        page_content = page.content()
        match = re.search(r"([\d\.,\s]+[M|K|萬]?)\s*(followers|位粉絲)", page_content, re.IGNORECASE)
        if match:
            return match.group(1).strip()

        return "未公開/格式變更"
    except Exception as e:
        print(f"❌ 抓取 @{username} 失敗: {e}")
        return "抓取錯誤"


def send_to_google_sheets(username, followers):
    """用最純粹的網頁請求，直接把資料送給 Google 試算表"""
    query_string = urllib.parse.urlencode({"username": username, "followers": followers})
    full_url = f"{WEB_APP_URL}?{query_string}"
    
    try:
        req = urllib.request.Request(full_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as response:
            result = response.read().decode('utf-8')
            return result
    except Exception as e:
        return f"連線錯誤: {e}"


def main():
    print(f"📋 偵測到共有 {len(THREADS_ACCOUNTS)} 個飲水機帳號準備更新...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        for idx, username in enumerate(THREADS_ACCOUNTS, start=1):
            print(f"🔎 [{idx}/{len(THREADS_ACCOUNTS)}] 正在網頁讀取 @{username}")
            followers = get_threads_follower(page, username)
            print(f"-> 粉絲數: {followers}")

            print(f"💾 正在同步更新至 Google 試算表...")
            api_result = send_to_google_sheets(username, followers)
            print(f"-> 試算表後台回應: {api_result}")

            time.sleep(3)

        browser.close()

    print("\n🎉 試算表更新程序完全執行完畢！")


if __name__ == "__main__":
    main()
