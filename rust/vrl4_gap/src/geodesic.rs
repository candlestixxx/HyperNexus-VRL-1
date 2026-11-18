//! WGS 84 geodesic math: bounds the physical distance a request can travel for
//! a given round-trip time, and compares it to a device's IP geolocation.

const EARTH_RADIUS_KM: f64 = 6371.0;

pub fn haversine_km(lat1: f64, lon1: f64, lat2: f64, lon2: f64) -> f64 {
    let (la1, lo1) = (lat1.to_radians(), lon1.to_radians());
    let (la2, lo2) = (lat2.to_radians(), lon2.to_radians());
    let dlat = la2 - la1;
    let dlon = lo2 - lo1;
    let a = (dlat / 2.0).sin().powi(2)
        + la1.cos() * la2.cos() * (dlon / 2.0).sin().powi(2);
    2.0 * EARTH_RADIUS_KM * a.sqrt().asin()
}

/// Maximum one-way physical distance for a round-trip time.
/// `speed_km_per_ms` ≈ 200 km/ms for light in fiber (~2/3 c).
pub fn max_radius_km(rtt_ms: f64, speed_km_per_ms: f64) -> f64 {
    rtt_ms * speed_km_per_ms / 2.0
}

pub fn is_within_radius(
    lat1: f64, lon1: f64, lat2: f64, lon2: f64,
    rtt_ms: f64, speed_km_per_ms: f64,
) -> bool {
    haversine_km(lat1, lon1, lat2, lon2) <= max_radius_km(rtt_ms, speed_km_per_ms)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn nyc_la_geodesic_bounds() {
        let nyc = (40.7128, -74.0060);
        let la = (34.0522, -118.2437);
        let d = haversine_km(nyc.0, nyc.1, la.0, la.1);
        assert!((d - 3936.0).abs() < 50.0); // ~3940 km
        let speed = 200.0; // km/ms in fiber
        // 40 ms RTT bounds ~4000 km -> NYC->LA is within
        assert!(is_within_radius(nyc.0, nyc.1, la.0, la.1, 40.0, speed));
        // 10 ms RTT bounds ~1000 km -> NYC->LA is NOT within
        assert!(!is_within_radius(nyc.0, nyc.1, la.0, la.1, 10.0, speed));
    }
}
