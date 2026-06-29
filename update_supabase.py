import requests
from bs4 import BeautifulSoup
from supabase import create_client, Client
import json
import time

# 設定你的 Supabase 連線資訊（已比照 index.html 格式修正）
SUPABASE_URL = "https://azezhxlatzfgltzqguoa.supabase.co"
SUPABASE_ANON_KEY = "sb_publishable_FPMDx4PO77A99RzoVbs3XQ_P9R5aOFP"

# 初始化 Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

def fetch_threads_followers(threads_id):
    url = f"https://www.threads.net/@{threads_id}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            meta_tag = soup.find('meta', property='og:description')
            if meta_tag:
                desc = meta_tag.get('content', '')
                if 'followers' in desc:
                    # 抓取 Threads 頁面的 description 欄位並取出粉絲數
                    followers = desc.split('followers')[0].strip()
                    return followers
        return None
    except Exception as e:
        print(f"💥 錯誤 @{threads_id}: {e}")
        return None

def main():
    print("🔄 開始自 Supabase 讀取目前飲水機清單...")
    response = supabase.table("water_dispensers").select("id, threads_id").execute()
    items = response.data
    
    if not items:
        print("📭 資料庫內沒有資料！")
        return

    for item in items:
        record_id = item['id']
        threads_id = item['threads_id'] if item['threads_id'] else record_id
        
        print(f"🔎 正在爬取 @{threads_id}...")
        new_followers = fetch_threads_followers(threads_id)
        
        if new_followers:
            print(f"✨ 最新粉絲數: {new_followers}。正在更新至 Supabase...")
            current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            supabase.table("water_dispensers") \
                .update({"followers": str(new_followers), "last_updated_time": current_time}) \
                .eq("id", record_id) \
                .execute()
            print(f"✅ @{threads_id} 更新成功！")
        else:
            print(f"⚠️ 跳過 @{threads_id}")
            
        time.sleep(3)

if __name__ == "__main__":
    main()
