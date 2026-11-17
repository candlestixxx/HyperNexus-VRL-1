"""Optional Rust core (PyO3) acceleration.

Imports the compiled `_vrl1_core` extension when available and exposes the
ported primitives. When the extension is not built (fresh checkout, CI, or a
platform without Rust), everything degrades to the pure-Python implementations
in `core/vrl1_algo.py` / `core/vector_math.py`.
"""
from __future__ import annotations

try:
    from _vrl1_core import derive_coordinate as rust_derive_coordinate
    from _vrl1_core import make_proof as rust_make_proof
    from _vrl1_core import spatialize_key as rust_spatialize_key

    RUST_AVAILABLE = True
except Exception:  # ImportError (not built) or any ABI/version mismatch
    rust_derive_coordinate = None  # type: ignore[assignment]
    rust_make_proof = None         # type: ignore[assignment]
    rust_spatialize_key = None     # type: ignore[assignment]
    RUST_AVAILABLE = False
