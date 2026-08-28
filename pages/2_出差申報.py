"""
出差申報頁面掛載點。

正式串接時，這個檔案會被 trip-expense-app repo 的 app.py 取代（Git Submodule），
身分資料改由入口網站登入後的 session_state 帶入。目前先放版位，示範身分自動帶入。
"""
import streamlit as st

import bootstrap  # noqa: F401

st.set_page_config(page_title="出差申報", page_icon="🧳")

if not st.session_state.get("logged_in"):
    st.warning("請先登入")
    st.page_link("app.py", label="回登入頁")
    st.stop()

st.title("🧳 出差申報")
st.info("此頁面尚未併入 trip-expense-app 子系統，以下為登入身分自動帶入示範。")
st.write(f"員工編號：{st.session_state['employee_id']}")
st.write(f"姓名：{st.session_state['employee_name']}")
st.write(f"單位：{st.session_state['employee_department']}")
st.write(f"職務：{st.session_state.get('employee_title') or '（尚未取得）'}")

st.page_link("app.py", label="← 回選單")
