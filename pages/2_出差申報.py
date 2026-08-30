"""
版本：20260827-UX-FIXES-ROUND17
更新內容：app.py 本身沒有改動，這裡只是同步版本標籤——ROUND16（機票/計程車發票裁切
方向錯誤、裁切範圍切到單據內容、PDF 電子發票改滿版整頁）跟 ROUND17（補強裁切方向
測試、修正 Word 標題字型沒有變成標楷體）的實際修改都在 receipt_recognizer.py／
docx_generator.py。附帶一提：ROUND16 當時 commit 做了但沒有實際 push 到 GitHub，
這段期間的實測其實一直打在舊程式碼上，這次確認一起推送。

---（以下為 ROUND15 紀錄）---
1. 員工編號比對不分大小寫（見 employee_directory.py）。
2. 員工清單自動帶入比對成功後，4 個欄位（員工編號/姓名/單位/職務）反灰鎖定禁止手動
   編輯——避免使用者手動改掉跟清單不一致的資料；新增「清除重新輸入」按鈕可以重置這
   4 個欄位重新輸入。注意：不能在按鈕的 if st.button(...) 區塊裡直接改這幾個 widget
   綁定的 session_state（widget 已經在這一輪實例化過了，Streamlit 會直接拋
   StreamlitAPIException），改成設一個 `_reset_employee_fields` 旗標觸發 rerun，
   實際清空動作放到下一輪最前面（widget 實例化之前）執行——這是實測時 dev server
   噴例外才抓到的，錯誤訊息在畫面上完全看不出來，只有後台 log 看得到。
   Enter/Tab 也要跳過反灰鎖定的欄位，直接跳到下一個還能填的欄位（見
   ui_enhancements.py 的 focusableInputs()）。
3. 產生 Excel/Word 時包一層 st.spinner("檔案產生中，請耐心等候...")——避免處理期間
   畫面看起來像當機。

---（以下為 ROUND14 紀錄）---
Step 3 辨識改用多模型自動切換備援（見 config.GEMINI_MODEL_FALLBACK_CHAIN、
   receipt_recognizer._generate_content_with_retry）——免費方案每日額度偏低又是
   多人共用，額度用完/伺服器過載時自動換下一個模型，不用整批中止等隔天重置。
   app.py 這邊不需要改，呼叫端用的還是同一個 recognize_receipt/
   detect_and_crop_document，只是內部預設參數換成模型清單。

---（以下為 ROUND13 紀錄）---
1. 修正「出差事由」跟「申請日期」輸入框還是對不齊的問題——ROUND10 的修法把標籤
   分別放在 col1/col2 各自巢狀的 st.columns() 裡，這兩個巢狀呼叫的列高是各自獨立
   計算的，Streamlit 不會跨呼叫同步，所以右邊多了勾選框那一行還是比左邊高。改成
   標籤/勾選框、輸入框都各自用同一個 st.columns() 涵蓋左右兩側，列高才會真正被
   強制同步。
2. Step 3 批次辨識遇到 Gemini 伺服器過載（503 UNAVAILABLE）時，改用
   receipt_recognizer.ServiceUnavailableError 顯示白話訊息（不中止整批，因為這種
   過載是暫時性的，不像額度用完幾乎確定後面都會失敗）；機票裁切迴圈原本沒有特別
   處理額度用完（QuotaExceededError），會一直浪費時間重試到底，一併補上。
3. Step 5「產生 Excel/Word」按鈕反白時，原本不管缺哪一項都顯示同一句固定的需求
   說明（範本已上傳、員工資訊已填寫、所有收據已複核確認），使用者沒辦法知道自己
   到底漏了哪一項。改成 _missing_generation_reasons() 動態列出「目前實際缺什麼」
   （例如具體缺哪個員工資訊欄位、還有幾筆收據沒勾選確認）。

---（以下為 ROUND11 紀錄）---
Step 1 新增員工清單自動帶入（見 employee_directory.py）——輸入員工編號或
姓名，清單（employees.csv）裡找得到就自動帶出單位/職務（跟另一個識別欄位）。清單檔案
讀不到時完全靜默略過，不影響 Step 1 正常填寫。

---（以下為 ROUND10 紀錄）---
申請日期新增「變更或調整申請日期」勾選框——預設鎖定、顯示今天（上傳辨識當天）
的日期，避免使用者不小心改動；需要用不同日期申請時才勾選解鎖。

---（以下為 ROUND8 紀錄）---
修正「自動產生雜費津貼/餐費」的觸發時機 bug——先前的觸發條件只看出差
起訖日期/出差地有沒有變，沒有把「範本是否已上傳」算進去。如果使用者先填 Step 1
日期、之後才上傳 Step 2 範本，填日期當下範本的地區費率表根本還讀不到，餐費算不出來；
之後範本上傳了，因為觸發條件沒有再變一次，餐費就永遠沒有機會補算（雜費津貼不需要看
範本內容，不受影響，才會出現「雜費津貼有、餐費沒有」的現象）。修法：把範本檔名也算進
觸發條件，範本一到位就會自動重新計算。

補記：這支檔案先前幾次修改（Step 1 出差地下拉選單改成「代碼(中文)」顯示、機票日期
比對提醒、雜費津貼合併勾選框等）版本標籤忘記跟著更新，導致畫面上的版本號一度是舊的，
沒辦法用來確認部署是否為最新——以後每次改這支檔案都要記得同步更新這裡的版本號。

---（以下為 ROUND3 紀錄）---
新增「餐費核銷明細」自動計算失敗時的畫面提示——之前地區費率表讀不到，或
出差地對應的地區別在範本裡找不到時，是完全靜默跳過（沒有任何錯誤訊息），使用者只會
看到「怎麼沒有自動填」但不知道原因。現在會在 Step 4 顯示具體原因（讀不到對照表 / 地區
別對不上，並列出範本實際讀到哪些地區別）。

---（以下為 ROUND2 紀錄）---
1. 網頁標題改置中顯示。
2. 機票票根裁切時一併抽取搭乘日期，跟 Step 1 出差起訖日期不一致時在 Step 4 顯示提醒。
3. 雜費津貼偵測到多筆時，新增實際可操作的「合併為一筆」勾選框（之前只有文字提醒，
   沒有對應欄位可以動作）——只影響 Excel 資料列，Word 明細清單仍列出每張原始收據
   （合併只是把最終要寫進 Excel 的那一列合併，不影響單據附件的完整記錄）。

---（以下為先前版本紀錄）---
1. Step 1 新增「出差起訖日期」（月曆範圍選取）與「出差地」代號下拉選單（含 Other + 地區子選單）。
2. Step 2 讀取範本後，額外讀取「餐費核銷明細」分頁的地區費率對照表，供自動計算用。
3. 出差起訖日期＋出差地填好後，自動在複核清單加入「雜費津貼」（整趟合計）與「餐費」
   （範圍內每個星期日各一筆）兩種資料列，不需要上傳收據、不經過 Gemini 辨識；餐費同時會
   寫入「餐費核銷明細」分頁對應列。
4. Step 5 產生 Excel 時，一併回填「支出憑單」分頁（需要範本已重算出退補金額）。

出差報支自動填表工具 —— Streamlit 網頁版入口。

流程：員工資訊表單（含出差起訖日期/出差地） → 上傳當月範本 → 依科目分類上傳收據並批次辨識
（同時自動產生雜費津貼/餐費）→ 人工複核 → 各自產生並下載 Excel/Word。
伺服器端不落地保存使用者上傳的收據與產出結果，全部用記憶體 bytes 處理。
"""
import os
from datetime import date, timedelta

