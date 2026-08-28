"""
版本：20260827-UX-FIXES-ROUND17
更新內容：ROUND16 這個修正版本其實一直沒有真的推送到 GitHub（commit 做了但沒有
push），使用者這段期間的實測都還是打在舊版程式碼上，才會一直看到已經修好的問題。
補強了 ROUND16 的裁切方向邏輯：追加驗證單據整個旋轉 90/180/270 度擺放（不是只有
corners 陣列起點不同）時，crop＋rotate 兩者搭配起來的最終結果是否正確——過程中發現
曾經想加的「貼近水平/垂直軸」判斷式對任何矩形都必然打平手、完全沒有作用（純數學結論，
不是猜測），已經拿掉，維持 ROUND16 原本單純的「離原點最近」判斷式，測試
test_crop_and_rotate_together_correct_when_document_itself_is_rotated_in_photo
涵蓋 90／180／270 度三種整轉角度，確認現有判斷式搭配正確的 rotate 值都能正確還原
方向。

---（以下為 ROUND16 紀錄）---
修正兩個使用者實測回報的裁切 bug（機票票根、計程車發票都遇到過）：
1. 「裁切後圖片整個方向轉錯／看起來像鏡像顛倒」——根因是 _crop_to_document() 一律把
   Gemini 回傳的 corners 陣列第一個點當作輸出左上角，但提示詞只要求「順時針排列、
   起點任意」，如果模型這次選了別的角落當起點，裁切本身就會悄悄帶入一個額外的
   90/180/270 度旋轉；這個旋轉跟 rotate 欄位（模型另外判斷「原始照片」文字朝向）
   的座標系統對不上，兩者疊加就可能讓最終圖片整個轉錯方向。新增
   _reorder_points_from_top_left()，裁切前先在程式端自動把「最靠近照片畫面左上角」
   的角落重新排序成固定的第一個點，不再依賴模型是否遵守提示詞裡「從左上角開始」
   的要求，兩個判斷從此不會再互相干擾。同時也把提示詞裡「起點任意」的說法拿掉，
   改成明確要求從照片左上角開始（雙重保險）。
2. 「裁切範圍已經在單據裡面、切到內容本身」——Gemini 估計的角落座標常常比單據紙本
   真正的邊緣略微內縮，先前完全照座標裁切，偶爾會把單據本身的文字/金額切掉一角。
   新增 _pad_quad_outward()，裁切前把四個角落沿著中心點往外推 _CORNER_PAD_RATIO
   （2.5%）的安全邊距，用「相對四邊形自己的尺寸」的比例而不是固定像素數，不管照片
   解析度高低都有一致的效果。
測試：tests/test_receipt_image_processing.py 新增
test_crop_to_document_orientation_independent_of_corner_start_point，用同一組角落
座標、四種不同起點排列去裁切，驗證裁切結果的方向永遠一致；既有的裁切尺寸測試也
更新為容許新的安全邊距。

---（以下為 ROUND14 紀錄）---
更新內容：改成多模型自動切換備援——免費方案的每日額度是依模型各自獨立計算的，且偏低
（gemini-3.6-flash 只有 24 次/天），多人共用同一組 key 很容易一天就用完。
_generate_content_with_retry() 改成接受 config.GEMINI_MODEL_FALLBACK_CHAIN 這份模型
清單，額度用完（429）或伺服器過載（503）時直接切換下一個模型（不同模型是各自獨立的
額度池），只有清單最後一個模型才照原本的邏輯多重試一次，全部都失敗才顯示白話訊息
（列出實際依序試過哪些模型）。另外修正 detect_and_crop_document()（機票票根裁切）
裡的一個既有 bug：原本的通用 except Exception 會把 QuotaExceededError／
ServiceUnavailableError 也一起吃掉、靜默當成「裁切失敗但不影響流程」處理，導致
app.py 裡專門處理這兩種例外的邏輯其實從來沒被觸發過——現在讓這兩種例外正常往上拋。

---（以下為 ROUND13 紀錄）---
新增 ServiceUnavailableError——Gemini 伺服器過載時回傳 503 UNAVAILABLE，
跟額度用完（429）是不同狀況，先前完全沒處理，會把原始 JSON 錯誤整包丟給使用者看，
也不會重試。現在比照 429 的做法，固定等待幾秒後重試一次，仍失敗才轉成白話訊息。

---（以下為 ROUND8 紀錄）---
1. 修正 _crop_to_document() 一個可能導致「完全沒去背」的 bug——模型估計的角落座標
   靠近照片邊緣時常會有一點點誤差（例如估成 -2 或 1004），先前的邏輯是「只要有任何
   一個座標超出 0~1000 就整組放棄、完全不裁切」，一點點誤差就讓整次裁切失效。改成把
   座標夾在 0~1000 範圍內再繼續處理，而不是直接放棄。
2. 加上除錯訊息（print，會進 Streamlit Cloud 後台 log）：印出每次辨識/裁切實際拿到
   的 corners/rotate 值，以及裁切失敗時卡在哪一步、丟了什麼例外——機票票根裁切這次
   完全沒有效果，但本機沒有真實照片能重現，需要靠使用者下次測試時的後台 log 才能
   精準定位問題，不用再靠猜測來回修正浪費 API 額度。

---（以下為 ROUND5 紀錄）---
Gemini 免費額度用完時（429 RESOURCE_EXHAUSTED），原本會把整包原始 JSON 錯誤
直接丟給使用者看。新增 QuotaExceededError：遇到 429 先依 Google 建議的等待秒數重試一次，
還是失敗就轉成白話訊息（區分「每日」/「每分鐘」額度上限）。app.py 的批次辨識迴圈偵測到
這個例外就整批中止，不會對後面每個檔案都再浪費一次重試等待的時間。

---（以下為 ROUND4 紀錄）---
修正裁切背景裁不乾淨的根因——加強提示詞（見 ROUND2 紀錄）後問題沒解決，
追查發現真正原因是 EXIF 方向標籤：手機拍照（尤其微信儲存的圖片）常把「顯示方向」記錄
在 EXIF metadata，檔案裡存的其實是感光元件的原始畫面。Gemini 判讀時通常會先依 EXIF
轉正再看，box_2d 座標是基於「轉正後」的畫面；但 PIL 開圖預設不會套用 EXIF 方向，直接
拿轉正後的座標去裁原始未轉正的像素，兩邊座標系統對不起來，裁出來的框自然是亂的——
提示詞調得再準都沒用，因為根本不是「框不準」的問題，是「座標系統對不上」。新增
_normalize_orientation()，在丟給 Gemini 判讀之前就統一轉正、往後全程用同一份轉正後
的 bytes。另外參考另一個類似專案的做法，加上 rotate 欄位（讓 Gemini 順便判斷單據文字
本身朝向），裁切後自動把單據轉正，不用使用者自己轉。

---（以下為 ROUND2 紀錄）---
1. 加強裁切邊界框（box_2d）的提示詞——使用者反映部分照片裁切後仍留一大片桌面背景，
   改成明確要求「即使單據傾斜也要框出最小外接矩形、寧可切到單據邊緣也不要留背景」。
2. detect_and_crop_document() 除了裁切，同時抽取機票票根上的搭乘日期（flight_date，
   同一次呼叫，不增加費用），回傳型別改成 (裁切後bytes, 日期或None)，供 app.py 拿去跟
   Step 1 填的出差起訖日期交叉比對、不一致時提醒使用者。

---（以下為先前版本紀錄）---
新增自動裁切收據背景功能——使用者反映 Word 明細清單貼的是整張照片（含桌面/
背景），希望只留單據本身。試過傳統影像處理（Otsu 二值化找輪廓、旋轉矩形+透視校正）
在木紋桌面等真實背景下都不夠準，改成直接請 Gemini 回傳單據在照片中的邊界框（bounding
box，0~1000 正規化座標），用 PIL 裁切——這是同一個 recognize_receipt() 呼叫裡新增的
一個欄位，不用額外呼叫 API、不增加費用。ReceiptItem.raw_bytes 存的是裁切後的圖片。
另外新增 detect_and_crop_document()，是給機票票根用的獨立輕量呼叫（機票票根不經過
recognize_receipt 的完整欄位辨識，只需要裁切）。

呼叫 Gemini 視覺 API（免費額度）辨識收據，依科目分類帶入不同提示，抽取日期/金額/幣別/說明。

信心與手寫判斷完全交給模型自評（confidence, is_handwritten），但 needs_review 的最終判斷
不只依賴模型自評分數——缺欄位（日期或金額抓不到）一律強制複核，這是交接文件第5節
「手寫收據辨識信心低，必須人工複核」規則的落實。

用 Gemini 而不是其他付費視覺 API，是因為 Gemini API 有免費額度可用，適合這種內部小工具、
多人共用同一組 key 的情境，不需要為每次呼叫另外編列預算。
"""
import io
import math
import time
from datetime import date as date_type
from decimal import Decimal, InvalidOperation

