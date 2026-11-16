"""
VRL-1 Transparency Log: append-only Merkle log over vault enrollments.

AEAD stops record tampering; this stops silent rollback/deletion: any
removed or reordered enrollment changes the root. Inclusion proofs let a
third party verify one enrollment against a published root.
"""
from __future__ import annotations

import hashlib
import threading


def _h(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


class MerkleLog:
    def __init__(self) -> None:
        self._leaves: list[bytes] = []
        self._lock = threading.Lock()

    def append(self, entry: bytes) -> int:
        with self._lock:
            self._leaves.append(_h(b"\x00" + entry))
            return len(self._leaves) - 1

    def __len__(self) -> int:
        return len(self._leaves)

    def _level(self, nodes: list[bytes]) -> list[bytes]:
        out = []
        for i in range(0, len(nodes), 2):
            left = nodes[i]
            right = nodes[i + 1] if i + 1 < len(nodes) else left
            out.append(_h(b"\x01" + left + right))
        return out

    def root(self) -> str:
        with self._lock:
            nodes = list(self._leaves)
        if not nodes:
            return _h(b"").hex()
        while len(nodes) > 1:
            nodes = self._level(nodes)
        return nodes[0].hex()

    def inclusion_proof(self, index: int) -> list[tuple[str, str]]:
        """List of (side, hex) siblings from leaf to root."""
        with self._lock:
            nodes = list(self._leaves)
        if not 0 <= index < len(nodes):
            raise IndexError("leaf index out of range")
        proof: list[tuple[str, str]] = []
        idx = index
        while len(nodes) > 1:
            if idx % 2 == 0:
                sibling = nodes[idx + 1] if idx + 1 < len(nodes) else nodes[idx]
                proof.append(("R", sibling.hex()))
            else:
                proof.append(("L", nodes[idx - 1].hex()))
            nodes = self._level(nodes)
            idx //= 2
        return proof

    @staticmethod
    def verify_inclusion(entry: bytes, proof: list[tuple[str, str]], root: str) -> bool:
        node = _h(b"\x00" + entry)
        for side, sib_hex in proof:
            sib = bytes.fromhex(sib_hex)
            node = _h(b"\x01" + sib + node) if side == "L" else _h(b"\x01" + node + sib)
        return node.hex() == root
