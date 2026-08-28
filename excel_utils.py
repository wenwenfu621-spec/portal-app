"""
版本：20260826-UX-FIXES-UPDATE
更新內容：無邏輯變更，僅補上版本標頭。

共用的儲存格座標轉換工具，excel_reader / excel_writer 都會用到。
"""
import re

_CELL_REF_RE = re.compile(r"^([A-Z]+)(\d+)$")


def col_letter_to_index(letters: str) -> int:
    """'A' -> 0, 'Z' -> 25, 'AA' -> 26 ..."""
    col = 0
    for ch in letters:
        col = col * 26 + (ord(ch) - ord("A") + 1)
    return col - 1


def col_index_to_letter(index: int) -> str:
    """0 -> 'A', 25 -> 'Z', 26 -> 'AA' ..."""
    index += 1
    s = ""
    while index > 0:
        index, r = divmod(index - 1, 26)
        s = chr(65 + r) + s
    return s


def cell_ref_to_rc(cell_ref: str) -> tuple[int, int]:
    """'U3' -> (row, col)，0-indexed。"""
    m = _CELL_REF_RE.match(cell_ref)
    if not m:
        raise ValueError(f"invalid cell reference: {cell_ref!r}")
    letters, row_num = m.group(1), int(m.group(2))
    return int(row_num) - 1, col_letter_to_index(letters)
