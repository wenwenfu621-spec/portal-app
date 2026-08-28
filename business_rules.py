"""
版本：20260826-UX-FIXES-ROUND2
更新內容：check_multiple_misc_allowance() 的提示文字改為指向 app.py 新增的「合併為一筆」
勾選框（之前只出現文字提醒，畫面上卻沒有對應的可操作欄位，使用者無從動作）。

交接文件第4節已驗證的業務規則，提供 UI 複核階段的提示用。

這些都只是「提示」，不會自動改資料——最終欄位內容以使用者在複核畫面確認的為準。
"""
from dataclasses import dataclass
from datetime import date as date_type

from models import ReceiptItem


@dataclass
class RuleHint:
    receipt: ReceiptItem
    message: str


def is_sunday(d: date_type) -> bool:
    return d.weekday() == 6


def check_meal_on_non_sunday(items: list[ReceiptItem]) -> list[RuleHint]:
    """餐費欄位只用在津貼不涵蓋的日子（目前確認的情況是週日），非週日的餐費收據提醒使用者確認。"""
    hints = []
    for item in items:
        if item.category == "餐費" and item.date is not None and not is_sunday(item.date):
            hints.append(RuleHint(
                receipt=item,
                message=f"{item.date} 不是週日，請確認這筆餐費是否真的屬於「津貼不涵蓋的日子」，"
                        f"還是應該併入雜費津貼合計。",
            ))
    return hints


def check_multiple_misc_allowance(items: list[ReceiptItem]) -> list[RuleHint]:
    """雜費津貼通常整趟合計一筆，如果同一趟出差出現多筆雜費津貼收據，提醒使用者是否要合併。"""
    misc_items = [item for item in items if item.category == "雜費津貼"]
    if len(misc_items) <= 1:
        return []
    return [RuleHint(
        receipt=item,
        message="偵測到多筆雜費津貼收據，雜費津貼通常整趟出差合計成一筆填寫，"
                "請在下方「合併為一筆」勾選框確認是否需要合併（合併後日期會填成區間，"
                "如 2026/4/7~2026/4/17；不勾選則維持分開各自一列）。",
    ) for item in misc_items]


def collect_all_hints(items: list[ReceiptItem]) -> list[RuleHint]:
    return check_meal_on_non_sunday(items) + check_multiple_misc_allowance(items)
