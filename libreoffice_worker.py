"""
版本：20260827-UX-FIXES-ROUND9
更新內容：加上中文字型替代設定（_ensure_font_substitution_config）——先前的字型保護
機制（見下方 ROUND3 紀錄）在本機 Windows 測試都正常，但實際部署到 Streamlit Cloud
（Linux）後，使用者反映輸出檔案的中文字型（標楷體）整個變成 DejaVu Sans（Linux 預設
字型）。追查發現：本機測試「看起來沒問題」是因為 Windows 本身就有裝標楷體/新細明體，
LibreOffice 找得到字型，不需要替代；但 Linux 伺服器上根本沒有這兩個字型，LibreOffice
存檔時的匯出邏輯會自己決定要換成哪個字型名稱寫進檔案（不是單純顯示層級的替代），這個
決定發生在我們的字型保護程式碼之後，所以先前的機制完全防不住——這是本機測試環境跟
實際部署環境的差異，本機驗證不出這個問題。修法：在啟動 LibreOffice 前，把「標楷體→
AR PL UKai TW」「新細明體→AR PL UMing TW」這類替代規則寫進 fontconfig 設定，並在
packages.txt 加裝 fonts-arphic-ukai / fonts-arphic-uming 這兩個開源中文字型套件，讓
LibreOffice 在 Linux 上也「找得到」範本要求的字型名稱，就不需要自己決定換成什麼。

---（以下為 ROUND3 紀錄）---
1. 新增字型保護——LibreOffice 重新存檔時，偶爾會把完全沒動過的儲存格的字型也重新
   詮釋掉（實測發現過 Tahoma 被換成新細明體），跟數字格式/框線那類良性副作用不同，
   這個是看得出來的視覺變化。做法：開檔後、做任何操作前，先把每個分頁「有內容」的
   儲存格字型（西方/中文/複合字型、大小、粗細、斜體）記下來，存檔前比對一次，只要
   跟原本不一樣就強制改回去，不管 LibreOffice 這次又對哪裡動了手腳都能保證字型不變。
2. 新增 _patch_row1518_limit_formulas()——範本本身第15~18列的「限額」公式（M/N/O欄）
   是舊版寫法，沒有「住宿欄位空白就跳過」的判斷，只要那幾列不是住宿費就會跳 #REF!；
   第19列以後的同一個公式範本自己已經修正過。已取得使用者明確授權，照抄範本自己
   19列以後已經在用、確認沒問題的公式版本，只調整列號，不是發明新邏輯。

---（以下為先前版本紀錄）---
新增此檔案。這支程式**必須用 LibreOffice 內建的 Python 執行**（不是專案的
.venv），因為 `uno`（LibreOffice 的程式化操作介面）只有 LO 自帶的 Python 才有。
excel_writer.py 用 subprocess 呼叫這支程式，透過一個 JSON job 檔案傳入「要寫哪些儲存格」，
這支程式只負責機械式地照做（開檔→依序寫入→強制重算→[選擇性:找退補金額回填支出憑單]→
存成 .xls→關閉），所有「哪個科目該寫哪個欄位」之類的商業邏輯都留在 excel_writer.py
（venv 端，用一般 Python 就能測試，不需要依賴 LibreOffice）。

背景：原本用 Windows 專屬的 Excel COM 自動化，但 Streamlit Cloud 是 Linux 環境，沒有
Windows 也沒有 Excel，無法執行。改用 LibreOffice（可以裝在 Linux 雲端主機上）+ 它的
UNO API，概念上是同一招——叫真正的辦公軟體來操作儲存格，不要自己重新序列化整份檔案，
這樣才能保證公式不會被破壞（已用「故意改金額、確認退補金額真的會跟著變」的方式驗證過）。

已知的差異（跟 Excel COM 比較）：LibreOffice 重新存檔時，部分儲存格的數字格式代碼字串
會被它自己的匯出邏輯重新詮釋（例如日期格式 'm/d/yy' 可能變成 'yyyy/mm/dd'，儲存格框線的
顏色索引可能從「自動」被展開成明確的索引值），值本身與公式都不受影響，只是格式代碼的
「寫法」不同、但視覺上通常等價。針對我們自己寫入的日期欄位，這支程式會在寫入後明確
重新指定原始的數字格式字串，強制蓋掉 LibreOffice 自己的猜測，確保跟範本原本的顯示方式
一致；其餘完全沒動過的儲存格，格式代碼字串可能有這種良性差異，但實測不影響任何視覺效果。
"""
import json
import os
import subprocess
import sys
import time

import uno
from com.sun.star.beans import PropertyValue


