"""
shared-core 匯入設定：把 shared-core 資料夾加進 sys.path，讓 portal-app 與底下的
pages 可以直接 `import auth`、`import database`。

兩種佈局都支援，呼叫端（app.py、pages/*.py）不用管是哪一種：
- 開發階段：shared-core 跟 portal-app 平行擺放在同一層目錄下（相鄰資料夾），
  方便在 shared-core 端邊改邊測，不用每次都 commit/pull 進 submodule 才看得到變化。
- 正式部署（Streamlit Cloud 等）：只會 clone portal-app 這個 repo，不會有相鄰的
  shared-core 資料夾，改用 Git Submodule 掛在 portal-app/shared-core 底下這份。
兩個都存在時（例如本機同時裝了 submodule）優先用相鄰資料夾那份，因為那是開發者
正在編輯、最新的版本。
"""
import sys
from pathlib import Path

_PORTAL_ROOT = Path(__file__).resolve().parent
_SHARED_CORE_DEV_PATH = _PORTAL_ROOT.parent / "shared-core"
_SHARED_CORE_SUBMODULE_PATH = _PORTAL_ROOT / "shared-core"

_SHARED_CORE_PATH = (
    _SHARED_CORE_DEV_PATH if _SHARED_CORE_DEV_PATH.is_dir() else _SHARED_CORE_SUBMODULE_PATH
)

if str(_SHARED_CORE_PATH) not in sys.path:
    sys.path.insert(0, str(_SHARED_CORE_PATH))
