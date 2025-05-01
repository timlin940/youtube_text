新版的資料庫在這裡喔，MongoDB的我就不會再更新了。

mysql_video_2.py是用來儲存影片各種資訊的，大家通常用不到，有興趣可以看一下。

store_vector.py是用來儲存summary的vector進入ChromaDB，大家通常用不到，有興趣可以看一下。

一般操作是先用mysql_video_2.py抓影片再用store_vector.py來存向量。

vector_query.py是讓大家可以測試向量資料庫的搜尋效果，這個等我做好連線後就可以用了。

我會讓大家有辦法可以連線到Mysql(用來儲存到影片的各種資訊)、ChromaDB(儲存summary的vector)
