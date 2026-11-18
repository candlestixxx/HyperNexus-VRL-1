//! Fuzzy extractor (code-offset construction) for noisy hardware readings.
//!
//! `generate` produces a stable key plus helper data from an enrollment
//! reading; `reproduce` reconstructs the same key from a later, noisy reading.
//! The inner code is a repetition code (each key bit repeated `repeat` times,
//! majority vote). Honest scope: this demonstrates the extractor mechanism;
//! swap the inner codec for BCH/Reed-Solomon for production-grade error
//! tolerance.

use rand::RngCore;

fn pack_bits(bits: &[u8]) -> Vec<u8> {
    let mut out = Vec::with_capacity((bits.len() + 7) / 8);
    for chunk in bits.chunks(8) {
        let mut b = 0u8;
        for (j, &bit) in chunk.iter().enumerate() {
            b |= bit << (7 - j);
        }
        out.push(b);
    }
    out
}

fn unpack_bits(bytes: &[u8]) -> Vec<u8> {
    let mut bits = Vec::with_capacity(bytes.len() * 8);
    for &b in bytes {
        for i in (0..8).rev() {
            bits.push((b >> i) & 1);
        }
    }
    bits
}

fn encode(data: &[u8], repeat: usize) -> Vec<u8> {
    let mut bits = Vec::with_capacity(data.len() * 8 * repeat);
    for &byte in data {
        for i in (0..8).rev() {
            let bit = (byte >> i) & 1;
            for _ in 0..repeat {
                bits.push(bit);
            }
        }
    }
    pack_bits(&bits)
}

pub fn generate(reading: &[u8], key_len: usize, repeat: usize) -> (Vec<u8>, Vec<u8>) {
    let mut key = vec![0u8; key_len];
    rand::thread_rng().fill_bytes(&mut key);
    let codeword = encode(&key, repeat);
    // Requires reading.len() >= codeword.len(); callers validate.
    let helper: Vec<u8> = codeword
        .iter()
        .zip(reading.iter())
        .take(codeword.len())
        .map(|(c, r)| c ^ r)
        .collect();
    (key, helper)
}

pub fn reproduce(reading: &[u8], helper: &[u8], key_len: usize, repeat: usize) -> Vec<u8> {
    let codeword: Vec<u8> = helper
        .iter()
        .zip(reading.iter())
        .take(helper.len())
        .map(|(h, r)| h ^ r)
        .collect();
    let bits = unpack_bits(&codeword);
    let mut key_bits = Vec::with_capacity(key_len * 8);
    for block_start in (0..key_len * 8 * repeat).step_by(repeat) {
        let ones: usize = bits[block_start..block_start + repeat]
            .iter()
            .map(|&b| b as usize)
            .sum();
        key_bits.push(if ones * 2 >= repeat { 1 } else { 0 });
    }
    pack_bits(&key_bits)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn flip_bits(data: &[u8], positions: &[usize]) -> Vec<u8> {
        let mut d = data.to_vec();
        for &p in positions {
            d[p / 8] ^= 1 << (7 - (p % 8));
        }
        d
    }

    #[test]
    fn recovers_from_tolerable_noise() {
        let (repeat, key_len) = (3, 8);
        let reading = vec![0xA5u8; key_len * repeat];
        let (key, helper) = generate(&reading, key_len, repeat);
        // One bit error per 3-bit block (tolerable).
        let positions: Vec<usize> = (0..key_len * 8).map(|b| b * repeat).collect();
        let noisy = flip_bits(&reading, &positions);
        assert_eq!(reproduce(&noisy, &helper, key_len, repeat), key);
    }

    #[test]
    fn diverges_on_excessive_noise() {
        let (repeat, key_len) = (3, 8);
        let reading = vec![0x5Au8; key_len * repeat];
        let (key, helper) = generate(&reading, key_len, repeat);
        // Two of three bits corrupted per block -> majority flips.
        let mut positions = Vec::new();
        for b in 0..key_len * 8 {
            positions.push(b * repeat);
            positions.push(b * repeat + 1);
        }
        let noisy = flip_bits(&reading, &positions);
        assert_ne!(reproduce(&noisy, &helper, key_len, repeat), key);
    }
}
