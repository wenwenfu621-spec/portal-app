"""
版本：20260826-FEATURE-BATCH-UPDATE
更新內容：新增此檔案。Step 1 填完出差起訖日期與出差地後，不需要上傳收據、不經過 Gemini
辨識，直接依規則算出「雜費津貼」（整趟合計一筆）與「餐費」（範圍內每個星期日各一筆，
金額依範本「餐費核銷明細」分頁當下的地區費率動態計算）。
"""
from datetime import date as date_type
from datetime import timedelta
from decimal import Decimal

import config
from excel_reader import MealRegionRate
from models import ExpenseRow, MealDetailEntry, TripHeader


def _date_display(d: date_type) -> str:
    return f"{d.year}/{d.month}/{d.day}"


def destination_plain_name(header: TripHeader) -> str:
    """支出憑單用的純中文地名（不含代號）。"""
    if header.destination_code and header.destination_code != "Other":
        dest = config.DESTINATIONS.get(header.destination_code)
        return dest.plain_name if dest else ""
    return header.destination_custom_name or ""


def destination_name_with_code(header: TripHeader) -> str:
    """雜費津貼/餐費說明欄用的地名（例如「昆山ESK」）。"""
    if header.destination_code and header.destination_code != "Other":
        dest = config.DESTINATIONS.get(header.destination_code)
        return dest.name_with_code if dest else ""
    return header.destination_custom_name or ""


def destination_meal_region(header: TripHeader) -> str | None:
    if header.destination_code and header.destination_code != "Other":
        dest = config.DESTINATIONS.get(header.destination_code)
        return dest.meal_region if dest else None
    if header.destination_code == "Other":
        return header.destination_region
    return None


def _misc_allowance_rate(header: TripHeader) -> tuple[str, Decimal] | tuple[None, None]:
    if header.destination_code and header.destination_code != "Other":
        dest = config.DESTINATIONS.get(header.destination_code)
        if dest:
            return dest.misc_currency, dest.misc_daily_amount
    elif header.destination_code == "Other" and header.destination_region:
        return config.OTHER_MISC_DAILY_RATES.get(header.destination_region, (None, None))
    return None, None


def generate_misc_allowance_row(header: TripHeader) -> ExpenseRow | None:
    """整趟出差合計一筆雜費津貼：天數 × 日額。缺起訖日期或出差地時回傳 None。"""
    if not (header.trip_start and header.trip_end):
        return None
    days = (header.trip_end - header.trip_start).days + 1
    if days <= 0:
        return None
    currency, daily_amount = _misc_allowance_rate(header)
    if currency is None:
        return None

    start_label = f"{header.trip_start.month}/{header.trip_start.day}"
    end_label = f"{header.trip_end.month}/{header.trip_end.day}"
    return ExpenseRow(
        category="雜費津貼",
        date_display=f"{_date_display(header.trip_start)}~{_date_display(header.trip_end)}",
        currency=currency,
        amount=daily_amount * days,
        description=f"出差雜費津貼{start_label}~{end_label}(共{days}天)",
    )


def generate_meal_items(
    header: TripHeader,
    region_rates: dict[str, MealRegionRate],
) -> tuple[list[ExpenseRow], list[MealDetailEntry]]:
    """出差範圍內每個星期日各產生一筆餐費：一份給主表用的 ExpenseRow，
    一份給「餐費核銷明細」分頁用的 MealDetailEntry（兩者金額/幣別一致）。
    地區費率從範本本身動態讀取（見 excel_reader.read_meal_region_rates），不寫死。
    """
    if not (header.trip_start and header.trip_end):
        return [], []
    region = destination_meal_region(header)
    if not region or region not in region_rates:
        return [], []

    rate = region_rates[region]
    total = rate.breakfast + rate.lunch + rate.dinner
    location_label = destination_name_with_code(header)

    expense_rows: list[ExpenseRow] = []
    detail_entries: list[MealDetailEntry] = []

    current = header.trip_start
    while current <= header.trip_end:
        if current.weekday() == 6:  # Monday=0 ... Sunday=6
            expense_rows.append(ExpenseRow(
                category="餐費",
                date_display=_date_display(current),
                currency=rate.currency,
                amount=total,
                description=f"出差至{location_label}餐費一天",
            ))
            detail_entries.append(MealDetailEntry(
                date=current,
                region=region,
                currency=rate.currency,
                breakfast=rate.breakfast,
                lunch=rate.lunch,
                dinner=rate.dinner,
                total=total,
                location_label=location_label,
            ))
        current += timedelta(days=1)

    return expense_rows, detail_entries