import streamlit as st
from dotenv import load_dotenv

import business_rules
import config
import docx_generator
import employee_directory
import excel_reader
import excel_writer
import receipt_recognizer
import trip_calculations
from config import CATEGORIES
from excel_writer import ExcelWriteError
from identity_watermark import get_git_version, inject_custom_footer, inject_version_tag
from models import ExpenseRow, ReceiptItem, TripHeader
from portal_theme import inject_glass_theme
from ui_enhancements import inject_form_navigation_helpers, inject_theme_css
from usage_log import log_page_open, log_usage

import database

if not st.session_state.get("logged_in"):
    st.warning("請先登入")
    st.page_link("app.py", label="回登入頁")
    st.stop()

log_page_open("出差申報")

load_dotenv()

APP_VERSION = get_git_version()

RECEIPT_FILE_TYPES = ["jpg", "jpeg", "png", "pdf", "heic", "heif", "webp"]
AUTO_MISC_FILENAME = "（系統自動計算）雜費津貼"

st.set_page_config(page_title="出差報支自動填表工具", layout="wide", initial_sidebar_state="collapsed")

# 版本標籤／卡片美化／Tab 鍵導覽輔助這三個呼叫，刻意搬到導覽列 sticky 容器「之後」才
# 執行——它們都只是注入 CSS/JS，實際效果不受執行順序影響，但 Streamlit 會把每個呼叫
# 當成一個獨立元件，元件之間即使沒有畫面內容也會插入預設間距（gap）。搬到後面執行，
# 才不會在導覽列前面疊出好幾個看不見卻佔間距的元件，導致導覽列初始位置比私車公用報支
# 低一截（實測差了快 49px）。
with st.container(key="portal_sticky_header"):
    with st.container(key="portal_nav_bar"):
        _nav_col1, _nav_col2 = st.columns(2)
        with _nav_col1:
            st.page_link("app.py", label="← 返回主頁", width=160)
        with _nav_col2:
            if st.button("登出", key="trip_expense_logout", width=160):
                for _key in (
                    "logged_in",
                    "employee_id",
                    "employee_name",
                    "employee_department",
                    "employee_title",
                    "is_admin_verified",
                ):
                    st.session_state.pop(_key, None)
                st.switch_page("app.py")

    if "receipts" not in st.session_state:
        st.session_state.receipts: list[ReceiptItem] = []
    if "template_bytes" not in st.session_state:
        st.session_state.template_bytes = None
    if "template_filename" not in st.session_state:
        st.session_state.template_filename = None
    if "flight_ticket_filenames" not in st.session_state:
        st.session_state.flight_ticket_filenames: list[str] = []
    if "flight_ticket_files" not in st.session_state:
        st.session_state.flight_ticket_files: list[tuple[str, bytes]] = []
    if "excel_bytes" not in st.session_state:
        st.session_state.excel_bytes = None
    if "docx_bytes" not in st.session_state:
        st.session_state.docx_bytes = None
    if "meal_region_rates" not in st.session_state:
        st.session_state.meal_region_rates = None
    if "meal_detail_entries" not in st.session_state:
        st.session_state.meal_detail_entries = []
    if "auto_row_signature" not in st.session_state:
        st.session_state.auto_row_signature = None

    with st.container(key="page_title_bar"):
        st.markdown(
            '<h1 style="text-align:center;">出差報支自動填表工具</h1>',
            unsafe_allow_html=True,
        )

