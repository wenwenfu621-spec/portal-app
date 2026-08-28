"""
入口網站主頁：登入頁 + 登入後的選單頁。

登入成功後身分資料存進 st.session_state（employee_id/employee_name/employee_department/
employee_title），供 pages/ 底下的子系統直接讀取，不需要再次輸入帳密或手動選擇姓名。
"""
import base64
import csv
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

import auth
import database
from identity_watermark import inject_custom_footer, inject_version_tag

APP_VERSION = "20260828-REAL-SUBSYSTEMS-CSV-SEED"

st.set_page_config(
    page_title="伺服器事業部入口網站",
    page_icon="🖥️",
    layout="wide",
    initial_sidebar_state="collapsed",
)
inject_version_tag(APP_VERSION)

_APP_DIR = Path(__file__).parent
_BACKGROUND_IMAGE_PATH = _APP_DIR / "portal_background.jpg"

# ---- 初始密碼（2026-08-28 使用者確認的初始值）----
# 部署後管理員應立即到「管理員維護區」把這兩組密碼改掉；這裡只是讓系統第一次能夠登入。
# 密碼刻意維持寫死在程式碼裡（不拆成獨立檔案）——拆成單獨一份「密碼.xlsx」之類的檔案
# 反而更容易被單獨複製/外流/誤傳，寫在程式碼裡至少不會被當成一般文件檔案處理。
_INITIAL_SHARED_LOGIN_PASSWORD = "28977162"
_INITIAL_ADMIN_PASSWORD = "20080418"
_INITIAL_ADMIN_PASSWORD_HINT = "管理員小孩生日"

# 員工清單改成獨立的 CSV 檔案（employees_seed.csv），不再寫死在程式碼裡——之後要新增/
# 補齊員工編號，直接用 Excel 開這份檔案改、存檔、上傳到 GitHub 即可，不用再改程式碼。
_EMPLOYEES_SEED_PATH = _APP_DIR / "employees_seed.csv"
_EMPLOYEES_SEED_ENCODINGS = ["utf-8-sig", "cp950"]


def _load_employees_seed() -> list[tuple[str, str | None, str, str | None]]:
    """讀取 employees_seed.csv，回傳 [(單位, 員工編號, 姓名, 職務), ...]。
    用 Excel 維護這份清單時，存檔容易不小心選到舊版「CSV（逗號分隔）」（Windows 地區
    編碼，繁體中文環境是 cp950/Big5）而不是「CSV UTF-8」，依序都試一次；檔案不存在、
    編碼不對、缺欄位等任何問題都靜默回傳空清單，不讓整個入口網站掛掉——沒有這份檔案
    時單純不做員工清單的初始 seed，等管理員之後在維護區手動新增即可。"""
    if not _EMPLOYEES_SEED_PATH.exists():
        return []
    for encoding in _EMPLOYEES_SEED_ENCODINGS:
        try:
            with open(_EMPLOYEES_SEED_PATH, encoding=encoding, newline="") as f:
                reader = csv.DictReader(f)
                rows = []
                for row in reader:
                    department = (row.get("單位") or "").strip()
                    employee_id = (row.get("員工編號") or "").strip() or None
                    name = (row.get("姓名") or "").strip()
                    title = (row.get("職務") or "").strip() or None
                    if not department or not name:
                        continue
                    rows.append((department, employee_id, name, title))
            return rows
        except (OSError, UnicodeDecodeError):
            continue
        except Exception:
            return []
    return []