def _make_prop(name, value):
    p = PropertyValue()
    p.Name = name
    p.Value = value
    return p


_FONTCONFIG_ALIASES = """<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "fonts.dtd">
<fontconfig>
  <!-- 範本用的中文字型（標楷體、新細明體）是 Windows 內建字型，Linux 伺服器上沒有，
       LibreOffice 找不到時會整個換成別的字型名稱寫進存檔結果，不是單純顯示上的替代——
       用 fontconfig 的 alias 讓「標楷體」「新細明體」這些名字直接對應到伺服器上已經
       裝好、風格相近的開源中文字型（AR PL UKai/UMing，由 fonts-arphic-ukai/uming 這兩個
       套件提供），LibreOffice 找得到字型就不用再幫我們「決定」換成什麼名字，存檔結果
       才能保留範本原本指定的字型名稱。這個檔案只在 Linux 上有意義（Windows 本機開發
       環境本來就有標楷體/新細明體，不需要這個機制）。 -->
  <match target="pattern">
    <test name="family"><string>標楷體</string></test>
    <edit name="family" mode="prepend" binding="strong"><string>AR PL UKai TW</string></edit>
  </match>
  <match target="pattern">
    <test name="family"><string>新細明體</string></test>
    <edit name="family" mode="prepend" binding="strong"><string>AR PL UMing TW</string></edit>
  </match>
  <match target="pattern">
    <test name="family"><string>細明體</string></test>
    <edit name="family" mode="prepend" binding="strong"><string>AR PL UMing TW</string></edit>
  </match>
</fontconfig>
"""


def _ensure_font_substitution_config():
    """把中文字型替代規則寫進使用者層級的 fontconfig 設定檔（~/.fonts.conf），只在
    Linux（Streamlit Cloud）上有意義，Windows 本機開發環境會直接跳過。fontconfig 對
    使用者層級設定檔是「疊加」在系統設定之上，不會蓋掉/影響其他系統字型設定。每次都
    覆寫，成本很低（幾KB的檔案），確保設定一定是最新的。"""
    if os.name != "posix":
        return
    try:
        config_path = os.path.expanduser("~/.fonts.conf")
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(_FONTCONFIG_ALIASES)
    except Exception:
        pass  # 寫失敗就算了，頂多字型還是跟之前一樣被替換，不影響其他功能


def _bootstrap(soffice_path: str, user_installation_dir: str):
    _ensure_font_substitution_config()
    pipe_name = "uno_pipe_" + str(os.getpid()) + "_" + str(int(time.time() * 1000))
    user_install_url = "file:///" + os.path.abspath(user_installation_dir).replace("\\", "/")
    args = [
        soffice_path,
        "--headless", "--invisible", "--nocrashreport", "--nodefault",
        "--norestore", "--nologo", "--nofirststartwizard",
        f"-env:UserInstallation={user_install_url}",
        f"--accept=pipe,name={pipe_name};urp;",
    ]
    proc = subprocess.Popen(args)

    local_context = uno.getComponentContext()
    resolver = local_context.ServiceManager.createInstanceWithContext(
        "com.sun.star.bridge.UnoUrlResolver", local_context
    )
    ctx = None
    last_exc = None
    for _ in range(120):
        try:
            ctx = resolver.resolve(f"uno:pipe,name={pipe_name};urp;StarOffice.ComponentContext")
            break
        except Exception as exc:
            last_exc = exc
            time.sleep(0.5)
    if ctx is None:
        proc.kill()
        raise RuntimeError(f"無法連線到 LibreOffice：{last_exc}")

    smgr = ctx.ServiceManager
    desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    return proc, ctx, desktop, smgr


def _path_to_url(path: str) -> str:
    return "file:///" + os.path.abspath(path).replace("\\", "/").replace(" ", "%20")


def _set_number_format(doc, cell, format_str: str):
    formats = doc.getNumberFormats()
    locale = uno.createUnoStruct("com.sun.star.lang.Locale")
    key = formats.queryKey(format_str, locale, False)
    if key == -1:
        key = formats.addNew(format_str, locale)
    cell.NumberFormat = key


