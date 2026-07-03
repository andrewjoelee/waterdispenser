import os
import uuid
import requests
from datetime import datetime
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from playwright.async_api import async_playwright

app = FastAPI(title="宜中臨風樓飲水機觀測站-雲端驗證後端")

# 🟢 允許所有人跨網域呼叫（這樣你的前端網頁才能連到 Render）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🔐 Supabase 設定（從 Render 環境變數讀取，避免金鑰外洩）
SUPABASE_URL = "https://azezhxlatzfgltzqguoa.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# 📌 官方驗證貼文網址（請填入你實際的貼文網址）
OFFICIAL_THREADS_URL = "https://www.threads.net/@waterdispenserylshlinfeng2f2nd/post/XXXXXX"
OFFICIAL_IG_URL = "https://www.instagram.com/p/XXXXXX/"

# =====================================================================
# 🕷️ Playwright 雲端爬蟲核心（專為 Linux 伺服器優化的設定）
# =====================================================================
async def scrape_threads_comments(post_url: str):
    comments_data = []
    async with async_playwright() as p:
        # 💡 在 Linux 雲端環境跑 Playwright 必須加上 --no-sandbox 等參數，否則會崩潰
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
        )
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = await context.new_page()
        try:
            print(f"🌐 雲端正在即時爬取 Threads...")
            await page.goto(post_url, wait_until="networkidle", timeout=15000)
            await page.wait_for_timeout(2000)
            
            user_elements = await page.query_selector_all('a[href^="/@"]')
            for el in user_elements:
                username_raw = await el.get_attribute("href")
                username = username_raw.replace("/@", "").strip().lower()
                parent = await el.evaluate_handle("el => el.closest('div')")
                container = await page.evaluate_handle("parent => parent.closest('[class*=\"xtw6a9f\"]') || parent", parent)
                if container:
                    text = await container.evaluate("node => node.innerText")
                    comments_data.append({"username": username, "text": text})
        except Exception as e:
            print(f"❌ Threads 爬蟲異常: {e}")
        finally:
            await browser.close()
    return comments_data

async def scrape_instagram_comments(post_url: str):
    comments_data = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
        )
        context = await browser.new_context(user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)")
        page = await context.new_page()
        try:
            print(f"🌐 雲端正在即時爬取 Instagram...")
            await page.goto(post_url, wait_until="networkidle", timeout=15000)
            await page.wait_for_timeout(3000)
            
            comment_nodes = await page.query_selector_all('ul[class*="_a9z6"] li, div[class*="x1lliihq"]')
            for node in comment_nodes:
                text_content = await node.evaluate("el => el.innerText")
                lines = text_content.split('\n')
                if len(lines) >= 2:
                    username = lines[0].strip().lower()
                    text = lines[1]
                    comments_data.append({"username": username, "text": text})
        except Exception as e:
            print(f"❌ Instagram 爬蟲異常: {e}")
        finally:
            await browser.close()
    return comments_data

# =====================================================================
# 📡 FastAPI 驗證核心
# =====================================================================
class VerifyRequest(BaseModel):
    threads_id: str

@app.post("/api/verify-comment")
async def verify_comment(req: VerifyRequest):
    target_id = req.threads_id.strip().lower()
    
    headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json"
    }
    
    # 1. 去 Supabase 撈取 pending 資料
    db_url = f"{SUPABASE_URL}/rest/v1/verified_users?threads_id=eq.{target_id}&status=eq.pending&select=*"
    res = requests.get(db_url, headers=headers)
    
    if res.status_code != 200 or not res.json():
        raise HTTPException(status_code=400, detail="找不到您的驗證申請紀錄，或該帳號已完成驗證。")
    
    user_record = res.json()[0]
    expected_code = user_record['verification_code']
    
    print(f"🔔 [雲端驗證請求] 帳號: @{target_id} | 期待暗號: {expected_code}")

    # 2. 雙平台平行爬蟲比對
    threads_comments = await scrape_threads_comments(OFFICIAL_THREADS_URL)
    ig_comments = await scrape_instagram_comments(OFFICIAL_IG_URL)
    all_comments = threads_comments + ig_comments

    is_matched = False
    for comment in all_comments:
        if comment['username'] == target_id and expected_code in comment['text']:
            is_matched = True
            break

    # 3. 比對成功，寫入 Supabase 開通
    if is_matched:
        new_token = str(uuid.uuid4())
        update_url = f"{SUPABASE_URL}/rest/v1/verified_users?threads_id=eq.{target_id}"
        update_data = {
            "status": "verified",
            "session_token": new_token,
            "last_updated_time": datetime.utcnow().isoformat()
        }
        requests.patch(update_url, headers=headers, json=update_data)
        return {"status": "success", "message": "Verification passed."}
    else:
        raise HTTPException(status_code=422, detail=f"未在留言中找到帳號 @{target_id} 帶有暗號 [{expected_code}] 的留言。")