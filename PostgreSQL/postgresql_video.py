import subprocess
import os
import re
import json
import psycopg2
from datetime import datetime
from getpass import getpass
from urllib.parse import quote_plus
from transformers import pipeline, AutoTokenizer
from configparser import ConfigParser
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

# 初始化 Gemini API
config = ConfigParser()
config.read("config.ini")
llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash-latest",
    google_api_key=config["Gemini"]["API_KEY"],
    convert_system_message_to_human=True,
)

# 初始化 Summarizer 與 Tokenizer
summarizer = pipeline("summarization", model="sshleifer/distilbart-cnn-6-6")
tokenizer = AutoTokenizer.from_pretrained("sshleifer/distilbart-cnn-6-6")

def time_str_to_str(tstr):
    parts = [float(p) for p in tstr.split(":")]
    if len(parts) == 3:
        return f"{int(parts[0])}:{int(parts[1]):02}:{int(parts[2]):02}"
    elif len(parts) == 2:
        return f"{int(parts[0])}:{int(parts[1]):02}"
    return "00:00"

def login_postgresql():
    print(" 請登入 PostgreSQL 資料庫")
    host = ''#這邊是看外部連線的連結名稱，那一長串要從中間找出我們要的!
    port = 5432
    user = 'teammate'
    password = ''
    db_name = 'youtube_data_qkc5'
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            dbname=db_name
        )
        print(" 成功連線到 PostgreSQL！")
        return conn
    except Exception as e:
        print(" 連線失敗：", e)
        exit()

def search_youtube_with_subtitles(keyword, max_results=10):
    yt_dlp_path = r"C:\\Users\\Tim\\AppData\\Roaming\\Python\\Python311\\Scripts\\yt-dlp.exe"
    print(f"\U0001f50d 搜尋關鍵字：{keyword}")
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
        print(" 執行 yt-dlp 發生錯誤：", e)
        return []

def split_text_by_tokens(text, max_tokens=800):
    words = text.split()
    chunks = []
    current = []
    for word in words:
        current.append(word)
        token_len = len(tokenizer(" ".join(current))["input_ids"])
        if token_len > max_tokens:
            chunks.append(" ".join(current[:-1]))
            current = [word]
    if current:
        chunks.append(" ".join(current))
    return chunks

def generate_summary_local(subtitle_text):
    if len(subtitle_text) < 200:
        return subtitle_text.strip()
    try:
        chunks = split_text_by_tokens(subtitle_text)
        partial_summaries = []
        for i, chunk in enumerate(chunks):
            print(f"\U0001f9e9 正在處理第 {i+1} 段摘要...")
            result = summarizer(chunk, max_length=100, min_length=30, do_sample=False)
            partial_summaries.append(result[0]['summary_text'])
        return "\n".join(partial_summaries)
    except Exception as e:
        print(" 摘要失敗，回傳前段文字：", e)
        return subtitle_text[:400]

def predict_topic_with_gemini(summary_text):
    messages = [
        SystemMessage(content=f"這是一段YouTube影片的摘要內容：{summary_text}。請根據以下主題分類中，選出最適合的1到2個主題（只回傳英文主題名稱，用逗號分隔）：Computer Science, Law, Mathematics, Physics, Chemistry, Biology, Earth Science, History, Geography, Sports, Astronomy,Daily Life。請勿自行創造其他分類。"),
        HumanMessage(content="根據摘要來判斷最適合的分類是哪種")
    ]
    result = llm.invoke(messages)
    return result.content