inject_version_tag(APP_VERSION)
inject_theme_css()
inject_form_navigation_helpers()

_conn = database.get_connection()
try:
    _sop = database.get_sop_document(_conn, "trip_expense")
finally:
    _conn.close()
if _sop:
    st.download_button("📄 查看操作SOP", data=_sop["content"], file_name=_sop["filename"])

try:
    _secrets_api_key = st.secrets.get("GEMINI_API_KEY", "")
except Exception:
    # 本機獨立測試進入點沒有設定 .streamlit/secrets.toml 時，st.secrets 會直接拋例外
    # （不是回傳空字串），要接住，不然這支頁面在沒設定 secrets 的環境會直接掛掉。
    _secrets_api_key = ""
# 優先讀 st.secrets（跟私車公用報支一致，Streamlit Cloud 網頁上設定的 Secrets 主要
# 會進到這裡），環境變數當備援（例如用 .env + python-dotenv 的本機開發方式）。
api_key = _secrets_api_key or os.environ.get("GEMINI_API_KEY", "")
if not api_key:
    st.error("伺服器尚未設定 GEMINI_API_KEY，收據辨識功能無法使用，請聯絡工具管理員。")

# 假身分測試進入點（見 project_spec.md 第七節）：獨立跑這支 app 開發測試時，
# 不用每次都跑完整的入口網站登入流程，用假的員工資料快速模擬「已從入口網站登入」的
# session_state。這支 app 併入 portal-app 之後，session_state 已經有 logged_in，
# 這個區塊就不會再顯示。
if not st.session_state.get("logged_in"):
    with st.sidebar.expander("🧪 開發測試：假身分登入", expanded=False):
        st.caption("僅供獨立測試使用，正式併入入口網站後這裡會自動隱藏。")
        if st.button("使用測試身分（ETW00375 溫文福）"):
            st.session_state["logged_in"] = True
            st.session_state["employee_id"] = "ETW00375"
            st.session_state["employee_name"] = "溫文福"
            st.session_state["employee_department"] = "伺服器事業部"
            st.session_state["employee_title"] = "主任工程師"
            st.rerun()

# ---------- Step 1：員工資訊 ----------
st.header("Step 1　員工資訊")

# 身分資料優先使用入口網站（portal-app）登入後帶入的 session_state
# （logged_in/employee_id/employee_name/employee_department/employee_title）。
# 這支 app 併入入口網站的 pages/ 之後，同仁不用再自己輸入員工編號/姓名去比對
# 清單，登入身分直接帶入、4 個欄位鎖定確認即可。沒有登入資料時（獨立測試進入點，
# 直接 streamlit run 這支 app），維持原本 employees.csv 清單比對/手動輸入的
# fallback 邏輯，不拿掉。
_portal_login = bool(st.session_state.get("logged_in") and st.session_state.get("employee_name"))

if _portal_login:
    for _field_key, _field_value in [
        ("employee_id_input", st.session_state.get("employee_id") or ""),
        ("employee_name_input", st.session_state.get("employee_name") or ""),
        ("department_input", st.session_state.get("employee_department") or ""),
        ("title_input", st.session_state.get("employee_title") or ""),
    ]:
        st.session_state[_field_key] = _field_value

    _employee_fields_locked = True