from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from PIL import Image, ImageOps
from pydantic import BaseModel

import config
from models import ReceiptItem


class QuotaExceededError(Exception):
    """Gemini API 免費額度用完（429 RESOURCE_EXHAUSTED），這是 Google 帳號/專案當下的
    即時額度限制，不是程式邏輯錯誤，訊息內容是給使用者看的白話說明，不是原始 JSON。"""


class ServiceUnavailableError(Exception):
    """Gemini API 伺服器當下過載（503 UNAVAILABLE），這是 Google 那邊暫時性的壅塞，
    跟額度用完（429）是不同狀況，重試通常就會恢復；訊息內容是給使用者看的白話說明，
    不是原始 JSON。"""


_MAX_RETRY_DELAY_SECONDS = 15
_SERVER_ERROR_RETRY_DELAY_SECONDS = 5.0


def _extract_retry_delay_seconds(exc: genai_errors.APIError) -> float:
    try:
        error_body = exc.details.get("error", exc.details) if isinstance(exc.details, dict) else {}
        for item in error_body.get("details", []):
            delay = item.get("retryDelay")
            if delay:
                return min(float(str(delay).rstrip("s")), _MAX_RETRY_DELAY_SECONDS)
    except Exception:
        pass
    return 5.0


def _friendly_quota_message(exc: genai_errors.APIError, tried_models: list[str]) -> str:
    message = (getattr(exc, "message", "") or str(exc))
    if "PerDay" in message:
        scope = "每日"
    elif "PerMinute" in message:
        scope = "每分鐘"
    else:
        scope = ""
    tried = "、".join(tried_models)
    return (
        f"Gemini API 免費額度已經用完（{scope}額度上限），已依序嘗試「{tried}」都用完了，"
        "這是 Google 帳號/專案當下的即時額度限制，不是程式錯誤。請稍後再試，或聯絡工具"
        "管理員確認 API 專案的額度設定。"
    )


