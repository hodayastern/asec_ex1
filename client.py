import math
import random
from typing import Optional

from Crypto.Random import get_random_bytes

from server import Server
from utils import decrypt_block, Block, encrypt_block, Z


class Client:
    def __init__(self, num_blocks: int):
        self.num_blocks = num_blocks
        self.tree_height = math.ceil(math.log2(num_blocks))
        self.num_leaves = 2 ** self.tree_height
        self.position_map = [self._get_random_leaf() for _ in range(num_blocks)]
        self.stash = []  # Holds decrypted blocks
        self.key = get_random_bytes(16)

    def _path(self, leaf: int) -> list:
        """ Return node indices from root to the leaf """
        idx = self._get_leaf_index(leaf)
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
                    continue  # Ignore decryption or HMAC failures
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
        new_leaf = self._get_random_leaf()
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
        old_leaf = self.position_map[block_id]
        new_leaf = self._get_random_leaf()
        self.position_map[block_id] = new_leaf
        self._read_path(server, old_leaf)
        self.stash = [b for b in self.stash if b.id != block_id]
        self.stash.append(Block(block_id, data))
        self._write_path(server, old_leaf)

    def delete_data(self, server: Server, block_id: int):
        if block_id not in self.position_map:
            return
        old_leaf = self.position_map[block_id]
        new_leaf = self._get_random_leaf()
        self.position_map[block_id] = new_leaf
        self._read_path(server, old_leaf)
        self.stash = [b for b in self.stash if b.id != block_id]
        self._write_path(server, old_leaf)

    def _get_leaf_index(self, leaf) -> int:
        return 2 ** self.tree_height - 1 + leaf

    def _get_random_leaf(self) -> int:
        return random.randint(0, self.num_leaves - 1)