else:
    # 員工清單自動帶入：輸入員工編號或姓名，清單裡找得到就自動帶出其餘欄位。清單檔案讀不到
    # （還沒建立、格式錯誤等）完全靜默略過，不影響 Step 1 正常填寫——這是輔助功能，不是必要
    # 條件。要在對應欄位的 st.text_input 呼叫「之前」把 session_state 值準備好，widget
    # 才會讀到帶入的值（widget 建立之後就不能再改它的 session_state，這也是下面「清除重新
    # 輸入」按鈕不能直接在按下當下賦值、要用旗標延後到下一輪最前面才清空的原因）。
    if st.session_state.pop("_reset_employee_fields", False):
        for _field_key in ("employee_id_input", "employee_name_input", "department_input", "title_input"):
            st.session_state[_field_key] = ""

    _employee_directory = employee_directory.load_employee_directory()
    _matched_employee = employee_directory.find_match(
        _employee_directory,
        st.session_state.get("employee_id_input", ""),
        st.session_state.get("employee_name_input", ""),
    )
    if _matched_employee:
        for _field_key, _field_value in [
            ("employee_id_input", _matched_employee["employee_id"]),
            ("employee_name_input", _matched_employee["employee_name"]),
            ("department_input", _matched_employee["department"]),
            ("title_input", _matched_employee["title"]),
        ]:
            if _field_value and st.session_state.get(_field_key) != _field_value:
                st.session_state[_field_key] = _field_value

    # 自動帶出的資料是清單裡的權威資料，比對成功後 4 個欄位（含員工編號本身）都反灰鎖定，
    # 不能再手動改——如果只鎖姓名/單位/職務、留員工編號可編輯，使用者把員工編號改掉/清空
    # 之後，姓名欄位還鎖著、值還是原本比對成功的姓名，find_match() 下一輪還是會用這個沒被
    # 清掉的姓名再比對到同一人，鎖定狀態解不開；乾脆 4 個欄位一起鎖，要換人時用下面的
    # 「清除重新輸入」按鈕一次重置，不會卡住。
    _employee_fields_locked = bool(_matched_employee)

col1, col2 = st.columns(2)
with col1:
    employee_id = st.text_input(
        "員工編號", icon=":material/badge:", key="employee_id_input", disabled=_employee_fields_locked,
    )
    department = st.text_input(
        "單位", icon=":material/apartment:", key="department_input", disabled=_employee_fields_locked,
    )
with col2:
    employee_name = st.text_input(
        "姓名", icon=":material/person:", key="employee_name_input", disabled=_employee_fields_locked,
    )
    title = st.text_input(
        "職務", icon=":material/work:", key="title_input", disabled=_employee_fields_locked,
    )
if _employee_fields_locked:
    if _portal_login:
        st.caption("已依入口網站登入身分自動帶入，欄位鎖定無法編輯。")
    else:
        lock_caption_col, lock_button_col = st.columns([3, 1])
        with lock_caption_col:
            st.caption("已依員工清單自動帶入，欄位鎖定無法編輯。")
        with lock_button_col:
            if st.button("清除重新輸入", icon=":material/refresh:"):
                # 這裡不能直接改 employee_id_input 等 widget 綁定的 session_state（widget
                # 已經在這一輪跑過 st.text_input() 了，Streamlit 會直接拋例外），改成設一個
                # 旗標、觸發 rerun，實際清空的動作放到下一輪最前面（widget 實例化之前）執行。
                st.session_state["_reset_employee_fields"] = True
                st.rerun()

# 「出差事由」和「申請日期」的標籤/勾選框，必須放在同一個 st.columns() 呼叫裡，
# 兩欄的列高才會被 Streamlit 強制同步；分開放在 col1/col2 各自巢狀的 st.columns()
# 裡面，兩邊列高是各自獨立計算的，看起來對齊實際上不會對齊（先前版本的錯誤修法）。
trip_reason_label_col, _spacer_col, apply_date_label_col, apply_date_checkbox_col = st.columns(
    [1, 1.6, 1, 1.6]
)
with trip_reason_label_col:
    st.markdown("出差事由")
with apply_date_label_col:
    st.markdown("申請日期")
with apply_date_checkbox_col:
    unlock_apply_date = st.checkbox(
        "變更或調整申請日期", key="unlock_apply_date",
        help="預設是今天（上傳收據辨識當天），需要改成別的日期時才勾選這裡。",
    )

trip_reason_input_col, apply_date_input_col = st.columns(2)
with trip_reason_input_col:
    trip_reason = st.text_input(
        "出差事由", icon=":material/description:", label_visibility="collapsed",
    )
with apply_date_input_col:
    apply_date = st.date_input(
        "申請日期", value=date.today(), disabled=not unlock_apply_date, label_visibility="collapsed",
    )

col3, col4 = st.columns(2)
with col3:
    trip_date_range = st.date_input(
        "出差起訖日期", value=(date.today(), date.today() + timedelta(days=1)),
    )
    trip_start = trip_date_range[0] if len(trip_date_range) >= 1 else None
    trip_end = trip_date_range[1] if len(trip_date_range) >= 2 else None