@st.cache_resource
def _bootstrap_database() -> None:
    """建表 + 寫入初始密碼／員工清單，整個 process 生命週期只需要真的執行一次
    （用 st.cache_resource 快取，不是每次 rerun 都重新檢查一遍）。本機開發環境的
    portal.db 已經手動跑過 shared-core/init_db.py 初始化過，這裡主要是為了雲端部署
    ——部署到 Streamlit Cloud 時容器是全新的，事先不會有任何資料庫檔案，第一次啟動
    App 時要能自己把資料表建起來、把最初能登入的密碼寫進去，不然會在還沒建表前就被
    login 頁面查詢 system_settings 撞成 sqlite3.OperationalError。
    全部都是 idempotent 寫法：資料表用 CREATE TABLE IF NOT EXISTS；密碼設定只在該筆
    設定完全不存在時才寫入，不會覆蓋管理員之後在維護區改過的密碼；員工清單只在資料表
    目前是空的時候才寫入，不會覆蓋管理員之後新增/停用過的資料。"""
    conn = database.get_connection()
    try:
        database.init_schema(conn)

        existing_keys = {row["key"] for row in conn.execute("SELECT key FROM system_settings")}
        to_seed = {
            "shared_login_password_hash": auth.hash_password(_INITIAL_SHARED_LOGIN_PASSWORD),
            "admin_password_hash": auth.hash_password(_INITIAL_ADMIN_PASSWORD),
            "admin_password_hint": _INITIAL_ADMIN_PASSWORD_HINT,
        }
        for key, value in to_seed.items():
            if key not in existing_keys:
                conn.execute("INSERT INTO system_settings (key, value) VALUES (?, ?)", (key, value))

        employee_count = conn.execute("SELECT COUNT(*) AS c FROM employees").fetchone()["c"]
        if employee_count == 0:
            seed_rows = _load_employees_seed()
            if seed_rows:
                conn.executemany(
                    "INSERT INTO employees (department, employee_id, name, title) VALUES (?, ?, ?, ?)",
                    seed_rows,
                )

        conn.commit()
    finally:
        conn.close()


_bootstrap_database()

# 選單上「管理員維護區」入口只給這份名單裡的員工編號看得到，其他同仁登入後選單不會
# 顯示這個選項（但不是新的安全邊界——管理員密碼仍是唯一的實際驗證關卡，這裡只是
# UX 上不要讓非管理員同仁看到用不到、也進不去的選項）。要新增/移除管理員，改這裡
# 這行常數即可。
ADMIN_EMPLOYEE_IDS = {"ETW00375"}


