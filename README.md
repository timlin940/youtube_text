專題前置處理:抓影片字幕檔
使用者資訊:

使用者 | 密碼 | Compass / Python / URI 連線字串
* roy | ***** | mongodb://roy:*****@192.168.100.*:27017/youtube?authSource=youtube
* jj | ***** | mongodb://jj:*****@192.168.100.*:27017/youtube?authSource=youtube
* yuye | ***** | mongodb://yuye:*****@192.168.100.*:27017/youtube?authSource=youtube
* liang | ***** | mongodb://liang:*****@192.168.100.*:27017/youtube?authSource=youtube

各位可以去下載mongodb compass。

進入後新增connection，把url換成以上對應的連接字串就可以存取資料庫了(其實密碼都一樣，我只是想分開用)

然後在vscode下載mongodb的套件 ( "MongoDB for VS Code" )，接著輸入下方程式碼應該就沒問題了(記得要下載yt-dlp)。

注意事項:如果發現Compass無法登入，首先用管理員身份打開cmd，指令net START MongoDB，這樣應該就打得開了(不要忘記輸入上面的連結喔)，如果要關閉就是net STOP MongoDB。
