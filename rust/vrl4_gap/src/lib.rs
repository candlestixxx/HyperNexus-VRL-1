//! HyperNexus VRL-4 GAP — Rust core (PyO3).
//!
//! Pure-math primitives for the Geometric Authentication Protocol:
//! fuzzy extractor, Kalman latency filter, WGS 84 geodesic bounds, and the
//! RTT challenge sign/verify. Vault-agnostic by design — these know nothing
//! about rings/tenants; the VRL-1 engine supplies that half at the seam.

mod fuzzy;
mod geodesic;
mod kalman;
mod rtt;

use pyo3::prelude::*;

#[pyfunction]
fn fuzzy_generate(py: Python<'_>, reading: &[u8], key_len: usize, repeat: usize) -> (Vec<u8>, Vec<u8>) {
    py.detach(|| fuzzy::generate(reading, key_len, repeat))
}

#[pyfunction]
fn fuzzy_reproduce(reading: &[u8], helper: &[u8], key_len: usize, repeat: usize) -> Vec<u8> {
    fuzzy::reproduce(reading, helper, key_len, repeat)
}

#[pyfunction]
fn sign_challenge(key: &[u8], nonce: &[u8], client_nonce: &[u8], payload: &[u8]) -> Vec<u8> {
    rtt::sign_challenge(key, nonce, client_nonce, payload)
}

#[pyfunction]
fn verify_challenge(key: &[u8], nonce: &[u8], client_nonce: &[u8], payload: &[u8], sig: &[u8]) -> bool {
    rtt::verify_challenge(key, nonce, client_nonce, payload, sig)
}

#[pyfunction]
fn haversine_km(lat1: f64, lon1: f64, lat2: f64, lon2: f64) -> f64 {
    geodesic::haversine_km(lat1, lon1, lat2, lon2)
}

#[pyfunction]
fn max_radius_km(rtt_ms: f64, speed_km_per_ms: f64) -> f64 {
    geodesic::max_radius_km(rtt_ms, speed_km_per_ms)
}

#[pyclass]
struct KalmanTracker {
    inner: kalman::KalmanLatencyTracker,
}

#[pymethods]
impl KalmanTracker {
    #[new]
    fn new(q: f64, r: f64) -> Self {
        KalmanTracker { inner: kalman::KalmanLatencyTracker::new(q, r) }
    }
    fn update(&mut self, z: f64) -> f64 {
        self.inner.update(z)
    }
    fn estimate(&self) -> f64 {
        self.inner.estimate()
    }
    fn is_anomalous(&self, z: f64, n_sigma: f64) -> bool {
        self.inner.is_anomalous(z, n_sigma)
    }
}

#[pymodule]
fn _vrl4_gap(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(fuzzy_generate, m)?)?;
    m.add_function(wrap_pyfunction!(fuzzy_reproduce, m)?)?;
    m.add_function(wrap_pyfunction!(sign_challenge, m)?)?;
    m.add_function(wrap_pyfunction!(verify_challenge, m)?)?;
    m.add_function(wrap_pyfunction!(haversine_km, m)?)?;
    m.add_function(wrap_pyfunction!(max_radius_km, m)?)?;
    m.add_class::<KalmanTracker>()?;
    Ok(())
}
