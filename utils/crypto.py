"""敏感数据加解密工具 — Fernet 对称加密（用于共享 API Key 落库）。

密钥来源（按优先级）：
1. 环境变量 ENCRYPTION_KEY（Fernet key，44 字符 base64，生产环境必须配置）；
2. data/encryption.key 文件（首次启动未配置时自动生成并落盘，
   该目录不入库；Docker 中随 web_data 卷持久化，重启不丢）。

注意：密钥丢失将导致已加密的共享 Key 无法解密（需重新填写）；
生产环境建议在 .env 中显式配置 ENCRYPTION_KEY 并妥善备份。
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

_KEY_FILE = BASE_DIR / 'data' / 'encryption.key'

_fernet = None


def _get_fernet():
    """惰性加载 Fernet 实例（进程内缓存）。"""
    global _fernet
    if _fernet is not None:
        return _fernet

    key = os.environ.get('ENCRYPTION_KEY', '').strip()
    if key:
        _fernet = _make_fernet(key)
        return _fernet

    # 未配置环境变量：自动生成并持久化到 data/encryption.key
    if _KEY_FILE.exists():
        key = _KEY_FILE.read_text(encoding='utf-8').strip()
        if key:
            _fernet = _make_fernet(key)
            return _fernet
    from cryptography.fernet import Fernet
    key = Fernet.generate_key().decode('ascii')
    _KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    _KEY_FILE.write_text(key, encoding='utf-8')
    _fernet = _make_fernet(key)
    return _fernet


def _make_fernet(key: str):
    from cryptography.fernet import Fernet
    return Fernet(key.encode('ascii'))


def encrypt_secret(plaintext: str) -> str:
    """加密敏感值，返回 Fernet token 字符串；空串原样返回。"""
    if not plaintext:
        return ''
    return _get_fernet().encrypt(plaintext.encode('utf-8')).decode('ascii')


def decrypt_secret(ciphertext: str) -> str:
    """解密敏感值；空串或解密失败（密钥更换/旧数据）返回空串。"""
    if not ciphertext:
        return ''
    try:
        return _get_fernet().decrypt(ciphertext.encode('ascii')).decode('utf-8')
    except Exception:
        return ''
