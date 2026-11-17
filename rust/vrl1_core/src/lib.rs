//! HyperNexus VRL-1 — Rust core (PyO3).
//!
//! Ports the pure-compute primitives from `core/vrl1_algo.py` and
//! `core/vector_math.py`, keeping the Python API identical. The Python
//! modules fall back to their pure implementations when this extension is
//! not built, so the package still runs without Rust.
//!
//! Parity is enforced by `tests/test_rust_core.py` (Rust output vs. the
//! reference Python math).

use hmac::{Hmac, Mac};
use pyo3::prelude::*;
use sha2::{Digest, Sha256};

type HmacSha256 = Hmac<Sha256>;

/// Length-prefixed canonical encoding — parity with `core/vrl1_algo.py::_canon`.
fn canon(fields: &[&[u8]]) -> Vec<u8> {
    let mut out = Vec::with_capacity(80);
    out.extend_from_slice(b"VRL1\x01");
    for f in fields {
        out.extend_from_slice(&(f.len() as u64).to_be_bytes());
        out.extend_from_slice(f);
    }
    out
}

fn hex_encode(bytes: &[u8]) -> String {
    const HEX: &[u8; 16] = b"0123456789abcdef";
    let mut s = String::with_capacity(bytes.len() * 2);
    for &b in bytes {
        s.push(HEX[(b >> 4) as usize] as char);
        s.push(HEX[(b & 0x0f) as usize] as char);
    }
    s
}

/// `VRL1ZeroTrustEngine.derive_coordinate`: HMAC-SHA256 over the canonical
/// (tenant, key, epoch) tuple, unpacked into (radius, (s0, s1, s2)) as u64s.
#[pyfunction]
fn derive_coordinate(tenant_key: &[u8], tenant_id: &str, api_key: &str, epoch: i64) -> (u64, (u64, u64, u64)) {
    let msg = canon(&[tenant_id.as_bytes(), api_key.as_bytes(), &epoch.to_be_bytes()]);
    let mut mac = HmacSha256::new_from_slice(tenant_key).expect("HMAC accepts any key length");
    mac.update(&msg);
    let digest = mac.finalize().into_bytes();
    let radius = u64::from_be_bytes(digest[0..8].try_into().unwrap());
    let s0 = u64::from_be_bytes(digest[8..16].try_into().unwrap());
    let s1 = u64::from_be_bytes(digest[16..24].try_into().unwrap());
    let s2 = u64::from_be_bytes(digest[24..32].try_into().unwrap());
    (radius, (s0, s1, s2))
}

/// `VRL1ZeroTrustEngine.make_proof`: HMAC-SHA256 over the canonical
/// (nonce, ts, method, path, sha256(body)) tuple, hex-encoded.
#[pyfunction]
fn make_proof(proof_key: &[u8], nonce: &str, ts: i64, method: &str, path: &str, body: &[u8]) -> String {
    let body_hash = Sha256::digest(body).to_vec();
    let msg = canon(&[
        nonce.as_bytes(),
        &ts.to_be_bytes(),
        method.to_uppercase().as_bytes(),
        path.as_bytes(),
        &body_hash,
    ]);
    let mut mac = HmacSha256::new_from_slice(proof_key).expect("HMAC accepts any key length");
    mac.update(&msg);
    hex_encode(&mac.finalize().into_bytes())
}

/// `RadialVectorEngine.spatialize_key` for the locked/default d=4, ring_width=100.
/// SHA-256 -> radius + 3 angles in [0, 2*pi). Other dimensions fall back to Python.
#[pyfunction]
fn spatialize_key(api_key: &str) -> (f64, Vec<f64>) {
    const U64_MAX: f64 = u64::MAX as f64;
    let digest = Sha256::digest(api_key.as_bytes());
    let frac = u64::from_be_bytes(digest[0..8].try_into().unwrap()) as f64 / U64_MAX;
    let radius = 100.0 * (1.0 + frac);
    let mut angles = Vec::with_capacity(3);
    for i in 0..3 {
        let seg = &digest[8 + i * 8..8 + (i + 1) * 8];
        let v = u64::from_be_bytes(seg.try_into().unwrap()) as f64;
        angles.push((v / U64_MAX) * std::f64::consts::TAU);
    }
    (radius, angles)
}

#[pymodule]
fn _vrl1_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(derive_coordinate, m)?)?;
    m.add_function(wrap_pyfunction!(make_proof, m)?)?;
    m.add_function(wrap_pyfunction!(spatialize_key, m)?)?;
    Ok(())
}
