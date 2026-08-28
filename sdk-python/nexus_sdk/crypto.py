import base64
import json
import os

from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


def generate_keypair():
    """Génère une paire de clés RSA-2048."""
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def get_public_key_pem(private_key) -> str:
    """Exporte la clé publique au format PEM."""
    return private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode("utf-8")


def get_private_key_pem(private_key) -> str:
    """Exporte la clé privée au format PEM."""
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).decode("utf-8")


def load_public_key(pem_string: str):
    """Charge une clé publique depuis un PEM."""
    return serialization.load_pem_public_key(pem_string.encode("utf-8"))


def load_private_key(pem_string: str):
    """Charge une clé privée depuis un PEM."""
    return serialization.load_pem_private_key(pem_string.encode("utf-8"), password=None)


def encrypt_for(recipient_public_key_pem: str, plaintext: str) -> str:
    """Chiffrement hybride RSA-OAEP + AES-256-GCM."""
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
    """Déchiffrement hybride RSA-OAEP + AES-256-GCM."""
    envelope = json.loads(base64.b64decode(encrypted_b64))
    aes_key = private_key.decrypt(
        base64.b64decode(envelope["ek"]),
        padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None)
    )
    aesgcm = AESGCM(aes_key)
    return aesgcm.decrypt(base64.b64decode(envelope["n"]), base64.b64decode(envelope["ct"]), None).decode("utf-8")


# --- CHIFFREMENT AU REPOS PAR PASSPHRASE (PBKDF2 + AES-256-GCM) ---

PBKDF2_ITERATIONS = 100_000


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    """Dérive une clé AES-256 depuis une passphrase, via PBKDF2-HMAC-SHA256."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    return kdf.derive(passphrase.encode("utf-8"))


def encrypt_blob(plaintext: str, passphrase: str) -> dict:
    """
    Chiffre un texte quelconque avec une passphrase.

    Retourne un dict JSON-sérialisable (`salt`/`nonce`/`ciphertext` en
    base64) : le sel est stocké en clair, il n'est pas secret — il empêche
    seulement de pré-calculer une table pour toutes les passphrases.
    """
    salt = os.urandom(16)
    nonce = os.urandom(12)
    ciphertext = AESGCM(_derive_key(passphrase, salt)).encrypt(
        nonce, plaintext.encode("utf-8"), None
    )
    return {
        "salt": base64.b64encode(salt).decode("utf-8"),
        "nonce": base64.b64encode(nonce).decode("utf-8"),
        "ciphertext": base64.b64encode(ciphertext).decode("utf-8"),
    }


def decrypt_blob(blob: dict, passphrase: str) -> str:
    """
    Déchiffre un blob produit par `encrypt_blob`.

    Raises:
        cryptography.exceptions.InvalidTag: passphrase incorrecte, ou
            contenu altéré — AES-GCM ne distingue pas les deux cas, et
            c'est voulu : les deux signifient « ne fais pas confiance ».
    """
    key = _derive_key(passphrase, base64.b64decode(blob["salt"]))
    return AESGCM(key).decrypt(
        base64.b64decode(blob["nonce"]),
        base64.b64decode(blob["ciphertext"]),
        None,
    ).decode("utf-8")


# --- COFFRE-FORT DE CLÉS LOCAL CHIFFRÉ (LOCAL KEY VAULT) ---

def save_encrypted_vault(file_path: str, private_key_pem: str, passphrase: str):
    """
    Chiffre et sauvegarde la clé privée sur le disque avec PBKDF2 (100 000 itérations) + AES-256-GCM.
    """
    vault_data = encrypt_blob(private_key_pem, passphrase)
    vault_data["version"] = "nexus_vault_v1"

    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(vault_data, f, indent=2)

    # Restreindre les permissions du fichier sous Linux (600 = lecture/écriture propriétaire seul)
    os.chmod(file_path, 0o600)


def load_encrypted_vault(file_path: str, passphrase: str) -> str:
    """
    Déchiffre et charge la clé privée depuis le coffre-fort local.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        vault_data = json.load(f)
    return decrypt_blob(vault_data, passphrase)
