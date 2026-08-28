"""
版本：20260826-FEATURE-BATCH-UPDATE
更新內容：新增 read_meal_region_rates()——動態讀取「餐費核銷明細」分頁的地區別/幣別/
早午晚餐對照表（不寫死費率數字，公司以後調整費率不用改程式），供雜費津貼/餐費自動計算用。

讀取範本：確認請款月份、比對表頭標籤、找下一個可寫列、找退（補）款金額儲存格、
讀取餐費地區費率對照表。

只做讀取與校驗，不修改任何內容 —— 真正寫入交給 excel_writer.py。
"""
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal

import xlrd

import config
from excel_utils import cell_ref_to_rc, col_index_to_letter


@dataclass
class LayoutWarning:
    label: str
    expected_column: str
    detected_column: str


@dataclass
class LayoutDetectionResult:
    layout: config.ColumnLayout
    warnings: list[LayoutWarning]
    missing_labels: list[str]


def open_workbook(path_or_bytes) -> xlrd.Book:
    if isinstance(path_or_bytes, (bytes, bytearray)):
        return xlrd.open_workbook(file_contents=bytes(path_or_bytes), formatting_info=True)
    return xlrd.open_workbook(path_or_bytes, formatting_info=True)


def get_main_sheet(wb: xlrd.Book):
    return wb.sheet_by_name(config.MAIN_SHEET_NAME)


def find_exchange_rate_sheet_name(wb: xlrd.Book) -> str | None:
    for name in wb.sheet_names():
        if name.endswith(config.EXCHANGE_RATE_SHEET_NAME_SUFFIX):
            return name
    return None


def read_billing_month(sheet) -> datetime | None:
    row, col = cell_ref_to_rc(config.HEADER_CELLS["billing_month"])
    cell = sheet.cell(row, col)
    if cell.ctype == xlrd.XL_CELL_DATE:
        return xlrd.xldate.xldate_as_datetime(cell.value, 0)
    if isinstance(cell.value, (int, float)) and cell.value > 0:
        try:
            return xlrd.xldate.xldate_as_datetime(cell.value, 0)
        except Exception:
            return None
    return None


def detect_layout(sheet) -> LayoutDetectionResult:
    """掃描表頭列文字，確認實際欄位字母跟 config.DEFAULT_LAYOUT 是否一致。"""
    start_row, end_row = config.HEADER_LABEL_SEARCH_ROWS
    found: dict[str, str] = {}  # label -> column letter

    for row_1indexed in range(start_row, end_row + 1):
        row = row_1indexed - 1
        for col in range(sheet.ncols):
            value = sheet.cell_value(row, col)
            if isinstance(value, str):
                text = value.strip()
                if text in config.HEADER_LABEL_MAP and text not in found:
                    found[text] = col_index_to_letter(col)

    warnings: list[LayoutWarning] = []
    missing: list[str] = []
    layout_kwargs = {}

    for label, attr_name in config.HEADER_LABEL_MAP.items():
        expected_column = getattr(config.DEFAULT_LAYOUT, attr_name)
        detected_column = found.get(label)
        if detected_column is None:
            missing.append(label)
            continue
        if detected_column != expected_column:
            warnings.append(LayoutWarning(label=label, expected_column=expected_column, detected_column=detected_column))
        layout_kwargs[attr_name] = detected_column

    layout = replace(config.DEFAULT_LAYOUT, **layout_kwargs) if layout_kwargs else config.DEFAULT_LAYOUT
    return LayoutDetectionResult(layout=layout, warnings=warnings, missing_labels=missing)


def find_next_empty_row(sheet, layout: config.ColumnLayout) -> int | None:
    """回傳下一個可寫列（1-indexed）。若整個範圍都滿了回傳 None。

    只看「說明」欄：空白格代表可寫；空白範本的第15列會預先放一筆「範例」示範資料
    （日期/金額等欄位都非空，但說明欄是固定文字「範例」），視同可覆寫，不當作已使用。
    """
    from excel_utils import col_letter_to_index

    desc_col = col_letter_to_index(layout.desc)
    start_row, end_row = config.DATA_ROW_RANGE

    for row_1indexed in range(start_row, end_row + 1):
        row = row_1indexed - 1
        desc_val = sheet.cell_value(row, desc_col)
        is_available = desc_val in ("", None) or (
            isinstance(desc_val, str) and desc_val.strip() == "範例"
        )
        if is_available:
            return row_1indexed
    return None


@dataclass
class RefundCell:
    label_row: int  # 0-indexed
    label_col: int
    amount_row: int
    amount_col: int
    currency_col: int


def find_refund_amount_cell(sheet) -> RefundCell | None:
    """標籤比對找『退(補)款金額』這一列，回傳金額實際所在的儲存格位置。

    已用 2_已核准範例 核對：標籤在 AA48（文字含「退」與「金額」），
    幣別在 AB48，金額在 AC48 —— 標籤欄往右數兩欄。不寫死座標，一律搜尋。
    """
    for row in range(sheet.nrows):
        for col in range(sheet.ncols):
            value = sheet.cell_value(row, col)
            if isinstance(value, str) and config.REFUND_LABEL_TEXT in value and "金額" in value:
                currency_col = col + 1
                amount_col = col + config.REFUND_AAMOUNT_COLUMN_OFFSET
                return RefundCell(
                    label_row=row, label_col=col,
                    amount_row=row, amount_col=amount_col,
                    currency_col=currency_col,
                )
    return None


@dataclass
class MealRegionRate:
    currency: str
    breakfast: Decimal
    lunch: Decimal
    dinner: Decimal


def read_meal_region_rates(wb: xlrd.Book) -> dict[str, MealRegionRate]:
    """讀取「餐費核銷明細」分頁的地區別/幣別/早午晚餐對照表（用標籤搜尋，不寫死座標，
    已用 reference_files 兩份參考檔案核對：三個地區「美歐」「亞洲」「大陸子公司」都在
    表頭「地區別」那一列往下的連續幾列）。"""
    sheet = wb.sheet_by_name(config.MEAL_DETAIL_SHEET_NAME)

    header_row = None
    header_col = None
    for row in range(sheet.nrows):
        for col in range(sheet.ncols):
            if sheet.cell_value(row, col) == "地區別":
                next_val = sheet.cell_value(row, col + 1) if col + 1 < sheet.ncols else None
                if isinstance(next_val, str) and "幣別" in next_val:
                    header_row, header_col = row, col
                    break
        if header_row is not None:
            break

    if header_row is None:
        raise ValueError("在「餐費核銷明細」分頁找不到「地區別/幣別」對照表表頭")

    rates: dict[str, MealRegionRate] = {}
    row = header_row + 1
    while row < sheet.nrows:
        region = sheet.cell_value(row, header_col)
        if not region or not isinstance(region, str):
            break
        currency = sheet.cell_value(row, header_col + 1)
        breakfast = sheet.cell_value(row, header_col + 2)
        lunch = sheet.cell_value(row, header_col + 3)
        dinner = sheet.cell_value(row, header_col + 4)
        rates[region] = MealRegionRate(
            currency=currency,
            breakfast=Decimal(str(breakfast)),
            lunch=Decimal(str(lunch)),
            dinner=Decimal(str(dinner)),
        )
        row += 1

    return rates
