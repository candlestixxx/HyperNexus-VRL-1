"""Generate a self-signed TLS certificate for local/dev testing.

NOT for production — use Let's Encrypt (certbot) or your CA there.

Usage:
  python tools/gen_cert.py [cert_path] [key_path] [hostname]
"""
import datetime
import os
import sys

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


def generate(cert_path: str, key_path: str, hostname: str = "localhost") -> None:
    os.makedirs(os.path.dirname(os.path.abspath(cert_path)), exist_ok=True)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, hostname)])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=365))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(hostname)]),
                       critical=False)
        .sign(key, hashes.SHA256())
    )
    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    with open(key_path, "wb") as f:
        f.write(key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption()))
    print(f"wrote {cert_path} and {key_path}")


if __name__ == "__main__":
    cert = sys.argv[1] if len(sys.argv) > 1 else "certs/server.crt"
    key = sys.argv[2] if len(sys.argv) > 2 else "certs/server.key"
    host = sys.argv[3] if len(sys.argv) > 3 else "localhost"
    generate(cert, key, host)
