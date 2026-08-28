"""
管理員維護區：第二層驗證（獨立管理員密碼，跟同仁的統一登入密碼分開存放），
驗證通過後提供三項維護功能：部門員工資料維護、上傳操作SOP、更新登入密碼。
"""
import sqlite3

import pandas as pd
import streamlit as st

import bootstrap  # noqa: F401
import auth
import database

st.set_page_config(page_title="管理員維護區", page_icon="🛠️", layout="centered")

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
st.page_link("app.py", label="← 回選單")

# 動作完成後會 st.rerun() 讓表格/清單重新讀取資料庫最新狀態，但 st.rerun() 會讓當次
# script run 提前中止，寫在動作處理常式裡的 st.success/st.warning 訊息還沒被看到就消失。
# 改用 session_state 存一份「重新整理後要顯示的訊息」，在新的一輪 script run 開頭顯示。
_flash_messages = st.session_state.pop("admin_flash_messages", None)
if _flash_messages:
    for level, message in _flash_messages:
        getattr(st, level)(message)

# ---------------------------------------------------------------------------
# 1. 部門員工資料維護
# ---------------------------------------------------------------------------
st.header("部門員工資料維護")
st.caption(
    "勾選「在職」欄可停用（離職）或恢復帳號；停用不會刪除歷史資料。"
    "表格最下方可用「＋」新增員工列。員工編號留空的同仁暫時無法登入入口網站。"
)

conn = database.get_connection()
try:
    employees = database.list_all_employees(conn)
finally:
    conn.close()

original_df = pd.DataFrame(
    [
        {
            "id": row["id"],
            "在職": bool(row["is_active"]),
            "單位": row["department"],
            "員工編號": row["employee_id"] or "",
            "姓名": row["name"],
            "職務": row["title"] or "",
        }
        for row in employees
    ]
)

edited_df = st.data_editor(
    original_df,
    column_order=["在職", "單位", "員工編號", "姓名", "職務"],
    column_config={"在職": st.column_config.CheckboxColumn("在職")},
    num_rows="dynamic",
    width="stretch",
    hide_index=True,
    key="employee_editor",
)

if st.button("儲存員工資料變更", type="primary"):
    original_ids = set(original_df["id"])
    edited_ids = set(edited_df["id"].dropna())
    removed_ids = original_ids - edited_ids

    conn = database.get_connection()
    try:
        for _, row in edited_df.iterrows():
            department = str(row["單位"]).strip()
            employee_id = str(row["員工編號"]).strip() or None
            name = str(row["姓名"]).strip()
            title = str(row["職務"]).strip() or None
            is_active = bool(row["在職"])

            if not department or not name:
                raise ValueError("單位與姓名為必填欄位，請確認每一列都已填寫。")

            row_id = row["id"]
            if pd.isna(row_id):
                database.insert_employee(conn, department, employee_id, name, title, is_active)
            else:
                database.update_employee(conn, int(row_id), department, employee_id, name, title, is_active)
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
        st.error("儲存失敗：員工編號重複，請確認每個員工編號只對應一位同仁。")
    except ValueError as e:
        conn.rollback()
        st.error(f"儲存失敗：{e}")
    else:
        messages = []
        if removed_ids:
            messages.append((
                "warning",
                f"偵測到 {len(removed_ids)} 筆資料在表格中被移除，但系統不允許刪除員工資料，"
                "這些同仁的紀錄仍保留在資料庫中；如需停用請改用「在職」核取欄位。",
            ))
        messages.append(("success", "已儲存"))
        st.session_state["admin_flash_messages"] = messages
        st.rerun()
    finally:
        conn.close()

# ---------------------------------------------------------------------------
# 2. 上傳操作SOP
# ---------------------------------------------------------------------------
st.divider()
st.header("上傳操作SOP")
st.caption("上傳新版本會直接覆蓋舊版本，不保留歷史版本。")

conn = database.get_connection()
try:
    car_sop = database.get_sop_document(conn, "car_expense")
    trip_sop = database.get_sop_document(conn, "trip_expense")
finally:
    conn.close()

sop_col1, sop_col2 = st.columns(2)

with sop_col1:
    st.markdown("**私車公用報支**")
    if car_sop:
        st.download_button(
            "下載目前版本",
            data=car_sop["content"],
            file_name=car_sop["filename"],
            key="download_car_sop",
        )
        st.caption(f"上傳時間：{car_sop['uploaded_at']}")
    else:
        st.caption("尚未上傳")
    new_car_sop = st.file_uploader("上傳新版本（PDF）", type=["pdf"], key="upload_car_sop")
    if new_car_sop is not None and st.button("確認覆蓋上傳", key="confirm_car_sop"):
        conn = database.get_connection()
        try:
            database.set_sop_document(conn, "car_expense", new_car_sop.name, new_car_sop.getvalue())
        finally:
            conn.close()
        st.session_state["admin_flash_messages"] = [("success", "已上傳新版本")]
        st.rerun()

with sop_col2:
    st.markdown("**出差申報**")
    if trip_sop:
        st.download_button(
            "下載目前版本",
            data=trip_sop["content"],
            file_name=trip_sop["filename"],
            key="download_trip_sop",
        )
        st.caption(f"上傳時間：{trip_sop['uploaded_at']}")
    else:
        st.caption("尚未上傳")
    new_trip_sop = st.file_uploader("上傳新版本（PDF）", type=["pdf"], key="upload_trip_sop")
    if new_trip_sop is not None and st.button("確認覆蓋上傳", key="confirm_trip_sop"):
        conn = database.get_connection()
        try:
            database.set_sop_document(conn, "trip_expense", new_trip_sop.name, new_trip_sop.getvalue())
        finally:
            conn.close()
        st.session_state["admin_flash_messages"] = [("success", "已上傳新版本")]
        st.rerun()

# ---------------------------------------------------------------------------
# 3. 更新登入密碼
# ---------------------------------------------------------------------------
st.divider()
st.header("更新密碼")

conn = database.get_connection()
try:
    current_hint = database.get_setting(conn, "admin_password_hint") or ""
finally:
    conn.close()

with st.form("update_shared_password_form"):
    st.markdown("**統一登入密碼**（全體同仁登入入口網站用）")
    new_shared_password = st.text_input("新密碼", type="password", key="new_shared_password")
    submit_shared = st.form_submit_button("更新統一登入密碼")
if submit_shared:
    if not new_shared_password:
        st.error("請輸入新密碼")
    else:
        conn = database.get_connection()
        try:
            database.set_setting(conn, "shared_login_password_hash", auth.hash_password(new_shared_password))
        finally:
            conn.close()
        st.success("統一登入密碼已更新")

with st.form("update_admin_password_form"):
    st.markdown("**管理員密碼**（本頁的第二層驗證密碼）")
    new_admin_password = st.text_input("新密碼（留空表示不更改密碼，只更新提示語）", type="password", key="new_admin_password")
    new_hint = st.text_input("密碼提示語", value=current_hint, key="new_admin_hint")
    submit_admin = st.form_submit_button("更新管理員密碼／提示語")
if submit_admin:
    conn = database.get_connection()
    try:
        if new_admin_password:
            database.set_setting(conn, "admin_password_hash", auth.hash_password(new_admin_password))
        database.set_setting(conn, "admin_password_hint", new_hint)
    finally:
        conn.close()
    st.success("管理員密碼設定已更新")
