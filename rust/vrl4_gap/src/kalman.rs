//! 1-D Kalman filter for network latency: learns a device's "geometric latency
//! sphere" and flags physically-impossible spikes without trusting absolute time.

pub struct KalmanLatencyTracker {
    x: f64,         // estimated true latency (ms)
    p: f64,         // estimate covariance
    q: f64,         // process noise (how fast the true latency drifts)
    r: f64,         // measurement noise (per-sample jitter)
    initialized: bool,
}

impl KalmanLatencyTracker {
    pub fn new(q: f64, r: f64) -> Self {
        KalmanLatencyTracker { x: 0.0, p: 1.0, q, r, initialized: false }
    }

    pub fn update(&mut self, z: f64) -> f64 {
        if !self.initialized {
            self.x = z;
            self.p = self.r;
            self.initialized = true;
            return self.x;
        }
        let p_pred = self.p + self.q;
        let k = p_pred / (p_pred + self.r);
        self.x += k * (z - self.x);
        self.p = (1.0 - k) * p_pred;
        self.x
    }

    pub fn estimate(&self) -> f64 {
        self.x
    }

    /// True if `z` is more than `n_sigma` standard deviations from the
    /// predicted state — a physically impossible spike (proxy/VPN hop).
    pub fn is_anomalous(&self, z: f64, n_sigma: f64) -> bool {
        let p_pred = self.p + self.q;
        (z - self.x).abs() > n_sigma * (p_pred + self.r).sqrt()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn tracks_mean_and_flags_spikes() {
        let mut k = KalmanLatencyTracker::new(0.1, 4.0);
        for i in 0..50 {
            // deterministic jitter around 20 ms
            let z = 20.0 + ((i * 7) % 5) as f64 - 2.0;
            k.update(z);
        }
        assert!((k.estimate() - 20.0).abs() < 1.5);
        assert!(k.is_anomalous(200.0, 5.0));   // huge spike
        assert!(!k.is_anomalous(21.0, 5.0));   // normal jitter
    }
}
