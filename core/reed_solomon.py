"""Reed-Solomon error-correcting code over GF(256).

A self-contained RS codec (encoder + Berlekamp-Massey/Chien/Forney decoder) for
the VRL-4 fuzzy extractor: it corrects up to `nsym/2` byte errors at unknown
positions, giving production-grade error tolerance versus the repetition code.

Field: GF(256), primitive polynomial 0x11D, generator 2 (the standard RS field).
The encoder uses highest-degree-first polynomial lists (as in the reference
implementations); the decoder uses ascending-degree lists (index = power of x)
for clarity and correctness of the BM / Chien / Forney steps.
"""
from __future__ import annotations


class ReedSolomonError(Exception):
    """Uncorrectable codeword (too many errors)."""


# --- GF(256) tables ----------------------------------------------------------
_EXP = [0] * 512
_LOG = [0] * 256
_x = 1
for _i in range(255):
    _EXP[_i] = _x
    _LOG[_x] = _i
    _x <<= 1
    if _x & 0x100:
        _x ^= 0x11D
for _i in range(255, 512):
    _EXP[_i] = _EXP[_i - 255]


def gf_mul(a: int, b: int) -> int:
    return 0 if a == 0 or b == 0 else _EXP[_LOG[a] + _LOG[b]]


def gf_pow(a: int, power: int) -> int:
    return _EXP[(_LOG[a] * (power % 255)) % 255]


def gf_inverse(a: int) -> int:
    return _EXP[255 - _LOG[a]]


def gf_div(a: int, b: int) -> int:
    if b == 0:
        raise ZeroDivisionError()
    return 0 if a == 0 else _EXP[(_LOG[a] + 255 - _LOG[b]) % 255]


# --- encoder (highest-degree-first polynomials) ------------------------------
def _poly_mul(p: list[int], q: list[int]) -> list[int]:
    r = [0] * (len(p) + len(q) - 1)
    for j in range(len(q)):
        for i in range(len(p)):
            r[i + j] ^= gf_mul(p[i], q[j])
    return r


def rs_generator_poly(nsym: int) -> list[int]:
    g = [1]
    for i in range(nsym):
        g = _poly_mul(g, [1, gf_pow(2, i)])
    return g


def rs_encode_msg(msg_in: bytes | bytearray | list[int], nsym: int) -> bytearray:
    gen = rs_generator_poly(nsym)
    msg_out = bytearray(len(msg_in) + nsym)
    msg_out[: len(msg_in)] = msg_in
    for i in range(len(msg_in)):
        coef = msg_out[i]
        if coef != 0:
            for j in range(1, len(gen)):
                msg_out[i + j] ^= gf_mul(gen[j], coef)
    msg_out[: len(msg_in)] = msg_in
    return msg_out


# --- decoder (ascending-degree polynomials: index = power of x) --------------
def _poly_add_asc(a: list[int], b: list[int]) -> list[int]:
    n = max(len(a), len(b))
    out = [0] * n
    for i in range(len(a)):
        out[i] ^= a[i]
    for i in range(len(b)):
        out[i] ^= b[i]
    return out


def _poly_mul_asc(a: list[int], b: list[int]) -> list[int]:
    out = [0] * (len(a) + len(b) - 1)
    for i in range(len(a)):
        for j in range(len(b)):
            out[i + j] ^= gf_mul(a[i], b[j])
    return out


def _poly_eval_asc(coeffs: list[int], x: int) -> int:
    r = 0
    for c in reversed(coeffs):
        r = gf_mul(r, x) ^ c
    return r


def _poly_deriv_asc(a: list[int]) -> list[int]:
    # formal derivative: coeff of x^i is (i+1)*a[i+1], zero when (i+1) is even.
    return [a[i + 1] if i % 2 == 0 else 0 for i in range(len(a) - 1)]


def _syndromes(codeword, nsym: int) -> list[int]:
    # S_j = r(alpha^j), codeword[0] is the highest-degree coefficient.
    syn = []
    for j in range(nsym):
        a = gf_pow(2, j)
        s = 0
        for b in codeword:
            s = gf_mul(s, a) ^ b
        syn.append(s)
    return syn


def _berlekamp_massey(syn: list[int]) -> list[int]:
    # Returns the error-locator polynomial ascending (Lambda[0] = 1).
    c = [1]
    b = [1]
    l = 0
    m = 1
    b_coef = 1
    for n in range(len(syn)):
        d = syn[n]
        for i in range(1, l + 1):
            if n >= i:
                d ^= gf_mul(c[i], syn[n - i])
        if d == 0:
            m += 1
        else:
            t = c[:]
            scale = gf_mul(d, gf_inverse(b_coef))
            shifted = [0] * m + b
            c = _poly_add_asc(c, [gf_mul(scale, s) for s in shifted])
            if 2 * l <= n:
                l = n + 1 - l
                b = t
                b_coef = d
                m = 1
            else:
                m += 1
    return c


def rs_correct_msg(msg_in: bytes | bytearray | list[int], nsym: int) -> bytes:
    """Correct errors and return the message (codeword minus parity)."""
    if len(msg_in) > 255:
        raise ValueError("codeword too long for GF(256) RS")
    n = len(msg_in)
    syn = _syndromes(msg_in, nsym)
    if max(syn) == 0:
        return bytes(msg_in[: n - nsym])
    lam = _berlekamp_massey(syn)
    # Chien search: error at index k iff Lambda(alpha^{-(n-1-k)}) == 0.
    err_pos = []
    for k in range(n):
        x = gf_pow(2, n - 1 - k)
        if _poly_eval_asc(lam, gf_inverse(x)) == 0:
            err_pos.append(k)
    if not err_pos or 2 * len(err_pos) > nsym:
        raise ReedSolomonError("Too many errors to correct")
    # Forney: Omega = (S * Lambda) mod x^nsym.
    omega = _poly_mul_asc(syn, lam)[:nsym]
    lam_deriv = _poly_deriv_asc(lam)
    corrected = bytearray(msg_in)
    for k in err_pos:
        x = gf_pow(2, n - 1 - k)
        x_inv = gf_inverse(x)
        num = gf_mul(x, _poly_eval_asc(omega, x_inv))
        den = _poly_eval_asc(lam_deriv, x_inv)
        if den == 0:
            raise ReedSolomonError("Could not find error magnitude")
        corrected[k] ^= gf_div(num, den)
    # verify
    if max(_syndromes(corrected, nsym)) != 0:
        raise ReedSolomonError("Could not correct message")
    return bytes(corrected[: n - nsym])