with col4:
    destination_code = st.selectbox(
        "出差地", options=config.DESTINATION_CODES,
        format_func=lambda code: (
            f"{code}({config.DESTINATIONS[code].plain_name})" if code in config.DESTINATIONS else "Other(自訂地名)"
        ),
    )

destination_custom_name = None
destination_region = None
if destination_code == "Other":
    col5, col6 = st.columns(2)
    with col5:
        destination_custom_name = st.text_input("自訂地名", icon=":material/edit_location:")
    with col6:
        destination_region = st.selectbox("地區（決定雜費津貼/餐費日額）", options=config.OTHER_DESTINATION_REGIONS)

header = TripHeader(
    employee_id=employee_id,
    employee_name=employee_name,
    department=department,
    title=title,
    trip_reason=trip_reason,
    apply_date=apply_date,
    trip_start=trip_start,
    trip_end=trip_end,
    destination_code=destination_code,
    destination_custom_name=destination_custom_name,
    destination_region=destination_region,
)

# ---------- Step 2：上傳當月範本 ----------
st.header("Step 2　上傳當月報支範本（.xls）")
template_file = st.file_uploader("上傳會計提供的當月空白範本", type=["xls"])

if template_file is not None:
    template_bytes = template_file.getvalue()
    st.session_state.template_bytes = template_bytes
    st.session_state.template_filename = template_file.name

    try:
        wb = excel_reader.open_workbook(template_bytes)
        sheet = excel_reader.get_main_sheet(wb)
        billing_month = excel_reader.read_billing_month(sheet)
        layout_result = excel_reader.detect_layout(sheet)
        st.session_state.meal_region_rates = excel_reader.read_meal_region_rates(wb)

        if billing_month:
            st.success(f"偵測到範本的請款月份：{billing_month.strftime('%Y/%m')}，請確認是否正確。")
        else:
            st.warning("讀不到請款月份（U3），請確認這是會計發送的正確範本。")

        if layout_result.missing_labels:
            st.error(f"範本版本可能與預期不符，找不到以下欄位標籤：{layout_result.missing_labels}，請確認範本版本後再繼續。")
        elif layout_result.warnings:
            for w in layout_result.warnings:
                st.warning(f"「{w.label}」欄位偵測到的位置（{w.detected_column}）與預期（{w.expected_column}）不同，已自動改用偵測結果。")
        else:
            st.info("範本欄位版面與預期一致。")
    except Exception as exc:
        st.error(f"讀取範本失敗：{exc}")

# ---------- Step 3：依科目分類上傳收據 ----------
st.header("Step 3　依科目分類上傳收據")
st.caption("請依科目分類上傳，避免混在一起造成分類錯誤。全部上傳完後，按下方「開始辨識」按鈕一次觸發辨識。")

_UPLOAD_SIZE_HINT = "建議每張單據檔案控制在 10MB 以內，上傳與 AI 辨識速度較順暢（系統技術上限為 200MB，非強制）。"

uploads_by_category: dict[str, list] = {}
for category in CATEGORIES:
    st.subheader(category)
    uploads_by_category[category] = st.file_uploader(
        f"上傳{category}收據", type=RECEIPT_FILE_TYPES,
        accept_multiple_files=True, key=f"upload_{category}",
        help=_UPLOAD_SIZE_HINT,
    )
    st.divider()

st.subheader("來回機票票根（僅列入 Word 明細清單附件，不寫入 Excel）")
flight_ticket_uploads = st.file_uploader(
    "上傳來回機票票根", type=RECEIPT_FILE_TYPES,
    accept_multiple_files=True, key="upload_flight_ticket",
    help=_UPLOAD_SIZE_HINT,
)
if "flight_ticket_crop_cache" not in st.session_state:
    st.session_state.flight_ticket_crop_cache: dict[str, bytes] = {}
if "flight_ticket_date_cache" not in st.session_state:
    st.session_state.flight_ticket_date_cache: dict[str, "date | None"] = {}
st.session_state.flight_ticket_files = [
    (f.name, st.session_state.flight_ticket_crop_cache.get(f.name, f.getvalue()))
    for f in (flight_ticket_uploads or [])
]
st.session_state.flight_ticket_filenames = [name for name, _ in st.session_state.flight_ticket_files]
st.divider()

already_processed = {(r.category, r.source_filename) for r in st.session_state.receipts}
pending_uploads = [
    (category, uf)
    for category, files in uploads_by_category.items()
    for uf in (files or [])
    if (category, uf.name) not in already_processed
]
pending_flight_tickets = [
    f for f in (flight_ticket_uploads or [])
    if f.name not in st.session_state.flight_ticket_crop_cache
]
total_pending = len(pending_uploads) + len(pending_flight_tickets)

if total_pending:
    st.info(f"已選擇 {total_pending} 個尚未辨識的檔案。")

start_recognition = st.button(
    f"開始辨識（{total_pending} 個檔案）",
    icon=":material/auto_awesome:",
    disabled=not total_pending or not api_key,
)

