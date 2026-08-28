"""
版本：20260826-UX-FIXES-ROUND3
更新內容：ColumnLayout 新增 total_currency（X 欄）——範本裡這欄其實是寫死的示範文字，
不是公式，寫入時要一併帶入該列實際幣別，否則會留著範本原本對不上的示範幣別代碼。

集中管理欄位座標、科目標籤與各項門檻常數。

所有「魔法座標」只能出現在這裡；excel_reader / excel_writer 一律透過這裡的常數存取儲存格。
"""
from dataclasses import dataclass
from decimal import Decimal

MAIN_SHEET_NAME = "報銷清單-修改"
MEAL_DETAIL_SHEET_NAME = "餐費核銷明細"
PAYMENT_VOUCHER_SHEET_NAME = "支出憑單"
LODGING_STANDARD_SHEET_NAME = "住宿標準"
# 匯率分頁名稱包含年份，跨年會變（例如「2026立帳匯率」），一律用比對找出來，不要寫死。
EXCHANGE_RATE_SHEET_NAME_SUFFIX = "立帳匯率"

# 抬頭欄位（整趟出差通常不變，只有出差事由/申請日期每次不同）
HEADER_CELLS = {
    "employee_id": "B6",
    "employee_name": "D6",
    "department": "I6",
    "title": "R6",
    "trip_reason": "B7",
    "apply_date": "R5",
    "billing_month": "U3",  # 會計已預先填好，程式只讀取確認，不覆寫
}


@dataclass(frozen=True)
class ColumnLayout:
    """主表第15~33列，每欄的意義。欄位字母來源：交接文件第2.2節，並已用
    reference_files/1_空白範本_202608V05.xls 與 2_已核准範例 實際核對過。"""

    date: str = "A"
    loc_from: str = "B"
    loc_to: str = "C"
    desc: str = "D"
    no: str = "E"
    transport_currency: str = "F"
    transport_amount: str = "G"
    lodging_currency: str = "H"
    lodging_amount: str = "I"
    lodging_region: str = "J"       # 美歐 / 亞洲
    lodging_days: str = "K"
    lodging_people: str = "L"
    misc_allowance_currency: str = "P"
    misc_allowance_amount: str = "Q"
    meal_currency: str = "R"
    meal_amount: str = "S"
    entertainment_currency: str = "T"
    entertainment_amount: str = "U"
    other_currency: str = "V"
    other_amount: str = "W"
    card_fee_currency: str = "AB"
    card_fee_amount: str = "AC"
    total_currency: str = "X"       # 「合計」欄旁的幣別，範本裡是寫死的示範文字不是公式，
                                     # 要跟著每列實際填的幣別一起寫，否則會留著範本原本的
                                     # 亂數示範幣別（跟這列實際金額對不上）


DEFAULT_LAYOUT = ColumnLayout()

# 表頭列（第13列，0-indexed row 12）文字 -> layout 屬性名稱，用於 detect_layout() 標籤比對。
HEADER_LABEL_MAP = {
    "交通費": "transport_currency",
    "住宿費": "lodging_currency",
    "雜費津貼": "misc_allowance_currency",
    "餐費": "meal_currency",
    "交際費": "entertainment_currency",
    "其它": "other_currency",
}

CATEGORY_TO_LAYOUT_FIELDS = {
    "交通費": ("transport_currency", "transport_amount"),
    "住宿費": ("lodging_currency", "lodging_amount"),
    "雜費津貼": ("misc_allowance_currency", "misc_allowance_amount"),
    "餐費": ("meal_currency", "meal_amount"),
    "交際費": ("entertainment_currency", "entertainment_amount"),
    "其它": ("other_currency", "other_amount"),
}

CATEGORIES = list(CATEGORY_TO_LAYOUT_FIELDS.keys())

DATA_ROW_RANGE = (15, 33)  # 1-indexed，含頭尾，程式可寫入的資料列範圍
HEADER_LABEL_SEARCH_ROWS = (9, 14)  # 1-indexed，掃描表頭文字的列範圍

# 範本本身的既有 bug：M/N/O（限額/超限USD）欄位在第15~18列用的是舊版公式，沒有
# 「住宿欄位空白就跳過」的判斷（第19列以後的同一個公式已經修正過，有加這個判斷）——
# 只要這4列的住宿欄位是空的（不是住宿費的列），不管是這個工具寫的還是人工在 Excel
# 手動填的，都會跳 #REF!/#N/A，這是範本本身的既有缺陷，不是這個工具造成的。
# 已取得使用者授權（2026-08-26），照第19列以後範本自己已經在用、確認沒問題的公式
# 版本原樣套用到這4列，只是把列號對應調整，沒有發明新邏輯。見 libreoffice_worker.py
# 的 _patch_row1518_limit_formulas()。
LEGACY_BUGGY_LIMIT_FORMULA_ROWS = (15, 18)  # 1-indexed，含頭尾