def _friendly_server_error_message(tried_models: list[str]) -> str:
    tried = "、".join(tried_models)
    return (
        f"Gemini 伺服器目前忙碌中（503 服務暫時無法使用），已依序嘗試「{tried}」都無法"
        "使用，這是 Google 那邊當下的暫時性壅塞，不是程式錯誤也不是額度用完。請稍後再試一次。"
    )


def _generate_content_with_retry(client: genai.Client, models: list[str], **kwargs):
    """依序嘗試 models 清單裡的每個模型呼叫 Gemini 的 generate_content。遇到額度用完
    （429 RESOURCE_EXHAUSTED）或伺服器過載（503 UNAVAILABLE）時，不在同一個模型上原地
    等待重試就直接切換下一個模型——不同模型是 Google 那邊各自獨立計算的額度池，換一個
    模型繞過限制，比死等同一個模型的額度/過載狀況解除快得多。只有清單最後一個模型（沒有
    下一個可以切換了）才照原本的邏輯多重試一次：429 依 Google 建議的等待秒數，503 用
    固定的短延遲。全部都失敗，才依最後一次失敗的類型轉成 QuotaExceededError／
    ServiceUnavailableError，讓上層顯示清楚好懂的訊息（列出實際依序試過哪些模型），
    而不是把原始 JSON 錯誤直接丟給使用者看。"""
    tried_models: list[str] = []
    for index, model in enumerate(models):
        is_last = index == len(models) - 1
        tried_models.append(model)
        try:
            return client.models.generate_content(model=model, **kwargs)
        except genai_errors.ClientError as exc:
            if exc.code != 429:
                raise
            if not is_last:
                continue
            time.sleep(_extract_retry_delay_seconds(exc))
            try:
                return client.models.generate_content(model=model, **kwargs)
            except genai_errors.ClientError as exc2:
                if exc2.code == 429:
                    raise QuotaExceededError(_friendly_quota_message(exc2, tried_models)) from exc2
                raise
        except genai_errors.ServerError as exc:
            if not is_last:
                continue
            time.sleep(_SERVER_ERROR_RETRY_DELAY_SECONDS)
            try:
                return client.models.generate_content(model=model, **kwargs)
            except genai_errors.ServerError as exc2:
                raise ServiceUnavailableError(_friendly_server_error_message(tried_models)) from exc2
    raise QuotaExceededError("沒有設定任何可用的 Gemini 模型可供辨識，請聯絡工具管理員確認設定。")


