"""
統一讀取設定值（API key、服務帳號憑證等）的小工具，讓同一套程式碼在 Streamlit
Community Cloud 和 Google Cloud Run 都能正常運作：

- Streamlit Cloud／本機開發：設定值來自 st.secrets（網頁後台設定的 Secrets，或本機
  .streamlit/secrets.toml）。
- Google Cloud Run：沒有 secrets.toml 這個檔案，st.secrets 會直接拋例外；改成讀
  同名的環境變數（部署時透過 Cloud Run 的環境變數／Secret Manager 注入）。

呼叫端不用自己判斷現在跑在哪個平台，一律呼叫這裡的函式即可。
"""
import json
import os

import streamlit as st


def get_secret(key: str, default: str = "") -> str:
    """讀單一字串型設定值（例如 GEMINI_API_KEY）。"""
    try:
        value = st.secrets[key]
        if value:
            return value
    except Exception:
        pass
    return os.environ.get(key, default)


def get_secret_dict(key: str) -> dict:
    """讀一整組多欄位設定（例如 gcp_service_account 服務帳號憑證）。

    Streamlit Cloud／本機：對應 secrets.toml 裡的 [key] 區塊。
    Cloud Run：改讀同名環境變數，內容是整份憑證的 JSON 字串。
    兩邊都讀不到就回傳空 dict，交由呼叫端處理（呼叫端原本就要能處理讀取失敗的情況）。
    """
    try:
        value = st.secrets[key]
        if value:
            return dict(value)
    except Exception:
        pass
    raw = os.environ.get(key, "")
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return {}
