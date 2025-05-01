from chromadb import PersistentClient
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

# 初始化 Chroma 與嵌入模型
client = PersistentClient(path="D:/Chroma", settings=Settings(allow_reset=True))
collection = client.get_collection(name="youtube_data")
embedder = SentenceTransformer('all-MiniLM-L6-v2')

# 使用者輸入查詢語句
query = input("🔍 請輸入你想搜尋的內容：")

# 轉成向量
query_vector = embedder.encode(query).tolist()

# 查詢最相近的影片（你可以改成 n_results=5）
results = collection.query(
    query_embeddings=[query_vector],
    n_results=3,
    include=["metadatas", "documents", "distances"]
)

# 顯示結果
print("\n🔎 查詢結果如下：\n")
for i in range(len(results["ids"][0])):
    print(f"🎬 Title: {results['metadatas'][0][i]['title']}")
    print(f"🔗 URL: {results['metadatas'][0][i]['url']}")
    print(f"📄 Summary: {results['documents'][0][i][:200]}...")
    print(f"📏 Similarity (距離越小越相近): {results['distances'][0][i]:.4f}")
    print("─" * 60)