class _ReceiptExtraction(BaseModel):
    date: str = ""  # YYYY-MM-DD，看不出來留空字串
    amount: str = ""  # 純數字字串，不含幣別符號或千分位逗號，看不出來留空字串
    currency: str = ""  # 幣別代碼，必須是 TWD/RMB/USD/EUR/SGD/GBP/JPY/MYR/VND/MXN 之一，看不出來留空字串
    description: str = ""
    location_from: str = ""  # 僅交通費適用
    location_to: str = ""  # 僅交通費適用
    lodging_region: str = ""  # 美歐 或 亞洲，僅住宿費適用
    lodging_days: int = 0  # 僅住宿費適用，看不出來留 0
    lodging_people: int = 0  # 僅住宿費適用，看不出來留 0
    is_handwritten: bool = False
    confidence: float = 0.0
    confidence_reason: str = ""
    corners: list[int] = []  # [x1,y1,x2,y2,x3,y3,x4,y4]，0~1000正規化座標，單據紙本四個角落
    rotate: int = 0  # 0/90/180/270，讓單據文字轉正需要「順時針」旋轉的角度


_CORNERS_PROMPT = (
    "\ndocument_corners：如果這是一張「拍照」的實體單據（照片背景看得到桌面/桌墊等），"
    "找出單據紙本四個角落在照片中的座標，回傳 corners 為 [x1,y1,x2,y2,x3,y3,x4,y4]，"
    "數值正規化到 0~1000（左上角為原點）。**即使單據在照片中是傾斜擺放的，也要照單據"
    "實際歪斜的樣子，找出四個角落各自精確的座標，不要用一個「正的矩形」去框——** "
    "四個點依「順時針」方向排列，且 (x1,y1) 必須是這四個角落裡最靠近『照片畫面本身"
    "左上角』的那一個（是照片畫面的左上角，不是單據文字讀起來的左上角），其餘三點依"
    "序順時針排列。"
    "每一個點都要盡量貼齊單據紙本真正的角落，寧可稍微超出單據邊緣一點點，也不要內縮"
    "切到單據本身的文字內容（背景頂多留一點點邊，比裁到內容安全）。"
    "如果這本來就是電子單據/截圖（PDF、手機截圖，沒有實體背景），corners 留空陣列即可。\n"
    "rotate：為了讓單據文字變成「由左至右、由上至下」正向可讀，判斷需要【順時針旋轉多少度】："
    "文字已經正向就填 0；文字開頭朝左（整張圖要順時針轉90度才會正）填 90；"
    "文字上下顛倒填 180；文字開頭朝右填 270。電子單據/截圖通常已經是正的，填 0 即可。"
)


def _normalize_orientation(file_bytes: bytes) -> bytes:
    """把 EXIF 方向標籤「烘」進實際像素、拿掉 EXIF 方向標籤，回傳重新編碼後的 bytes。

    手機拍照常見陷阱：有些相機/App（例如微信儲存的圖片）存的是「感光元件拍到的原始
    畫面」，實際顯示方向記錄在 EXIF 標籤裡，不是真的把像素轉正。Gemini 這類視覺模型
    通常會先依 EXIF 轉正再判讀（符合人眼看到的方向），box_2d 座標是基於「轉正後」的
    畫面；但 PIL 開圖預設不會套用 EXIF 方向，如果直接拿轉正後的座標去裁沒轉正的原始
    像素，兩邊座標系統對不起來，裁出來的框會整個跑掉。這裡統一在丟給 Gemini 判讀之前
    就先轉正、往後全程都用轉正後的這份 bytes（辨識、裁切都用同一份），確保座標系統
    從頭到尾一致，不管原始 EXIF 內容為何都不影響結果。"""
    try:
        image = Image.open(io.BytesIO(file_bytes))
        image = ImageOps.exif_transpose(image)  # 依 EXIF 轉正並清除方向標籤
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return file_bytes


