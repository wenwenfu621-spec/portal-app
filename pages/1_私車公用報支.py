"""
私車公用報支頁面掛載點。

正式串接時，這個檔案會被 car-expense-app repo 的 app.py 取代（Git Submodule），
沿用其既有邏輯，只是身分資料改由入口網站登入後的 session_state 帶入，
不再讓使用者手動選部門/姓名。目前先放版位，示範身分自動帶入。
"""
import streamlit as st

import bootstrap  # noqa: F401

st.set_page_config(page_title="私車公用報支", page_icon="🚗")

if not st.session_state.get("logged_in"):
    st.warning("請先登入")
    st.page_link("app.py", label="回登入頁")
    st.stop()

st.title("🚗 私車公用報支")
st.info("此頁面尚未併入 car-expense-app 子系統，以下為登入身分自動帶入示範。")
st.write(f"單位：{st.session_state['employee_department']}")
st.write(f"姓名：{st.session_state['employee_name']}")

st.page_link("app.py", label="← 回選單")
