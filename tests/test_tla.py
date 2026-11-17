"""Re-run the TLA+ model check (TLC) over the vault invariants.

Skips when Java or `tools/tla2tools.jar` is absent (e.g. CI without Java).
"""
import shutil
import subprocess
from pathlib import Path

import pytest

JAVA = shutil.which("java")
REPO = Path(__file__).resolve().parent.parent
JAR = REPO / "tools" / "tla2tools.jar"

pytestmark = pytest.mark.skipif(JAVA is None, reason="java not available")


def test_tla_model_check_registers_persist_reload():
    if not JAR.exists():
        pytest.skip("tools/tla2tools.jar not available")
    proc = subprocess.run(
        [JAVA, "-cp", str(JAR), "tlc2.TLC", "-config", "Vault.cfg", "Vault.tla"],
        cwd=str(REPO / "spec"), capture_output=True, text=True, timeout=300)
    out = proc.stdout + proc.stderr
    assert proc.returncode == 0, out
    assert "No error has been found" in out, out
