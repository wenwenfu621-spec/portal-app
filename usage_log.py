"""
使用統計記錄——把「開啟頁面」「產表」兩種事件靜默送到 Google 表單，表單的
回覆會自動進到連動的 Google 試算表，供管理員維護區的使用統計讀取。

沿用私車公用報支原本就有的做法（舊的 log_usage_to_google_form()）：直接用
requests.post() 送到表單的 formResponse 網址，不需要 Google API 金鑰；送出
失敗（網路問題等）一律靜默吞掉，不影響任何主要功能。
"""
import pandas as pd
import requests
import streamlit as st

_FORM_RESPONSE_URL = "https://docs.google.com/forms/d/e/1FAIpQLSeWI7dFxqjMeX9H0KxbSYVETuBiTOLEqZs43T06yKdbQofNAQ/formResponse"
_ENTRY_NAME = "entry.505350995"
_ENTRY_DEPT = "entry.1840094204"
_ENTRY_EMPLOYEE_ID = "entry.1533038394"
_ENTRY_EVENT_TYPE = "entry.1182613762"
_ENTRY_SYSTEM = "entry.1801175218"

# 讀取（管理員維護區的使用統計）用的是另一條路——寫入是直接 POST 到表單、不需要
# 金鑰；但表單本身沒有「讀回已收到哪些回覆」的功能，資料實際存放的地方是表單連動
# 的這份 Google 試算表，讀取需要透過 Google 服務帳號金鑰（見 .streamlit/secrets.toml
# 的 [gcp_service_account] 區塊）。
_SPREADSHEET_ID = "1oWD-2HSarqTvi_mxfdbSd8xB3DIaSA-Rqiltc8deHww"
_WORKSHEET_GID = 1520823618
_SYSTEMS = ("私車公用報支", "出差申報")
_EVENT_TYPES = ("開啟頁面", "產表")


def log_usage(system: str, event_type: str) -> None:
    """靜默記錄一次使用事件。

    Args:
        system: 「私車公用報支」或「出差申報」，要跟 Google 表單「系統」
            欄位的下拉選項文字完全一致，才能正確對應到選項。
        event_type: 「開啟頁面」或「產表」，同樣要跟表單「事件類型」欄位
            的選項文字完全一致。
    """
    try:
        form_data = {
            _ENTRY_NAME: st.session_state.get("employee_name") or "NA",
            _ENTRY_DEPT: st.session_state.get("employee_department") or "NA",
            _ENTRY_EMPLOYEE_ID: st.session_state.get("employee_id") or "NA",
            _ENTRY_EVENT_TYPE: event_type,
            _ENTRY_SYSTEM: system,
        }
        requests.post(
            _FORM_RESPONSE_URL,
            data=form_data,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            },
            timeout=5,
            allow_redirects=True,
        )
    except Exception:
        pass


def log_page_open(system: str) -> None:
    """「開啟頁面」事件：只在「這次是從別的頁面剛切換過來」時記一次。

    Streamlit 每次互動（打字、勾選、上傳檔案）都會重新執行整支頁面腳本，
    如果單純在頁面一開頭呼叫 log_usage，會變成使用者在頁面裡操作表單時
    也被誤記成又開了一次頁面。改用 session_state 記錄「目前所在頁面」，
    只有跟上一輪紀錄的頁面不同時才視為一次真正的「開啟」並送出，同一頁面
    內的後續重新整理不會重複計次；使用者離開又切回來則會記錄成新的一次。
    """
    if st.session_state.get("_current_page") != system:
        st.session_state["_current_page"] = system
        log_usage(system, "開啟頁面")


def parse_timestamp(series: pd.Series) -> pd.Series:
    """把 Google 表單「時間戳記」欄位的中文格式（例如 2026/8/30 上午 11:11:23）
    轉成 pandas 看得懂的日期時間。

    pandas 的 pd.to_datetime() 預設不認得「上午／下午」這種中文 AM/PM 標記，
    直接餵進去整批都會解析失敗變成 NaT（之前管理員維護區的日期篩選欄位因此一直
    是空的，就是這個原因）。中文格式的上午/下午是放在時間「前面」，英文慣例是
    放在「後面」，先置換文字、再搬動位置，才能讓 pandas 正確解析。
    """
    normalized = series.astype(str).str.replace("上午", "AM", regex=False).str.replace("下午", "PM", regex=False)
    normalized = normalized.str.replace(
        r"^(\d{4}/\d{1,2}/\d{1,2}) (AM|PM) (\d{1,2}:\d{2}:\d{2})$",
        r"\1 \3 \2",
        regex=True,
    )
    return pd.to_datetime(normalized, errors="coerce")


@st.cache_data(ttl=60, show_spinner=False)
def load_usage_log() -> pd.DataFrame:
    """讀取使用統計試算表，回傳整理過的 DataFrame（欄位：時間戳記、姓名、部門、
    員工編號、事件類型、系統）。

    讀取失敗時（例如金鑰未設定、網路問題、試算表權限被收回）回傳空的 DataFrame，
    不讓管理員維護區整頁掛掉——使用統計本來就是輔助資訊，不該影響其他核心功能。
    用 st.cache_data 快取 60 秒，避免管理員每次操作畫面（例如切分頁、勾選篩選
    條件）都重新打一次 Google API。

    新增「員工編號／事件類型／系統」三個欄位之前就已經存在的舊資料，這三欄會是
    空字串，篩不出系統/事件類型，一律排除，不計入統計數字。
    """
    try:
        import gspread

        gc = gspread.service_account_from_dict(dict(st.secrets["gcp_service_account"]))
        sh = gc.open_by_key(_SPREADSHEET_ID)
        ws = sh.get_worksheet_by_id(_WORKSHEET_GID)
        records = ws.get_all_records()
    except Exception:
        return pd.DataFrame(columns=["時間戳記", "姓名", "部門", "員工編號", "事件類型", "系統"])

    df = pd.DataFrame(records)
    if df.empty:
        return df
    df = df[df["員工編號"].astype(str).str.strip() != ""]
    return df


def usage_summary(df: pd.DataFrame) -> dict:
    """回傳 {系統: {事件類型: 次數}} 的統計字典，兩個系統、兩種事件類型固定都有
    鍵值（沒有資料時為 0），方便畫面直接讀取不用另外判斷欄位存不存在。"""
    summary = {}
    for system in _SYSTEMS:
        sub = df[df["系統"] == system] if not df.empty else df
        summary[system] = {
            event_type: int((sub["事件類型"] == event_type).sum()) if not sub.empty else 0
            for event_type in _EVENT_TYPES
        }
    return summary
