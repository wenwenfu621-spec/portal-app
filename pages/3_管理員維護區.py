"""
管理員維護區：第二層驗證（獨立管理員密碼，跟同仁的統一登入密碼分開存放），
驗證通過後提供三項維護功能：部門員工資料維護、上傳操作SOP、更新登入密碼。
"""
import sqlite3

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

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
    column_config={
        "在職": st.column_config.CheckboxColumn("在職"),
        # 員工編號欄位刻意設成 "small"（比其他文字欄位窄很多），這樣下面注入的
        # JS 才能單靠「編輯框目前渲染出來多寬」去分辨使用者現在是不是在編輯這一欄
        # ——這個表格是畫布（canvas）繪的第三方套件，沒有明確的「目前編輯哪一欄」
        # 資訊可以讀，用寬度反推是唯一不用去猜套件內部結構就能做到的辦法。
        "員工編號": st.column_config.TextColumn("員工編號", width="small"),
    },
    num_rows="dynamic",
    width="stretch",
    hide_index=True,
    key="employee_editor",
)

# 這個表格所有文字欄位（員工編號/姓名/單位/職務）邊打邊即時轉大寫。表格本身是畫布
# 繪製的第三方套件（glide-data-grid），點下去編輯時彈出的是套件內部產生的通用輸入
# 框，所有文字欄位共用同一種，沒有屬性能直接看出「目前編輯的是哪一欄」，沒辦法只
# 精準鎖定員工編號這一欄（試過用欄寬反推，實測沒用）。
# 改用另一個更可靠的判斷依據：Streamlit 自己產生的正式元件（例如下面的「新密碼」
# 「密碼提示語」輸入框）一定會有 aria-label 屬性；這個表格套件內部彈出的通用編輯框
# 沒有 aria-label。用「有沒有 aria-label」分辨，才不會不小心把密碼欄位也轉成大寫
# （密碼可能刻意用小寫，轉大寫會直接讓密碼失效，是不能犯的錯）。
# 代價：單位/姓名/職務這幾欄如果打英文字母也會被轉大寫；但這幾欄實際上都是中文，
# 中文字沒有大小寫之分，轉換沒有任何視覺影響，只有極少數會打英文暱稱的情況才會受到
# 影響，權衡下這個代價可以接受。
components.html(
    """
    <script>
    (function() {
        function getDoc() {
            try { return window.parent.document; } catch (e) { return null; }
        }
        function applyUppercase(el) {
            const proto = el.tagName === 'TEXTAREA' ? window.parent.HTMLTextAreaElement.prototype : window.parent.HTMLInputElement.prototype;
            const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
            const start = el.selectionStart;
            const end = el.selectionEnd;
            const upper = el.value.toUpperCase();
            if (upper === el.value) return;
            setter.call(el, upper);
            try { el.setSelectionRange(start, end); } catch (e) {}
            el.dispatchEvent(new Event('input', {bubbles: true}));
        }
        function watch(el) {
            if (el.dataset.upperWatch) return;
            // 有 aria-label 的是 Streamlit 正式元件（帳號/密碼/提示語等），不要碰，
            // 只處理沒有 aria-label 的表格內部通用編輯框。
            if (el.getAttribute('aria-label')) return;
            el.dataset.upperWatch = '1';
            el.addEventListener('input', function() { applyUppercase(el); });
            applyUppercase(el);
        }
        function scan(doc) {
            doc.querySelectorAll('input[type="text"], textarea').forEach(watch);
        }
        function attach() {
            const doc = getDoc();
            if (!doc || doc.__adminUpperAttached) return;
            doc.__adminUpperAttached = true;
            const observer = new doc.defaultView.MutationObserver(function() { scan(doc); });
            observer.observe(doc.body, {childList: true, subtree: true});
            scan(doc);
        }
        attach();
        const doc0 = getDoc();
        if (doc0 && doc0.defaultView && !doc0.__adminUpperInterval) {
            doc0.__adminUpperInterval = true;
            doc0.defaultView.setInterval(attach, 800);
        }
    })();
    </script>
    """,
    height=0,
)

def _cell_text(value) -> str:
    """把表格儲存格的值轉成乾淨字串。空儲存格轉成字串後可能是 "None"／"nan" 這種
    非空字面字串（例如 pandas 的 NaN 用 str() 轉型會變成 "nan"；data_editor 新增列
    未填的儲存格實測會是 Python None，str() 轉型變成 "None"），直接看字串是否為空
    會誤判成「有填」，讓空白列被當成正常資料存進資料庫——這是「按 + 多留一列空白列
    存檔，卻被當成新員工插入」這個問題的根本原因。要先用 pd.isna() 擋一次，字串轉型
    後再擋一次常見的「空值轉字串」字樣，兩層都擋才保險。"""
    if pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() in ("none", "nan", "<na>") else text


