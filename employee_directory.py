"""
版本：20260827-UX-FIXES-ROUND15
更新內容：find_match() 比對員工編號時不分大小寫（by_id 的 key 統一存大寫，查詢字串也
轉大寫再比對）——使用者反應輸入小寫員工編號比對不到；姓名是中文不受影響，維持原樣。

---（以下為 ROUND12 紀錄）---
讀取清單時依序嘗試 utf-8-sig／cp950 兩種編碼——使用者用 Excel 維護這份清單，
存檔時很容易不小心選到舊版「CSV（逗號分隔）」（Windows 地區編碼）而不是「CSV UTF-8」，
之前只認 UTF-8，選錯格式就會讓自動帶入整個靜默失效，改成兩種編碼都試，減少這種存檔
格式選錯造成的困擾。

---（以下為 ROUND11 紀錄）---
新增此檔案。Step 1 員工資訊自動帶入——維護一份員工清單（員工編號/姓名/單位/
職務），使用者輸入員工編號或姓名時，如果清單裡找得到，自動帶出其餘欄位，不用每次都
重新打一遍。清單檔案（employees.csv）不存在、編碼錯誤、缺欄位等任何問題都完全靜默
略過，Step 1 不會顯示任何錯誤——這是「錦上添花」的輔助功能，不能因為清單檔案維護不到位
或還沒建立，就擋住整個表單的正常使用。

清單存成 CSV 放在 GitHub 倉庫裡（跟程式碼一起管理，這樣雲端部署上才讀得到），已取得
使用者同意；repo 本身必須維持 Private，避免同仁的員工編號/姓名等資料外流。
"""
import csv

DEFAULT_EMPLOYEE_LIST_PATH = "employees.csv"

_CSV_COLUMNS = {
    "employee_id": "員工編號",
    "employee_name": "姓名",
    "department": "單位",
    "title": "職務",
}


# 使用者用 Excel 維護這份清單，存檔時很容易不小心選到舊版「CSV（逗號分隔）」
# （Windows 系統的地區編碼，繁體中文環境是 cp950/Big5）而不是「CSV UTF-8（逗號分隔）」，
# 依序都試一次，盡量不要因為存檔格式選錯就讓自動帶入整個失效。
_CANDIDATE_ENCODINGS = ["utf-8-sig", "cp950"]


def load_employee_directory(path: str = DEFAULT_EMPLOYEE_LIST_PATH) -> dict[str, dict[str, dict[str, str]]]:
    """讀取員工清單 CSV，回傳依員工編號、依姓名分別查詢的兩個對照表：
    {"by_id": {員工編號: 資料}, "by_name": {姓名: 資料}}。
    檔案不存在、編碼錯誤、缺欄位等任何問題都靜默回傳空字典，不拋例外。"""
    for encoding in _CANDIDATE_ENCODINGS:
        try:
            with open(path, encoding=encoding, newline="") as f:
                reader = csv.DictReader(f)
                by_id: dict[str, dict[str, str]] = {}
                by_name: dict[str, dict[str, str]] = {}
                for row in reader:
                    entry = {key: (row.get(column) or "").strip() for key, column in _CSV_COLUMNS.items()}
                    if entry["employee_id"]:
                        # key 統一存大寫，比對時查詢字串也轉大寫（見 find_match），這樣使用者
                        # 輸入員工編號不論大小寫都能比對到；entry 裡實際存的 employee_id
                        # 還是清單原始大小寫，帶回欄位時顯示不會被強制變成大寫。
                        by_id[entry["employee_id"].upper()] = entry
                    if entry["employee_name"]:
                        by_name[entry["employee_name"]] = entry
            return {"by_id": by_id, "by_name": by_name}
        except (OSError, UnicodeDecodeError):
            continue
        except Exception:
            return {"by_id": {}, "by_name": {}}
    return {"by_id": {}, "by_name": {}}


def find_match(directory: dict, employee_id: str, employee_name: str) -> dict[str, str] | None:
    """依員工編號或姓名（任一個在清單裡找得到就算）找出對應資料，都找不到回傳 None。
    員工編號優先比對，因為編號比姓名更不容易撞名。員工編號是英文字母＋數字，比對時
    不分大小寫（使用者可能習慣打小寫），姓名是中文不受影響。"""
    if employee_id and employee_id.upper() in directory.get("by_id", {}):
        return directory["by_id"][employee_id.upper()]
    if employee_name and employee_name in directory.get("by_name", {}):
        return directory["by_name"][employee_name]
    return None
