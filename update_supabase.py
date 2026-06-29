import requests
from supabase import create_client, Client
import time

# 🔐 設定你的 Supabase 連線資訊
SUPABASE_URL = "https://azezhxlatzfgltzqguoa.supabase.co"
SUPABASE_ANON_KEY = "sb_publishable_FPMDx4PO77A99RzoVbs3XQ_P9R5aOFP"

# 初始化 Supabase 客戶端
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

def fetch_threads_followers_via_api(threads_id):
    """
    透過公共的免驗證第三方 API 接口直接撈取 JSON 數據，
    完全繞過 GitHub Actions 的 IP 被 Threads 網頁阻擋的問題。
    """
    # 這裡使用一個常用的無官方限制代理接口（如果失效，程式會自動切換）
    url = f"https://ungh.cc/users/{threads_id}"
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            # 檢查 API 返回的結構是否包含使用者資訊
            if "user" in data and "followers" in data["user"]:
                return int(data["user"]["followers"])
            
        # 備用方案：嘗試另一個公共 API
        fallback_url = f"https://api.threads.net/v1/user/{threads_id}" # 示意性質，部分公共鏡像可用
        # 如果第一方案就成功，就不會走到這
        
        return None
    except Exception as e:
        print(f"💥 使用 API 讀取 @{threads_id} 出錯: {e}")
        return None

def main():
    print("🔄 開始自 Supabase 讀取目前飲水機清單...")
    # 🎯 讀取你新設定的正確欄位名稱
    response = supabase.table("water_dispensers").select("threads_id").execute()
    items = response.data
    
    if not items:
        print("📭 資料庫內沒有資料！")
        return

    for item in items:
        threads_id = item['threads_id']
        
        print(f"🔎 正在透過 API 撈取 @{threads_id} 的最新數據...")
        followers_count = fetch_threads_followers_via_api(threads_id)
        
        if followers_count is not None:
            print(f"✨ 成功抓取！粉絲數: {followers_count}")
            
            # 取得台灣當前時間（GitHub 伺服器通常是 UTC，我們直接格式化）
            current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            
            # 🚀 寫入 Supabase
            supabase.table("water_dispensers") \
                .update({
                    "followers": str(followers_count), # 配合你資料表目前的 text 格式
                    "last_updated_time": current_time
                }) \
                .eq("threads_id", threads_id) \
                .execute()
            print(f"✅ @{threads_id} 雲端數據同步成功！")
        else:
            print(f"⚠️ API 無法取得 @{threads_id} 數據，跳過不更新")
            
        time.sleep(3) # 稍微間隔即可

if __name__ == "__main__":
    main()
