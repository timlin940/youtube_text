import subprocess
import os
import re
import json
from pymongo import MongoClient
from datetime import datetime
import subprocess
import json
from pymongo import MongoClient
import getpass
from urllib.parse import quote_plus

def login_mongodb():
    host = "192.168.100.3"  # 這是我的電腦IP
    port = 27017
    db_name = "youtube"
    auth_db = "youtube"#這代表你們的使用者是在"youtube"建立的，我自己是admin

    print("🔐 請登入 MongoDB")
    username = input("使用者名稱：")
    password = getpass.getpass("密碼（輸入時不顯示）：")

    uri = f"mongodb://{quote_plus(username)}:{quote_plus(password)}@{host}:{port}/{db_name}?authSource={auth_db}"

    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=3000)
        client.server_info()  # 測試連線
        print("✅ 登入成功！\n")
        return client[db_name]  # 回傳資料庫物件
    except Exception as e:
        print("❌ 登入失敗：", e)
        exit()

def search_youtube_with_subtitles(keyword, max_results=10):
    yt_dlp_path = r"C:\Users\Tim\AppData\Roaming\Python\Python311\Scripts\yt-dlp.exe"

    print(f"🔍 搜尋關鍵字：{keyword}")

    # 建立 yt-dlp 搜尋指令
    command = [
        yt_dlp_path,
        f"ytsearch{max_results}:{keyword}",   # 搜尋前 N 筆
        "--dump-json",                        # 輸出為 JSON 格式
        "--no-warnings"
    ]

    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        lines = result.stdout.strip().split('\n')

        valid_videos = []
        for line in lines:
            video_data = json.loads(line)

            # 檢查是否有字幕 available_captions
            if video_data.get("subtitles") or video_data.get("automatic_captions"):
                valid_videos.append({
                    "title": video_data.get("title"),
                    "url": video_data.get("webpage_url"),
                    "duration": video_data.get("duration_string"),
                    "channel": video_data.get("channel"),
                    "has_subtitles": True
                })

        return valid_videos

    except subprocess.CalledProcessError as e:
        print("❌ 執行 yt-dlp 發生錯誤：", e)
        return []
#######################################################################(上面是爬影片，下面是下載字幕黨到mongodb)
def download_subtitle_to_mongodb(video_url, db, language="en"):
    yt_dlp_path = r"C:\Users\Tim\AppData\Roaming\Python\Python311\Scripts\yt-dlp.exe"
    print(f"🎬 處理影片：{video_url}")

    # 取得影片資訊
    info_cmd = [yt_dlp_path, "--dump-json", video_url]
    info_result = subprocess.run(info_cmd, capture_output=True, text=True)
    video_info = json.loads(info_result.stdout)
    title = video_info.get("title", "Unknown Title")

    # 下載字幕（存在本地）
    command = [
        yt_dlp_path,
        "--write-auto-sub",
        "--sub-lang", language,
        "--skip-download",
        "--output", "-",
        video_url
    ]

    try:
        subprocess.run(command, check=True)

        vtt_filename = None
        for f in os.listdir():
            if f.endswith(f"{language}.vtt"):
                vtt_filename = f
                break

        if not vtt_filename:
            print("❌ 找不到字幕檔")
            return

        # 同時建立兩種字幕版本
        structured_subtitles = []  # 有時間戳
        output_lines = []          # 純文字
        previous_line = ""
        current_start = ""
        current_end = ""
        current_text = ""

        with open(vtt_filename, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()

                match = re.match(r"(\d\d:\d\d:\d\d\.\d+) --> (\d\d:\d\d:\d\d\.\d+)", line)
                if match:
                    if current_text:
                        structured_subtitles.append({
                            "start": current_start,
                            "end": current_end,
                            "content": current_text.strip()
                        })
                        current_text = ""
                    current_start, current_end = match.groups()
                elif line and not line.startswith("NOTE") and "align:start" not in line and "position:" not in line:
                    line = re.sub(r"<.*?>", "", line)
                    current_text += line + " "
                    if line != previous_line:
                        output_lines.append(line)
                        previous_line = line

            if current_start and current_text:
                structured_subtitles.append({
                    "start": current_start,
                    "end": current_end,
                    "content": current_text.strip()
                })

        os.remove(vtt_filename)

        # 準備文件資料
        subtitle_text = "\n".join(output_lines)
        collection = db["videos"]

        if collection.find_one({"url": video_url}):
            print("⚠️ 已存在此影片資料，略過")
            return

        document = {
            "title": title,
            "url": video_url,
            "text_no_time": subtitle_text,
            "text": structured_subtitles,
            "language": language,
            "created_at": datetime.utcnow()
        }
        result = collection.insert_one(document)
        print(f"✅ 已寫入 MongoDB，_id: {result.inserted_id}")

    except subprocess.CalledProcessError as e:
        print("❌ 執行 yt-dlp 失敗：", e)
        print("❌ 執行 yt-dlp 失敗：", e)
if __name__ == "__main__":
    # ⬅️ 使用者登入
    db = login_mongodb()

    # 🧠 接著輸入主題關鍵字
    keyword = input("🔍 請輸入你想搜尋的英文主題：")#目前最大的問題還是只能搜關鍵字沒有語意理解
    videos = search_youtube_with_subtitles(keyword, max_results=10)

    for i, video in enumerate(videos, 1):
        print(f"\n🎬 {i}. {video['title']}")
        print(f"📺 連結: {video['url']}")
        print(f"📡 頻道: {video['channel']}")
        print(f"⏱ 時長: {video['duration']}")
        download_subtitle_to_mongodb(str(video['url']), db,language="en")
