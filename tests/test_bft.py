"""PBFT core: agreement, liveness (honest primary), and safety under faults."""
import pytest

from core.bft import Message, Network, Replica, digest


def _build(n: int, f: int, byzantine: set[int] | None = None,
           requests: list[bytes] | None = None) -> list[Replica]:
    net = Network()
    replicas = []
    for i in range(n):
        if byzantine and i in byzantine:
            r = PassiveByzantineReplica(i, n, f, net)
        else:
            r = Replica(i, n, f, net)
        replicas.append(r)
        net.add_replica(r)
    for op in (requests or []):
        net.broadcast(Message("REQUEST", 0, 0, digest(op), op, sender=-1, client=0))
    net.run()
    return replicas


class PassiveByzantineReplica(Replica):
    """A faulty replica that never participates (the worst it can do passively)."""

    def handle(self, m: Message) -> None:
        return


class ForkingPrimary(Replica):
    """Byzantine primary: sends conflicting pre-prepares to different replicas."""

    def _handle_request(self, m: Message) -> None:
        key = (m.client, m.digest)
        if key in self.requests_seen:
            return
        self.requests_seen.add(key)
        seq = self.next_seq
        self.next_seq += 1
        other = b"CONFLICTING-OP"
        # Half the replicas see the real op, half see a conflicting one.
        for i in range(self.n):
            op = m.op if i % 2 == 0 else other
            self.network.send_to(i, Message("PRE_PREPARE", self.view, seq,
                                            digest(op), op, self.rid))


def test_honest_primary_commits_all_requests():
    ops = [b"enroll tenant_a", b"append leaf 1", b"rotate epoch 2"]
    replicas = _build(n=4, f=1, requests=ops)
    honest = [r for r in replicas if not isinstance(r, PassiveByzantineReplica)]
    for r in honest:
        assert list(r.log.values()) == ops  # same order on every honest replica


def test_agreement_with_one_passive_fault():
    # 4 replicas, 1 passive Byzantine (f=1) -> the 3 honest ones still agree.
    ops = [b"op-1", b"op-2", b"op-3"]
    replicas = _build(n=4, f=1, byzantine={3}, requests=ops)
    honest = [r for r in replicas if not isinstance(r, PassiveByzantineReplica)]
    logs = [tuple(r.log.values()) for r in honest]
    assert len(set(logs)) == 1  # all identical
    assert logs[0] == tuple(ops)


def test_safety_with_byzantine_primary_no_fork():
    # A forking primary must never cause two honest replicas to commit
    # different operations at the same sequence number.
    net = Network()
    r0 = ForkingPrimary(0, 4, 1, net)
    r1, r2, r3 = Replica(1, 4, 1, net), Replica(2, 4, 1, net), Replica(3, 4, 1, net)
    for r in (r0, r1, r2, r3):
        net.add_replica(r)
    op = b"enroll tenant_a"
    net.broadcast(Message("REQUEST", 0, 0, digest(op), op, sender=-1, client=0))
    net.run()
    honest = [r1, r2, r3]
    # No two honest replicas may have different committed values at any seq.
    for seq in range(3):
        vals = {r.log.get(seq) for r in honest}
        assert len(vals) <= 1  # either all agree or none committed


def test_duplicate_request_is_deduplicated():
    # The same client request must only be committed once.
    net = Network()
    reps = [Replica(i, 4, 1, net) for i in range(4)]
    for r in reps:
        net.add_replica(r)
    op = b"enroll tenant_a"
    m = Message("REQUEST", 0, 0, digest(op), op, sender=-1, client=0)
    net.broadcast(m)
    net.broadcast(m)  # duplicate
    net.run()
    for r in reps:
        assert list(r.log.values()) == [op]
