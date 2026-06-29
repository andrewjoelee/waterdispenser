import requests
from bs4 import BeautifulSoup
from supabase import create_client, Client
import json
import time

# 🔐 設定你的 Supabase 連線資訊
SUPABASE_URL = "https://azezhxlatzfgltzqguoa.supabase.co"
SUPABASE_ANON_KEY = "sb_publishable_FPMDx4PO77A99RzoVbs3XQ_P9R5aOFP"

# 初始化 Supabase 客戶端
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

def parse_followers_to_int(val):
    """
    將爬到的字串（例如 '1.2K', '552', '2,500'）安全轉換為純整數，避免 Supabase 型態出錯
    """
    if not val:
        return 0
    str_val = str(val).upper().strip()
    try:
        if 'K' in str_val:
            return int(float(str_val.replace('K', '').strip()) * 1000)
        if 'M' in str_val:
            return int(float(str_val.replace('M', '').strip()) * 1000000)
        return int(str_val.replace(',', '').strip())
    except Exception as e:
        print(f"⚠️ 數字轉換失敗 ({val}): {e}")
        return 0

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
                
                # 🎯 關鍵優化：同時相容中英文的 Threads 網頁描述
                if 'followers' in desc:
                    return desc.split('followers')[0].strip()
                elif '名粉絲' in desc:
                    return desc.split('名粉絲')[0].strip()
                elif '位粉絲' in desc:
                    return desc.split('位粉絲')[0].strip()
        return None
    except Exception as e:
        print(f"💥 爬取 @{threads_id} 出錯: {e}")
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
        
        print(f"🔎 正在爬取 @{threads_id} 的最新 Threads 數據...")
        raw_followers = fetch_threads_followers(threads_id)
        
        if raw_followers is not None:
            int_followers = parse_followers_to_int(raw_followers)
            print(f"✨ 成功抓取！原始資料: {raw_followers} -> 轉為整數: {int_followers}")
            
            current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            
            # 🚀 真正寫入、更新你的 Supabase 資料庫
            supabase.table("water_dispensers") \
                .update({
                    "followers": int_followers, 
                    "last_updated_time": current_time
                }) \
                .eq("id", record_id) \
                .execute()
            print(f"✅ @{threads_id} 雲端數據同步成功！")
        else:
            print(f"⚠️ 無法取得 @{threads_id} 數據，跳過不更新")
            
        time.sleep(3)

if __name__ == "__main__":
    main()
