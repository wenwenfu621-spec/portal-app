"""
版本：20260827-UX-FIXES-ROUND10
更新內容：
1. 修正支出憑單／餐費核銷明細的日期格式 bug——先前這兩個分頁的日期欄位都直接借用
   「主表」申請日期儲存格的格式字串，但範本裡不同分頁的日期顯示樣式本來就不一樣
   （例如主表是 8/27/26，支出憑單是完整的「2026年8月27日」），借用主表格式會讓這兩個
   分頁的日期顯示變得跟範本原本不同。改成每個分頁各自讀自己原本的日期格式。
2. 新增 _sanitize_number_format()，修正兩種已知會讓日期顯示跑掉的格式代碼問題：
   (a) Excel 內建格式14「簡短日期」的實際顯示樣式是跟著開啟者的系統地區設定變動的，
       xlrd 對這個內建代碼固定回報美式寫法「m/d/yy」，照抄會讓輸出檔案顯示成美式日期，
       跟範本在使用者（台灣地區設定）電腦上原本顯示的「yyyy/m/d」不一樣——這正是主表
       申請日期先前顯示成「8/27/26」而不是「2026/8/27」的根因。
   (b) 格式字串帶有 [$-404] 這種地區代碼標籤語法（用來讓星期幾縮寫顯示中文），
       LibreOffice 透過 UNO 的 addNew() 直接重新套用會拋出
       MalformedNumberFormatException（已用測試腳本驗證），拿掉地區標籤、保留其餘
       格式代碼即可——這是餐費核銷明細的日期欄位先前顯示出「2026/4/12[$-404]週日」
       這種帶有原始語法字元的怪異文字的根因。
3. 新增「申請人」欄位（餐費核銷明細分頁 B4）寫入——範本原本是空白提示文字，之前完全
   沒有填。

---（以下為 ROUND3 紀錄）---
1. ColumnLayout 新增 X 欄（total_currency）寫入——這欄範本裡是寫死的示範文字不是公式，
   每列要跟著實際幣別一起寫，否則「合計」旁邊會顯示範本原本對不上的示範幣別代碼。
2. 修正「餐費核銷明細」多筆同批寫入時的列衝突——原本每一筆都重新對原始範本查一次
   「下一個空白列」，同一批多筆全部查到同一列、只有最後一筆存活；改成整批只查一次
   起始列，其餘依序往下排。
3. 新增 legacy_buggy_limit_formula_rows 傳給 worker，讓它修正範本第15~18列既有的
   「限額」公式缺陷（詳見 libreoffice_worker.py 的說明，已取得使用者授權）。

---（以下為先前版本紀錄）---
**改用 LibreOffice 取代 Windows 專屬的 Excel COM 自動化**——原本的做法只能在
裝了 Windows + Microsoft Excel 的電腦上執行，使用者要把這個工具部署到 Streamlit Cloud
（Linux 雲端環境，沒有 Windows 也沒有 Excel）時完全跑不起來。LibreOffice 可以安裝在
Linux 雲端主機上（Streamlit Cloud 用 packages.txt 指定 apt 套件），概念上沿用同一招：
叫真正的辦公軟體來操作儲存格，不要自己重新序列化整份檔案，這樣公式才不會被破壞（已用
「故意改金額、確認退補金額真的會跟著變」的方式對 LibreOffice 重新驗證過一次，見
tests/test_regression_202604.py 的 test_regression_detects_changed_input）。

技術路線：這支檔案（一般 venv 的 Python）只負責組出「要在哪個分頁的哪個儲存格寫什麼值」
的操作清單（跟以前一樣，商業邏輯完全沒變），實際動手寫入的工作透過 subprocess 交給
libreoffice_worker.py 執行——那支程式必須用 LibreOffice 自帶的 Python 執行，因為只有
它才 import 得到 `uno`（LibreOffice 的程式化操作介面）。兩邊透過一個 JSON 檔案傳遞
「操作清單」，回傳結果也透過 JSON 檔案傳回來。

已知的格式差異（跟先前的 Excel COM 版本比較）：LibreOffice 重新存檔時，沒被我們寫入的
儲存格，其數字格式代碼字串可能被它自己的匯出邏輯重新詮釋（例如框線顏色索引從「自動」
展開成明確索引值），視覺上通常等價；我們自己寫入的日期欄位，会在寫入後明確重新指定
從範本讀到的原始格式字串，強制蓋掉 LibreOffice 的猜測。
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from datetime import date as date_type
from datetime import datetime

import config
import excel_reader
from excel_utils import cell_ref_to_rc
from models import ExpenseRow, MealDetailEntry, TripHeader

_JOB_LOCK = threading.Lock()

_EXCEL_EPOCH = date_type(1899, 12, 30)


class ExcelWriteError(Exception):
    pass


class TemplateLayoutError(ExcelWriteError):
    pass


class TooManyRowsError(ExcelWriteError):
    pass


class RefundCellNotFoundError(ExcelWriteError):
    pass


class LibreOfficeUnavailableError(ExcelWriteError):
    pass


def _date_to_serial(d: date_type) -> float:
    return float((d - _EXCEL_EPOCH).days)


def _python_can_import_uno(python_path: str) -> bool:
    """實際試跑一次 `import uno`，而不是只檢查路徑存不存在——在 Streamlit Cloud 這種
    環境，`shutil.which("python3")`／PATH 上第一個 python3 常常是我們這個 app 自己的
    venv（跑這支程式本身用的那個），跟 apt 裝 python3-uno 時註冊 uno 模組的「系統」
    python3 是兩個不同的直譯器，只看路徑或 which 結果會誤判，必須實際 import 一次確認。
    """
    try:
        result = subprocess.run(
            [python_path, "-c", "import uno"],
            capture_output=True, timeout=15,
        )
        return result.returncode == 0
    except Exception:
        return False


def _find_soffice_and_python() -> tuple[str, str]:
    """找出 soffice 執行檔，以及能 import uno 的 Python 執行檔路徑。優先用環境變數指定
    （方便部署時明確指定路徑，不會被探測覆蓋），否則依平台列出候選路徑，每個都實際
    測試 `import uno` 會不會成功，選第一個真的能用的。

    注意：Windows 版 LibreOffice 安裝程式會附一份自己的 python.exe（內建 uno 模組）；
    但 Streamlit Cloud 這種 Debian/Ubuntu 環境用 apt 裝的 libreoffice 套件不會附自己的
    python，而是要另外裝 python3-uno 這個套件，把 uno 模組註冊進「系統的 python3」，
    所以 Linux 上要找的其實是系統 python3（通常是 /usr/bin/python3），不是我們這個
    Streamlit app 自己所在的 venv python，也不一定是 PATH 上第一個 python3。
    """
    soffice_env = os.environ.get("SOFFICE_PATH")
    python_env = os.environ.get("SOFFICE_PYTHON_PATH")
    if soffice_env and python_env:
        return soffice_env, python_env

    windows_candidates = [
        (r"C:\Program Files\LibreOffice\program\soffice.exe", r"C:\Program Files\LibreOffice\program\python.exe"),
        (r"C:\Program Files (x86)\LibreOffice\program\soffice.exe", r"C:\Program Files (x86)\LibreOffice\program\python.exe"),
    ]
    for soffice_path, python_path in windows_candidates:
        if os.path.exists(soffice_path) and os.path.exists(python_path):
            return soffice_path, python_path

    soffice_candidates = ["/usr/bin/soffice", "/usr/lib/libreoffice/program/soffice", "/opt/libreoffice/program/soffice"]
    soffice_path = next((p for p in soffice_candidates if os.path.exists(p)), None) or shutil.which("soffice")
    if not soffice_path:
        raise LibreOfficeUnavailableError(
            "找不到 LibreOffice（soffice），請安裝 LibreOffice，"
            "或用環境變數 SOFFICE_PATH 明確指定路徑"
        )

    python_candidates = [
        os.path.join(os.path.dirname(soffice_path), "python"),  # LibreOffice 自帶（若有）
        "/usr/lib/libreoffice/program/python",
        "/opt/libreoffice/program/python",
        "/usr/bin/python3",  # Debian/Ubuntu 系統 python3，apt 裝 python3-uno 通常註冊在這
        shutil.which("python3"),
        shutil.which("python"),
    ]
    for python_path in python_candidates:
        if python_path and os.path.exists(python_path) and _python_can_import_uno(python_path):
            return soffice_path, python_path

    raise LibreOfficeUnavailableError(
        "找到 soffice，但試過的 Python 執行檔都 import 不到 uno 模組（需要 LibreOffice "
        "自帶的 Python，或系統 python3 + python3-uno 套件）。請用環境變數 "
        "SOFFICE_PYTHON_PATH 明確指定一個能 import uno 的 Python 路徑"
    )


def _sanitize_number_format(format_key: int, format_str: str | None) -> str | None:
    """有兩種已知會出問題的格式代碼，這裡做修正，其餘原樣照抄：

    1. 內建格式代碼14（Excel 標準「簡短日期」）的實際顯示樣式是跟著開啟者的系統地區
       設定變動的——xlrd 回報這個內建代碼時固定用美式寫法「m/d/yy」，但範本是台灣公司
       用的範本，使用者自己的 Windows Excel（繁體中文地區設定）打開來看到的其實是
       「yyyy/m/d」。照抄 xlrd 給的字串當成「固定格式」寫回去，會讓輸出檔案的日期
       顯示樣式變成美式，跟範本原本在使用者電腦上顯示的樣子不一樣。
    2. 格式字串裡帶有 [$-404] 這種「地區代碼標籤」語法（用來讓星期幾縮寫依地區顯示
       中文），LibreOffice 透過 UNO 的 addNew() 直接重新套用這種語法會拋出
       MalformedNumberFormatException（已用測試腳本驗證過）——只是拿掉地區標籤、
       保留其餘格式代碼，效果完全一樣（這個範本本來就是給台灣地區用的，不需要真的
       做到「隨開啟者的地區設定切換語言」這麼通用）。
    """
    if format_key == 14:
        return "yyyy/m/d"
    if format_str and "[$-" in format_str:
        return re.sub(r"\[\$-[0-9A-Fa-f]+\]", "", format_str)
    return format_str


def _read_number_format(template_bytes: bytes, sheet_name: str, cell_ref: str) -> str | None:
    """從範本讀取指定儲存格目前的數字格式字串（用 xlrd，純讀取不涉及寫入安全問題），
    寫入時會拿這個字串明確覆蓋 LibreOffice 自己重新詮釋出來的格式，確保跟範本一致。"""
    rb = excel_reader.open_workbook(template_bytes)
    sheet = rb.sheet_by_name(sheet_name)
    row, col = cell_ref_to_rc(cell_ref)
    xf_index = sheet.cell_xf_index(row, col)
    xf = rb.xf_list[xf_index]
    fmt = rb.format_map.get(xf.format_key)
    format_str = fmt.format_str if fmt else None
    return _sanitize_number_format(xf.format_key, format_str)


class _OperationBuilder:
    def __init__(self):
        self.operations: list[dict] = []

    def write_string(self, sheet: str, cell: str, value: str):
        self.operations.append({"sheet": sheet, "cell": cell, "type": "string", "value": value})

    def write_number(self, sheet: str, cell: str, value: float):
        self.operations.append({"sheet": sheet, "cell": cell, "type": "number", "value": float(value)})

    def write_date(self, sheet: str, cell: str, value: date_type, format_str: str | None):
        self.operations.append({
            "sheet": sheet, "cell": cell, "type": "date",
            "value": _date_to_serial(value), "format": format_str,
        })

    def write_value(self, sheet: str, cell: str, value, date_format: str | None = None):
        if isinstance(value, date_type) and not isinstance(value, datetime):
            self.write_date(sheet, cell, value, date_format)
        elif isinstance(value, (int, float)):
            self.write_number(sheet, cell, value)
        else:
            self.write_string(sheet, cell, "" if value is None else str(value))


def _write_header(ops: _OperationBuilder, header: TripHeader, date_format: str | None):
    for key in ("employee_id", "employee_name", "department", "title", "trip_reason"):
        ops.write_string(config.MAIN_SHEET_NAME, config.HEADER_CELLS[key], getattr(header, key))
    ops.write_date(config.MAIN_SHEET_NAME, config.HEADER_CELLS["apply_date"], header.apply_date, date_format)


_ROW_DATA_FIELDS = [
    "date", "loc_from", "loc_to", "desc", "no",
    "transport_currency", "transport_amount",
    "lodging_currency", "lodging_amount", "lodging_region", "lodging_days", "lodging_people",
    "misc_allowance_currency", "misc_allowance_amount",
    "meal_currency", "meal_amount",
    "entertainment_currency", "entertainment_amount",
    "other_currency", "other_amount",
    "card_fee_currency", "card_fee_amount",
    "total_currency",
]
# 註：不含 M/N/O（住宿限額/超限計算，屬公式或查表輸出）與 Y/Z/AA（合計金額/匯率/USD 換算，
# 屬公式），這些欄位程式一律不寫入。X（total_currency）例外——範本裡是寫死的示範文字不是
# 公式，所以要跟著清空/改寫，否則會留著範本原本對不上的示範幣別代碼。


def _clear_row_data_columns(ops: _OperationBuilder, row_1indexed: int, layout: config.ColumnLayout):
    for field_name in _ROW_DATA_FIELDS:
        col_letter = getattr(layout, field_name)
        ops.write_string(config.MAIN_SHEET_NAME, f"{col_letter}{row_1indexed}", "")


def _parse_single_date(text: str) -> date_type:
    """支援 '2026/4/8'（doc 慣例格式）與 '2026-04-08'（date.isoformat() 格式）兩種輸入。"""
    parts = [int(p) for p in re.split(r"[/-]", text.strip())]
    year, month, day = parts
    return date_type(year, month, day)


def _write_expense_row(ops: _OperationBuilder, layout: config.ColumnLayout, row_1indexed: int,
                        item: ExpenseRow, seq_no: int, date_format: str | None):
    _clear_row_data_columns(ops, row_1indexed, layout)

    if "~" in item.date_display:
        ops.write_string(config.MAIN_SHEET_NAME, f"{layout.date}{row_1indexed}", item.date_display)
    else:
        ops.write_date(config.MAIN_SHEET_NAME, f"{layout.date}{row_1indexed}", _parse_single_date(item.date_display), date_format)

    if item.loc_from:
        ops.write_string(config.MAIN_SHEET_NAME, f"{layout.loc_from}{row_1indexed}", item.loc_from)
    if item.loc_to:
        ops.write_string(config.MAIN_SHEET_NAME, f"{layout.loc_to}{row_1indexed}", item.loc_to)
    if item.description:
        ops.write_string(config.MAIN_SHEET_NAME, f"{layout.desc}{row_1indexed}", item.description)

    ops.write_number(config.MAIN_SHEET_NAME, f"{layout.no}{row_1indexed}", seq_no)

    currency_field, amount_field = config.CATEGORY_TO_LAYOUT_FIELDS[item.category]
    ops.write_string(config.MAIN_SHEET_NAME, f"{getattr(layout, currency_field)}{row_1indexed}", item.currency)
    ops.write_number(config.MAIN_SHEET_NAME, f"{getattr(layout, amount_field)}{row_1indexed}", float(item.amount))
    ops.write_string(config.MAIN_SHEET_NAME, f"{layout.total_currency}{row_1indexed}", item.currency)

    if item.category == "住宿費":
        if item.lodging_region:
            ops.write_string(config.MAIN_SHEET_NAME, f"{layout.lodging_region}{row_1indexed}", item.lodging_region)
        if item.lodging_days is not None:
            ops.write_number(config.MAIN_SHEET_NAME, f"{layout.lodging_days}{row_1indexed}", item.lodging_days)
        if item.lodging_people is not None:
            ops.write_number(config.MAIN_SHEET_NAME, f"{layout.lodging_people}{row_1indexed}", item.lodging_people)


def _write_meal_detail_entry(ops: _OperationBuilder, row_1indexed: int, entry: MealDetailEntry, date_format: str | None):
    sheet = config.MEAL_DETAIL_SHEET_NAME
    ops.write_date(sheet, f"A{row_1indexed}", entry.date, date_format)
    if entry.location_label:
        ops.write_string(sheet, f"B{row_1indexed}", entry.location_label)
    ops.write_string(sheet, f"Q{row_1indexed}", entry.region)
    ops.write_string(sheet, f"R{row_1indexed}", entry.currency)
    ops.write_number(sheet, f"S{row_1indexed}", float(entry.breakfast))
    ops.write_number(sheet, f"T{row_1indexed}", float(entry.lunch))
    ops.write_number(sheet, f"U{row_1indexed}", float(entry.dinner))
    ops.write_number(sheet, f"V{row_1indexed}", float(entry.total))


def _find_meal_detail_next_row(template_bytes: bytes) -> int:
    """用 xlrd 讀取，找「餐費核銷明細」分頁 Q 欄第一個空白列（跟主表 find_next_empty_row
    邏輯一致，只是換一個分頁/欄位）。"""
    rb = excel_reader.open_workbook(template_bytes)
    sheet = rb.sheet_by_name(config.MEAL_DETAIL_SHEET_NAME)
    start_row, end_row = config.MEAL_DETAIL_DATA_ROW_RANGE
    for row_1indexed in range(start_row, end_row + 1):
        row0, col0 = cell_ref_to_rc(f"Q{row_1indexed}")
        if sheet.cell_value(row0, col0) in ("", None):
            return row_1indexed
    raise TooManyRowsError("餐費核銷明細分頁可寫入的列已經用完，請聯絡會計")


def _validate_before_write(template_bytes: bytes, rows: list[ExpenseRow]):
    rb = excel_reader.open_workbook(template_bytes)
    sheet = excel_reader.get_main_sheet(rb)
    layout_result = excel_reader.detect_layout(sheet)
    if layout_result.missing_labels:
        raise TemplateLayoutError(
            f"範本版本與預期不符，找不到欄位標籤：{layout_result.missing_labels}，請確認範本版本"
        )
    start_row = excel_reader.find_next_empty_row(sheet, layout_result.layout)
    if start_row is None:
        raise TooManyRowsError("本次出差項目已超過本範本上限，請聯絡會計或拆成兩張報支單")
    last_row = config.DATA_ROW_RANGE[1]
    if start_row + len(rows) - 1 > last_row:
        raise TooManyRowsError(
            f"項目數量超過範本可寫入範圍（第{start_row}~{last_row}列），請聯絡會計或拆成兩張報支單"
        )
    return layout_result.layout, start_row


def _run_worker(job: dict) -> None:
    soffice_path, python_path = _find_soffice_and_python()
    job["soffice_path"] = soffice_path

    worker_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "libreoffice_worker.py")

    with _JOB_LOCK:
        fd, job_path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        fd, result_path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        job["result_path"] = result_path
        profile_dir = tempfile.mkdtemp(prefix="lo_profile_")
        job["user_installation_dir"] = profile_dir

        try:
            with open(job_path, "w", encoding="utf-8") as f:
                json.dump(job, f, ensure_ascii=False)

            proc = subprocess.run(
                [python_path, worker_script, job_path],
                capture_output=True, text=True, timeout=120,
            )

            if not os.path.exists(result_path) or os.path.getsize(result_path) == 0:
                raise ExcelWriteError(
                    f"LibreOffice 背景程式沒有正常結束（returncode={proc.returncode}）。"
                    f"stderr: {proc.stderr[-2000:]}"
                )
            with open(result_path, "r", encoding="utf-8") as f:
                result = json.load(f)
            if not result.get("ok"):
                raise ExcelWriteError(f"LibreOffice 寫入失敗：{result.get('error')}")
        finally:
            for p in (job_path, result_path):
                try:
                    os.remove(p)
                except OSError:
                    pass
            shutil.rmtree(profile_dir, ignore_errors=True)


def write_expense_rows(
    template_bytes: bytes,
    header: TripHeader,
    rows: list[ExpenseRow],
    meal_detail_entries: list[MealDetailEntry] | None = None,
    fill_payment_voucher: bool = False,
    destination_plain_name: str = "",
) -> bytes:
    """把 header + rows 寫進範本主表，回傳新的 .xls 檔案 bytes（已重算過公式）。

    不修改任何公式儲存格（第34列以後），不動匯率/住宿標準分頁。
    fill_payment_voucher=True 時，會在寫完主表並重算後，讀取退補金額並回填支出憑單分頁。
    """
    layout, start_row = _validate_before_write(template_bytes, rows)
    # 不同分頁的日期格式不能共用同一個——之前支出憑單的申請日期直接借用主表申請日期的
    # 格式，兩個分頁範本原本的日期顯示樣式根本不一樣（例如主表是 8/27/26，支出憑單是
    # 2026年8月27日），借用主表格式會讓支出憑單的日期顯示變成跟範本原本不同的樣子。
    # 每個分頁各自讀自己原本的格式字串。
    date_format = _read_number_format(template_bytes, config.MAIN_SHEET_NAME, config.HEADER_CELLS["apply_date"])
    voucher_date_format = _read_number_format(
        template_bytes, config.PAYMENT_VOUCHER_SHEET_NAME, config.PAYMENT_VOUCHER_CELLS["apply_date"]
    )
    meal_detail_date_format = _read_number_format(
        template_bytes, config.MEAL_DETAIL_SHEET_NAME, f"A{config.MEAL_DETAIL_DATA_ROW_RANGE[0]}"
    )

    ops = _OperationBuilder()
    _write_header(ops, header, date_format)
    ops.write_string(
        config.MEAL_DETAIL_SHEET_NAME, config.MEAL_DETAIL_APPLICANT_CELL, header.employee_name
    )
    for i, item in enumerate(rows):
        row_1indexed = start_row + i
        seq_no = row_1indexed - config.DATA_ROW_RANGE[0] + 1
        _write_expense_row(ops, layout, row_1indexed, item, seq_no, date_format)

    if meal_detail_entries:
        # 「下一個空白列」只從範本（沒動過的原始檔案）算一次，同一批要寫的多筆
        # 依序往下排在連續列——不能每筆都重新查一次範本，那樣同一批的所有筆都會
        # 查到同一個「空白列」，全部搶著寫同一格，只剩最後一筆存活。
        detail_start_row = _find_meal_detail_next_row(template_bytes)
        detail_end_row = config.MEAL_DETAIL_DATA_ROW_RANGE[1]
        if detail_start_row + len(meal_detail_entries) - 1 > detail_end_row:
            raise TooManyRowsError(
                f"餐費核銷明細分頁可寫入的列不夠（第{detail_start_row}~{detail_end_row}列），請聯絡會計"
            )
        for i, entry in enumerate(meal_detail_entries):
            _write_meal_detail_entry(ops, detail_start_row + i, entry, meal_detail_date_format)

    fd, in_path = tempfile.mkstemp(suffix=".xls")
    os.write(fd, template_bytes)
    os.close(fd)
    fd, out_path = tempfile.mkstemp(suffix=".xls")
    os.close(fd)
    os.remove(out_path)  # worker 會建立這個檔案，先確保不存在殘留內容

    job = {
        "template_path": in_path,
        "output_path": out_path,
        "operations": ops.operations,
        "main_sheet_name": config.MAIN_SHEET_NAME,
        "payment_voucher_sheet_name": config.PAYMENT_VOUCHER_SHEET_NAME,
        "payment_voucher_cells": config.PAYMENT_VOUCHER_CELLS,
        "refund_label_text": config.REFUND_LABEL_TEXT,
        "refund_amount_col_offset": config.REFUND_AAMOUNT_COLUMN_OFFSET,
        "payment_voucher": None,
        "legacy_buggy_limit_formula_rows": list(range(
            config.LEGACY_BUGGY_LIMIT_FORMULA_ROWS[0], config.LEGACY_BUGGY_LIMIT_FORMULA_ROWS[1] + 1
        )),
    }

    if fill_payment_voucher:
        start_str = f"{header.trip_start.year}/{header.trip_start.month}/{header.trip_start.day}" if header.trip_start else ""
        end_str = f"{header.trip_end.year}/{header.trip_end.month}/{header.trip_end.day}" if header.trip_end else ""
        job["payment_voucher"] = {
            "enabled": True,
            "apply_date_value": _date_to_serial(header.apply_date),
            "apply_date_format": voucher_date_format,
            "project_id_text": f"      專案編號： {header.employee_name}",
            "support_desc": f"出差至{destination_plain_name}{start_str}~{end_str}費用",
        }

    try:
        _run_worker(job)
        with open(out_path, "rb") as f:
            return f.read()
    finally:
        for p in (in_path, out_path):
            for _ in range(5):
                try:
                    if os.path.exists(p):
                        os.remove(p)
                    break
                except OSError:
                    time.sleep(0.2)