def _apply_operation(doc, sheets_cache: dict, op: dict):
    sheet_name = op["sheet"]
    sheet = sheets_cache.get(sheet_name)
    if sheet is None:
        sheet = doc.Sheets.getByName(sheet_name)
        sheets_cache[sheet_name] = sheet

    op_type = op["type"]
    if op_type == "clear_range":
        rng = sheet.getCellRangeByName(op["range"])
        rng.clearContents(1 + 2 + 4 + 16)  # VALUE+DATETIME+STRING+FORMULA，保留格式與其他分頁不動
        return

    cell = sheet.getCellRangeByName(op["cell"])
    if op_type == "string":
        cell.setString(op["value"])
    elif op_type == "number":
        cell.setValue(float(op["value"]))
    elif op_type == "date":
        cell.setValue(float(op["value"]))
        if op.get("format"):
            _set_number_format(doc, cell, op["format"])
    else:
        raise ValueError(f"未知的操作類型：{op_type}")


_FONT_PROPS = ("CharFontName", "CharFontNameAsian", "CharFontNameComplex", "CharHeight", "CharWeight", "CharPosture")


def _capture_fonts(doc) -> dict:
    """把每個分頁「目前有內容」的儲存格字型設定記下來（寫入操作與 calculateAll 之前）。
    存檔前會拿這份記錄去比對、把任何被 LibreOffice 自己重新詮釋掉的字型強制改回來——
    這是唯二能保證字型 100% 不變的辦法，不用去猜 LibreOffice 這次又對哪個角落動了手腳。"""
    snapshot = {}
    for sheet in doc.Sheets:
        cursor = sheet.createCursor()
        cursor.gotoEndOfUsedArea(False)
        end_col = cursor.RangeAddress.EndColumn
        end_row = cursor.RangeAddress.EndRow
        sheet_name = sheet.Name
        for row in range(0, end_row + 1):
            for col in range(0, end_col + 1):
                cell = sheet.getCellByPosition(col, row)
                if cell.getFormula() == "":
                    continue
                snapshot[(sheet_name, col, row)] = tuple(getattr(cell, p) for p in _FONT_PROPS)
    return snapshot


def _restore_fonts(doc, snapshot: dict):
    for (sheet_name, col, row), values in snapshot.items():
        sheet = doc.Sheets.getByName(sheet_name)
        cell = sheet.getCellByPosition(col, row)
        current = tuple(getattr(cell, p) for p in _FONT_PROPS)
        if current == values:
            continue
        for prop, value in zip(_FONT_PROPS, values):
            setattr(cell, prop, value)


def _patch_row1518_limit_formulas(sheet, rows: list[int]):
    """範本本身第15~18列的「限額」公式是舊版寫法，沒有「住宿欄位空白就跳過」的判斷，
    第19列以後的同一個公式已經修正過。已取得使用者授權，照第19列以後範本自己已經在用
    的公式版本原樣套用到這幾列（只調整列號，沒有發明新邏輯）。只在偵測到還是舊版（沒有
    IF(H..="";...) 判斷）時才覆蓋，避免哪天範本更新後又誤蓋掉。"""
    for row in rows:
        m_cell = sheet.getCellRangeByName(f"M{row}")
        if "IF(H" in m_cell.getFormula():
            continue
        m_cell.setFormula(f'=IF(H{row}="";"";HLOOKUP(H{row};INDIRECT(J{row});2;0))')
        sheet.getCellRangeByName(f"N{row}").setFormula(
            f'=IF(H{row}="";"";HLOOKUP(M{row};INDIRECT(J{row});3;FALSE())*K{row}*L{row})'
        )
        sheet.getCellRangeByName(f"O{row}").setFormula(
            '=IF(H{r}="";"";IF((ROUND(VLOOKUP(H{r};$Y$2:$AA$12;3;FALSE())*I{r}-'
            'VLOOKUP(M{r};$Y$2:$AA$12;3;FALSE())*N{r};0))>0;'
            'ROUND(VLOOKUP(H{r};$Y$2:$AA$12;3;FALSE())*I{r}-'
            'VLOOKUP(M{r};$Y$2:$AA$12;3;FALSE())*N{r};0);0))'.format(r=row)
        )


