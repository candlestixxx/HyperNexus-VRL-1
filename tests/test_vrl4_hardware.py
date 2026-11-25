"""Hardware root of trust: TPM detection + deterministic fallback."""
from core.vrl4_client import detect_tpm, hardware_root_of_trust


def test_hardware_root_of_trust_is_deterministic():
    seed1, tier1 = hardware_root_of_trust()
    seed2, tier2 = hardware_root_of_trust()
    assert seed1 == seed2
    assert tier1 == tier2
    assert isinstance(seed1, bytes) and len(seed1) == 96
    assert tier1 in ("tpm", "fingerprint")


def test_detect_tpm_shape():
    info = detect_tpm()
    assert set(info.keys()) == {"present", "version"}
    assert isinstance(info["present"], bool)
