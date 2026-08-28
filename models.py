"""
版本：20260826-FEATURE-BATCH-UPDATE
更新內容：ReceiptItem 新增 raw_bytes（保留原始收據檔案內容），供 Word 明細清單改版後
把收據原圖貼進文件用；docx_generator 之前只用檔名列表，現在需要實際檔案內容才能嵌圖。
"""
from dataclasses import dataclass, field
from datetime import date as date_type
from decimal import Decimal
from typing import Optional


@dataclass
class TripHeader:
    employee_id: str
    employee_name: str
    department: str
    title: str
    trip_reason: str
    apply_date: date_type
    trip_start: Optional[date_type] = None
    trip_end: Optional[date_type] = None
    destination_code: Optional[str] = None  # ESK/ESC/EMJ/ESV/EST/ESM/ESH/Other
    destination_custom_name: Optional[str] = None  # destination_code == "Other" 時使用者輸入的地名
    destination_region: Optional[str] = None  # destination_code == "Other" 時選的 美歐/亞洲


@dataclass
class ReceiptItem:
    source_filename: str
    category: str  # 交通費 / 住宿費 / 雜費津貼 / 餐費 / 交際費 / 其它
    raw_bytes: bytes = b""  # 原始檔案內容，供 Word 明細清單嵌圖用；系統自動計算的項目留空

    date: Optional[date_type] = None
    date_range_end: Optional[date_type] = None  # 雜費津貼常見「整趟合計」情境

    amount: Optional[Decimal] = None
    currency: Optional[str] = None

    description: str = ""
    location_from: Optional[str] = None
    location_to: Optional[str] = None

    # 住宿費專用（其他科目留空）
    lodging_region: Optional[str] = None  # 美歐 / 亞洲
    lodging_days: Optional[int] = None
    lodging_people: Optional[int] = None

    is_handwritten: bool = False
    confidence: float = 0.0
    confidence_reason: str = ""
    raw_model_response: str = ""

    needs_review: bool = True
    user_confirmed: bool = False


@dataclass
class ExpenseRow:
    """寫入 Excel 前的最終資料列（人工複核確認後，從 ReceiptItem 轉換而來，
    或在回歸測試中直接手動建構）。"""

    category: str
    date_display: str  # 單日 'YYYY/M/D' 或區間 'YYYY/M/D~YYYY/M/D'
    currency: str
    amount: Decimal
    description: str = ""
    loc_from: str = ""
    loc_to: str = ""
    lodging_region: Optional[str] = None
    lodging_days: Optional[int] = None
    lodging_people: Optional[int] = None


@dataclass
class MealDetailEntry:
    """「餐費核銷明細」分頁的一列資料（星期日餐費，Q~V 欄的查表金額）。"""

    date: date_type
    region: str  # 美歐 / 亞洲 / 大陸子公司
    currency: str
    breakfast: Decimal
    lunch: Decimal
    dinner: Decimal
    total: Decimal
    location_label: str = ""
