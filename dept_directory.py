"""
從 GitHub 倉庫內的清單檔案（department_staff.csv）讀取「部門 -> 人員」對照表，
取代原本寫死在 app.py 裡的 dept_options / NAME_MAP。清單檔案跟著程式碼一起放在
repo 裡，雲端部署上才讀得到（做法參考「出差報銷」工具的 employee_directory.py）。

清單檔案不存在、格式錯誤等任何問題都靜默回傳空字典，由呼叫端 (app.py) 改用
「自己填寫」的手動輸入模式，不會讓表單掛掉或跳出錯誤訊息。
"""
import csv

DEFAULT_LIST_PATH = "department_staff.csv"

_CSV_COLUMNS = {
    "department": "部門",
    "nickname": "暱稱",
    "real_name": "姓名",
}

# 使用者可能用 Excel 維護這份清單，存檔時容易不小心選到舊版「CSV（逗號分隔）」
# （Windows 地區編碼，繁體中文環境是 cp950/Big5）而不是「CSV UTF-8」，依序都試一次。
_CANDIDATE_ENCODINGS = ["utf-8-sig", "cp950"]


def load_dept_directory(path: str = DEFAULT_LIST_PATH) -> dict[str, list[tuple[str, str]]]:
    """讀取部門/人員清單 CSV，回傳 {部門: [(暱稱, 姓名), ...]}（依清單原始順序）。
    檔案不存在、編碼錯誤、缺欄位等任何問題都靜默回傳空字典，不拋例外。"""
    for encoding in _CANDIDATE_ENCODINGS:
        try:
            with open(path, encoding=encoding, newline="") as f:
                reader = csv.DictReader(f)
                directory: dict[str, list[tuple[str, str]]] = {}
                for row in reader:
                    dept = (row.get(_CSV_COLUMNS["department"]) or "").strip()
                    nickname = (row.get(_CSV_COLUMNS["nickname"]) or "").strip()
                    real_name = (row.get(_CSV_COLUMNS["real_name"]) or "").strip()
                    if not dept or not nickname:
                        continue
                    directory.setdefault(dept, []).append((nickname, real_name or nickname))
            return directory
        except (OSError, UnicodeDecodeError):
            continue
        except Exception:
            return {}
    return {}
