import pymysql
import chromadb
from chromadb.config import Settings
from chromadb import PersistentClient
from getpass import getpass
from sentence_transformers import SentenceTransformer

#這隻程式碼在將sql中的summary拿出來做embadding並存進向量資料庫ChromaDB當中

# Step 1: 連接 MySQL
print("🔐 請登入 MySQL 資料庫")
host = '127.0.0.1'
port = 3306
user = '自己的user'
password = '自己的密碼'
db_name = 'youtube_data'

try:
    mysql_conn = pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=db_name,
        charset='utf8mb4'
    )
    print("✅ 成功連線到 MySQL！")
except Exception as e:
    print("❌ 連線失敗：", e)
    exit()

# Step 2: 建立 Chroma PersistentClient ➜ 指定儲存路徑 D:\Chroma
client = PersistentClient(path="D:/Chroma", settings=Settings(allow_reset=True))

# Step 3: 建立或取得 collection
collection_name = "youtube_data"
try:
    collection = client.get_or_create_collection(name=collection_name)
    print(f"✅ 成功連接 Collection：{collection_name}")
except Exception as e:
    print("❌ Collection 初始化失敗：", e)
    exit()

# Step 4: 初始化嵌入模型
embedder = SentenceTransformer('all-MiniLM-L6-v2')

# Step 5: 從 MySQL 抓出資料
cursor = mysql_conn.cursor(pymysql.cursors.DictCursor)
cursor.execute("SELECT id, url, title, summary FROM videos")
rows = cursor.fetchall()

# Step 6: 檢查已存在的 ID（已在 Chroma 的略過）
try:
    all_data = collection.get(include=["metadatas"])  # 或 documents
    existing_ids = set(all_data["ids"])
except Exception as e:
    print("⚠️ 無法讀取現有 IDs，視為空集合")
    existing_ids = set()

# Step 7: 準備新增的資料
new_documents = []
new_embeddings = []
new_metadatas = []
new_ids = []

for row in rows:
    video_id = str(row['id'])
    summary = row.get('summary', '').strip()
    if not summary or video_id in existing_ids:
        continue  # 跳過空 summary 或已存在資料

    new_documents.append(summary)
    new_metadatas.append({
        "url": row['url'],
        "title": row['title']
    })
    new_ids.append(video_id)

# Step 8: 做 embedding 並寫入 Chroma
if new_documents:
    print(f"🔍 準備新增 {len(new_documents)} 筆資料到 ChromaDB...")

    try:
        vectors = embedder.encode(new_documents).tolist()
        assert len(vectors) == len(new_documents) == len(new_metadatas) == len(new_ids)

        print("🧪 測試第一筆：")
        print("📄 文本:", new_documents[0][:60])
        print("🆔 ID:", new_ids[0])
        print("📦 Meta:", new_metadatas[0])

        collection.add(
            documents=new_documents,
            embeddings=vectors,
            metadatas=new_metadatas,
            ids=new_ids
        )

        print(f"✅ 成功同步 {len(new_documents)} 筆資料到 Chroma！")
        print(f"📊 ChromaDB 現在總筆數：{collection.count()}")

    except Exception as e:
        print("❌ 寫入 Chroma 發生錯誤：", e)
else:
    print("✅ 所有影片都已同步到 Chroma，無需新增")

    
print("\n📋 全部 Collection 資料如下：")
try:
    all_data = collection.get(include=["documents", "metadatas"])
    for i in range(len(all_data["ids"])):
        print(f"🆔 ID: {all_data['ids'][i]}")
        print(f"📄 Document: {all_data['documents'][i][:100]}...")  # 最多顯示前 100 字
        print(f"📦 Metadata: {all_data['metadatas'][i]}")
        print("─" * 50)
except Exception as e:
    print("❌ 讀取資料失敗：", e)
# 結束連線
cursor.close()
mysql_conn.close()
