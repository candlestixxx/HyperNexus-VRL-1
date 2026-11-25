"""Multi-node replicated vault: PBFT consensus over SecureRadialVault operations.

Each replica owns a `SecureRadialVault` (all share the same master key, so a
given key derives the same coordinate everywhere) and applies only operations
committed by the PBFT log. With `N = 3f + 1` nodes, all honest nodes agree on
ring state even when up to `f` are Byzantine.

This is the integration that turns the PBFT library (`core/bft.py`) and the
vault into a real multi-writer ring-state store: enroll/register operations are
ordered by consensus, then applied deterministically on every honest replica.
"""
from __future__ import annotations

import json

from core.bft import Message, Network, Replica, digest
from core.secure_vault import SecureRadialVault
from core.vrl1_algo import VRL1ZeroTrustEngine


class VaultReplica(Replica):
    """A PBFT replica that applies committed ops to its local vault."""

    def __init__(self, rid: int, n: int, f: int, network: Network,
                 vault: SecureRadialVault) -> None:
        super().__init__(rid, n, f, network)
        self.vault = vault

    def _on_commit(self, seq: int, op: bytes) -> None:
        try:
            self.vault.apply_op(json.loads(op.decode()))
        except ValueError:
            # An invalid op (e.g. overlapping ring) is rejected identically by
            # every honest node, keeping replicas consistent.
            pass


class ByzantineVaultReplica(Replica):
    """A faulty replica that never votes or applies ops (passive fault)."""

    def __init__(self, rid: int, n: int, f: int, network: Network,
                 vault: SecureRadialVault | None = None) -> None:
        super().__init__(rid, n, f, network)
        self.vault = vault

    def handle(self, m: Message) -> None:
        return


class DistributedVault:
    """N=3f+1 vault replicas, coordinated by PBFT consensus."""

    def __init__(self, master_key: bytes, n: int = 4, f: int = 1,
                 byzantine: set[int] | None = None) -> None:
        self.n = n
        self.f = f
        self.network = Network()
        self.nodes: list[Replica] = []
        for i in range(n):
            vault = SecureRadialVault(VRL1ZeroTrustEngine(master_key))
            if byzantine and i in byzantine:
                r = ByzantineVaultReplica(i, n, f, self.network, vault)
            else:
                r = VaultReplica(i, n, f, self.network, vault)
            self.nodes.append(r)
            self.network.add_replica(r)

    def submit(self, op: dict) -> None:
        """Broadcast an operation and run consensus to quiescence."""
        payload = json.dumps(op).encode()
        self.network.broadcast(Message("REQUEST", 0, 0, digest(payload), payload,
                                       sender=-1, client=0))
        self.network.run()

    def honest_vaults(self) -> list[SecureRadialVault]:
        return [node.vault for node in self.nodes if isinstance(node, VaultReplica)]