if st.button("儲存員工資料變更", type="primary"):
    original_ids = set(original_df["id"])
    edited_ids = set(edited_df["id"].dropna())
    removed_ids = original_ids - edited_ids

    conn = database.get_connection()
    try:
        for _, row in edited_df.iterrows():
            department = _cell_text(row["單位"])
            employee_id = _cell_text(row["員工編號"]).upper() or None
            name = _cell_text(row["姓名"])
            title = _cell_text(row["職務"]) or None
            is_active = bool(row["在職"])
            row_id = row["id"]

            if not department and not name and pd.isna(row_id):
                # 按「+」多留的空白列，沒填任何東西就直接存檔——不當成新增，靜默略過。
                continue

            if not department or not name:
                raise ValueError("單位與姓名為必填欄位，請確認每一列都已填寫。")

            if pd.isna(row_id):
                database.insert_employee(conn, department, employee_id, name, title, is_active)
            else:
                database.update_employee(conn, int(row_id), department, employee_id, name, title, is_active)

        # 表格裡被移除的列：只有「本來就是空白列」（沒有單位也沒有姓名——例如前面那個
        # 舊 bug 不小心存進去的空白列）才真的從資料庫刪除；已經有真實姓名/單位的員工列
        # 一律不允許從這裡刪除，改用「在職」核取欄位停用，避免誤刪還在職或報支紀錄
        # 對得上的同仁資料。
        real_removed_ids: list[int] = []
        blank_removed_ids: list[int] = []
        if removed_ids:
            original_by_id = {r["id"]: r for _, r in original_df.iterrows()}
            for rid in removed_ids:
                orow = original_by_id.get(rid)
                is_blank = orow is not None and not str(orow["單位"]).strip() and not str(orow["姓名"]).strip()
                (blank_removed_ids if is_blank else real_removed_ids).append(rid)
            for rid in blank_removed_ids:
                database.delete_employee(conn, int(rid))

        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
        st.error("儲存失敗：員工編號重複，請確認每個員工編號只對應一位同仁。")
    except ValueError as e:
        conn.rollback()
        st.error(f"儲存失敗：{e}")
    else:
        messages = []
        if real_removed_ids:
            messages.append((
                "warning",
                f"偵測到 {len(real_removed_ids)} 筆資料在表格中被移除，但系統不允許刪除員工資料，"
                "這些同仁的紀錄仍保留在資料庫中；如需停用請改用「在職」核取欄位。",
            ))
        if blank_removed_ids:
            messages.append(("success", f"已刪除 {len(blank_removed_ids)} 筆空白列。"))
        messages.append(("success", "已儲存"))
        st.session_state["admin_flash_messages"] = messages
        # 表格元件（key="employee_editor"）自己在瀏覽器端記著使用者按「+」加過的列，
        # 就算存檔時被我們判定是空白列而略過（沒有真的寫進資料庫），沒清掉這份本地
        # 暫存狀態的話，畫面上那列空白列還是會一直卡在那裡、揮之不去，看起來像
        # 「怎麼存檔了還在」。存檔成功後把這個 key 清掉，逼表格下一輪重新整理時
        # 完全依照資料庫目前的真實內容重畫，不會殘留任何本地暫存的空白列。
        st.session_state.pop("employee_editor", None)
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
    new_shared_password_confirm = st.text_input("再輸入一次新密碼", type="password", key="new_shared_password_confirm")
    submit_shared = st.form_submit_button("更新統一登入密碼")
if submit_shared:
    if not new_shared_password:
        st.error("請輸入新密碼")
    elif new_shared_password != new_shared_password_confirm:
        st.error("兩次輸入的新密碼不一致，請重新輸入。")
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
    new_admin_password_confirm = st.text_input("再輸入一次新密碼", type="password", key="new_admin_password_confirm")
    new_hint = st.text_input("密碼提示語", value=current_hint, key="new_admin_hint")
    submit_admin = st.form_submit_button("更新管理員密碼／提示語")
if submit_admin and new_admin_password and new_admin_password != new_admin_password_confirm:
    st.error("兩次輸入的新密碼不一致，請重新輸入。")
elif submit_admin:
    conn = database.get_connection()
    try:
        if new_admin_password:
            database.set_setting(conn, "admin_password_hash", auth.hash_password(new_admin_password))
        database.set_setting(conn, "admin_password_hint", new_hint)
    finally:
        conn.close()
    st.success("管理員密碼設定已更新")
