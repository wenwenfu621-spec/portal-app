"""
Streamlit 應用程式「識別浮水印」標準元件
=========================================

用途：
- 畫面左下角：固定顯示「程式版本」標籤（monospace 字型 + 綠色版本號徽章）
- 畫面正下方置中：固定顯示「作者頭像 + 署名」膠囊徽章

這兩個元件是 Max 所有要上傳到 GitHub 的個人 Streamlit 專案的標準識別方式，
新專案請直接複製這支檔案裡的兩個函式到專案的 app.py，並依下方「使用方式」
呼叫即可，不需要每次重新設計樣式。

這兩個元件單純是「畫面裝飾」，本身不含任何商業邏輯，可以安全地放進任何
Streamlit 專案，不會影響其他功能。

使用方式
--------
1. 把這支檔案內容複製到你的 app.py 中（或是 import 這個檔案）。
2. 在 st.set_page_config(...) 之後，馬上呼叫一次：
       inject_version_tag(APP_VERSION)
   其中 APP_VERSION 是你自己專案裡定義的版本字串常數，例如：
       APP_VERSION = "20260826-XXX-UPDATE"
3. 在整支程式的「最後一行」呼叫：
       inject_custom_footer()
   （預設署名為 "Design by Max"，頭像預設會在專案根目錄尋找
    avatar.jpg / avatar.jpeg / avatar.png / avatar.JPG，
    找不到就不顯示頭像，只顯示文字）
   如果該專案要換成別的署名文字，呼叫時帶入參數即可：
       inject_custom_footer(author_text="Design by Max")

範例（新專案 app.py 開頭）：
--------------------------------
    import streamlit as st
    from identity_watermark import get_git_version, inject_version_tag, inject_custom_footer

    APP_VERSION = get_git_version()

    st.set_page_config(page_title="我的新工具", layout="centered")
    inject_version_tag(APP_VERSION)

    # ... 這裡放你的正式功能程式碼 ...

    inject_custom_footer()

更新記錄（20260828）：APP_VERSION 改用 get_git_version() 讀取目前部署當下實際簽出的
Git commit 短 hash，取代手動維護、容易忘記更新的寫死字串——每次程式碼異動、部署
完成後自動反映實際版本，不需要（也不可能）每次改程式碼都記得手動同步這行文字。
"""

import base64
import os
import subprocess

import streamlit as st


def get_git_version(app_dir: str | None = None) -> str:
    """讀取目前部署當下實際簽出的 Git commit 短 hash，取代手動維護、容易忘記更新的
    版本字串常數——每次程式碼異動、重新部署完成後這裡自動反映實際版本，不再需要（也
    不可能）手動同步。app_dir 預設用呼叫端檔案所在目錄；Git 會自動往上層找 .git
    目錄，所以就算 app_dir 是子目錄（例如多頁應用程式的 pages/ 底下）也能正確運作。
    讀不到（例如執行環境沒有 git 指令、或不是 git checkout）就回傳 "unknown"，這只是
    裝飾性的顯示標籤，讀取失敗不該影響主要功能。"""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=app_dir or os.path.dirname(os.path.abspath(__file__)),
            capture_output=True, text=True, timeout=3,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    return "unknown"


def inject_version_tag(app_version: str) -> None:
    """畫面左下角固定顯示程式版本標籤。

    Args:
        app_version: 版本字串，例如 "20260826-XXX-UPDATE"
    """
    version_css = f"""
    <style>
    .custom-version-tag {{
        position: fixed;
        bottom: 16px;
        left: 20px;
        background-color: rgba(255, 255, 255, 0.9);
        padding: 4px 10px;
        border-radius: 12px;
        box-shadow: 0px 2px 6px rgba(0, 0, 0, 0.1);
        font-size: 0.8rem;
        color: #555;
        z-index: 999999;
        pointer-events: none;
        font-family: monospace, sans-serif;
    }}
    .custom-version-tag code {{
        color: #2e7d32;
        background-color: #f1f8e9;
        padding: 2px 5px;
        border-radius: 4px;
    }}
    </style>
    <div class="custom-version-tag">
        📌 程式版本：<code>{app_version}</code>
    </div>
    """
    st.markdown(version_css, unsafe_allow_html=True)


def inject_custom_footer(
    author_text: str = "Design by Max",
    avatar_candidates=None,
) -> None:
    """畫面正下方置中固定顯示「頭像 + 署名」膠囊徽章。

    Args:
        author_text: 顯示的署名文字，預設 "Design by Max"
        avatar_candidates: 依序嘗試尋找的頭像檔名列表（相對於執行目錄），
            預設為 ["avatar.jpg", "avatar.jpeg", "avatar.png", "avatar.JPG"]。
            找不到任何一個檔案時，只會顯示文字、不顯示頭像。
    """
    if avatar_candidates is None:
        avatar_candidates = ["avatar.jpg", "avatar.jpeg", "avatar.png", "avatar.JPG"]

    img_base64 = ""
    mime_type = "image/png"

    for af in avatar_candidates:
        if os.path.exists(af):
            with open(af, "rb") as img_f:
                img_base64 = base64.b64encode(img_f.read()).decode("utf-8")
                if af.lower().endswith((".jpg", ".jpeg")):
                    mime_type = "image/jpeg"
                else:
                    mime_type = "image/png"
            break

    avatar_html = (
        f'<img src="data:{mime_type};base64,{img_base64}" style="width: 36px; height: 36px; border-radius: 50%; object-fit: cover; margin-right: 8px; border: 1.5px solid #ccc; background-color: #fff;">'
        if img_base64
        else ""
    )

    footer_css = f"""
    <style>
    .custom-footer-max {{
        position: fixed;
        bottom: 16px;
        left: 50%;
        transform: translateX(-50%);
        display: flex;
        align-items: center;
        background-color: rgba(255, 255, 255, 0.95);
        padding: 4px 14px;
        border-radius: 20px;
        box-shadow: 0px 2px 8px rgba(0, 0, 0, 0.15);
        z-index: 999999;
        pointer-events: none;
    }}
    .custom-footer-text {{
        font-family: 'Comic Sans MS', cursive, sans-serif;
        font-weight: bold;
        font-style: italic;
        font-size: 0.95rem;
        color: #333333;
        white-space: nowrap;
    }}
    </style>
    <div class="custom-footer-max">
        {avatar_html}
        <span class="custom-footer-text">{author_text}</span>
    </div>
    """
    st.markdown(footer_css, unsafe_allow_html=True)
