import math

from utils import Bucket


class Server:
    def __init__(self, num_blocks: int):
        self.tree_height = math.ceil(math.log2(num_blocks))
        self.num_leaves = 2 ** self.tree_height
        self.num_nodes = 2 * self.num_leaves - 1
        self._buckets = [Bucket() for _ in range(self.num_nodes)]  # Full binary tree
        self.is_initialized = False

    def get_bucket(self, node_index: int) -> Bucket:
        return self._buckets[node_index]


