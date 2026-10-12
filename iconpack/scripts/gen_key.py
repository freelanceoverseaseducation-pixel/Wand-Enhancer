#!/usr/bin/env python3
"""Generate a long-lived self-signed RSA keypair for signing the pack."""
import datetime
import os
import sys

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEYDIR = os.path.join(ROOT, "keystore")


def main():
    os.makedirs(KEYDIR, exist_ok=True)
    key_path = os.path.join(KEYDIR, "aura.key.pem")
    if os.path.exists(key_path) and "--force" not in sys.argv:
        print("key already exists:", key_path)
        return
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "Aura Icons"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Aura"),
    ])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=365 * 30))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    with open(key_path, "wb") as f:
        f.write(key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ))
    with open(os.path.join(KEYDIR, "aura.cert.pem"), "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    print("generated", key_path)


if __name__ == "__main__":
    main()
