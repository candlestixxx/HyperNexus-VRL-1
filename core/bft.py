"""Byzantine-fault-tolerant consensus for multi-writer ring state (PBFT core).

`N = 3f + 1` replicas tolerate up to `f` Byzantine faults and agree on an
ordered log of operations (e.g. tenant enrollment / transparency-leaf appends
for the vault's ring state). This implements the 3-phase agreement core:

    REQUEST -> PRE-PREPARE -> PREPARE (2f) -> COMMIT (2f+1) -> execute

Safety: two honest replicas never commit different operations at the same
sequence number (the 2f+1 quorum makes conflicting commits impossible).

Scope note (honest): view-change (recovering liveness after a Byzantine or
failed *primary*) is the documented next increment; this module proves the
agreement/safety core. Messages are delivered in-process for determinism.
"""
from __future__ import annotations

import hashlib
from collections import deque
from dataclasses import dataclass


def digest(op: bytes) -> str:
    return hashlib.sha256(op).hexdigest()


@dataclass
class Message:
    kind: str          # REQUEST | PRE_PREPARE | PREPARE | COMMIT
    view: int
    seq: int
    digest: str
    op: bytes | None
    sender: int
    client: int | None = None


class Network:
    """In-process message delivery. `None` target = broadcast to all replicas."""

    def __init__(self) -> None:
        self._q: deque[tuple[int | None, Message]] = deque()
        self.replicas: list["Replica"] = []

    def add_replica(self, r: "Replica") -> None:
        self.replicas.append(r)

    def broadcast(self, m: Message) -> None:
        self._q.append((None, m))

    def send_to(self, rid: int, m: Message) -> None:
        self._q.append((rid, m))

    def run(self, max_iters: int = 100_000) -> None:
        for _ in range(max_iters):
            if not self._q:
                return
            target, m = self._q.popleft()
            if target is None:
                for r in self.replicas:
                    r.handle(m)
            else:
                self.replicas[target].handle(m)
        raise RuntimeError("consensus did not quiesce")


class Replica:
    def __init__(self, rid: int, n: int, f: int, network: Network) -> None:
        self.rid = rid
        self.n = n
        self.f = f
        self.network = network
        self.view = 0
        self.log: dict[int, bytes] = {}      # committed seq -> op
        self.committed: set[int] = set()
        self.next_seq = 0                     # primary only
        self.requests_seen: set[tuple[int | None, str]] = set()
        self.pre_prepares: dict[tuple[int, int], str] = {}
        self.ops: dict[tuple[int, int], bytes] = {}
        self.prepares: dict[tuple[int, int, str], set[int]] = {}
        self.commits: dict[tuple[int, int, str], set[int]] = {}

    @property
    def primary_id(self) -> int:
        return self.view % self.n

    @property
    def is_primary(self) -> bool:
        return self.rid == self.primary_id

    # -- inbound -------------------------------------------------------------
    def handle(self, m: Message) -> None:
        if m.kind == "REQUEST":
            if self.is_primary:
                self._handle_request(m)
        elif m.kind == "PRE_PREPARE":
            self._handle_pre_prepare(m)
        elif m.kind == "PREPARE":
            self._handle_prepare(m)
        elif m.kind == "COMMIT":
            self._handle_commit(m)

    def _handle_request(self, m: Message) -> None:
        key = (m.client, m.digest)
        if key in self.requests_seen:
            return
        self.requests_seen.add(key)
        seq = self.next_seq
        self.next_seq += 1
        self.pre_prepares[(self.view, seq)] = m.digest
        self.ops[(self.view, seq)] = m.op
        self.network.broadcast(Message("PRE_PREPARE", self.view, seq, m.digest,
                                       m.op, self.rid))

    def _handle_pre_prepare(self, m: Message) -> None:
        # Only the primary may pre-prepare, and the op must match its digest.
        if m.sender != self.primary_id or m.op is None or m.digest != digest(m.op):
            return
        existing = self.pre_prepares.get((m.view, m.seq))
        if existing is not None and existing != m.digest:
            return  # conflicting pre-prepare (Byzantine primary) -> ignore
        self.pre_prepares[(m.view, m.seq)] = m.digest
        self.ops[(m.view, m.seq)] = m.op
        self._record_prepare(m.view, m.seq, m.digest, self.rid)
        self.network.broadcast(Message("PREPARE", m.view, m.seq, m.digest,
                                       None, self.rid))

    def _handle_prepare(self, m: Message) -> None:
        if self.pre_prepares.get((m.view, m.seq)) != m.digest:
            return
        self._record_prepare(m.view, m.seq, m.digest, m.sender)

    def _handle_commit(self, m: Message) -> None:
        if self.pre_prepares.get((m.view, m.seq)) != m.digest:
            return
        self._record_commit(m.view, m.seq, m.digest, m.sender)

    # -- quorum advancement --------------------------------------------------
    def _record_prepare(self, view: int, seq: int, d: str, rid: int) -> None:
        key = (view, seq, d)
        s = self.prepares.setdefault(key, set())
        if rid in s:
            return
        s.add(rid)
        if len(s) >= 2 * self.f:
            self._record_commit(view, seq, d, self.rid)
            self.network.broadcast(Message("COMMIT", view, seq, d, None, self.rid))

    def _record_commit(self, view: int, seq: int, d: str, rid: int) -> None:
        key = (view, seq, d)
        s = self.commits.setdefault(key, set())
        if rid in s:
            return
        s.add(rid)
        if len(s) >= 2 * self.f + 1 and seq not in self.committed:
            self.committed.add(seq)
            self.log[seq] = self.ops[(view, seq)]
