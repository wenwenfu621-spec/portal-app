"""
出貨階規劃：分階段上線（staged rollout）中的新功能，目前只開放測試名單裡的
員工編號使用。工具本體是一支獨立的單一 HTML 檔案（step1_shipping_stage_planner.html，
沿用自 Capacity-Scheduler 專案），純前端、資料只存在使用者自己瀏覽器的
localStorage，不上傳雲端／伺服器——這支頁面只負責「登入身分檢查＋測試名單權限
檢查＋嵌入顯示」，不去改動工具本身的樣式或邏輯。
"""
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from identity_watermark import get_git_version, inject_custom_footer, inject_version_tag
from portal_theme import inject_glass_theme

# 跟 app.py 選單那邊用同一份白名單常數會比較理想，但 app.py 是入口頁、這裡是子頁面，
# Streamlit 頁面之間沒有共用模組層級變數的機制，兩邊各自維護一份、要新增測試帳號時
# 兩處都要改。之後正式開放給全體同仁時，把這裡跟 app.py 的判斷式一起拿掉即可。
CAPACITY_SCHEDULER_TESTERS = {"ETW00375", "ETW00378"}

APP_VERSION = get_git_version()

st.set_page_config(page_title="出貨階規劃", page_icon="🗄️", layout="wide", initial_sidebar_state="collapsed")

if not st.session_state.get("logged_in"):
    st.warning("請先登入")
    st.page_link("app.py", label="回登入頁")
    st.stop()

# 真正的權限關卡在這裡——選單上「出貨階規劃」入口雖然只給白名單帳號看得到，
# 但那只是 UX 上不顯示而已，不是安全邊界；就算不在名單裡的同仁直接用網址列連過來，
# 這裡的伺服器端檢查一樣會擋下來，不會讓工具內容渲染出來。
if st.session_state.get("employee_id") not in CAPACITY_SCHEDULER_TESTERS:
    st.warning("此功能尚未開放，仍在測試階段。")
    st.page_link("app.py", label="← 回選單")
    st.stop()

# 工具本體自己的「匯出Excel／清空表單」按鈕會固定在工具內部那個 iframe 的最上方
# （position: sticky），但畫面往下捲到「頁面」本身（不是 iframe 內部）超過一個畫面高
# 時，整個 iframe 會被外層頁面的捲動一起帶走，工具自己的 sticky 按鈕就跟著看不見了
# ——sticky 沒辦法跨越 iframe 邊界生效，這是瀏覽器本身的限制，不是工具的 bug（詳見
# Capacity-Scheduler 那邊的說明）。這裡在 portal 外層另外做一組「真的」按鈕，放進本來
# 就會固定在最上方的 portal_sticky_header 容器裡，按下去時透過 postMessage 通知裡面
# 的 iframe 去執行真正的匯出／清空動作——不是假裝點兩下工具自己的按鈕，是工具那邊
# 也各自拆出 performExport()／performFullReset() 兩個函式直接呼叫，清空表單的兩次
# 確認機制則是這裡自己重新做一份（不會影響工具內部按鈕自己的兩次確認邏輯）。
# 這組按鈕整個用 components.html 做純前端小元件，按下去不會觸發 Streamlit rerun
# ——如果透過 st.button 觸發 rerun 再回頭去操作 iframe，沒辦法確定 Streamlit 會不會
# 順便重新整個渲染工具那個 iframe（等於重新整理，已上傳的BOM等記憶體資料會被清空），
# 所以刻意選擇「按鈕本身也活在一個小 iframe 裡，純 JS 直接跨 iframe 傳訊息」這個做法，
# 完全不經過 Python／Streamlit 的重跑流程 (2026-09-10)。
_CS_STICKY_ACTIONS_HTML = """
<style>
  html, body { margin: 0; padding: 0; background: transparent; }
  .cs-sticky-actions {
    display: flex; gap: 8px; align-items: center; justify-content: flex-end;
    padding: 4px 3rem 8px; font-family: 'IBM Plex Sans', 'Microsoft JhengHei', sans-serif;
  }
  .cs-btn {
    border: none; border-radius: 999px; padding: 8px 18px; font-size: 13px; font-weight: 600;
    cursor: pointer; color: #fff; white-space: nowrap;
    background: linear-gradient(135deg, #22d3ee, #6366f1);
    transition: opacity 0.12s ease;
  }
  .cs-btn:hover { opacity: 0.88; }
  .cs-btn.reset { background: linear-gradient(135deg, #94a3b8, #64748b); }
  .cs-btn.reset.armed { background: linear-gradient(135deg, #f97316, #ea580c); }
</style>
<div class="cs-sticky-actions">
  <button class="cs-btn export" id="csExportBtn" type="button">匯出 Excel</button>
  <button class="cs-btn reset" id="csResetBtn" type="button">清空表單</button>
</div>
<script>
(function () {
  function findToolFrames() {
    try { return Array.prototype.slice.call(window.parent.document.querySelectorAll("iframe")); }
    catch (e) { return []; }
  }
  function sendToTool(action) {
    findToolFrames().forEach(function (f) {
      try { f.contentWindow.postMessage({ source: "capacityScheduler", action: action }, "*"); }
      catch (e) {}
    });
  }
  document.getElementById("csExportBtn").addEventListener("click", function () {
    sendToTool("export");
  });
  var armed = false;
  var resetBtn = document.getElementById("csResetBtn");
  resetBtn.addEventListener("click", function () {
    if (!armed) {
      armed = true;
      resetBtn.textContent = "再按一次確認清空";
      resetBtn.classList.add("armed");
      setTimeout(function () {
        armed = false;
        resetBtn.textContent = "清空表單";
        resetBtn.classList.remove("armed");
      }, 3000);
      return;
    }
    armed = false;
    resetBtn.textContent = "清空表單";
    resetBtn.classList.remove("armed");
    sendToTool("resetConfirmed");
  });
})();
</script>
"""

with st.container(key="portal_sticky_header"):
    with st.container(key="portal_nav_bar"):
        _nav_col1, _nav_col2 = st.columns(2)
        with _nav_col1:
            st.page_link("app.py", label="← 返回主頁", width=160)
        with _nav_col2:
            if st.button("登出", key="capacity_scheduler_logout", width=160):
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
        st.title("🗄️ 出貨階規劃（測試中）")
    components.html(_CS_STICKY_ACTIONS_HTML, height=54, scrolling=False)

inject_version_tag(APP_VERSION)
inject_glass_theme()

st.caption("目前僅開放測試名單使用；測試完成後才會開放給全體同仁。工具內容渲染在下方獨立區塊內，視覺樣式是工具原本的設計，跟入口網站其他頁面不同屬正常現象。")

_html_path = Path(__file__).parent.parent / "step1_shipping_stage_planner.html"
_html_content = _html_path.read_text(encoding="utf-8")
components.html(_html_content, height=1400, scrolling=True)

inject_custom_footer()
