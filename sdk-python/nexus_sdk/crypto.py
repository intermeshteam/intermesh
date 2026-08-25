import base64
import json
import os

from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def generate_keypair():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def get_public_key_pem(private_key) -> str:
    return private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode("utf-8")


def load_public_key(pem_string: str):
    return serialization.load_pem_public_key(pem_string.encode("utf-8"))


def encrypt_for(recipient_public_key_pem: str, plaintext: str) -> str:
    plaintext_bytes = plaintext.encode("utf-8")
    aes_key = AESGCM.generate_key(bit_length=256)
    nonce = os.urandom(12)
    aesgcm = AESGCM(aes_key)
    ciphertext = aesgcm.encrypt(nonce, plaintext_bytes, None)
    pub_key = load_public_key(recipient_public_key_pem)
    encrypted_aes_key = pub_key.encrypt(
        aes_key,
        padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None)
    )
    envelope = {
        "ek": base64.b64encode(encrypted_aes_key).decode(),
        "n": base64.b64encode(nonce).decode(),
        "ct": base64.b64encode(ciphertext).decode()
    }
    return base64.b64encode(json.dumps(envelope).encode()).decode()


def decrypt_with(private_key, encrypted_b64: str) -> str:
    envelope = json.loads(base64.b64decode(encrypted_b64))
    aes_key = private_key.decrypt(
        base64.b64decode(envelope["ek"]),
        padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None)
    )
    aesgcm = AESGCM(aes_key)
    return aesgcm.decrypt(base64.b64decode(envelope["n"]), base64.b64decode(envelope["ct"]), None).decode("utf-8")
