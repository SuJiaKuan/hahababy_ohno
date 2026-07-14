# hahababy 對照牆

網友於 Threads 等公開社群自主蒐集、整理的 hahababy 與其他品牌相似設計對照案例，彙整成一個可篩選、可檢視的網頁，供大眾知情與公共討論。

線上瀏覽請開啟 `index.html`（或部署後的 GitHub Pages 網址）。

## 專案結構

```
data/comparisons.csv   資料來源，每一列是一筆「品牌 vs hahababy」對照
images/                 對照截圖，檔名對應 CSV 的 image 欄位
build.py                讀取 CSV，產生 index.html 的靜態網頁產生器
index.html              產生出來的成品，直接部署即可，不需要額外 build 步驟
.claude/skills/          Claude Code 專案 skill（taste-skill，設計品味參考）
```

## 更新資料

1. 編輯 `data/comparisons.csv`，新增或修改一列。欄位說明：

   | 欄位 | 說明 |
   |---|---|
   | `image` | 圖片檔名，需存在於 `images/` 資料夾 |
   | `brand` | 被比對的品牌名稱，同品牌會自動分在一起 |
   | `brand_item_name` / `brand_product_url` | 該品牌的商品名稱／商品頁連結（找不到可留空）|
   | `hahababy_item_name` / `hahababy_product_url` | hahababy 對應商品名稱／商品頁連結 |
   | `source` / `source_url` | 提供者的 Threads 帳號／貼文連結 |

   若多筆資料的 `brand` + `hahababy_item_name` + `brand_item_name` 完全相同，會自動合併成同一張卡片（多張截圖、多個來源），不需要手動處理。

2. 把對應圖片放進 `images/`。

3. 重新產生網頁：

   ```bash
   python3 build.py
   ```

   會覆寫 `index.html`。

4. 本機預覽：

   ```bash
   python3 -m http.server 8791
   ```

   開啟 `http://localhost:8791/index.html`。

## 部署

`index.html` 本身就是完整的靜態網頁（CSS/JS 都內嵌在檔案裡），連同 `images/` 一起推到 GitHub Pages（或任何靜態主機）即可，不需要任何 build step。

## 免責聲明

本頁內容為網友自主蒐集整理，僅作為消費者知情與公共討論用途，不代表本站對任何品牌之侵權指控做出法律判斷。詳見網頁頁尾聲明。
