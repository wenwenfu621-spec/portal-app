"""
密碼雜湊與驗證工具（PBKDF2-HMAC-SHA256，Python 標準函式庫 hashlib 內建，
不需要額外安裝 bcrypt 等第三方套件，避免雲端部署時的套件相容性問題）。

儲存格式："pbkdf2_sha256$迭代次數$salt(hex)$hash(hex)"，同一組明文密碼每次雜湊出來的
salt 都不同，即使兩個人設定一樣的密碼，資料庫裡存的雜湊字串也不會相同。

此檔案原本放在 shared-core repo，靠 Git Submodule 掛進 portal-app；改成直接放在
portal-app 這裡，原因是 Streamlit Community Cloud 的部署流程不支援 Git Submodule
（clone 時不會抓 submodule 內容），部署到雲端會直接在 import 這一步失敗。目前只有
portal-app 會用到這個模組，car-expense-app／trip-expense-app 都是靠登入後的
session_state 拿到身分資料，不會直接呼叫這裡的函式，所以直接搬過來維護不會造成
其他專案的困擾；shared-core repo 本身還留著，之後如果真的有第二個部署對象需要共用
這份邏輯，再考慮改用「pip 安裝 git 套件」之類的方式共用。
"""
import hashlib
import hmac
import os

_ALGORITHM = "pbkdf2_sha256"
_ITERATIONS = 260_000
_SALT_BYTES = 16


def hash_password(plain_password: str) -> str:
    salt = os.urandom(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, _ITERATIONS)
    return f"{_ALGORITHM}${_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(plain_password: str, stored_hash: str) -> bool:
    """驗證明文密碼是否與資料庫存的雜湊字串相符。stored_hash 格式不對（例如尚未初始化）
    一律回傳 False，不拋例外。"""
    try:
        algorithm, iterations_str, salt_hex, digest_hex = stored_hash.split("$")
        if algorithm != _ALGORITHM:
            return False
        iterations = int(iterations_str)
        salt = bytes.fromhex(salt_hex)
        expected_digest = bytes.fromhex(digest_hex)
    except (ValueError, AttributeError):
        return False

    actual_digest = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual_digest, expected_digest)
