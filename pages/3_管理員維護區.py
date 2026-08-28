"""
管理員維護區：第二層驗證（獨立管理員密碼，跟同仁的統一登入密碼分開存放）。

目前只完成密碼驗證關卡本身；員工資料維護／SOP 上傳／密碼修改等維護功能尚未實作。
"""
import streamlit as st

import bootstrap  # noqa: F401
import auth
import database

st.set_page_config(page_title="管理員維護區", page_icon="🛠️")

if not st.session_state.get("logged_in"):
    st.warning("請先登入")
    st.page_link("app.py", label="回登入頁")
    st.stop()

if not st.session_state.get("is_admin_verified"):
    st.subheader("🛠️ 管理員驗證")
    admin_password = st.text_input("管理員密碼", type="password", key="admin_password_input")
    if st.button("驗證"):
        conn = database.get_connection()
        try:
            stored_hash = database.get_setting(conn, "admin_password_hash")
            hint = database.get_setting(conn, "admin_password_hint")
        finally:
            conn.close()

        if stored_hash and auth.verify_password(admin_password, stored_hash):
            st.session_state["is_admin_verified"] = True
            st.rerun()
        else:
            st.error(f"密碼錯誤。提示：{hint}" if hint else "密碼錯誤")
    st.page_link("app.py", label="← 回選單")
    st.stop()

st.title("🛠️ 管理員維護區")
st.info("維護功能（部門員工資料維護／上傳操作SOP／更新登入密碼）尚未實作。")

st.page_link("app.py", label="← 回選單")
