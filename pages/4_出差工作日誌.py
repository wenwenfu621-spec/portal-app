"""
出差工作日誌：分階段上線（staged rollout）中的新功能，目前只開放測試名單裡的
員工編號使用。工具本體是一支獨立的單一 HTML 檔案（business_trip_daily_log.html，
沿用自 Business-Trip-Daily-Report 專案），純前端、資料只存在使用者自己電腦，
不上傳雲端／伺服器——這支頁面只負責「登入身分檢查＋測試名單權限檢查＋嵌入顯示」，
不去改動工具本身的樣式或邏輯。
"""
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from identity_watermark import get_git_version, inject_custom_footer, inject_version_tag
from portal_theme import inject_glass_theme

# 跟 app.py 選單那邊用同一份白名單常數會比較理想，但 app.py 是入口頁、這裡是子頁面，
# Streamlit 頁面之間沒有共用模組層級變數的機制，兩邊各自維護一份、要新增測試帳號時
# 兩處都要改。之後正式開放給全體同仁時，把這裡跟 app.py 的判斷式一起拿掉即可。
TRIP_DAILY_LOG_TESTERS = {"ETW00375"}

APP_VERSION = get_git_version()

st.set_page_config(page_title="出差工作日誌", page_icon="📝", layout="wide", initial_sidebar_state="collapsed")

if not st.session_state.get("logged_in"):
    st.warning("請先登入")
    st.page_link("app.py", label="回登入頁")
    st.stop()

# 真正的權限關卡在這裡——選單上「出差工作日誌」入口雖然只給白名單帳號看得到，
# 但那只是 UX 上不顯示而已，不是安全邊界；就算不在名單裡的同仁直接用網址列連過來，
# 這裡的伺服器端檢查一樣會擋下來，不會讓工具內容渲染出來。
if st.session_state.get("employee_id") not in TRIP_DAILY_LOG_TESTERS:
    st.warning("此功能尚未開放，仍在測試階段。")
    st.page_link("app.py", label="← 回選單")
    st.stop()

with st.container(key="portal_sticky_header"):
    with st.container(key="portal_nav_bar"):
        _nav_col1, _nav_col2 = st.columns(2)
        with _nav_col1:
            st.page_link("app.py", label="← 返回主頁", width=160)
        with _nav_col2:
            if st.button("登出", key="trip_log_logout", width=160):
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
    with st.container(key="page_title_bar"):
        st.title("📝 出差工作日誌（測試中）")

inject_version_tag(APP_VERSION)
inject_glass_theme()

st.caption("目前僅開放測試名單使用；測試完成後才會開放給全體同仁。工具內容渲染在下方獨立區塊內，視覺樣式（暖色調、標楷體）是工具原本的設計，跟入口網站其他頁面不同屬正常現象。")

_html_path = Path(__file__).parent.parent / "business_trip_daily_log.html"
_html_content = _html_path.read_text(encoding="utf-8")
components.html(_html_content, height=1800, scrolling=True)

inject_custom_footer()
