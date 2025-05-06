import psycopg2

# 資料庫連線參數（請替換成你的實際值）
conn = psycopg2.connect(
    host="dpg-d0d4h8q4d50c73eeu1ng-a.oregon-postgres.render.com",
    port=5432,
    database="youtube_data_qkc5",
    user="teammate",
    password="cGu5jdTwy4JLriDMylTlzNmW4S9jJHNF"
)

cursor = conn.cursor()

# tables = ["videos", "categories", "video_categories"]

# for table in tables:
#     print(f"\n📋 表格：{table}")
#     cursor.execute(f"SELECT * FROM {table}")
#     rows = cursor.fetchall()
#     colnames = [desc[0] for desc in cursor.description]

#     print("欄位：", colnames)
#     for row in rows:
#         print(row)
##################################以上是檢查資料有沒有都抓到，接下來如果要仔細看videos資料

cursor.execute(f"SELECT id,title,summary FROM videos where id = 3") #檢查id = 3的影片資訊
rows = cursor.fetchall()
colnames = [desc[0] for desc in cursor.description]
print("欄位：", colnames)
for row in rows:
    print(row )
    
# (*)可以改成 ['id', 'url', 'title', 'description', 'summary', 'transcription', 'transcription_with_time', 'duration_str', 'embed_url', 'created_at']

cursor.close()
conn.close()
