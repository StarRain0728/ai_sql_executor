"""SM2 加解密工具单元测试。"""
from gmssl import sm2 as gmssl_sm2

from core.config import get_settings
from utils.sm2_util import SM2Util

_settings = get_settings()
PRIV = _settings.sm2_private_key
PUB = _settings.sm2_public_key


def _util():
    return SM2Util(private_key=PRIV, public_key=PUB)


def test_empty_returns_empty():
    assert _util().decrypt("") == ""


def test_none_returns_empty_string():
    assert _util().decrypt(None) == ""


def test_roundtrip_ciphertext():
    cipher = gmssl_sm2.CryptSM2(private_key=PRIV, public_key=PUB, mode=1)
    cipher_hex = cipher.encrypt("p@ssw0rd".encode()).hex()
    assert _util().decrypt(cipher_hex) == "p@ssw0rd"


def test_plaintext_dirty_data_returned_as_is():
    # 历史明文/脏数据不是有效密文，边界容错应原样返回而非抛错
    util = _util()
    assert util.decrypt("not-a-hex-cipher") == "not-a-hex-cipher"
    assert util.decrypt("123456") == "123456"