if start_recognition and total_pending:
    progress_bar = st.progress(0)
    status_placeholder = st.empty()
    total = total_pending
    step = 0
    quota_hit = False
    for category, uf in pending_uploads:
        if quota_hit:
            break
        step += 1
        status_placeholder.text(f"正在處理 ({step}/{total})：{uf.name} ...")
        try:
            item = receipt_recognizer.recognize_receipt(
                file_bytes=uf.getvalue(), filename=uf.name,
                category=category, api_key=api_key,
            )
            st.session_state.receipts.append(item)
        except receipt_recognizer.QuotaExceededError as exc:
            st.error(str(exc))
            quota_hit = True
        except receipt_recognizer.ServiceUnavailableError as exc:
            st.error(f"{uf.name}：{exc}")
        except Exception as exc:
            st.error(f"{uf.name} 辨識失敗：{exc}")
        progress_bar.progress(step / total)

    for uf in pending_flight_tickets:
        if quota_hit:
            break
        step += 1
        status_placeholder.text(f"正在處理 ({step}/{total})：{uf.name} ...")
        try:
            cropped, flight_date = receipt_recognizer.detect_and_crop_document(
                file_bytes=uf.getvalue(), filename=uf.name, api_key=api_key,
            )
            st.session_state.flight_ticket_crop_cache[uf.name] = cropped
            st.session_state.flight_ticket_date_cache[uf.name] = flight_date
        except receipt_recognizer.QuotaExceededError as exc:
            st.error(str(exc))
            quota_hit = True
        except receipt_recognizer.ServiceUnavailableError as exc:
            st.error(f"{uf.name}：{exc}")
        except Exception as exc:
            st.error(f"{uf.name} 裁切失敗：{exc}")
        progress_bar.progress(step / total)

    if quota_hit:
        status_placeholder.text(f"因額度用完中止，已處理 {step}/{total} 個檔案。")

    status_placeholder.text(f"辨識完成，共處理 {total} 個檔案。")

# ---------- 自動產生雜費津貼／餐費 ----------
# 觸發條件要包含「範本是否已上傳」（用 template_filename 當代表）：如果使用者先填了
# Step 1 的出差日期、之後才上傳 Step 2 的範本，範本讀到的地區費率表在填日期當下根本
# 還不存在，餐費那時候算不出來；如果觸發條件只看日期/出差地，之後範本才上傳，因為
# 這個 signature 沒有再變一次，這段邏輯就不會重新跑，餐費就永遠沒有機會補算——
# 雜費津貼不需要看範本內容，不受這個問題影響，才會出現「雜費津貼有、餐費沒有」的現象。
auto_signature = (
    trip_start, trip_end, destination_code, destination_custom_name, destination_region,
    st.session_state.template_filename,
)
if auto_signature != st.session_state.auto_row_signature:
    st.session_state.auto_row_signature = auto_signature
    st.session_state.receipts = [
        r for r in st.session_state.receipts
        if r.source_filename != AUTO_MISC_FILENAME and not r.source_filename.startswith("（系統自動計算）餐費")
    ]
    st.session_state.meal_detail_entries = []

    misc_row = trip_calculations.generate_misc_allowance_row(header)
    if misc_row:
        st.session_state.receipts.append(ReceiptItem(
            source_filename=AUTO_MISC_FILENAME, category="雜費津貼",
            date=trip_start, date_range_end=trip_end,
            amount=misc_row.amount, currency=misc_row.currency, description=misc_row.description,
            is_handwritten=False, confidence=1.0, confidence_reason="依出差起訖日期與出差地自動計算",
            needs_review=False, user_confirmed=False,
        ))

    trip_has_sunday = bool(trip_start and trip_end and any(
        (trip_start + timedelta(days=d)).weekday() == 6
        for d in range((trip_end - trip_start).days + 1)
    ))
    if st.session_state.template_bytes is not None and not st.session_state.meal_region_rates:
        st.warning(
            "範本的「餐費核銷明細」分頁讀不到地區別/幣別對照表，雜費津貼、星期日餐費都無法"
            "自動計算，請確認範本版本是否正確（或聯絡工具管理員）。"
        )
    elif st.session_state.meal_region_rates:
        meal_rows, meal_entries = trip_calculations.generate_meal_items(header, st.session_state.meal_region_rates)
        if trip_has_sunday and not meal_entries:
            resolved_region = trip_calculations.destination_meal_region(header)
            st.warning(
                f"出差期間內有星期日，但沒有自動產生餐費——出差地對應的地區別"
                f"「{resolved_region}」在範本「餐費核銷明細」分頁的對照表裡找不到"
                f"（目前讀到的地區別：{list(st.session_state.meal_region_rates.keys())}），"
                "請確認範本版本或出差地設定是否正確。"
            )
        st.session_state.meal_detail_entries = meal_entries
        for meal_row, meal_entry in zip(meal_rows, meal_entries):
            st.session_state.receipts.append(ReceiptItem(
                source_filename=f"（系統自動計算）餐費 {meal_row.date_display}", category="餐費",
                date=meal_entry.date,
                amount=meal_row.amount, currency=meal_row.currency, description=meal_row.description,
                is_handwritten=False, confidence=1.0,
                confidence_reason="依出差起訖日期內的星期日與出差地自動計算（範本餐費核銷明細地區費率）",
                needs_review=False, user_confirmed=False,
            ))

