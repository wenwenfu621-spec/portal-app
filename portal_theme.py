"""
入口網站統一視覺主題（玻璃擬態 / Glassmorphism）——讓私車公用報支、出差申報這兩支
併進來的子系統，跟登入/選單頁維持同一套視覺語言：漸層底圖若隱若現、卡片用半透明+
模糊濾鏡（backdrop-filter blur）、白色玻璃光澤邊框、懸浮陰影層次感。

這兩支子系統原本各自帶自己的一套 CSS（私車公用報支是「Apple 風格」白色不透明卡片、
出差申報是 ui_enhancements.py 的卡片化樣式），跟登入頁完全是兩套不同風格。這支模組
不去動子系統原本的版面/欄位邏輯，只疊加一層玻璃主題 CSS 蓋掉背景色/邊框，讓視覺風格
統一，不影響任何辨識、匯出等功能。
"""
import base64
from pathlib import Path

import streamlit as st

_APP_DIR = Path(__file__).parent
_BACKGROUND_IMAGE_PATH = _APP_DIR / "portal_background.jpg"


def inject_glass_theme() -> None:
    """套用玻璃擬態主題：底圖 + 主內容卡片玻璃化 + 按鈕/連結統一漸層樣式。"""
    if not _BACKGROUND_IMAGE_PATH.exists():
        return
    image_b64 = base64.b64encode(_BACKGROUND_IMAGE_PATH.read_bytes()).decode("utf-8")
    st.markdown(
        f"""
        <style>
        .stApp {{
            background-image: url("data:image/jpeg;base64,{image_b64}");
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }}

        /* 主內容區塊改成半透明玻璃卡片，蓋掉子系統原本各自的不透明白底樣式。
           max-width 特別加 !important——私車公用報支自己的 apple_style_css 有設
           max-width: 760px（沒有 !important，但因為是它自己專用的規則、注入順序又在
           inject_glass_theme() 之前，理論上會被蓋掉，但保險起見還是明著蓋一次），
           不然卡片會被鎖在小於畫面的固定寬度，變成浮在滿版底圖正中央一小塊的「畫中畫」
           效果，而不是跟出差申報頁一樣滿版鋪開。

           背景模糊（backdrop-filter）刻意不直接放在這個容器本身，改放到 ::before
           偽元素上——backdrop-filter 這類 filter 系屬性放在「祖先」元素上，會讓瀏覽器
           （主要是 Chromium）幫這個祖先另外建立一個新的 containing block，底下所有
           position: sticky（我們的導覽列/標題列都要用）的子元素會因此整個失效、變得
           跟 position: static 沒兩樣（滾動一下子就被捲到畫面外，完全黏不住）。改用
           ::before 偽元素頂著模糊效果、容器本身保持沒有 filter，兩邊都能兼顧。 */
        [data-testid="stMainBlockContainer"],
        .main .block-container {{
            position: relative !important;
            background: transparent !important;
            border-radius: 24px !important;
            border: 1px solid rgba(255, 255, 255, 0.6) !important;
            box-shadow: 0 8px 32px rgba(31, 38, 135, 0.18), 0 0 40px rgba(103, 232, 249, 0.18) !important;
            max-width: 100% !important;
            isolation: isolate;
            /* 左右內邊距統一寫死成 5rem，不讓兩個子系統各自的舊 CSS（或 Streamlit
               預設值）決定——私車公用報支的 apple_style_css 殘留 padding: 2.2rem
               2.4rem 3rem，出差申報沒設、吃 Streamlit wide layout 預設值，兩邊實測
               寬度不一樣，卡片內縮幅度不同，連帶導覽列/標題的左右位置也對不齊。 */
            padding-left: 5rem !important;
            padding-right: 5rem !important;
            /* margin-top 也統一——私車公用報支殘留 margin-top: 1.5rem（apple_style_css
               裡的舊設定），出差申報是 0，兩頁卡片距離畫面最上方的距離因此差了 24px。 */
            margin-top: 0 !important;
            /* 同理，頂部內距也統一——私車公用報支殘留 35.2px（apple_style_css 的
               2.2rem），出差申報吃 Streamlit 預設值 96px，兩頁導覽列/標題的初始垂直
               位置因此對不齊。統一採用私車公用報支現有的 35.2px。 */
            padding-top: 35.2px !important;
            /* 內容較少的頁面（例如私車公用報支只有兩個上傳欄位）原本卡片高度只跟著內容
               縮短，畫面下半段會露出裸的 .stApp 底圖（沒有卡片的白霧玻璃層蓋著，色彩
               對比明顯比卡片內鮮豔很多），看起來像是漏接到另一張圖。內容多的頁面
               （出差申報有 5 個 Step）因為本來就比一個畫面高，不會露出這段空隙，兩頁
               才會看起來不一致。加 min-height 強制卡片至少跟視窗一樣高，蓋滿整個
               可視範圍，不管內容多寡都不會露出裸底圖。

               光加 min-height 還不夠：這個卡片其實是 Streamlit 捲動容器（.stMain，
               display: flex）底下的一個 flex 子項目，flex 子項目預設 flex-shrink: 1
               （允許被壓縮）。內容一多（例如出差申報 5 個 Step 疊起來遠超過一個畫面
               高），flex 版面引擎會把卡片「壓縮」回 min-height 這個下限，超出的內容
               雖然還是會畫出來（overflow 預設 visible），但已經跑到卡片本身的背景/
               模糊層框框之外，一樣會露出沒有玻璃霧化效果的裸底圖——只是這次是發生在
               內容「多」的頁面捲到後段時，剛好跟內容少的情況相反。加 flex-shrink: 0
               禁止被壓縮，卡片才會確實撐到「內容實際需要的高度」（不小於一個畫面高，
               也不會被瀏覽器硬壓回一個畫面高）。 */
            min-height: 100vh !important;
            flex-shrink: 0 !important;
        }}
        [data-testid="stMainBlockContainer"]::before,
        .main .block-container::before {{
            content: "";
            position: absolute;
            inset: 0;
            background: rgba(255, 255, 255, 0.55);
            backdrop-filter: blur(18px);
            -webkit-backdrop-filter: blur(18px);
            border-radius: 24px;
            z-index: -1;
        }}

        /* 導覽列（返回主頁／登出）+ 頁面標題：用 st.container(key="portal_sticky_header")
           把兩者包在「同一個」容器裡（內部各自還是用 portal_nav_bar / page_title_bar
           這兩個 class 分別控制版面，但 sticky／背景色只套在最外層這一個容器上）。

           一開始是分別給導覽列、標題各自的容器套 sticky + 背景色，結果兩個容器在
           「還沒真正貼齊」的初始捲動位置，中間會空出 Streamlit 預設的元件間距
           （st.container 之間的 flex gap），這段空隙沒有背景色可蓋，會露出比兩側
           更淡、不連續的一小段裸底圖。改成兩者共用同一個容器、同一塊背景之後，
           中間的間距變成同一個背景色範圍「內部」的留白，不會再露出色差。

           sticky 貼在「用 :has() 選到的外層 wrapper div」上，不是直接貼在
           .st-key-portal_sticky_header 本身——實測發現 Streamlit 會幫每個元素
           （包含 st.container）另外包一層自動撐高的 wrapper div，這層 wrapper 的
           高度剛好等於內容本身的高度（沒有多餘空間）。CSS 的 position: sticky 只能
           在「自己的 containing block」範圍內游動貼齊，如果直接貼在
           .st-key-portal_sticky_header 上，它的 containing block 就是那層剛好緊貼
           內容高度的 wrapper，畫面一滾動、這層矮 wrapper 整個捲出可視範圍，sticky
           就沒有任何空間可以貼、直接跟著捲走不見。改成貼在「wrapper 本身」上，它的
           containing block 往上一層變成整個頁面內容的根容器（高度等於整頁內容總
           高），才有足夠空間讓它在整個頁面捲動過程中持續貼在最上方。:has() 目前
           主流瀏覽器（Chrome/Edge/Safari）都已支援。 */
        div:has(> .st-key-portal_sticky_header) {{
            position: sticky;
            /* top 要扣掉 Streamlit 自己畫面最上方那條工具列（[data-testid="stHeader"]，
               漢堡選單／Deploy 按鈕那條，z-index 高達 999990，永遠蓋在最上面）的高度，
               不然導覽列會貼齊 0px、整個被那條工具列蓋住看不見。 */
            top: 60px;
            z-index: 1000;
        }}
        .st-key-portal_sticky_header {{
            background: rgba(255, 255, 255, 0.7) !important;
            backdrop-filter: blur(18px) !important;
            -webkit-backdrop-filter: blur(18px) !important;
        }}
        .st-key-portal_nav_bar {{
            /* 左右各留 3rem（約 48px）內縮留白，不讓按鈕直接貼齊卡片最外側邊緣。 */
            padding: 0.5rem 3rem !important;
        }}
        .st-key-portal_nav_bar [data-testid="stHorizontalBlock"] {{
            display: flex !important;
            justify-content: space-between !important;
            align-items: center !important;
            gap: 1rem;
        }}
        .st-key-portal_nav_bar [data-testid="stHorizontalBlock"] > div {{
            flex: 0 0 auto !important;
            width: auto !important;
        }}
        .st-key-portal_nav_bar div[data-testid="stPageLink"] a,
        .st-key-portal_nav_bar .stButton > button {{
            /* min-width/max-width 兩個都鎖，不能只設 width——flex 子項目預設
               min-width: auto，內容（圖示+文字）需要的寬度只要超過 160px，瀏覽器會
               優先保證內容不被壓縮、放寬 min-width 蓋過我們設的 width，導致兩顆按鈕
               實際渲染寬度不一致（在較寬的螢幕/不同瀏覽器下更容易出現）。額外用
               white-space: nowrap + overflow: hidden 把內容鎖在 160px 範圍內，
               徹底避免內容撐開按鈕本身。 */
            width: 160px !important;
            min-width: 160px !important;
            max-width: 160px !important;
            /* 寬度雖然鎖住了，但「返回主頁」是 st.page_link 產生的 <a> 標籤、
               「登出」是 st.button 產生的 <button> 標籤，兩者 Streamlit 預設的
               padding/line-height 不一樣，導致 <a> 只有 28px 高、<button> 有 40px
               高——實測用瀏覽器開發者工具量出來的（不是肉眼猜的），寬度其實一樣，
               是「高矮」不一致讓兩顆看起來大小不同。額外鎖高度，兩者才會是真正
               等大的膠囊按鈕。 */
            height: 40px !important;
            box-sizing: border-box !important;
            white-space: nowrap !important;
            overflow: hidden !important;
            display: flex !important;
            align-items: center;
            justify-content: center;
            text-align: center;
        }}
        .st-key-page_title_bar {{
            padding: 0.3rem 0 !important;
        }}

        /* 檔案上傳（Upload）按鈕統一套用跟其他按鈕一致的漸層樣式，不用子系統各自
           內建的樣式（例如私車公用報支的 apple_style_css 是純藍色）。 */
        [data-testid="stFileUploaderDropzone"] button {{
            background: linear-gradient(135deg, #22d3ee, #6366f1) !important;
            color: #fff !important;
            border: none !important;
            box-shadow: 0 2px 8px rgba(31, 38, 135, 0.20);
        }}
        [data-testid="stFileUploaderDropzone"] button:hover {{
            background: linear-gradient(135deg, #06b6d4, #4f46e5) !important;
        }}

        /* 「返回主頁」連結跟「登出」按鈕統一成同一種漸層膠囊按鈕外觀，避免一個看起來
           像純文字連結、一個看起來像按鈕的不一致感。 */
        div[data-testid="stPageLink"] a,
        .stButton > button,
        .stDownloadButton > button {{
            background: linear-gradient(135deg, #22d3ee, #6366f1) !important;
            color: #fff !important;
            border: none !important;
            border-radius: 20px !important;
            font-weight: 600 !important;
            text-decoration: none !important;
            box-shadow: 0 2px 8px rgba(31, 38, 135, 0.20);
            transition: transform 0.12s ease, background 0.12s ease;
        }}
        div[data-testid="stPageLink"] a:hover,
        .stButton > button:hover,
        .stDownloadButton > button:hover {{
            background: linear-gradient(135deg, #06b6d4, #4f46e5) !important;
            color: #fff !important;
            transform: translateY(-1px);
        }}
        div[data-testid="stPageLink"] a p {{
            color: #fff !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
