# Google Cloud Run 部署用。Streamlit Community Cloud 不會用到這個檔案——那邊是直接
# 讀 requirements.txt + packages.txt 自動部署；兩個平台共用同一份程式碼，差別只在
# 部署機制本身。
FROM python:3.12-slim

# 對應 packages.txt 給 Streamlit Cloud 用的系統套件清單：LibreOffice/UNO 用來
# 即時重算 Excel 公式（見 libreoffice_worker.py），字型套件讓 LibreOffice 能正確
# 顯示標楷體／新細明體。兩份清單要保持同步，改其中一份記得另一份也要改。
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice-calc \
    python3-uno \
    fonts-arphic-ukai \
    fonts-arphic-uming \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1

# Cloud Build 部署時可用 --build-arg APP_VERSION=$COMMIT_SHA 帶入實際 commit hash，
# 讓畫面左下角版本標籤在沒有 .git 資料夾的容器裡也能正確顯示（見
# identity_watermark.get_git_version() 的環境變數備援）。不帶這個 build-arg
# 版本標籤會顯示 "unknown"，純裝飾用途，不影響任何功能。
ARG APP_VERSION=unknown
ENV APP_VERSION=${APP_VERSION}

# Cloud Run 用 PORT 環境變數指定實際監聽埠（預設 8080），且必須監聽 0.0.0.0，
# 否則平台的健康檢查連不到容器；--server.headless 避免 Streamlit 嘗試開啟瀏覽器
# 或等待互動輸入。用 shell form（非 JSON array）CMD 才能展開 ${PORT} 這個變數。
CMD streamlit run app.py --server.port=${PORT:-8080} --server.address=0.0.0.0 --server.headless=true