_CORNER_PAD_RATIO = 0.025  # 裁切四角往外留的安全邊距比例（相對四邊形自己的尺寸）


def _reorder_points_from_top_left(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """把 4 個角落座標（順時針排列、起點任意）重新排序，讓「最靠近照片畫面左上角」的
    那一點固定變成 points[0]，其餘 3 點維持原本的順時針相對順序。

    這是修正「裁切後文字方向偶爾整個轉錯」這個 bug 的關鍵：_crop_to_document() 一律把
    points[0] 當作輸出的左上角。如果 Gemini 這次剛好選了別的角落當起點（提示詞雖然要求
    從左上角開始，但不保證每次都遵守），裁切本身就會悄悄帶入一個額外的 90/180/270 度
    旋轉；而 rotate 欄位是模型另外看「原始照片」判斷的文字朝向，兩者的座標系統對不上時
    不會自動抵銷，疊加起來就可能讓最終圖片整個轉錯方向（甚至看起來像鏡像顛倒）。改成
    不管模型回傳的起點是哪一個，程式自己先重新對齊到「照片畫面左上角」這個固定基準，
    裁切結果的朝向就只跟後面單獨套用的 rotate 有關，兩個判斷不會再互相干擾。

    （曾經嘗試過在這裡疊加一個「找起點到下一點的邊最貼近水平/垂直軸」的判斷式，以為能
    處理單據整個旋轉 90/180/270 度擺放的情況，後來實測＋數學驗證發現是無效的：對任何
    矩形而言，這個「貼近軸線」的角度判斷式在 4 個候選起點之間必然完全打平手（矩形的
    對邊平行、鄰邊垂直，兩者在這個判斷式下的分數恆等），永遠都會落回到「離原點最近」
    這個判斷式，等於什麼都沒改，白白多繞一圈。「單據本身整個旋轉多少度」是語意層面的
    判斷，光憑角落幾何座標無法分辨，真正負責這件事的是 rotate 欄位——只要 corners 跟
    rotate 都是模型針對同一張照片一致地判斷出來的，兩者搭配起來就會正確，不需要、也
    無法只靠角落座標的幾何特徵去猜。這裡維持單純的「離原點最近」判斷式即可。）"""
    start_idx = min(range(4), key=lambda i: points[i][0] + points[i][1])
    return points[start_idx:] + points[:start_idx]


def _pad_quad_outward(points: list[tuple[float, float]], pad_ratio: float) -> list[tuple[float, float]]:
    """把四邊形四個角落各自沿著「中心點 -> 該角落」的方向往外推一點點，留一圈安全邊距。

    Gemini 估計的角落座標常常會比單據紙本真正的邊緣略微內縮一點（尤其單據邊緣反光、
    或跟桌面顏色太接近時），裁切如果完全照座標來，就可能把單據本身的文字/金額切掉一角
    ——比留一點點背景邊更嚴重，因為背景頂多不好看，切到內容金額或日期看不到就是真的
    出問題。往外留一點安全邊距，用「相對四邊形自己的尺寸」的比例（而不是固定像素數），
    這樣不管原始照片解析度高低都能有一致的效果。"""
    cx = sum(p[0] for p in points) / 4
    cy = sum(p[1] for p in points) / 4
    return [(cx + (x - cx) * (1 + pad_ratio), cy + (y - cy) * (1 + pad_ratio)) for x, y in points]


def _crop_to_document(file_bytes: bytes, corners: list[int], rotate_deg: int = 0) -> bytes:
    """依 Gemini 回傳的單據四角座標做「透視校正」裁切，把歪斜擺放的單據拉正、裁掉背景，
    再依 rotate_deg 把單據文字轉正，回傳處理後的 PNG bytes。

    先前的版本只用一個「軸對齊的矩形框」（box_2d）去裁切——如果單據在照片裡是斜放的，
    軸對齊矩形要框住一個歪斜的矩形，四個角落必然會多包到背景，這是幾何上無法避免的
    限制，跟提示詞寫得多準無關。改成請 Gemini 直接標出單據四個角落的精確座標，再用
    PIL 的透視變形（Image.QUAD）把這個歪斜四邊形「拉正」成長方形，才能真正裁乾淨。

    corners 無效（不是4個點/座標不合理）就不裁切，只套用旋轉（若有）。"""
    try:
        image = Image.open(io.BytesIO(file_bytes))
        image = image.convert("RGB")

        if corners and len(corners) == 8:
            # 模型估計的角落座標，靠近照片邊緣時常會有一點點誤差（例如估成 -2 或 1004）——
            # 之前這裡是「只要有一個座標超出 0~1000 就整組放棄、完全不裁切」，稍微超界
            # 一點點就整個裁切失效，這正是機票票根完全沒去背的可能原因之一。改成夾住在
            # 0~1000 範圍內再繼續處理，而不是直接放棄。
            corners = [max(0, min(1000, v)) for v in corners]
            w, h = image.size
            points = [(corners[i] / 1000 * w, corners[i + 1] / 1000 * h) for i in range(0, 8, 2)]
            # 不管 Gemini 這次實際選了哪一個角當起點，先重新對齊到「照片畫面左上角」，
            # 讓裁切帶入的朝向固定、不再跟 rotate 欄位互相打架（見函式說明）。
            points = _reorder_points_from_top_left(points)
            # 往外留一點安全邊距，避免座標稍微內縮就把單據內容本身切掉一角。
            points = _pad_quad_outward(points, _CORNER_PAD_RATIO)
            points = [(max(0.0, min(w, x)), max(0.0, min(h, y))) for x, y in points]
            (x1, y1), (x2, y2), (x3, y3), (x4, y4) = points
            # point1 對應輸出的左上角、point4 對應左下角、point3 對應右下角、point2
            # 對應右上角（PIL Image.QUAD 要求來源四點依「左上、左下、右下、右上」給）；
            # 「輸出寬」是 point1-point2 那條邊（左上到右上），「輸出高」是 point1-point4
            # 那條邊（左上到左下）。
            side_lengths = [
                math.hypot(points[i][0] - points[i - 1][0], points[i][1] - points[i - 1][1])
                for i in range(4)
            ]
            out_w = int(max(side_lengths[1], side_lengths[3]))
            out_h = int(max(side_lengths[0], side_lengths[2]))
            if out_w >= 10 and out_h >= 10:
                quad = (x1, y1, x4, y4, x3, y3, x2, y2)
                image = image.transform((out_w, out_h), Image.QUAD, quad, resample=Image.BICUBIC)
            else:
                print(f"[CROP-DEBUG] corners too degenerate to crop: out_w={out_w} out_h={out_h} corners={corners}")
        elif corners:
            print(f"[CROP-DEBUG] corners present but wrong length (expected 8): {corners}")

        if rotate_deg in (90, 180, 270):
            image = image.rotate(-rotate_deg, expand=True)  # PIL rotate() 是逆時針，取負角度變順時針

        buf = io.BytesIO()
        image.save(buf, format="PNG")
        return buf.getvalue()
    except Exception as exc:
        print(f"[CROP-DEBUG] _crop_to_document EXCEPTION: {exc!r} corners={corners} rotate_deg={rotate_deg}")
        return file_bytes


_CATEGORY_HINTS = {
    "交通費": "這是交通費收據（如計程車、機票、高鐵等）。請特別抽取起訖地點與車資/票價總額（含稅）。",
    "住宿費": "這是住宿費收據（如飯店帳單）。請特別抽取晚數、人數（若收據上有標示）與地區線索。",
    "雜費津貼": "這是雜費津貼相關收據（如通訊費、雜項支出）。這類收據常見是單日發生但最終會被整趟出差合計，"
               "抽取時只要照收據本身的實際日期與金額填寫即可，合併與否由後續流程處理。",
    "餐費": "這是餐費收據。注意：依公司規則，餐費欄位通常只用在出差津貼不涵蓋的日子（例如週日），"
            "但這不影響你的抽取工作，照實際內容抽取即可。",
    "交際費": "這是交際費收據（如宴客、商務餐敘）。",
    "其它": "這是其它類別收據，照實際內容抽取即可。",
}


_CURRENCY_ALIASES = {
    "CNY": "RMB", "RENMINBI": "RMB", "CN¥": "RMB", "¥": "RMB",
    "NT": "TWD", "NT$": "TWD", "NTD": "TWD", "新台幣": "TWD",
    "US$": "USD", "USD$": "USD",
}


def _normalize_currency(raw: str) -> tuple[str | None, bool]:
    """回傳 (正規化後的幣別代碼或原始字串, 是否為範本合法代碼)。

    範本的幣別欄位是下拉選單綁定 VLOOKUP，代碼錯了（例如人民幣寫成 CNY）匯率會查不到，
    所以這裡把常見別名轉成範本實際使用的代碼，轉不出來的話就照原樣回傳並標記不合法，
    交給後面的 needs_review 邏輯強制人工複核，不要讓錯誤的幣別代碼靜默寫進 Excel。
    """
    if not raw:
        return None, True
    code = raw.strip().upper()
    code = _CURRENCY_ALIASES.get(code, code)
    return code, code in config.VALID_CURRENCIES


_EXTENSION_MIME_MAP = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".webp": "image/webp",
    ".heic": "image/heic",
    ".heif": "image/heif",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}