# 「退（補）款金額」標籤與金額儲存格：已用 2_已核准範例 核對，標籤在 AA48
# （文字為「退(補)款金額：」），幣別在 AB48（NTD），實際金額在 AC48。
# 程式仍應優先用標籤比對定位（見 excel_reader.find_refund_amount_cell），
# 這裡的欄位常數只是「預期值」，用來在找不到標籤時提供除錯參考，不作為預設回退依據。
REFUND_LABEL_TEXT = "退"
REFUND_AAMOUNT_COLUMN_OFFSET = 2  # 從標籤欄往右數兩欄是金額（跳過中間的幣別欄）

CONFIDENCE_THRESHOLD = 0.8

# 範本「幣別」下拉選單實際支援的代碼（已用 reference_files/1_空白範本 的 Y3:Y12 核對），
# 匯率換算公式用這些代碼去 VLOOKUP，打錯字或用 ISO 別名（如人民幣寫成 CNY）會查不到匯率。
VALID_CURRENCIES = ["USD", "MXN", "TWD", "VND", "JPY", "MYR", "RMB", "EUR", "SGD", "GBP"]

# 用 Gemini 而不是付費視覺 API：Gemini API 有免費額度，適合這種內部小工具、
# 多人共用同一組 key 的情境。flash 系列速度快、免費額度內足以應付收據辨識。
GEMINI_MODEL = "gemini-3.6-flash"

# 免費方案的每日額度是「依模型各自獨立計算」的（每個模型一個獨立額度池），且額度本身
# 偏低（gemini-3.6-flash 只有 24 次/天）——多人共用同一組 key 很容易一天就用完。依序
# 嘗試這個清單裡的模型，第一個額度用完/伺服器過載就自動換下一個，不用整批中止等隔天。
# 排序：先用目前驗證過辨識品質沒問題的 gemini-3.6-flash，其餘依新舊排列，lite 系列
# 品質可能較弱，排最後當最後手段。
GEMINI_MODEL_FALLBACK_CHAIN: tuple[str, ...] = (
    GEMINI_MODEL,
    "gemini-3.7-flash",
    "gemini-3.5-flash-lite",
    "gemini-2.5-flash-lite",
)


@dataclass(frozen=True)
class Destination:
    code: str
    plain_name: str        # 支出憑單「出差至{地名}...」用，純中文地名不含代號
    name_with_code: str    # 雜費津貼/餐費說明欄用，例如「昆山ESK」
    meal_region: str       # 美歐 / 亞洲 / 大陸子公司 —— 對應「餐費核銷明細」分頁的地區別
    misc_currency: str     # 雜費津貼幣別
    misc_daily_amount: Decimal  # 雜費津貼日額


# 出差地代號對照表（使用者確認版本）。下拉選單只顯示 code；純中文地名/帶代號地名分別用在
# 支出憑單／雜費津貼與餐費的說明欄位，兩處文字格式不同，不能共用同一組字串。
DESTINATIONS: dict[str, Destination] = {
    "ESK": Destination("ESK", "昆山", "昆山ESK", "大陸子公司", "RMB", Decimal("50")),
    "ESC": Destination("ESC", "煙台", "煙台ESC", "大陸子公司", "RMB", Decimal("50")),
    "EMJ": Destination("EMJ", "馬來西亞", "馬來西亞EMJ", "亞洲", "USD", Decimal("7")),
    "ESV": Destination("ESV", "越南", "越南ESV", "亞洲", "USD", Decimal("7")),
    "EST": Destination("EST", "提華納", "提華納EST", "美歐", "USD", Decimal("30")),
    "ESM": Destination("ESM", "蒙特雷", "蒙特雷ESM", "美歐", "USD", Decimal("30")),
    "ESH": Destination("ESH", "新加坡", "新加坡ESH", "亞洲", "USD", Decimal("10")),
}
DESTINATION_CODES = list(DESTINATIONS.keys()) + ["Other"]
OTHER_DESTINATION_REGIONS = ["美歐", "亞洲"]

# 選 Other 時，雜費津貼日額依使用者選的地區（美歐/亞洲）決定，跟上面 DESTINATIONS 表的
# misc_currency/misc_daily_amount 是同一套邏輯，只是沒有對應到某個特定代號。
OTHER_MISC_DAILY_RATES: dict[str, tuple[str, Decimal]] = {
    "美歐": ("USD", Decimal("30")),
    "亞洲": ("USD", Decimal("10")),
}

# 「餐費核銷明細」分頁：地區對照表用標籤搜尋動態讀取（見 excel_reader.read_meal_region_rates），
# 不寫死費率數字；這裡只固定資料列可寫入範圍（Q~V 欄，第13~78列），以及「申請人」欄位
# （A4標籤旁的 B4，範本原本是空白提示文字，需要填入姓名）。
MEAL_DETAIL_DATA_ROW_RANGE = (13, 78)
MEAL_DETAIL_APPLICANT_CELL = "B4"

# 支出憑單分頁欄位（已用 reference_files 兩份參考檔案核對）。
PAYMENT_VOUCHER_CELLS = {
    "apply_date": "A5",
    "project_id": "A7",       # 整格文字："      專案編號： {姓名}"
    "support_desc": "A9",     # "出差至{純中文地名}{起}~{迄}費用"
    "amount": "G9",
    "subtotal": "G17",
}
