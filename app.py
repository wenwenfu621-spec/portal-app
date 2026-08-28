"""
入口網站主頁：登入頁 + 登入後的選單頁。

登入成功後身分資料存進 st.session_state（employee_id/employee_name/employee_department/
employee_title），供 pages/ 底下的子系統直接讀取，不需要再次輸入帳密或手動選擇姓名。
"""
import base64
from pathlib import Path

import streamlit as st

import bootstrap  # noqa: F401  (設定 sys.path，讓下面 import auth/database 找得到)
import auth
import database

st.set_page_config(page_title="伺服器事業部入口網站", page_icon="🖥️", layout="centered")

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
div[data-testid="stVerticalBlockBorderWrapper"] {
    background-color: rgba(255, 255, 255, 0.96);
    border-radius: 16px;
    box-shadow: 0px 8px 24px rgba(0, 0, 0, 0.25);
    border: none;
}
div.stButton > button, button[kind="primaryFormSubmit"] {
    background-color: #1976d2;
    color: white;
    border: none;
    width: 100%;
}
div.stButton > button:hover, button[kind="primaryFormSubmit"]:hover {
    background-color: #1565c0;
    color: white;
}
</style>
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
    _, center, _ = st.columns([1, 1.2, 1])
    with center:
        with st.container(border=True):
            st.markdown(
                "<h2 style='text-align:center; margin: 0.6rem 0 1rem;'>Login</h2>",
                unsafe_allow_html=True,
            )
            with st.form("login_form"):
                employee_id = st.text_input("帳號（員工編號）")
                password = st.text_input("密碼", type="password")
                submitted = st.form_submit_button("Log In", width="stretch")

            if submitted:
                success, error_message = _do_login(employee_id.strip(), password)
                if success:
                    st.rerun()
                else:
                    st.error(error_message)


def render_menu() -> None:
    _, center, _ = st.columns([1, 1.4, 1])
    with center:
        with st.container(border=True):
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
