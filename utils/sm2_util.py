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
        raw = self._decode_input(data)
        return self.sm2_crypto.decrypt(raw).decode()