def _mime_type_for(filename: str) -> str:
    lower = filename.lower()
    for ext, mime_type in _EXTENSION_MIME_MAP.items():
        if lower.endswith(ext):
            return mime_type
    return "image/jpeg"


def _parse_date(value: str) -> date_type | None:
    if not value:
        return None
    try:
        year, month, day = (int(p) for p in value.strip().split("-"))
        return date_type(year, month, day)
    except (ValueError, TypeError):
        return None


def _parse_amount(value: str) -> Decimal | None:
    if not value:
        return None
    try:
        return Decimal(value.strip().replace(",", ""))
    except (InvalidOperation, AttributeError):
        return None


def recognize_receipt(
    file_bytes: bytes,
    filename: str,
    category: str,
    api_key: str,
    models: tuple[str, ...] = config.GEMINI_MODEL_FALLBACK_CHAIN,
) -> ReceiptItem:
    client = genai.Client(api_key=api_key)
    mime_type = _mime_type_for(filename)
    if mime_type != "application/pdf":
        # 統一先轉正 EXIF 方向，後面辨識跟裁切全程用同一份 bytes，座標系統才會一致。
        file_bytes = _normalize_orientation(file_bytes)
        mime_type = "image/png"

    category_hint = _CATEGORY_HINTS.get(category, "")
    valid_currency_list = "、".join(config.VALID_CURRENCIES)
    prompt_text = (
        f"這是一張出差收據，使用者已經先分類為「{category}」。{category_hint}\n"
        f"currency 欄位必須是以下代碼之一：{valid_currency_list}。人民幣一律填 RMB，不要填 CNY；"
        "新台幣一律填 TWD，不要填 NT$ 或 NTD。\n"
        "任何欄位看不清楚或收據上根本沒有，一律誠實留空（文字欄位留空字串、數字欄位留0），"
        "不要用猜的填數字，並在 confidence 反映你的不確定程度（0.0~1.0）。"
        "如果日期或金額是手寫填寫的（即使是印刷收據上手寫填入的欄位也算），is_handwritten 要設為 true。"
        + _CORNERS_PROMPT
    )

    response = _generate_content_with_retry(
        client,
        models=list(models),
        contents=[
            types.Part.from_bytes(data=file_bytes, mime_type=mime_type),
            prompt_text,
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=_ReceiptExtraction,
        ),
    )

    fields: _ReceiptExtraction = response.parsed

    parsed_date = _parse_date(fields.date)
    parsed_amount = _parse_amount(fields.amount)
    confidence = float(fields.confidence or 0.0)
    is_handwritten = bool(fields.is_handwritten)
    normalized_currency, currency_is_valid = _normalize_currency(fields.currency)

    needs_review = (
        is_handwritten
        or confidence < config.CONFIDENCE_THRESHOLD
        or parsed_date is None
        or parsed_amount is None
        or not currency_is_valid
    )
    confidence_reason = fields.confidence_reason
    if not currency_is_valid:
        confidence_reason = (
            f"{confidence_reason}　（幣別「{fields.currency}」不是範本支援的代碼，"
            f"請從 {'/'.join(config.VALID_CURRENCIES)} 中手動選一個）"
        ).strip("　")

    print(f"[CROP-DEBUG] {filename}: corners={fields.corners} rotate={fields.rotate}")
    cropped_bytes = _crop_to_document(file_bytes, fields.corners, fields.rotate)

    return ReceiptItem(
        source_filename=filename,
        category=category,
        raw_bytes=cropped_bytes,
        date=parsed_date,
        amount=parsed_amount,
        currency=normalized_currency,
        description=fields.description,
        location_from=fields.location_from.strip() or None,
        location_to=fields.location_to.strip() or None,
        lodging_region=fields.lodging_region.strip() or None,
        lodging_days=fields.lodging_days or None,
        lodging_people=fields.lodging_people or None,
        is_handwritten=is_handwritten,
        confidence=confidence,
        confidence_reason=confidence_reason,
        raw_model_response=fields.model_dump_json(),
        needs_review=needs_review,
        user_confirmed=False,
    )


