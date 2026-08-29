# SOP 製作依據與程式碼檢查紀錄

本檔案記錄 `docs/SOP.md` 與 `docs/操作SOP_最新版.pptx` 的製作依據、檢查過的程式檔案、與舊版 SOP 的差異、以及仍需人工確認的項目，供之後維護 SOP 的人參考。

## 1. 本次檢查過的主要程式檔案

| 檔案 | 用途 |
|---|---|
| `app.py` | 入口網站主頁：登入表單、登入後選單、資料庫初始化、管理員名單常數 |
| `auth.py` | 密碼雜湊與驗證（PBKDF2-HMAC-SHA256） |
| `database.py` | SQLite 資料表結構與存取（employees / system_settings / sop_documents） |
| `pages/1_私車公用報支.py` | 私車公用報支完整邏輯（~1200 行，含 Gemini 辨識、Excel/Word 產出） |
| `pages/2_出差申報.py` | 出差申報完整邏輯（~750 行，Step 1～5） |
| `pages/3_管理員維護區.py` | 管理員第二層驗證、員工資料維護、SOP 上傳、密碼更新 |
| `config.py` | 出差申報欄位座標、出差地代號對照表、雜費津貼日額、幣別代碼、Gemini 模型清單 |
| `models.py` | `TripHeader` / `ReceiptItem` / `ExpenseRow` / `MealDetailEntry` 資料結構 |
| `business_rules.py` | 複核階段的提示規則（餐費非週日、多筆雜費津貼） |
| `trip_calculations.py` | 雜費津貼／餐費自動計算邏輯 |
| `receipt_recognizer.py` | Gemini 視覺 API 呼叫、裁切/轉正、額度用完與伺服器過載的重試/備援邏輯 |
| `excel_reader.py` / `excel_writer.py` / `excel_utils.py` | 出差申報範本讀取、欄位偵測、寫入（透過 LibreOffice） |
| `libreoffice_worker.py` | 實際執行 Excel 寫入與公式重算的背景程序（未逐行深入，僅確認呼叫關係與已知限制） |
| `docx_generator.py` | 出差申報 Word 明細清單產生（剪貼簿版面、PDF 滿版、字型設定） |
| `employee_directory.py` / `dept_directory.py` | 員工/部門清單讀取（CSV，供未整合入口網站時的獨立測試 fallback） |
| `identity_watermark.py` | 版本標籤／署名浮水印元件 |
| `portal_theme.py` / `ui_enhancements.py` | 共用玻璃擬態視覺樣式、Tab 鍵導覽輔助（僅讀取，未深入列出全部 CSS 細節） |
| `requirements.txt` / `packages.txt` | Python 套件與系統套件相依 |
| `employees_seed.csv` / `.gitignore` | 員工清單初始種子資料、忽略清單 |
| `reference/操作SOP.pptx` | 舊版 SOP 範本，15 頁，已完整讀取每頁文字方塊內容 |

## 2. SOP 各章節對應的程式來源

- **第 2 節 系統登入**：`app.py` 的 `render_login_form()` / `_do_login()` / `_CARD_CSS`。
- **第 3 節 系統首頁**：`app.py` 的 `render_menu()`、`ADMIN_EMPLOYEE_IDS` 常數。
- **第 4 節 私車公用報支**：`pages/1_私車公用報支.py` 全檔，含 `process_single_file_with_gemini()`（AI 辨識）、`render_block_progress_html()`（進度條）、Excel/Word 產出區塊（約第 1049～1188 行）。
- **第 5 節 出差申報**：`pages/2_出差申報.py` 全檔（Step 1～5）、`config.py`（出差地代號/雜費津貼日額）、`trip_calculations.py`（自動計算公式）、`receipt_recognizer.py`（辨識與例外處理）、`excel_writer.py`/`docx_generator.py`（產出邏輯）。
- **第 6 節 管理員維護區**：`pages/3_管理員維護區.py` 全檔。
- **第 7 節 FAQ／第 8 節 注意事項**：綜合以上檔案中實際的 `st.error` / `st.warning` / 例外類別訊息整理。

## 3. 舊 SOP 與目前程式的差異

已於 `docs/SOP.md` 第 10 節列出完整差異表，此處摘要最主要的 4 項：

1. **登入密碼**：舊 SOP 直接把當時的統一登入密碼明文寫在投影片上；目前程式的密碼已改為可由管理員在維護區更新，且**不是**固定值，舊 SOP 那組密碼已不適用，新版 SOP 一律不寫出實際密碼內容。
2. **系統網址**：舊 SOP 寫的 Streamlit Cloud 網址無法從目前 Repository 確認是否仍是正式部署網址，新版 SOP 標記待確認，不沿用。
3. **出差申報範本取得方式**：舊 SOP 提供一個內部網路芳鄰路徑，目前程式完全沒有對應的自動下載功能或路徑常數，新版 SOP 標記待確認，不沿用舊路徑。
4. **出差申報新增功能**：出差起訖日期／出差地欄位、雜費津貼與餐費自動計算、多筆雜費津貼合併勾選框、動態「缺什麼」錯誤訊息、機票票根裁切與日期比對提醒——這些都是舊 SOP（15 頁裡完全沒有提及）之後才新增的功能，已在新版 SOP 第 5 節完整補上。

## 4. 無法由程式碼確認的事項（已於 SOP 內標記 ⚠️ 待確認）

