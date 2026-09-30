from gmssl import sm2


class SM2Util:
    def __init__(self, private_key: str, public_key: str = None, mode: int = 1):
        self._private_key = private_key
        self.public_key = public_key
        self.sm2_crypto = sm2.CryptSM2(private_key=private_key, public_key=public_key, mode=mode)

    @staticmethod
    def _decode_input(data: str) -> bytes:
        return bytes.fromhex(data)

    def decrypt(self, data: str):
        """解密 SM2 hex 密文。

        边界容错：空密码（本地无密码数据源）或历史明文/脏数据不是有效密文，
        解密失败时原样返回，与元数据侧 decrypt_password 行为一致。
        """
        if not data:
            return data or ""
        try:
            raw = self._decode_input(data)
            plain = self.sm2_crypto.decrypt(raw)
            if not plain:
                return data
            return plain.decode()
        except Exception:
            return data