def _inject_background_css(image_path: Path) -> None:
    image_b64 = base64.b64encode(image_path.read_bytes()).decode("utf-8")
    st.markdown(
        f"""
        <style>
        .stApp {{
            background-image: url("data:image/jpeg;base64,{image_b64}");
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


_CARD_CSS = """
<style>
/* 卡片改用半透明毛玻璃質感，讓底圖若隱若現地透出來，不再是貼在底圖上突兀的一塊純白色
   方塊；並限制/置中一個固定的最大寬度，搭配 layout="wide" 讓卡片在各種螢幕尺寸下都
   維持適當比例（不會像 layout="centered" 那樣被壓縮成一小塊）。
   用 st.container(..., key="login_card"/"menu_card") 產生的穩定 class（st-key-xxx）
   來選取卡片本身，不用 data-testid="stVerticalBlockBorderWrapper"——新版 Streamlit
   （目前跑的是 1.62）已經把 border=True 容器直接做在 stVerticalBlock 上，不再包一層
   叫這個名字的外層 wrapper，用舊的 testid 選不到東西，加的樣式全部不會生效。 */
.st-key-login_card, .st-key-menu_card {
    /* 用 clamp() 讓卡片寬度跟著視窗大小流動：小螢幕（手機/窄視窗）跟著縮小、
       維持螢幕寬度的 92% 不會爆版；大螢幕（桌機/大螢幕）則固定卡在 480px，
       不會隨螢幕越大就越寬到跟底圖比例不協調。 */
    width: clamp(280px, 92vw, 480px) !important;
    flex-shrink: 0 !important;
    margin: 0 auto;
    padding: 1.5rem 1rem;
    background: rgba(255, 255, 255, 0.32);
    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
    border-radius: 24px;
    box-shadow: 0 8px 32px rgba(31, 38, 135, 0.18), 0 0 40px rgba(103, 232, 249, 0.18);
    border: 1px solid rgba(255, 255, 255, 0.6) !important;
}
/* 字體套用範圍要排除 stIconMaterial——那是 Streamlit 用「文字連字」渲染 Material
   圖示的機制（例如密碼欄位「顯示/隱藏密碼」的眼睛圖示，DOM 裡實際文字是
   "visibility"），套用其他字體會讓連字失效，圖示變成顯示一串英文字，而不是眼睛符號。 */
.st-key-login_card *:not([data-testid="stIconMaterial"]),
.st-key-menu_card *:not([data-testid="stIconMaterial"]) {
    font-family: "標楷體", "DFKai-SB", "BiauKai", "PingFang TC", "Microsoft JhengHei", sans-serif !important;
}
.st-key-login_card h2, .st-key-menu_card h2 {
    font-size: clamp(1.9rem, 8vw, 2.6rem) !important;
}
.st-key-login_card h3, .st-key-menu_card h3 {
    font-size: clamp(1.5rem, 6vw, 2rem) !important;
}
.st-key-login_card p, .st-key-menu_card p {
    font-size: 1.15rem !important;
}
.st-key-login_card [data-testid="stWidgetLabel"],
.st-key-menu_card [data-testid="stWidgetLabel"] {
    text-align: center;
    display: block;
}
[data-testid="stWidgetLabel"] p {
    font-size: 1.15rem !important;
    font-weight: 600;
}
.st-key-login_card input, .st-key-menu_card input {
    text-align: center;
    font-size: 1.25rem !important;
    padding: 0.7rem 0.9rem !important;
}
input[aria-label="帳號（員工編號）"] {
    text-transform: uppercase;
}
/* Login 按鈕改用跟底圖霓虹光感呼應的藍綠 -> 靛紫漸層，取代原本突兀的純藍色；字級/高度
   也一併放大，跟放大後的卡片比例相稱。用卡片的 st-key class 去限定範圍（不要直接選
   全站所有 button），避免不小心也套到頁首/側欄等其他按鈕；新版 Streamlit 的按鈕
   kind 已經改叫 secondaryFormSubmit，不再是 primaryFormSubmit，直接選 button 標籤
   比追著版本改的 kind 名稱穩定。 */
.st-key-login_card button, .st-key-menu_card button {
    background: linear-gradient(135deg, #22d3ee, #6366f1) !important;
    color: white !important;
    border: none !important;
    width: 100%;
    font-size: 1.25rem !important;
    font-weight: 600;
    padding: 0.9rem 1rem !important;
}
.st-key-login_card button:hover, .st-key-menu_card button:hover {
    background: linear-gradient(135deg, #06b6d4, #4f46e5) !important;
}
/* 登出按鈕字級。按鈕文字實際上是包在 stMarkdownContainer 的 <p> 裡面，套在外層
   <button>/<a> 上的 font-size 不會蓋過 Streamlit 對 <p> 另外設的字級規則（字級不是靠
   繼承 link/button 本身的 font-size，是 <p> 自己被另一條規則直接選到、直接決定大小），
   要連 <p> 本身也一起設才會真的變大。
   字級不能無限放大：文字外面包的 span 是 Streamlit 內建的 overflow:hidden，這會讓
   flex 版面的自動最小寬度算成 0（CSS flexbox 的預設行為──flex 子項目只要
   overflow 不是 visible，min-width 就會從「照內容大小」變成 0），字放太大、版面
   容不下時，瀏覽器會直接把文字所在的 span 壓縮到快要 0 寬度，畫面上文字會被壓到
   幾乎看不見，而不是換行或超出邊界，之前放到 5rem/7.2rem 就是踩到這個。 */
.st-key-menu_card button {
    font-size: 1.8rem !important;
}
.st-key-menu_card button [data-testid="stMarkdownContainer"] p {
    font-size: 1.8rem !important;
}

/* 選單三個項目改成各自獨立的區塊（圖示+字樣），取代原本看起來像純文字清單的連結。 */
.st-key-menu_card div[data-testid="stPageLink"] {
    margin-bottom: 14px;
}
.st-key-menu_card div[data-testid="stPageLink"] a {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 16px;
    padding: 22px 26px;
    height: auto !important;
    min-height: unset !important;
    border-radius: 16px;
    background: rgba(255, 255, 255, 0.6);
    border: 1px solid rgba(255, 255, 255, 0.75);
    border-left: 6px solid #22d3ee;
    box-shadow: 0 2px 8px rgba(31, 38, 135, 0.10);
    font-size: 2.4rem !important;
    font-weight: 600;
    text-decoration: none !important;
    transition: transform 0.15s ease, box-shadow 0.15s ease, background 0.15s ease;
}
.st-key-menu_card div[data-testid="stPageLink"] a [data-testid="stMarkdownContainer"] p {
    font-size: 2.4rem !important;
}
/* 保險：就算之後字級又調大到版面快裝不下，也讓文字用「超出邊界可見」或「換行」，
   不要被壓縮到看不見（見上面的說明）。 */
.st-key-menu_card div[data-testid="stPageLink"] a span,
.st-key-menu_card button span {
    overflow: visible !important;
    min-width: 0;
}
.st-key-menu_card div[data-testid="stPageLink"] a:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 16px rgba(31, 38, 135, 0.18);
    background: rgba(255, 255, 255, 0.8);
}
/* 用連結網址（href 含頁面檔名）分辨是哪一個選單項目，而不是用 :nth-of-type——Streamlit
   把每個 st.page_link 各自包在自己的 stElementContainer 裡，同一層裡永遠只有一個
   stPageLink，:nth-of-type 永遠等於 1，三個項目會選到同一種顏色。 */
.st-key-menu_card div[data-testid="stPageLink"] a[href*="私車公用報支"] { border-left-color: #22d3ee; }
.st-key-menu_card div[data-testid="stPageLink"] a[href*="出差申報"] { border-left-color: #818cf8; }
.st-key-menu_card div[data-testid="stPageLink"] a[href*="管理員維護區"] { border-left-color: #fb923c; }
</style>
"""

# 帳號欄位按 Enter 時，讓焦點跳到密碼欄位，而不是（因為在 st.form 裡）直接以空白密碼送出
# 表單。密碼欄位按 Enter 維持原生行為（送出表單），不用額外處理。
# 這段 JS 是「盡量攔截」，不是唯一防線——實測發現使用者在頁面/這段 script 所在的
# iframe 還沒載入完成前就快速打完帳號按 Enter，會攔截不到，導致表單直接以空密碼送出、
# 跳出「帳號或密碼錯誤」的嚇人訊息（帳號可能明明打對了）。真正保底的防線是
# render_login_form() 裡的 Python 端判斷（帳號有填、密碼空白時不顯示錯誤），這裡只是
# 讓「攔截成功」的情況下體驗更好、直接跳到密碼欄位；攔截失敗也不會顯示錯誤，只是使用者
# 要自己點一下密碼欄位。監聽器改掛在 window（而不是 document）上，理論上能比掛在
# document 更早進到 capture 階段，盡量搶在 Streamlit 自己的送出邏輯處理這個按鍵之前
# 攔截到，但不保證每次都攔得到（載入時機還是有可能太慢）。
_LOGIN_ENTER_NAV_JS = """
<script>
(function() {
    function getDoc() {
        try { return window.parent.document; } catch (e) { return null; }
    }
    function attach() {
        const doc = getDoc();
        const win = doc && doc.defaultView;
        if (!doc || !win || win.__loginEnterNavAttached) return;
        win.__loginEnterNavAttached = true;
        win.addEventListener('keydown', function(e) {
            if (e.isComposing || e.keyCode === 229) return;
            const isEnter = e.key === 'Enter' || e.keyCode === 13;
            if (!isEnter) return;
            const active = doc.activeElement;
            if (!active || active.getAttribute('aria-label') !== '帳號（員工編號）') return;
            e.preventDefault();
            e.stopPropagation();
            if (e.stopImmediatePropagation) { e.stopImmediatePropagation(); }
            const pwd = doc.querySelector('input[aria-label="密碼"]');
            if (pwd) { pwd.focus(); }
        }, true);
    }
    attach();
    const doc0 = getDoc();
    if (doc0 && doc0.defaultView && !doc0.__loginEnterNavInterval) {
        doc0.__loginEnterNavInterval = true;
        doc0.defaultView.setInterval(attach, 200);
    }
})();
</script>
"""


def _do_login(employee_id: str, password: str) -> tuple[bool, str]:
    """驗證統一登入密碼 + 員工編號是否為在職員工，成功時把身分資料寫進 session_state。
    回傳 (是否成功, 失敗時的錯誤訊息)。"""
    if not employee_id or not password:
        return False, "請輸入員工編號與密碼"

    conn = database.get_connection()
    try:
        stored_hash = database.get_setting(conn, "shared_login_password_hash")
        if not stored_hash or not auth.verify_password(password, stored_hash):
            return False, "帳號或密碼錯誤"

        employee = database.find_active_employee_by_employee_id(conn, employee_id)
        if employee is None:
            return False, "帳號或密碼錯誤"
    finally:
        conn.close()

    st.session_state["logged_in"] = True
    st.session_state["employee_id"] = employee["employee_id"]
    st.session_state["employee_name"] = employee["name"]
    st.session_state["employee_department"] = employee["department"]
    st.session_state["employee_title"] = employee["title"]
    return True, ""


def render_login_form() -> None:
    # 不再用 st.columns() 裁出一個窄欄位放卡片——欄位寬度是 st.columns() 依比例算好的
    # 固定像素，卡片被限制在那個欄位裡，在窄螢幕（平板/手機大小視窗）算出來的欄位可能
    # 比我們想要的卡片寬度還窄，卡片會被 Streamlit 自己版面的 max-width:100% 壓縮到比
    # 欄位還小，跟螢幕大小完全不成比例。改成卡片直接放在主要內容區，寬度／置中全部交給
    # CSS 的 max-width + margin:auto 處理，才能真正跟著螢幕寬度流動。
    with st.container(border=True, key="login_card"):
        st.markdown(
            "<h2 style='text-align:center; margin: 0.6rem 0 1rem;'>Login</h2>",
            unsafe_allow_html=True,
        )
        with st.form("login_form"):
            employee_id = st.text_input("帳號（員工編號）", autocomplete="off")
            password = st.text_input("密碼", type="password", autocomplete="off")
            submitted = st.form_submit_button("Log In", width="stretch")
        components.html(_LOGIN_ENTER_NAV_JS, height=0)

        if submitted:
            if employee_id.strip() and not password:
                # 帳號欄位有填、密碼欄位是空的：極可能是使用者剛打完帳號按 Enter，
                # 是想跳到密碼欄位（見下面的 _LOGIN_ENTER_NAV_JS），不是真的要送出
                # 表單。下面那段 JS 攔截 Enter 的時機是「iframe 載入完成後」，使用者
                # 打字夠快、頁面又還沒載入完的話會來不及攔截，讓表單真的送出，這時候
                # 不能顯示「帳號或密碼錯誤」這種嚇人的錯誤訊息（帳號可能明明是對的，
                # 只是密碼還沒打），靜默不處理、讓使用者接著打密碼即可，比對 JS 攔截
                # 時機更可靠——不管 JS 到底有沒有攔截成功，這裡都能兜底。
                pass
            else:
                success, error_message = _do_login(employee_id.strip().upper(), password)
                if success:
                    st.rerun()
                else:
                    st.error(error_message)


def render_menu() -> None:
    # 同 render_login_form()：不用 st.columns() 裁窄欄位放卡片，改讓卡片直接放在主要
    # 內容區，寬度／置中交給 CSS 的 max-width + margin:auto 處理，卡片才能真正跟著
    # 螢幕寬度流動，不會被欄位比例先卡住一個跟螢幕大小不成比例的寬度。
    with st.container(border=True, key="menu_card"):
        title_part = f" ・ {st.session_state['employee_title']}" if st.session_state.get("employee_title") else ""
        st.markdown(
            f"<h3 style='text-align:center; margin-top:0.6rem;'>{st.session_state['employee_name']} 您好</h3>"
            f"<p style='text-align:center; color:#666;'>"
            f"{st.session_state['employee_department']}{title_part}"
            f"</p>",
            unsafe_allow_html=True,
        )
        st.page_link("pages/1_私車公用報支.py", label="🚗 私車公用報支", width="stretch")
        st.page_link("pages/2_出差申報.py", label="🧳 出差申報", width="stretch")
        if st.session_state.get("employee_id") in ADMIN_EMPLOYEE_IDS:
            st.page_link("pages/3_管理員維護區.py", label="🛠️ 管理員維護區", width="stretch")

        st.write("")
        if st.button("登出", width="stretch"):
            for key in (
                "logged_in",
                "employee_id",
                "employee_name",
                "employee_department",
                "employee_title",
                "is_admin_verified",
            ):
                st.session_state.pop(key, None)
            st.rerun()


if _BACKGROUND_IMAGE_PATH.exists():
    _inject_background_css(_BACKGROUND_IMAGE_PATH)
st.markdown(_CARD_CSS, unsafe_allow_html=True)

if st.session_state.get("logged_in"):
    render_menu()
else:
    render_login_form()

inject_custom_footer()
