"""Multi-node replicated vault: PBFT consensus keeps ring state consistent."""
import pytest

from core.distributed_vault import DistributedVault

MASTER = b"test-master-key-32-bytes-minimum!!"


def test_distributed_vault_registers_tenants_across_nodes():
    dv = DistributedVault(MASTER, n=4, f=1, byzantine={3})
    dv.submit({"action": "register_tenant", "tenant_id": "tenant_a", "lo": 0, "hi": 1 << 62})
    dv.submit({"action": "register_tenant", "tenant_id": "tenant_b", "lo": 1 << 62, "hi": 1 << 63})
    dv.submit({"action": "register_tenant", "tenant_id": "tenant_c", "lo": 1 << 63, "hi": 1 << 64})
    for vault in dv.honest_vaults():
        assert vault.has_tenant("tenant_a")
        assert vault.has_tenant("tenant_b")
        assert vault.has_tenant("tenant_c")


def test_distributed_vault_enroll_and_resolve_consistently():
    dv = DistributedVault(MASTER, n=4, f=1, byzantine={3})
    dv.submit({"action": "register_tenant", "tenant_id": "tenant_a", "lo": 0, "hi": 1 << 64})
    key = dv.honest_vaults()[0].generate_in_ring_key("tenant_a")
    dv.submit({"action": "enroll", "tenant_id": "tenant_a", "api_key": key, "epoch": 1,
               "target_url": "https://a.example.com", "db_connection_string": "sqlite:///a.db"})
    for vault in dv.honest_vaults():
        out = vault.resolve_by_key("tenant_a", key, 1)
        assert out["target_url"] == "https://a.example.com"


def test_distributed_vault_rejects_overlapping_ring_consistently():
    dv = DistributedVault(MASTER, n=4, f=1, byzantine={3})
    dv.submit({"action": "register_tenant", "tenant_id": "tenant_a", "lo": 0, "hi": 1 << 62})
    # A Byzantine primary must not cause honest replicas to diverge: the
    # overlapping ring is rejected identically on every honest node.
    dv.submit({"action": "register_tenant", "tenant_id": "evil", "lo": (1 << 62) - 1, "hi": 1 << 63})
    for vault in dv.honest_vaults():
        assert vault.has_tenant("tenant_a")
        assert not vault.has_tenant("evil")
