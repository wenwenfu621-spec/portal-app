"""
入口網站主頁：登入頁 + 登入後的選單頁。

登入成功後身分資料存進 st.session_state（employee_id/employee_name/employee_department/
employee_title），供 pages/ 底下的子系統直接讀取，不需要再次輸入帳密或手動選擇姓名。
"""
import base64
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

import bootstrap  # noqa: F401  (設定 sys.path，讓下面 import auth/database 找得到)
import auth
import database

st.set_page_config(page_title="伺服器事業部入口網站", page_icon="🖥️", layout="wide")

_APP_DIR = Path(__file__).parent
_BACKGROUND_IMAGE_PATH = _APP_DIR / "portal_background.jpg"


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
@import url('https://fonts.googleapis.com/css2?family=ZCOOL+KuaiLe&display=swap');

/* 卡片改用半透明毛玻璃質感，讓底圖若隱若現地透出來，不再是貼在底圖上突兀的一塊純白色
   方塊；並限制/置中一個固定的最大寬度，搭配 layout="wide" 讓卡片在各種螢幕尺寸下都
   維持適當比例（不會像 layout="centered" 那樣被壓縮成一小塊）。
   用 st.container(..., key="login_card"/"menu_card") 產生的穩定 class（st-key-xxx）
   來選取卡片本身，不用 data-testid="stVerticalBlockBorderWrapper"——新版 Streamlit
   （目前跑的是 1.62）已經把 border=True 容器直接做在 stVerticalBlock 上，不再包一層
   叫這個名字的外層 wrapper，用舊的 testid 選不到東西，加的樣式全部不會生效。 */
.st-key-login_card, .st-key-menu_card {
    max-width: 640px;
    margin: 0 auto;
    padding: 1.5rem 1rem;
    background: rgba(255, 255, 255, 0.55);
    backdrop-filter: blur(18px);
    -webkit-backdrop-filter: blur(18px);
    border-radius: 24px;
    box-shadow: 0 8px 32px rgba(31, 38, 135, 0.18), 0 0 40px rgba(103, 232, 249, 0.18);
    border: 1px solid rgba(255, 255, 255, 0.6) !important;
}
.st-key-login_card *, .st-key-menu_card * {
    font-family: "ZCOOL KuaiLe", "PingFang TC", "Microsoft JhengHei", sans-serif !important;
}
.st-key-login_card h2, .st-key-menu_card h2 {
    font-size: 2.6rem !important;
}
.st-key-login_card h3, .st-key-menu_card h3 {
    font-size: 2rem !important;
}
.st-key-login_card p, .st-key-menu_card p {
    font-size: 1.15rem !important;
}
div[data-testid="stWidgetLabel"] p {
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

/* 選單三個項目改成各自獨立的區塊（圖示+字樣），取代原本看起來像純文字清單的連結。 */
.st-key-menu_card div[data-testid="stPageLink"] {
    margin-bottom: 14px;
}
.st-key-menu_card div[data-testid="stPageLink"] a {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 22px 26px;
    border-radius: 16px;
    background: rgba(255, 255, 255, 0.6);
    border: 1px solid rgba(255, 255, 255, 0.75);
    border-left: 6px solid #22d3ee;
    box-shadow: 0 2px 8px rgba(31, 38, 135, 0.10);
    font-size: 1.35rem !important;
    font-weight: 600;
    text-decoration: none !important;
    transition: transform 0.15s ease, box-shadow 0.15s ease, background 0.15s ease;
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
_LOGIN_ENTER_NAV_JS = """
<script>
(function() {
    function getDoc() {
        try { return window.parent.document; } catch (e) { return null; }
    }
    function attach() {
        const doc = getDoc();
        if (!doc || doc.__loginEnterNavAttached) return;
        doc.__loginEnterNavAttached = true;
        doc.addEventListener('keydown', function(e) {
            if (e.isComposing || e.keyCode === 229) return;
            const isEnter = e.key === 'Enter' || e.keyCode === 13;
            if (!isEnter) return;
            const active = doc.activeElement;
            if (!active || active.getAttribute('aria-label') !== '帳號（員工編號）') return;
            e.preventDefault();
            e.stopPropagation();
            const pwd = doc.querySelector('input[aria-label="密碼"]');
            if (pwd) { pwd.focus(); }
        }, true);
    }
    attach();
    const doc0 = getDoc();
    if (doc0 && doc0.defaultView && !doc0.__loginEnterNavInterval) {
        doc0.__loginEnterNavInterval = true;
        doc0.defaultView.setInterval(attach, 800);
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
    _, center, _ = st.columns([0.2, 1, 0.2])
    with center:
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
                success, error_message = _do_login(employee_id.strip().upper(), password)
                if success:
                    st.rerun()
                else:
                    st.error(error_message)


def render_menu() -> None:
    _, center, _ = st.columns([0.2, 1, 0.2])
    with center:
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
