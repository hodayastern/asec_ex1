import math
import random
from typing import Optional, List
from Crypto.Random import get_random_bytes

from server import Server
from utils import decrypt_block, Block, encrypt_block, Z, BLOCK_SIZE


class Client:
    KEY_SIZE = 16
    DUMMY_DATA = "0" * BLOCK_SIZE
    DUMMY_ID = -1

    def __init__(self, num_blocks: int):
        self.num_blocks = num_blocks
        self.tree_height = math.ceil(math.log2(num_blocks))
        self.num_leaves = 2 ** self.tree_height
        self.position_map = [self._get_random_leaf() for _ in range(num_blocks)]
        self.stash = []  # Holds decrypted blocks
        self.key = get_random_bytes(Client.KEY_SIZE)

    def _path(self, leaf: int) -> list:
        """
        return path from root to leaf
        :param leaf: leaf index (in range of leaf numbers, 0 to N)
        :return: path from root to leaf as list of indices
        """
        idx = self._get_leaf_index(leaf)
        path = []
        while idx >= 0:
            path.append(idx)
            idx = (idx - 1) // 2 if idx != 0 else -1
        return path[::-1]

    def _read_path(self, server: Server, path: List[int]):
        """
        reads a path and inserts all buckets to the stash (most of them will be placed back)
        :param server: server
        :param path: list of indices to read from server
        :return: None, buckets are read into stash if not dummy
        """
        for idx in path:
            bucket = server.get_bucket(idx)
            for enc_block in bucket.blocks:
                try:
                    raw = decrypt_block(self.key, enc_block)
                    block = Block.deserialize(raw)
                    if not self._is_dummy_block(block):
                        self.stash.append(block)
                except (ValueError, KeyError):
                    continue  # Ignore decryption or HMAC failures
            bucket.blocks.clear()

    def _write_path(self, server: Server, path: List[int]):
        path = path[::-1]  # from leaf to root so data is pushed down as possible
        for bucket_idx in path: # I'm filling blocks from leaf to root if possible
            bucket = server.get_bucket(bucket_idx)
            self._fill_path_bucket(bucket, bucket_idx)

    def _access(self, server, block_id, op_write=False, new_data=None):
        """
        implements the Access method offered in the article
        :param server: server
        :param block_id: block id
        :param op_write: if True, deletes the block from stash in order to not write it again as it was deleted
        :param new_data: new data if it's an actual write operation
        :return:
        """
        if block_id > self.num_blocks:
            raise ValueError(f"ID {block_id} is invalid in this server, insert number up to {self.num_blocks - 1}")
        if not server.is_initialized:
            self._fill_server_with_dummies(server)
        old_leaf = self.position_map[block_id]
        self._remap_block(block_id)
        path = self._path(old_leaf)
        self._read_path(server, path) # fills the stash with blocks so the actual block is there
        data = self._find_in_stash(block_id, delete=op_write)

        if op_write and new_data:
            self.stash.append(Block(block_id, data))

        self._write_path(server, path)
        return data

    def retrieve_data(self, server: Server, block_id: int) -> Optional[str]:
        if not self._access(server, block_id):
            raise ValueError(f"Block ID {block_id} is not stored in the server")

    def store_data(self, server: Server, block_id: int, data: str):
        return self._access(server, block_id, op_write=True, new_data=data)

    def delete_data(self, server: Server, block_id: int):
        if not self._access(server, block_id, op_write=True):
            raise ValueError(f"Block ID {block_id} is not stored in the server")

    def _get_leaf_index(self, leaf) -> int:
        return 2 ** self.tree_height - 1 + leaf

    def _get_random_leaf(self) -> int:
        return random.randint(0, self.num_leaves - 1)

    def _is_eligible_write_in_bucket(self, block, bucket_idx) -> bool:
        block_path = self._path(self.position_map[block.id])
        return bucket_idx in block_path

    def _create_encrypted_dummy_block(self) -> bytes:
        b = Block(Client.DUMMY_ID, Client.DUMMY_DATA)
        raw = b.serialize()
        enc = encrypt_block(self.key, raw)
        return enc

    def _fill_bucket(self, bucket_blocks: Optional[List[bytes]] = None) -> List[bytes]:
        """
        given an optional list of current blocks in bucket, fill the bucket up to Z blocks using padding dummy blocks.
        :param bucket_blocks: an optional list of blocks in bucket, if not exist, bucket is empty, fill with Z dummy
        :return:
        """
        bucket_blocks = bucket_blocks or []
        required_dummy_blocks = Z - len(bucket_blocks)
        return bucket_blocks + [self._create_encrypted_dummy_block() for _ in range(required_dummy_blocks)]

    @staticmethod
    def _is_dummy_block(block: Block) -> bool:
        return block.id == Client.DUMMY_ID and block.data == Client.DUMMY_DATA

    def _remap_block(self, block_id: int) -> None:
        new_leaf = self._get_random_leaf()
        self.position_map[block_id] = new_leaf

    def _find_in_stash(self, block_id, delete=False) -> Optional[str]:
        """
        finds block in stash
        :param block_id: block id
        :param delete: if delete is on, delete the block after finding (for writing/deleting data)
        :return: data of the block
        """
        for i, block in enumerate(self.stash):
            if block.id == block_id:
                data = block.data
                if delete:
                    del self.stash[i]
                return data
        return None  # Not found

    def _fill_path_bucket(self, bucket, bucket_idx):
        new_bucket_blocks = []
        remaining_stash = []
        for block in self.stash:
            if len(new_bucket_blocks) >= Z:
                remaining_stash.append(block)
                continue
            if self._is_eligible_write_in_bucket(block, bucket_idx):
                raw = block.serialize()
                enc = encrypt_block(self.key, raw)
                new_bucket_blocks.append(enc)
            else:
                remaining_stash.append(block)

        bucket.blocks = self._fill_bucket(new_bucket_blocks)
        self.stash = remaining_stash

    def _fill_server_with_dummies(self, server):
        server.is_initialized = True
        for i in range(server.num_nodes):
            bucket = server.get_bucket(i)
            bucket.blocks = self._fill_bucket()
