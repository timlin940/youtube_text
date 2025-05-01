import subprocess
import os
import re
import json
import pymysql
import requests
from datetime import datetime
from getpass import getpass
from urllib.parse import quote_plus
from transformers import pipeline
from configparser import ConfigParser
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
# 該程式碼做到抓影片下來到Mysql，同時會先用distilbart-cnn-6-6來獲得summary(還不確定是吃字幕檔嗎)，再給gemini來獲得主題分類。目前缺陷:主題分類有點爛嗎(有些影片同時有不同分類，正常，但是
# 不知道準不準)，還沒做向量化

# 你的 Gemini API 金鑰
config = ConfigParser()
config.read("config.ini")
llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash-latest",
    google_api_key=config["Gemini"]["API_KEY"],
    convert_system_message_to_human=True,
)

# 小型 Summary Pipeline (本地生成)
summarizer = pipeline("summarization", model="sshleifer/distilbart-cnn-6-6")

def login_mysql():
    print("🔐 請登入 MySQL 資料庫")
    host = input("主機IP（例如127.0.0.1）：")
    port = int(input("port（預設3306）：") or "3306")
    user = input("使用者名稱：")
    password = getpass("密碼（輸入時不顯示）：")
    db_name = input("資料庫名稱（例如youtube_data）：")

    try:
        conn = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=db_name,
            charset='utf8mb4'
        )
        print("✅ 成功連線到 MySQL！")
        return conn
    except Exception as e:
        print("❌ 連線失敗：", e)
        exit()

def search_youtube_with_subtitles(keyword, max_results=10):
    yt_dlp_path = r"C:\Users\Tim\AppData\Roaming\Python\Python311\Scripts\yt-dlp.exe"
    print(f"🔍 搜尋關鍵字：{keyword}")

    command = [
        yt_dlp_path,
        f"ytsearch{max_results}:{keyword}",
        "--dump-json",
        "--no-warnings"
    ]

    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        lines = result.stdout.strip().split('\n')

        valid_videos = []
        for line in lines:
            video_data = json.loads(line)
            if video_data.get("subtitles") or video_data.get("automatic_captions"):
                valid_videos.append({
                    "title": video_data.get("title"),
                    "url": video_data.get("webpage_url"),
                    "description": video_data.get("description"),
                    "duration": video_data.get("duration_string"),
                    "channel": video_data.get("channel")
                })

        return valid_videos

    except subprocess.CalledProcessError as e:
        print("❌ 執行 yt-dlp 發生錯誤：", e)
        return []

def generate_summary_local(subtitle_text):
    # 用 Mini Summarizer 本地生成 summary
    if len(subtitle_text) > 3000:
        subtitle_text = subtitle_text[:3000]  # 避免太長炸掉模型
    summary = summarizer(subtitle_text, max_length=100, min_length=30, do_sample=False)[0]['summary_text']
    return summary

def predict_topic_with_gemini(summary_text):
    messages = [
        SystemMessage(content=f"這是一段YouTube影片的摘要內容：{summary_text}。請根據以下11個主題分類中，選出最適合的1到2個主題（只回傳英文主題名稱，用逗號分隔）：Computer Science, Law, Mathematics, Physics, Chemistry, Biology, Earth Science, History, Geography, Sports, Daily Life。"),
        HumanMessage(content="根據摘要來判斷最適合的分類是哪種")
    ]
    result = llm.invoke(messages)
    return result.content

def download_and_save_to_mysql(video_url, title, description, conn, language="en"):
    yt_dlp_path = r"C:\Users\Tim\AppData\Roaming\Python\Python311\Scripts\yt-dlp.exe"
    print(f"🎬 處理影片：{video_url}")

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

        structured_subtitles = []
        output_lines = []
        current_start = ""
        current_end = ""
        current_text = ""
        previous_line = ""

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

        subtitle_text = "\n".join(output_lines)

        # 1️⃣ 用本地 Mini Summarizer 產生 summary
        summary = generate_summary_local(subtitle_text)

        # 2️⃣ 再用 summary 分類影片主題
        assigned_categories = predict_topic_with_gemini(summary)

        if not assigned_categories:
            assigned_categories = ['Daily Life']
        else:
            assigned_categories = [topic.strip() for topic in assigned_categories.split(",")]

        cursor = conn.cursor()

        # 3️⃣ 寫入 videos
        sql = """
        INSERT INTO videos (url, title, description, summary, transcription, transcription_with_time, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(sql, (
            video_url,
            title,
            description,
            summary,
            subtitle_text,
            json.dumps(structured_subtitles, ensure_ascii=False),
            datetime.utcnow()
        ))
        conn.commit()

        video_id = cursor.lastrowid

        # 4️⃣ 寫入 video_categories
        for topic in assigned_categories:
            sql_link = """
            INSERT IGNORE INTO video_categories (video_id, topic)
            VALUES (%s, %s)
            """
            cursor.execute(sql_link, (video_id, topic))

        conn.commit()

        print(f"✅ 成功存影片：{title}，主題：{', '.join(assigned_categories)}")

    except subprocess.CalledProcessError as e:
        print("❌ 執行 yt-dlp 失敗：", e)

if __name__ == "__main__":
    conn = login_mysql()

    keyword = input("🔍 請輸入你想搜尋的英文主題：")
    videos = search_youtube_with_subtitles(keyword, max_results=5)

    for i, video in enumerate(videos, 1):
        print(f"\n🎬 {i}. {video['title']}")
        print(f"📺 連結: {video['url']}")
        print(f"📡 頻道: {video['channel']}")
        print(f"⏱ 時長: {video['duration']}")
        download_and_save_to_mysql(video['url'], video['title'], video.get('description', ''), conn, language="en")