def _find_refund_cell(sheet, label_text: str, amount_col_offset: int):
    """標籤比對找『退(補)款金額』這一列，回傳 (label_row, label_col, amount_col)（0-indexed）。

    amount_col 不再用「標籤欄 + 固定 offset」算——實測發現「退（補）金額：」標籤儲存格
    在目前範本（202608-V05）是橫向合併 2 欄（AA:AB），導致金額實際落在 AD，比原本假設的
    「標籤+2＝AC」多一欄，取到的是幣別欄（文字）而不是金額，getValue() 對文字儲存格
    回傳 0，這正是使用者回報「支出憑單金額變成 NT$0」的根因（用實際輸出的 .xls 檔案
    直接比對主表 AD48＝5433.4、支出憑單卻寫入 0 才抓到）。改成動態找：從標籤欄往右
    掃到第一個非空儲存格＝幣別欄，幣別欄再往右一欄＝金額欄——不管標籤合併儲存格橫跨
    幾欄，這個相對關係都成立，不用再假設固定欄距。amount_col_offset 參數保留供
    找不到幣別欄時的除錯訊息使用，不再是主要判斷依據。"""
    used = sheet.getCellRangeByName("A1:AC60")
    start_row = used.RangeAddress.StartRow
    end_row = used.RangeAddress.EndRow
    start_col = used.RangeAddress.StartColumn
    end_col = used.RangeAddress.EndColumn
    for r in range(start_row, end_row + 1):
        for c in range(start_col, end_col + 1):
            value = sheet.getCellByPosition(c, r).getString()
            if label_text in value and "金額" in value:
                currency_col = None
                for probe_col in range(c + 1, c + 1 + max(amount_col_offset, 1) + 3):
                    if sheet.getCellByPosition(probe_col, r).getString().strip():
                        currency_col = probe_col
                        break
                amount_col = currency_col + 1 if currency_col is not None else c + amount_col_offset
                return r, c, amount_col
    return None


def run_job(job: dict):
    soffice_path = job["soffice_path"]
    user_install_dir = job["user_installation_dir"]

    proc, ctx, desktop, smgr = _bootstrap(soffice_path, user_install_dir)
    try:
        in_url = _path_to_url(job["template_path"])
        doc = desktop.loadComponentFromURL(in_url, "_blank", 0, (_make_prop("Hidden", True),))
        try:
            font_snapshot = _capture_fonts(doc)

            main_sheet_for_patch = doc.Sheets.getByName(job["main_sheet_name"])
            legacy_rows = job.get("legacy_buggy_limit_formula_rows") or []
            if legacy_rows:
                _patch_row1518_limit_formulas(main_sheet_for_patch, legacy_rows)

            sheets_cache: dict = {}
            for op in job["operations"]:
                _apply_operation(doc, sheets_cache, op)

            doc.calculateAll()

            voucher = job.get("payment_voucher")
            if voucher and voucher.get("enabled"):
                main_sheet = sheets_cache.get(job["main_sheet_name"]) or doc.Sheets.getByName(job["main_sheet_name"])
                found = _find_refund_cell(main_sheet, job["refund_label_text"], job["refund_amount_col_offset"])
                if found is None:
                    raise RuntimeError("找不到「退（補）款金額」標籤儲存格，範本版面可能與預期不符")
                _, _, amount_col = found
                refund_row = found[0]
                refund_amount = main_sheet.getCellByPosition(amount_col, refund_row).getValue()

                voucher_sheet = doc.Sheets.getByName(job["payment_voucher_sheet_name"])
                cells = job["payment_voucher_cells"]
                voucher_sheet.getCellRangeByName(cells["apply_date"]).setValue(float(voucher["apply_date_value"]))
                if voucher.get("apply_date_format"):
                    _set_number_format(doc, voucher_sheet.getCellRangeByName(cells["apply_date"]), voucher["apply_date_format"])
                voucher_sheet.getCellRangeByName(cells["project_id"]).setString(voucher["project_id_text"])
                voucher_sheet.getCellRangeByName(cells["support_desc"]).setString(voucher["support_desc"])
                voucher_sheet.getCellRangeByName(cells["amount"]).setValue(refund_amount)
                # 「小計」（G17）範本本身就是活公式 =SUM(G9:G16)，不能直接 setValue() 覆蓋——
                # 那樣會把公式砍掉、變成寫死的數字，之後在 Excel 裡手動調整 G9 也不會跟著
                # 重算。只寫 G9，讓 G17 自己的 SUM 公式在 doc.calculateAll() 時自然算出來
                # （目前只有 G9 這一列有值，G10:G16 是空的，算出來的結果本來就會跟 G9 相同）。

                doc.calculateAll()

            _restore_fonts(doc, font_snapshot)

            out_url = _path_to_url(job["output_path"])
            doc.storeToURL(out_url, (_make_prop("FilterName", "MS Excel 97"),))
        finally:
            doc.close(False)
    finally:
        try:
            desktop.terminate()
        except Exception:
            pass
        try:
            proc.wait(timeout=15)
        except Exception:
            proc.kill()


def main():
    job_path = sys.argv[1]
    with open(job_path, "r", encoding="utf-8") as f:
        job = json.load(f)
    try:
        run_job(job)
        result = {"ok": True}
    except Exception as exc:
        result = {"ok": False, "error": str(exc)}
    result_path = job["result_path"]
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(result, f)


if __name__ == "__main__":
    main()
