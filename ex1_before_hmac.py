import random
import math
from typing import Optional, Tuple
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.Hash import HMAC, SHA256

# Constants (example values)
Z = 4  # bucket size
BLOCK_SIZE = 4  # each data block is 4 characters


def encrypt_block(key: bytes, data: bytes) -> bytes:
    cipher = AES.new(key, AES.MODE_GCM)
    ciphertext, tag = cipher.encrypt_and_digest(data)
    return cipher.nonce + tag + ciphertext


def decrypt_block(key: bytes, encrypted_data: bytes) -> bytes:
    nonce = encrypted_data[:16]
    tag = encrypted_data[16:32]
    ciphertext = encrypted_data[32:]
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    return cipher.decrypt_and_verify(ciphertext, tag)


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
        return len(self.blocks) >= Z


class Server:
    def __init__(self, num_blocks: int):
        self.tree_height = math.ceil(math.log2(num_blocks))
        self.num_leaves = 2 ** self.tree_height
        self.num_nodes = 2 * self.num_leaves - 1
        self.buckets = [Bucket() for _ in range(self.num_nodes)]  # Full binary tree

    def get_bucket(self, node_index: int) -> Bucket:
        return self.buckets[node_index]


class Client:
    def __init__(self, num_blocks: int):
        self.num_blocks = num_blocks
        self.tree_height = math.ceil(math.log2(num_blocks))
        self.position_map = {i: random.randint(0, 2 ** self.tree_height - 1) for i in range(num_blocks)}
        self.stash = []  # Holds decrypted blocks
        self.key = get_random_bytes(16)

    def _path(self, leaf: int) -> list:
        """ Return node indices from root to the leaf """
        idx = leaf + 2 ** self.tree_height - 1
        path = []
        while idx >= 0:
            path.append(idx)
            idx = (idx - 1) // 2 if idx != 0 else -1
        return path[::-1]

    def _read_path(self, server: Server, leaf: int):
        for idx in self._path(leaf):
            bucket = server.get_bucket(idx)
            for enc_block in bucket.blocks:
                try:
                    raw = decrypt_block(self.key, enc_block)
                    block = Block.deserialize(raw)
                    self.stash.append(block)
                except (ValueError, KeyError):
                    continue  # Ignore decryption failures (dummy blocks)
            bucket.blocks.clear()

    def _write_path(self, server: Server, leaf: int):
        path = self._path(leaf)[::-1]  # from leaf to root
        for idx in path:
            bucket = server.get_bucket(idx)
            new_bucket_blocks = []
            remaining_stash = []
            for block in self.stash:
                if len(new_bucket_blocks) >= Z:
                    remaining_stash.append(block)
                    continue
                block_path = self._path(self.position_map[block.id])
                if idx in block_path:
                    raw = block.serialize()
                    enc = encrypt_block(self.key, raw)
                    new_bucket_blocks.append(enc)
                else:
                    remaining_stash.append(block)
            bucket.blocks = new_bucket_blocks
            self.stash = remaining_stash

    def retrieve_data(self, server: Server, block_id: int) -> Optional[str]:
        if block_id not in self.position_map:
            return None
        old_leaf = self.position_map[block_id]
        new_leaf = random.randint(0, 2 ** self.tree_height - 1)
        self.position_map[block_id] = new_leaf
        self._read_path(server, old_leaf)
        for block in self.stash:
            if block.id == block_id:
                data = block.data
                break
        else:
            return None
        self._write_path(server, old_leaf)
        return data

    def store_data(self, server: Server, block_id: int, data: str):
        old_leaf = self.position_map.get(block_id, random.randint(0, 2 ** self.tree_height - 1))
        new_leaf = random.randint(0, 2 ** self.tree_height - 1)
        self.position_map[block_id] = new_leaf
        self._read_path(server, old_leaf)
        self.stash = [b for b in self.stash if b.id != block_id]
        self.stash.append(Block(block_id, data))
        self._write_path(server, old_leaf)

    def delete_data(self, server: Server, block_id: int):
        if block_id not in self.position_map:
            return
        old_leaf = self.position_map[block_id]
        new_leaf = random.randint(0, 2 ** self.tree_height - 1)
        self.position_map[block_id] = new_leaf
        self._read_path(server, old_leaf)
        self.stash = [b for b in self.stash if b.id != block_id]
        self._write_path(server, old_leaf)

# Implementation follows the Path ORAM protocol from:
# "Path ORAM: An Extremely Simple Oblivious RAM Protocol" by Stefanov et al.
# Specifically based on the Access(op, a, data*) pseudocode in Figure 1.
