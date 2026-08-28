"""
開發階段的 shared-core 匯入設定：把相鄰的 shared-core 資料夾加進 sys.path，
讓 portal-app 與底下的 pages 可以直接 `import auth`、`import database`。

正式部署時 shared-core 會以 Git Submodule 掛進 portal-app 底下，屆時把
_SHARED_CORE_DEV_PATH 改成對應的子模組路徑即可，呼叫端（app.py、pages/*.py）不用改。
"""
import sys
from pathlib import Path

_PORTAL_ROOT = Path(__file__).resolve().parent
_SHARED_CORE_DEV_PATH = _PORTAL_ROOT.parent / "shared-core"

if str(_SHARED_CORE_DEV_PATH) not in sys.path:
    sys.path.insert(0, str(_SHARED_CORE_DEV_PATH))
