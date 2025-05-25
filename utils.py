from hmac import compare_digest

from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.Hash import HMAC, SHA256

Z = 4  # bucket size
BLOCK_SIZE = 4  # each data block is 4 characters


def compute_hmac(key: bytes, msg: bytes) -> bytes:
    h = HMAC.new(key, digestmod=SHA256)
    h.update(msg)
    return h.digest()


def encrypt_block(key: bytes, data: bytes) -> bytes:
    version = get_random_bytes(4)  # 4-byte nonce/version for freshness
    msg = version + data
    mac = compute_hmac(key, msg)
    cipher = AES.new(key, AES.MODE_GCM)
    ciphertext, tag = cipher.encrypt_and_digest(msg + mac)
    return cipher.nonce + tag + ciphertext


def decrypt_block(key: bytes, encrypted_data: bytes) -> bytes:
    nonce = encrypted_data[:16]
    tag = encrypted_data[16:32]
    ciphertext = encrypted_data[32:]
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    msg_mac = cipher.decrypt_and_verify(ciphertext, tag)
    msg, mac = msg_mac[:-32], msg_mac[-32:]
    expected_mac = compute_hmac(key, msg)
    if not compare_digest(mac, expected_mac):
        raise ValueError("HMAC verification failed")
    return msg[4:]  # strip version


class Block:
    def __init__(self, block_id: int, data: str):
        self.id = block_id
        self.data = data

    def serialize(self) -> bytes:
        return f"{self.id:08d}{self.data}".encode()

    @staticmethod
    def deserialize(raw: bytes) -> 'Block':
        block_id = int(raw[:8])
        data = raw[8:12].decode()
        return Block(block_id, data)


class Bucket:
    def __init__(self):
        self.blocks = []  # List of encrypted blocks (real or dummy)

    def is_full(self):
        return len(self.blocks) == Z