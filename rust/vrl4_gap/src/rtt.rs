//! RTT challenge-response: the gateway signs a nonce, the client signs it back
//! with its device key, and the gateway verifies with its own clock only.

use hmac::{Hmac, Mac};
use sha2::Sha256;

type HmacSha256 = Hmac<Sha256>;

fn mac(key: &[u8], nonce: &[u8], client_nonce: &[u8], payload: &[u8]) -> HmacSha256 {
    let mut m = HmacSha256::new_from_slice(key).expect("HMAC accepts any key length");
    m.update(b"VRL4-GAP-v1");
    m.update(nonce);
    m.update(client_nonce);
    m.update(payload);
    m
}

pub fn sign_challenge(key: &[u8], nonce: &[u8], client_nonce: &[u8], payload: &[u8]) -> Vec<u8> {
    mac(key, nonce, client_nonce, payload).finalize().into_bytes().to_vec()
}

pub fn verify_challenge(
    key: &[u8], nonce: &[u8], client_nonce: &[u8], payload: &[u8], sig: &[u8],
) -> bool {
    mac(key, nonce, client_nonce, payload).verify_slice(sig).is_ok()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn challenge_sign_verify() {
        let key = b"device-secret-key-32-bytes-minimum!";
        let nonce = b"gateway-nonce";
        let cn = b"client-nonce";
        let payload = b"proof";
        let sig = sign_challenge(key, nonce, cn, payload);
        assert!(verify_challenge(key, nonce, cn, payload, &sig));
        assert!(!verify_challenge(key, nonce, cn, b"other", &sig));
        assert!(!verify_challenge(b"wrong-key", nonce, cn, payload, &sig));
    }
}