def download_and_save_to_postgresql(video_url, title, description, conn, language="en"):
    yt_dlp_path = r"C:\\Users\\Tim\\AppData\\Roaming\\Python\\Python311\\Scripts\\yt-dlp.exe"
    print(f"\U0001f3ac 處理影片：{video_url}")
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
        vtt_filename = next((f for f in os.listdir() if f.endswith(f"{language}.vtt")), None)
        if not vtt_filename:
            print(" 找不到字幕檔")
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
                        structured_subtitles.append({"start": current_start, "end": current_end, "content": current_text.strip()})
                        current_text = ""
                    current_start, current_end = match.groups()
                elif line and not line.startswith("NOTE") and "align:start" not in line:
                    line = re.sub(r"<.*?>", "", line)
                    current_text += line + " "
                    if line != previous_line:
                        output_lines.append(line)
                        previous_line = line
        if current_start and current_text:
            structured_subtitles.append({"start": current_start, "end": current_end, "content": current_text.strip()})
        os.remove(vtt_filename)
        subtitle_text = "\n".join(output_lines)#字幕檔生成

        #如果時間太短就不要了
        if structured_subtitles:
            last_end = structured_subtitles[-1]["end"]
            duration_str = time_str_to_str(last_end)

            time_parts = [int(float(x)) for x in duration_str.split(":")]
            if len(time_parts) == 3:
                duration_sec = time_parts[0] * 3600 + time_parts[1] * 60 + time_parts[2]
            elif len(time_parts) == 2:
                duration_sec = time_parts[0] * 60 + time_parts[1]
            else:
                duration_sec = 0

            if duration_sec < 180:
                print(f" 影片長度僅 {duration_str}，少於 3 分鐘，略過儲存：{video_url}")
                return
        else:
            duration_str = ""
        
        #抽出內嵌碼
        video_id = video_url.split("v=")[-1].split("&")[0]
        embed_url = f"https://www.youtube.com/embed/{video_id}"
        
        #做summary
        summary = generate_summary_local(subtitle_text)
        
        #主題分類
        assigned_categories = predict_topic_with_gemini(summary)
        assigned_categories = [topic.strip() for topic in assigned_categories.split(",")]
        cursor = conn.cursor()
        
        #如果已儲存就跳過
        cursor.execute("SELECT id FROM videos WHERE url = %s", (video_url,))
        if cursor.fetchone():
            print(f" 影片已存在於資料庫中，略過：{video_url}")
            return
        last_end = structured_subtitles[-1]["end"] if structured_subtitles else ""
        duration_str = time_str_to_str(last_end) if last_end else ""
        insert_video = """
        INSERT INTO videos (url, title, description, summary, transcription, transcription_with_time, duration_str, embed_url, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id;
        """
        cursor.execute(insert_video, (
            video_url, title, description, summary, subtitle_text,
            json.dumps(structured_subtitles, ensure_ascii=False),
            duration_str, embed_url, datetime.utcnow()
        ))
        new_video_id = cursor.fetchone()[0]
        for topic in assigned_categories:
            # 查找該 topic 對應的 id
            cursor.execute("SELECT id FROM categories WHERE topic = %s", (topic,))
            result = cursor.fetchone()
            if result:
                category_id = result[0]
                cursor.execute(
                    "INSERT INTO video_categories (video_id, category_id) VALUES (%s, %s)",
                    (new_video_id, category_id)
                )
            else:
                print(f"⚠️ 找不到分類：{topic}，略過此分類")
        conn.commit()
        print(f" 成功存影片：{title}，主題：{', '.join(assigned_categories)}")
        print(f" 可嵌入網址：{embed_url}")
    except subprocess.CalledProcessError as e:
        print("執行 yt-dlp 失敗：", e)

if __name__ == "__main__":
    conn = login_postgresql()
    keyword = input(" 請輸入你想搜尋的英文主題：")
    videos = search_youtube_with_subtitles(keyword, max_results=5)
    for i, video in enumerate(videos, 1):
        print(f"{i}. {video['title']}")
        print(f"連結: {video['url']}")
        print(f"頻道: {video['channel']}")
        print(f"時長: {video['duration']}")
        download_and_save_to_postgresql(video['url'], video['title'], video.get('description', ''), conn)