# ---------- Step 4：人工複核 ----------
st.header("Step 4　人工複核")

if trip_start and trip_end:
    for fname, flight_date in st.session_state.flight_ticket_date_cache.items():
        if fname not in st.session_state.flight_ticket_filenames or flight_date is None:
            continue
        if flight_date != trip_start and flight_date != trip_end:
            st.warning(
                f"[{fname}] 票根辨識到的搭乘日期（{flight_date}）跟 Step 1 填的出差起訖日期"
                f"（{trip_start}~{trip_end}）兜不起來，請確認機票或出差日期是否正確。"
            )

if not st.session_state.receipts:
    st.info("目前還沒有辨識結果，請先在 Step 3 上傳收據並按「開始辨識」，或在 Step 1 填寫出差起訖日期與出差地。")
else:
    hints = business_rules.collect_all_hints(st.session_state.receipts)
    for hint in hints:
        st.warning(f"[{hint.receipt.source_filename}] {hint.message}")

    misc_allowance_count = sum(1 for r in st.session_state.receipts if r.category == "雜費津貼")
    if misc_allowance_count > 1:
        st.checkbox(
            f"將 {misc_allowance_count} 筆雜費津貼合併為一筆寫入 Excel（日期填成區間、金額加總；"
            "Word 明細清單仍會列出每張原始收據）",
            value=st.session_state.get("merge_misc_allowance", False),
            key="merge_misc_allowance",
        )

    for item in st.session_state.receipts:
        is_auto = item.source_filename.startswith("（系統自動計算）")
        badge = "🧮 自動計算" if is_auto else ("⚠️ 需複核" if item.needs_review else "✅")
        with st.expander(f"{badge} {item.source_filename}｜{item.category}｜{item.description or '(無說明)'}", expanded=item.needs_review and not is_auto):
            c1, c2, c3 = st.columns(3)
            with c1:
                date_str = st.text_input("日期 (YYYY-MM-DD)", value=item.date.isoformat() if item.date else "", key=f"date_{item.id}")
            with c2:
                item.currency = st.text_input("幣別", value=item.currency or "", key=f"currency_{item.id}")
            with c3:
                amount_str = st.text_input("金額", value=str(item.amount) if item.amount is not None else "", key=f"amount_{item.id}")
            item.description = st.text_input("說明", value=item.description, key=f"desc_{item.id}")

            if item.category == "交通費":
                c4, c5 = st.columns(2)
                with c4:
                    item.location_from = st.text_input("起點", value=item.location_from or "", key=f"from_{item.id}")
                with c5:
                    item.location_to = st.text_input("訖點", value=item.location_to or "", key=f"to_{item.id}")

            if item.confidence_reason:
                st.caption(f"{'計算依據' if is_auto else '模型信心'}：{item.confidence_reason if is_auto else f'{item.confidence:.2f}'}　{'（手寫）' if item.is_handwritten else ''}")

            from datetime import date as date_type
            from decimal import Decimal, InvalidOperation
            try:
                item.date = date_type.fromisoformat(date_str) if date_str else None
            except ValueError:
                st.error("日期格式錯誤，請用 YYYY-MM-DD")
            try:
                item.amount = Decimal(amount_str) if amount_str else None
            except InvalidOperation:
                st.error("金額格式錯誤")

            item.user_confirmed = st.checkbox("已確認此筆資料正確", value=item.user_confirmed, key=f"confirm_{item.id}")

# ---------- Step 5：產生並下載（Excel／Word 各自獨立） ----------
st.header("Step 5　產生並下載")

header_filled = all([employee_id, employee_name, department, title, trip_reason])
all_confirmed = bool(st.session_state.receipts) and all(r.user_confirmed for r in st.session_state.receipts)


def _missing_generation_reasons(require_template: bool) -> list[str]:
    """回傳「目前實際缺什麼」的具體原因清單，取代原本不管缺哪一項都顯示同一句
    固定需求說明的做法——使用者光看「需要：範本已上傳、員工資訊已填寫、所有收據已
    複核確認」沒辦法知道自己到底還漏了哪一項。"""
    reasons = []
    missing_header_fields = [
        label for label, value in [
            ("員工編號", employee_id), ("姓名", employee_name),
            ("單位", department), ("職務", title), ("出差事由", trip_reason),
        ] if not value
    ]
    if missing_header_fields:
        reasons.append(f"Step 1 員工資訊尚未填完（缺：{'、'.join(missing_header_fields)}）")
    if require_template and st.session_state.template_bytes is None:
        reasons.append("Step 2 尚未上傳範本")
    if not st.session_state.receipts:
        reasons.append("Step 3/4 尚未新增任何收據")
    else:
        unconfirmed_count = sum(1 for r in st.session_state.receipts if not r.user_confirmed)
        if unconfirmed_count:
            reasons.append(f"Step 4 還有 {unconfirmed_count} 筆收據尚未勾選「已確認此筆資料正確」")
    return reasons