class _FlightTicketExtraction(BaseModel):
    corners: list[int] = []  # [x1,y1,x2,y2,x3,y3,x4,y4]，0~1000正規化座標，票根四個角落
    rotate: int = 0  # 0/90/180/270，讓票根文字轉正需要「順時針」旋轉的角度
    flight_date: str = ""  # YYYY-MM-DD，票根上的搭乘日期，看不出來留空字串


def detect_and_crop_document(
    file_bytes: bytes,
    filename: str,
    api_key: str,
    models: tuple[str, ...] = config.GEMINI_MODEL_FALLBACK_CHAIN,
) -> tuple[bytes, date_type | None]:
    """機票票根用：裁掉背景 + 順便抽取票根上的搭乘日期（同一次呼叫，不額外增加費用），
    供 Step 1 填的出差起訖日期做交叉比對用。PDF/電子截圖本來就沒有實體背景，呼叫失敗或
    偵測不到框時裁切的部分一律回傳原始 bytes，不影響檔案能不能正常嵌入 Word；日期抽取
    失敗則回傳 None（比對邏輯遇到 None 就跳過，不會誤報）。"""
    mime_type = _mime_type_for(filename)
    if mime_type == "application/pdf":
        return file_bytes, None
    file_bytes = _normalize_orientation(file_bytes)
    mime_type = "image/png"
    try:
        client = genai.Client(api_key=api_key)
        response = _generate_content_with_retry(
            client,
            models=list(models),
            contents=[
                types.Part.from_bytes(data=file_bytes, mime_type=mime_type),
                "這是一張機票票根/登機證。\n"
                "1. corners：如果這是一張「拍照」的實體文件/票根（照片背景看得到桌面等），"
                "找出文件紙本四個角落在照片中的座標，回傳 corners 為 [x1,y1,x2,y2,x3,y3,x4,y4]，"
                "數值正規化到 0~1000。**即使文件是傾斜擺放的，也要照實際歪斜的樣子標出四個"
                "角落精確座標，不要用一個「正的矩形」去框**，四個點依順時針方向排列，且"
                "(x1,y1) 必須是這四個角落裡最靠近『照片畫面本身左上角』的那一個（不是票根"
                "文字讀起來的左上角），其餘三點依序順時針排列。盡量貼齊文件真正的角落，"
                "寧可稍微超出邊緣一點點也不要內縮切到文件本身的文字內容。如果本來就是電子"
                "截圖沒有實體背景，corners 留空陣列。\n"
                "2. rotate：為了讓票根文字變成「由左至右、由上至下」正向可讀，判斷需要"
                "【順時針旋轉多少度】：文字已經正向就填 0；文字開頭朝左填 90；文字上下"
                "顛倒填 180；文字開頭朝右填 270。電子截圖通常已經是正的，填 0 即可。\n"
                "3. flight_date：票根上實際的搭乘日期（格式 YYYY-MM-DD）。看不清楚或找不到"
                "就留空字串，不要用猜的。",
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=_FlightTicketExtraction,
            ),
        )
        fields: _FlightTicketExtraction = response.parsed
        print(f"[CROP-DEBUG] {filename}: corners={fields.corners} rotate={fields.rotate}")
        cropped = _crop_to_document(file_bytes, fields.corners, fields.rotate)
        return cropped, _parse_date(fields.flight_date)
    except (QuotaExceededError, ServiceUnavailableError):
        # 這兩種是使用者需要實際看到的白話訊息（額度用完/伺服器過載），不能被下面的
        # 通用 except 吃掉、靜默裁切失敗——那樣使用者只會看到票根沒去背，完全不知道
        # 真正原因是什麼。
        raise
    except Exception as exc:
        print(f"[CROP-DEBUG] {filename}: EXCEPTION before/during crop: {exc!r}")
        return file_bytes, None
