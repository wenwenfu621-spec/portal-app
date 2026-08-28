"""
共用 SQLite 資料庫連線與資料表結構（employees、system_settings、sop_documents）。

此檔案原本放在 shared-core repo，靠 Git Submodule 掛進 portal-app；改成直接放在
portal-app 這裡，原因是 Streamlit Community Cloud 的部署流程不支援 Git Submodule
（clone 時不會抓 submodule 內容），部署到雲端會直接在 import 這一步失敗。詳見
auth.py 開頭的說明。
"""
import os
import sqlite3

DEFAULT_DB_PATH = "portal.db"


def get_db_path() -> str:
    """資料庫檔案路徑，預設為目前工作目錄下的 portal.db（實際部署時即 portal-app 根目錄）；
    可用環境變數 PORTAL_DB_PATH 覆寫，方便測試或自訂部署路徑。"""
    return os.environ.get("PORTAL_DB_PATH", DEFAULT_DB_PATH)


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path or get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """建立資料表結構（CREATE TABLE IF NOT EXISTS，可重複執行，不會清掉既有資料）。"""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT UNIQUE,       -- 員工編號，登入帳號；部分同仁尚未取得編號時可為 NULL
            name TEXT NOT NULL,            -- 姓名
            department TEXT NOT NULL,      -- 單位/部門
            title TEXT,                    -- 職務；出差申報使用，私車公用報支不使用，可為 NULL
            is_active INTEGER NOT NULL DEFAULT 1  -- 在職狀態：1=在職，0=已停用（離職不做實體刪除）
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS system_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sop_documents (
            system_key TEXT PRIMARY KEY,   -- 'car_expense' / 'trip_expense'
            filename TEXT NOT NULL,
            content BLOB NOT NULL,
            uploaded_at TEXT NOT NULL
        )
        """
    )
    conn.commit()


def get_setting(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM system_settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        """
        INSERT INTO system_settings (key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (key, value),
    )
    conn.commit()


def find_active_employee_by_employee_id(conn: sqlite3.Connection, employee_id: str) -> sqlite3.Row | None:
    """依員工編號查在職員工（登入用）。已停用（離職）的員工找不到，帳號視同失效。"""
    return conn.execute(
        "SELECT * FROM employees WHERE employee_id = ? AND is_active = 1",
        (employee_id,),
    ).fetchone()


def list_all_employees(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """管理員維護區用：含已停用員工的完整清單。"""
    return conn.execute("SELECT * FROM employees ORDER BY department, name").fetchall()


def update_employee(
    conn: sqlite3.Connection,
    employee_row_id: int,
    department: str,
    employee_id: str | None,
    name: str,
    title: str | None,
    is_active: bool,
) -> None:
    """更新既有員工列（依資料表內部的 id，非員工編號）。不提交，交由呼叫端統一 commit/rollback。"""
    conn.execute(
        "UPDATE employees SET department=?, employee_id=?, name=?, title=?, is_active=? WHERE id=?",
        (department, employee_id, name, title, int(is_active), employee_row_id),
    )


def insert_employee(
    conn: sqlite3.Connection,
    department: str,
    employee_id: str | None,
    name: str,
    title: str | None,
    is_active: bool = True,
) -> None:
    """新增員工列。不提交，交由呼叫端統一 commit/rollback。"""
    conn.execute(
        "INSERT INTO employees (department, employee_id, name, title, is_active) VALUES (?, ?, ?, ?, ?)",
        (department, employee_id, name, title, int(is_active)),
    )


def delete_employee(conn: sqlite3.Connection, employee_row_id: int) -> None:
    """實體刪除一筆員工列（依資料表內部的 id）。只給「整列本來就是空白」的列用
    （例如管理員在資料編輯表按「+」多留一列空白列忘記刪掉）——已經有姓名/單位等
    真實資料的員工列一律不走這個函式，改用 update_employee 把在職狀態設為停用，
    避免刪掉還在職或曾經有報支紀錄同仁的歷史資料。不提交，交由呼叫端統一
    commit/rollback。"""
    conn.execute("DELETE FROM employees WHERE id=?", (employee_row_id,))


def get_sop_document(conn: sqlite3.Connection, system_key: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT filename, content, uploaded_at FROM sop_documents WHERE system_key = ?",
        (system_key,),
    ).fetchone()


def set_sop_document(conn: sqlite3.Connection, system_key: str, filename: str, content: bytes) -> None:
    """上傳新版本 SOP，直接覆蓋舊版本（不保留歷史版本）。"""
    import datetime

    conn.execute(
        """
        INSERT INTO sop_documents (system_key, filename, content, uploaded_at) VALUES (?, ?, ?, ?)
        ON CONFLICT(system_key) DO UPDATE SET
            filename = excluded.filename,
            content = excluded.content,
            uploaded_at = excluded.uploaded_at
        """,
        (system_key, filename, content, datetime.datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit()