def _expense_row_date_display(item: ReceiptItem) -> str:
    if item.date_range_end and item.date:
        return f"{item.date.isoformat()}~{item.date_range_end.isoformat()}"
    return item.date.isoformat() if item.date else ""


def _merged_for_excel(receipts: list[ReceiptItem]) -> list[ReceiptItem]:
    """勾選「合併雜費津貼」時，把多筆雜費津貼收據合併成一筆給 Excel 寫入用；
    只影響 Excel 這一份輸出，Word 明細清單一律用原始未合併的清單（見呼叫端），
    才能保留每張收據的附件記錄。"""
    if not st.session_state.get("merge_misc_allowance"):
        return receipts
    misc_items = [r for r in receipts if r.category == "雜費津貼"]
    if len(misc_items) <= 1:
        return receipts
    from decimal import Decimal
    other_items = [r for r in receipts if r.category != "雜費津貼"]
    dates = [r.date for r in misc_items if r.date]
    total = sum((r.amount or Decimal("0")) for r in misc_items)
    merged = ReceiptItem(
        source_filename="（已合併）雜費津貼", category="雜費津貼",
        date=min(dates) if dates else None,
        date_range_end=max(dates) if dates else None,
        amount=total, currency=misc_items[0].currency or "",
        description="、".join(r.description for r in misc_items if r.description) or "雜費津貼合計",
        is_handwritten=False, confidence=1.0,
        confidence_reason=f"由 {len(misc_items)} 筆雜費津貼合併",
        needs_review=False, user_confirmed=True,
    )
    return other_items + [merged]


rows = [
    ExpenseRow(
        category=item.category,
        date_display=_expense_row_date_display(item),
        currency=item.currency or "",
        amount=item.amount,
        description=item.description,
        loc_from=item.location_from or "",
        loc_to=item.location_to or "",
        lodging_region=item.lodging_region,
        lodging_days=item.lodging_days,
        lodging_people=item.lodging_people,
    )
    for item in _merged_for_excel(st.session_state.receipts)
]

col_excel, col_word = st.columns(2)

with col_excel:
    st.subheader(":material/table: Excel 出差報支表")
    excel_ready = header_filled and all_confirmed and st.session_state.template_bytes is not None
    if not excel_ready:
        st.caption("尚未能產生 Excel，原因：" + "；".join(_missing_generation_reasons(require_template=True)))
    if st.button("產生 Excel", icon=":material/description:", disabled=not excel_ready):
        try:
            with st.spinner("檔案產生中，請耐心等候..."):
                st.session_state.excel_bytes = excel_writer.write_expense_rows(
                    st.session_state.template_bytes, header, rows,
                    meal_detail_entries=st.session_state.meal_detail_entries,
                    fill_payment_voucher=True,
                    destination_plain_name=trip_calculations.destination_plain_name(header),
                )
            st.success("Excel 產生完成！打開時會自動重新計算金額，不需要手動按任何按鍵。")
            log_usage("出差申報", "產表")
        except ExcelWriteError as exc:
            st.session_state.excel_bytes = None
            st.error(str(exc))
    if st.session_state.excel_bytes:
        st.download_button(
            "下載出差報支 Excel", data=st.session_state.excel_bytes,
            file_name=f"出差報支_{employee_name}_{apply_date}.xls",
            mime="application/vnd.ms-excel", icon=":material/download:",
        )

with col_word:
    st.subheader(":material/description: Word 單據明細清單")
    word_ready = header_filled and all_confirmed
    if not word_ready:
        st.caption("尚未能產生 Word，原因：" + "；".join(_missing_generation_reasons(require_template=False)))
    if st.button("產生 Word", icon=":material/description:", disabled=not word_ready):
        with st.spinner("檔案產生中，請耐心等候..."):
            st.session_state.docx_bytes = docx_generator.generate_receipt_list_docx(
                header, st.session_state.receipts, st.session_state.flight_ticket_files
            )
        st.success("Word 明細清單產生完成！")
        log_usage("出差申報", "產表")
    if st.session_state.docx_bytes:
        st.download_button(
            "下載單據明細清單 Word", data=st.session_state.docx_bytes,
            file_name=f"單據明細清單_{employee_name}_{apply_date}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            icon=":material/download:",
        )

inject_glass_theme()
inject_custom_footer()