- 系統正式對外網址。
- 出差申報「當月報支範本」的實際取得方式／管道（會計信件、公告或其他方式）。
- 檔案上傳大小上限的實際可用值（元件顯示 200MB/檔，但實際受伺服器與網路環境影響）。
- Gemini API 免費額度的實際每日/每分鐘可用次數，以及公司目前簽署的 API 方案內容。
- 正式部署環境（作業系統、是否已安裝 LibreOffice 與所需系統套件）。

## 5. 建議人工確認的內容

- **`pages/1_私車公用報支.py` 第 461～465 行**：程式碼中有一組寫死在原始碼裡的 Gemini API 金鑰，做為 `st.secrets` 沒有設定時的預設備援值（`DEFAULT_API_KEY`）。這組金鑰**已內嵌在版本控管的原始碼中**，建議請管理者／資安相關人員確認是否需要撤銷重發、改成純粹由 `st.secrets` 提供且移除程式碼中的預設值，避免金鑰外流風險。本文件依規定不轉錄實際金鑰內容。
- **`pages/2_出差申報.py` Step 4**：住宿費科目的「地區／天數／人數」三個欄位，AI 辨識後**沒有**對應的 UI 可供使用者檢視或修改（只有交通費有額外的起點/訖點欄位），建議請開發端確認是否為刻意設計，或屬於待補功能。
- **`pages/1_私車公用報支.py` 的 `log_usage_to_google_form()`**：AI 辨識、產出 Excel、產出 Word 三個動作都會在背景把使用者姓名與部門靜默送到一個寫死在程式碼裡的 Google 表單網址做使用紀錄，使用者介面上完全沒有提示。建議確認這項背景紀錄行為是否已對同仁揭露、是否需要在系統內加上告知。
- **員工清單 `employees.csv` / `employees_seed.csv` / `department_staff.csv`**：這些 CSV 檔案含實際同仁姓名/員工編號，已隨 Repository 存在（非本次新增），本 SOP 與程式碼檢查僅使用其中的測試帳號 ETW00375（溫文福）作為畫面示範，未在文件中新增或列出其餘同仁名單。
- **`database.py` / `portal.db`**：`portal.db` 屬於 `.gitignore` 排除的本機資料庫檔案，實際部署環境的資料庫內容（例如目前有多少筆員工資料、是否已上傳過 SOP PDF）不在本次程式碼檢查範圍內，僅能確認資料表結構與存取邏輯。

## 6. 截圖清單

以下畫面已使用測試帳號 **ETW00375（溫文福）** 於本機環境（`streamlit run app.py --server.port 8502`）實際操作並截圖，全部存於 `docs/images/`：

| 檔名 | 內容 |
|---|---|
| `01-login.png` | 登入畫面 |
| `02-home.png` | 登入後首頁選單 |
| `03-car-top.png` | 私車公用報支頁面上半部（部門/姓名自動帶入） |
| `04-car-upload-section.png` | 私車公用報支上傳單據區塊 |
| `05-car-files-selected.png` | 已選好停車/加油單據檔案 |
| `06-car-ai-progress.png` | AI 辨識進度條畫面 |
| `08-car-supplement-fields.png` | AI 辨識完成後的補充填寫畫面（含真實辨識結果） |
| `09-car-excel-generated.png` | Excel 報銷檔案產出完成、下載按鈕出現 |
| `10-car-word-generated.png` | Excel 與 Word 皆已產出、兩個下載按鈕並列 |
| `11-trip-step1.png` | 出差申報 Step 1～Step 3 起始畫面 |
| `15b-trip-before-start.png` | Step 3 已選檔案、開始辨識按鈕已啟用 |
| `16-trip-recognition-progress.png` | Step 3 辨識進行中畫面 |
| `17-trip-step4-review.png` | Step 4 人工複核（含自動計算的雜費津貼與 AI 辨識的交通費） |
| `18-trip-step4-review-expanded.png` | Step 4 單筆收據展開後的複核欄位 |
| `19-trip-step5-generate.png` | Step 5 產生並下載（含動態列出的缺項原因） |

⚠️ 原本規劃的管理員維護區畫面（密碼驗證、員工資料表、SOP 上傳、密碼更新，共 4 張）已移除——SOP 改以一般同仁登入模式撰寫，不含管理員專用功能；其中一張員工資料表截圖background 裡有其他同仁未遮蔽的真實姓名/員工編號，一併確認已刪除，不會出現在交付物中。

沒有無法取得的畫面——所有規劃的操作步驟都已成功用測試帳號實際跑過一次並截圖，包含真實觸發 Gemini AI 辨識（以程式產生的示範收據圖片上傳測試，取得真實的辨識結果，而非手動編造畫面）。

⚠️ 唯一以合成測試資料代替真實單據的地方：AI 辨識所用的收據圖片（`scratch_receipts/*.png`，未納入 Repository 交付物）是用 Python 產生的簡易示範收據（僅含日期/金額等文字），不是真實的停車/加油/計程車單據照片；辨識結果的畫面呈現方式（欄位、按鈕、進度條、成功訊息等）皆為系統對這批測試檔案的真實反應，非手動偽造的假畫面。

## 7. Commit Hash

```
a6bd972a65e67f068d80062f353b606acb411e50
```

## 8. 產生日期

2026-08-29
